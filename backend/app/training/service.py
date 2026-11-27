"""Training with the user's own errors (phase 6c): exercises, sessions, Leitner boxes.

Exercises come from the precalculated rows of the statistics (phase 6b): the user's ?, ??
and ✗. Decided positions and positions without a clear solution are kept as excluded (with
the reason) so they are not judged again. Bullet games are left out at session time (a
setting). The daily session counts for the streak; a filtered one (from a weak point) does
not.
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Engine as DbEngine
from sqlmodel import Session, col, select

from app.analysis.classify import equal_moves
from app.analysis.runner import AnalysisNotReadyError, AnalysisService
from app.analysis.types import PositionEval
from app.analysis.winprob import position_win
from app.config import TRAINING, TrainingThresholds
from app.models.game import Game, GameSource, utcnow
from app.models.insight import GameInsight, MoveInsight
from app.models.training import TrainingItem, TrainingSession
from app.settings_store import get_setting, set_setting
from app.stats.insights import INSIGHTS_VERSION
from app.stats.queries import StatsFilters, load_stats
from app.training.logic import Box, Candidate, Filter, after_attempt, pick_session, streak

ERRORS = ("mistake", "blunder", "miss")
SIZE, WEAK_NEW, BULLET = "training_session_size", "training_weak_new", "training_include_bullet"
BOT = "training_include_bot"


@dataclass(frozen=True)
class TrainingSettings:
    session_size: int
    weak_new: int
    include_bullet: bool
    include_bot: bool = True  # games against the bot, only when no real ones are left


@dataclass(frozen=True)
class Recorded:
    session: TrainingSession
    item: TrainingItem
    counted: bool  # first answer of this exercise in the session (it moved the box)


def exclusion(
    win_before: float,
    win_previous: float,
    alternatives: int,
    t: TrainingThresholds = TRAINING,
) -> str | None:
    """Why a position is not an exercise: "decided" or "unclear" (several equally good moves
    besides the best one).

    "Decided": the user was already winning (or losing) before the opponent's last move and
    still is. The win% of the position alone is not enough: it includes the tactic on the
    board, so an opponent's blunder (a ✗ exercise) would always look "decided".
    `win_previous` is the user's win% before the opponent's last move.
    """
    above, below = t.decided_above, 100.0 - t.decided_above
    if (win_before > above and win_previous > above) or (
        win_before < below and win_previous < below
    ):
        return "decided"
    if alternatives >= t.unclear_alternatives:
        return "unclear"
    return None


class TrainingService:
    def __init__(
        self, db: DbEngine, analysis: AnalysisService, t: TrainingThresholds = TRAINING
    ) -> None:
        self._db = db
        self._analysis = analysis
        self._t = t

    # --- Settings ---------------------------------------------------------------

    def settings(self) -> TrainingSettings:
        return TrainingSettings(
            session_size=int(get_setting(self._db, SIZE, str(self._t.session_size))),
            weak_new=int(get_setting(self._db, WEAK_NEW, str(self._t.weak_new))),
            include_bullet=get_setting(self._db, BULLET, "1" if self._t.include_bullet else "0")
            == "1",
            include_bot=get_setting(self._db, BOT, "1" if self._t.include_bot else "0") == "1",
        )

    def set_settings(self, s: TrainingSettings) -> TrainingSettings:
        set_setting(self._db, SIZE, str(max(1, min(20, s.session_size))))
        set_setting(self._db, WEAK_NEW, str(max(0, s.weak_new)))
        set_setting(self._db, BULLET, "1" if s.include_bullet else "0")
        set_setting(self._db, BOT, "1" if s.include_bot else "0")
        return self.settings()

    # --- Exercises ----------------------------------------------------------------

    def sync_items(self) -> int:
        """Turn new errors of analysed games into exercises (or exclusions). Returns how many
        rows were created."""
        with Session(self._db) as session:
            known = {
                (g, p) for g, p in session.exec(select(TrainingItem.game_id, TrainingItem.ply))
            }
            rows = session.exec(
                select(MoveInsight)
                .join(GameInsight, col(GameInsight.game_id) == col(MoveInsight.game_id))
                .where(
                    col(MoveInsight.classification).in_(ERRORS),
                    GameInsight.version == INSIGHTS_VERSION,
                )
            ).all()
            new = [m for m in rows if (m.game_id, m.ply) not in known]
        by_game: dict[int, list[MoveInsight]] = defaultdict(list)
        for m in new:
            by_game[m.game_id].append(m)
        created = 0
        for game_id, moves in by_game.items():
            try:
                _, evals = self._analysis.evaluations(game_id)
            except AnalysisNotReadyError:
                continue
            with Session(self._db) as session:
                for m in moves:
                    session.add(
                        TrainingItem(
                            game_id=game_id,
                            ply=m.ply,
                            classification=m.classification,
                            error_kind=m.error_kind,
                            phase=m.phase,
                            low_time=m.low_time,
                            excluded=exclusion(
                                m.win_before,
                                _previous_win(evals, m.ply, m.win_before),
                                len(equal_moves(evals[m.ply])),
                            ),
                            created_at=utcnow(),
                        )
                    )
                    created += 1
                session.commit()
        return created

    def candidates(self) -> list[Candidate]:
        with Session(self._db) as session:
            rows = session.exec(
                select(TrainingItem, Game).join(Game, col(Game.id) == col(TrainingItem.game_id))
            ).all()
        return [
            Candidate(
                id=item.id or 0,
                box=item.box,
                due_on=item.due_on,
                learned=item.learned,
                excluded=item.excluded,
                error_kind=item.error_kind,
                phase=item.phase,
                low_time=item.low_time,
                time_class=game.time_class,
                played_at=game.played_at or game.created_at,
                real=game.source == GameSource.IMPORTED,
            )
            for item, game in rows
        ]

    def weak_kinds(self) -> list[str]:
        """Error kinds of "Tus 3 puntos débiles" (default statistics: real games)."""
        with Session(self._db) as session:
            stats = load_stats(session, StatsFilters()).stats
        return [w.train["error_kind"] for w in stats.weak_points if "error_kind" in w.train]

    # --- Sessions -------------------------------------------------------------------

    def session(self, flt: Filter, today: date) -> TrainingSession:
        """Today's daily session (one per day), or a new session with this filter."""
        wanted = json.dumps(_filter_dict(flt), sort_keys=True)
        with Session(self._db) as session:
            existing = session.exec(
                select(TrainingSession)
                .where(
                    TrainingSession.day == today,
                    TrainingSession.daily == flt.empty,
                    TrainingSession.filter_json == wanted,
                )
                .order_by(col(TrainingSession.id).desc())
            ).first()
            # The daily session is one per day; a filtered one (from a weak point) is a fresh
            # set every time (answers are never lost: each one moves its box at once).
            if existing is not None and flt.empty:
                return existing
        self.sync_items()
        s = self.settings()
        ids = pick_session(
            self.candidates(),
            today,
            s.session_size,
            self.weak_kinds() if flt.empty else [],
            s.weak_new,
            flt,
            s.include_bullet,
            s.include_bot,
        )
        created = TrainingSession(
            day=today,
            daily=flt.empty,
            filter_json=wanted,
            items_json=json.dumps(ids),
            results_json="{}",
            completed=not ids,
        )
        with Session(self._db) as session:
            session.add(created)
            session.commit()
            session.refresh(created)
        return created

    def get_session(self, session_id: int) -> TrainingSession | None:
        with Session(self._db) as session:
            return session.get(TrainingSession, session_id)

    def item(self, item_id: int) -> TrainingItem | None:
        with Session(self._db) as session:
            return session.get(TrainingItem, item_id)

    def record(self, session_id: int, position: int, correct: bool, today: date) -> Recorded:
        """The first answer at a position counts (retries do not). The first time an exercise
        is answered in a session it moves its Leitner box; a wrong one comes back once at the
        end of the session."""
        with Session(self._db) as session:
            ts = session.get(TrainingSession, session_id)
            if ts is None:
                raise KeyError(session_id)
            ids: list[int] = json.loads(ts.items_json)
            results: dict[str, str] = json.loads(ts.results_json)
            if not 0 <= position < len(ids):
                raise IndexError(position)
            item = session.get(TrainingItem, ids[position])
            assert item is not None
            counted = False
            if str(position) not in results:
                results[str(position)] = "correct" if correct else "wrong"
                first_time = ids.index(ids[position]) == position
                if first_time:
                    counted = True
                    box: Box = after_attempt(item.box, correct, today, self._t)
                    item.box, item.due_on, item.learned = box.box, box.due_on, box.learned
                    item.attempts += 1
                    item.correct += int(correct)
                    item.last_seen_at = utcnow()
                    if not correct and ids.count(ids[position]) == 1:
                        ids.append(ids[position])
                ts.items_json = json.dumps(ids)
                ts.results_json = json.dumps(results)
                ts.completed = len(results) == len(ids)
                session.add_all([ts, item])
                session.commit()
                session.refresh(ts)
                session.refresh(item)
            return Recorded(ts, item, counted)

    def streak(self, today: date) -> int:
        with Session(self._db) as session:
            done = session.exec(
                select(TrainingSession).where(
                    col(TrainingSession.daily).is_(True), col(TrainingSession.completed).is_(True)
                )
            ).all()
        return streak((s.day for s in done), today)

    def counts(self, today: date) -> dict[str, int]:
        s = self.settings()
        out = {"due": 0, "new": 0, "learned": 0, "decided": 0, "unclear": 0, "bullet": 0, "bot": 0}
        for c in self.candidates():
            if c.excluded is not None:
                out[c.excluded] = out.get(c.excluded, 0) + 1
            elif c.learned:
                out["learned"] += 1
            elif not s.include_bullet and c.time_class == "bullet":
                out["bullet"] += 1
            elif not s.include_bot and not c.real:
                out["bot"] += 1
            elif c.box == 0:
                out["new"] += 1
            elif c.due_on is not None and c.due_on <= today:
                out["due"] += 1
        return out


def _previous_win(evals: list[PositionEval], ply: int, fallback: float) -> float:
    """The user's win% before the opponent's last move (the position at `ply - 1`, where the
    opponent was to move)."""
    if ply == 0:
        return fallback
    return 100.0 - position_win(evals[ply - 1])


def _filter_dict(flt: Filter) -> dict[str, str | bool]:
    out: dict[str, str | bool] = {}
    if flt.error_kind is not None:
        out["error_kind"] = flt.error_kind
    if flt.phase is not None:
        out["phase"] = flt.phase
    if flt.low_time is not None:
        out["low_time"] = flt.low_time
    return out
