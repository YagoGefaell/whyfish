"""Precalculated data of analysed games (phase 6b): computing and storing it.

`compute_insights` is pure (game + moves + engine evaluations -> rows). `InsightService`
stores them when an analysis finishes and, in the background, for analysed games without
rows of the current `INSIGHTS_VERSION` (bump it when classification or facts rules change).
"""

import asyncio
import contextlib
import logging
import multiprocessing
import re
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import chess
from sqlalchemy import Engine as DbEngine
from sqlmodel import Session, col, delete, select

from app.analysis.book import OpeningBook, default_book
from app.analysis.detectors.structure import phase
from app.analysis.review import build_review
from app.analysis.runner import AnalysisNotReadyError, AnalysisService
from app.analysis.types import Classification, PositionEval
from app.config import STATS, StatsThresholds
from app.explain.idea import choose_idea
from app.explain.service import facts_for_ply
from app.models.analysis import AnalysisJob, AnalysisStatus
from app.models.game import Game, Move, utcnow
from app.models.insight import GameInsight, MoveInsight
from app.play.rules import PlayerColor

logger = logging.getLogger(__name__)

INSIGHTS_VERSION = 1

C = Classification
ERROR_CLASSES = (C.INACCURACY, C.MISTAKE, C.BLUNDER, C.MISS)


def clock_initial(time_control: str | None) -> float | None:
    """Base time in seconds of a PGN TimeControl ("600", "180+2"); None for correspondence
    ("1/259200"), unknown ("-", "?") or missing."""
    if not time_control:
        return None
    match = re.fullmatch(r"(\d+)(?:\+\d+)?", time_control.strip())
    return float(match.group(1)) if match else None


def is_low_time(
    clock_s: float | None, initial_s: float | None, t: StatsThresholds = STATS
) -> bool | None:
    """Little time left: below the smaller of `low_time_s` and `low_time_fraction` of the base
    time (30 s in a 10-minute game, 18 s in a 3-minute one). None without a clock."""
    if clock_s is None or initial_s is None:
        return None
    return clock_s < min(t.low_time_s, t.low_time_fraction * initial_s)


def user_result(result: str | None, color: PlayerColor) -> str | None:
    if result == "1/2-1/2":
        return "draw"
    if result in ("1-0", "0-1"):
        white_won = result == "1-0"
        return "win" if white_won == (color == PlayerColor.WHITE) else "loss"
    return None


def compute_insights(
    game: Game,
    moves: Sequence[Move],
    evals: Sequence[PositionEval],
    book: OpeningBook | None,
    t: StatsThresholds = STATS,
) -> tuple[GameInsight, list[MoveInsight]]:
    assert game.id is not None
    user = game.player_color.chess_color
    ucis = [m.uci for m in moves]
    review = build_review(game.initial_fen, ucis, evals, user, book)
    summary = review.white if user == chess.WHITE else review.black
    initial = clock_initial(game.time_control)
    rows: list[MoveInsight] = []
    board = chess.Board(game.initial_fen)
    for reviewed, move in zip(review.moves, moves, strict=True):
        if reviewed.color == user:
            kind = None
            if reviewed.classification in ERROR_CLASSES:
                facts = facts_for_ply(game.initial_fen, ucis, evals, review, reviewed.ply, book)
                idea = choose_idea(facts)
                kind = idea.kind.value if idea is not None else "positional"
            rows.append(
                MoveInsight(
                    game_id=game.id,
                    ply=reviewed.ply,
                    san=reviewed.san,
                    classification=reviewed.classification.value,
                    delta=reviewed.delta,
                    accuracy=reviewed.accuracy,
                    win_before=reviewed.win_before,
                    phase=phase(board),
                    error_kind=kind,
                    clock_s=move.clock_s,
                    low_time=is_low_time(move.clock_s, initial, t),
                )
            )
        board.push_uci(move.uci)
    opening = review.opening
    family = opening.name.split(":")[0].strip() if opening else None
    insight = GameInsight(
        game_id=game.id,
        version=INSIGHTS_VERSION,
        computed_at=utcnow(),
        accuracy=summary.accuracy,
        result=user_result(game.result, game.player_color),
        opening_eco=opening.eco if opening else None,
        opening_name=opening.name if opening else None,
        opening_family=family,
        user_moves=len(rows),
        clock_initial_s=initial,
    )
    return insight, rows


def _compute_plain(
    game: dict[str, Any], moves: list[dict[str, Any]], evals: list[PositionEval]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """`compute_insights` on plain data (it runs in the worker process): the book is built
    there once (~2 s) and kept for the next games."""
    insight, rows = compute_insights(
        Game.model_validate(game),
        [Move.model_validate(m) for m in moves],
        evals,
        default_book(),
    )
    return insight.model_dump(), [r.model_dump() for r in rows]


class InsightService:
    """Keeps the precalculated rows up to date, one game at a time, in a worker thread (the
    facts of a game take ~1 s on a PC, a few on a Raspberry Pi)."""

    def __init__(self, db: DbEngine, analysis: AnalysisService, use_process: bool = True) -> None:
        self._db = db
        self._analysis = analysis
        self._use_process = use_process
        self._pool: ProcessPoolExecutor | None = None
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._current: int | None = None
        self._failed: set[int] = set()  # skipped until the next analysis finishes

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None

    def wake(self, game_id: int | None = None) -> None:
        """An analysis finished (or rules changed): recompute what is stale."""
        del game_id
        self._failed.clear()
        self._wake.set()

    def stale(self) -> list[int]:
        """Analysed games without rows of the current version (or older than their analysis),
        most recent first."""
        with Session(self._db) as session:
            rows = session.exec(
                select(
                    Game.id, AnalysisJob.finished_at, GameInsight.version, GameInsight.computed_at
                )
                .join(AnalysisJob, col(AnalysisJob.game_id) == col(Game.id))
                .join(GameInsight, col(GameInsight.game_id) == col(Game.id), isouter=True)
                .where(AnalysisJob.status == AnalysisStatus.DONE)
                .order_by(col(Game.played_at).desc(), col(Game.id).desc())
            ).all()
        out: list[int] = []
        for game_id, finished, version, computed in rows:
            if game_id is None:
                continue
            outdated = version != INSIGHTS_VERSION
            reanalysed = finished is not None and computed is not None and finished > computed
            if outdated or reanalysed:
                out.append(game_id)
        return out

    def pending(self) -> int:
        stale = self.stale()
        return len(stale) + (1 if self._current is not None and self._current not in stale else 0)

    def _load(self, game_id: int) -> tuple[Game, list[Move], list[PositionEval]] | None:
        try:
            _, evals = self._analysis.evaluations(game_id)
        except AnalysisNotReadyError:
            return None
        with Session(self._db) as session:
            game = session.get(Game, game_id)
            if game is None:
                return None
            moves = list(
                session.exec(
                    select(Move).where(Move.game_id == game_id).order_by(col(Move.ply))
                ).all()
            )
            session.expunge_all()
        return game, moves, evals

    def _save(self, game_id: int, insight: GameInsight, rows: list[MoveInsight]) -> None:
        with Session(self._db) as session:
            session.exec(delete(MoveInsight).where(col(MoveInsight.game_id) == game_id))
            existing = session.get(GameInsight, game_id)
            if existing is not None:
                session.delete(existing)
                session.flush()
            session.add(insight)
            session.add_all(rows)
            session.commit()

    def refresh(self, game_id: int) -> bool:
        """Recompute one game (blocking). False if it is not analysed (any more)."""
        loaded = self._load(game_id)
        if loaded is None:
            return False
        self._save(game_id, *compute_insights(*loaded, default_book()))
        return True

    async def refresh_async(self, game_id: int) -> bool:
        """Like `refresh`, with the computation (pure, CPU-bound) in a separate worker process
        (a thread would compete with the server for the GIL and slow down analyses and
        responses) and the database only in the event loop's thread."""
        loaded = self._load(game_id)
        if loaded is None:
            return False
        game, moves, evals = loaded
        args = (game.model_dump(), [m.model_dump() for m in moves], evals)
        if self._use_process:
            if self._pool is None:
                context = multiprocessing.get_context("spawn")
                self._pool = ProcessPoolExecutor(max_workers=1, mp_context=context)
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(self._pool, _compute_plain, *args)
        else:
            result = await asyncio.to_thread(_compute_plain, *args)
        insight, rows = result
        self._save(
            game_id,
            GameInsight.model_validate(insight),
            [MoveInsight.model_validate(r) for r in rows],
        )
        return True

    async def _loop(self) -> None:
        while True:
            stale = [g for g in self.stale() if g not in self._failed]
            if not stale:
                self._wake.clear()
                await self._wake.wait()
                continue
            for game_id in stale:
                self._current = game_id
                try:
                    await self.refresh_async(game_id)
                except Exception:
                    logger.exception("Insights of game %s failed", game_id)
                    self._failed.add(game_id)
                finally:
                    self._current = None
