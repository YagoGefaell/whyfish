"""Loading the precalculated rows for the statistics (shared by the API and the report)."""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, select

from app.models.analysis import AnalysisJob, AnalysisStatus
from app.models.game import Game, GameSource, utcnow
from app.models.insight import GameInsight, MoveInsight
from app.play.rules import PlayerColor
from app.stats.aggregate import GameRow, MoveRow, Stats, build_stats
from app.stats.insights import INSIGHTS_VERSION


@dataclass(frozen=True)
class StatsFilters:
    include_bot: bool = False  # by default only real games (Lichess, Chess.com, PGN)
    time_class: str | None = None
    color: PlayerColor | None = None
    days: int | None = None


@dataclass(frozen=True)
class StatsResult:
    games_finished: int  # finished games matching the filters (analysed or not)
    games_unanalysed: int
    stats: Stats


def _opponent(game: Game) -> str | None:
    if game.source == GameSource.PLAYED:
        return "Stockfish"
    return game.black_name if game.player_color == PlayerColor.WHITE else game.white_name


def load_stats(session: Session, f: StatsFilters) -> StatsResult:
    """Only analysed games with rows of the current version count."""
    conditions: list[ColumnElement[bool]] = [col(Game.result).is_not(None)]
    if not f.include_bot:
        conditions.append(col(Game.source) == GameSource.IMPORTED)
    if f.time_class is not None:
        conditions.append(col(Game.time_class) == f.time_class)
    if f.color is not None:
        conditions.append(col(Game.player_color) == f.color)
    if f.days is not None:
        since = utcnow() - timedelta(days=f.days)
        conditions.append(func.coalesce(col(Game.played_at), col(Game.created_at)) >= since)

    finished = session.exec(select(func.count()).select_from(Game).where(*conditions)).one()
    analysed = session.exec(
        select(func.count())
        .select_from(Game)
        .join(AnalysisJob, col(AnalysisJob.game_id) == col(Game.id))
        .where(*conditions, AnalysisJob.status == AnalysisStatus.DONE)
    ).one()
    rows = session.exec(
        select(Game, GameInsight)
        .join(GameInsight, col(GameInsight.game_id) == col(Game.id))
        .join(AnalysisJob, col(AnalysisJob.game_id) == col(Game.id))
        .where(
            *conditions,
            AnalysisJob.status == AnalysisStatus.DONE,
            GameInsight.version == INSIGHTS_VERSION,
        )
    ).all()
    games = [
        GameRow(
            game_id=game.id or 0,
            date=game.played_at or game.created_at,
            color=game.player_color.value,
            opponent=_opponent(game),
            accuracy=insight.accuracy,
            result=insight.result,
            opening_family=insight.opening_family,
            opening_name=insight.opening_name,
        )
        for game, insight in rows
    ]
    ids = [g.game_id for g in games]
    moves = [
        MoveRow(
            game_id=m.game_id,
            ply=m.ply,
            san=m.san,
            classification=m.classification,
            delta=m.delta,
            phase=m.phase,
            error_kind=m.error_kind,
            low_time=m.low_time,
        )
        for m in session.exec(select(MoveInsight).where(col(MoveInsight.game_id).in_(ids))).all()
    ]
    return StatsResult(int(finished), int(finished) - int(analysed), build_stats(games, moves))
