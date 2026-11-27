"""Statistics of the user's analysed games (phase 6b)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlmodel import Session

from app.api.deps import get_session
from app.play.rules import PlayerColor
from app.stats.aggregate import Stats
from app.stats.insights import InsightService
from app.stats.queries import StatsFilters, load_stats

router = APIRouter()


def get_insights(request: Request) -> InsightService:
    service: InsightService = request.app.state.insights
    return service


class StatsRead(BaseModel):
    games_finished: int  # finished games matching the filters (analysed or not)
    games_unanalysed: int
    insights_pending: int  # analysed games whose data is still being calculated (all filters)
    stats: Stats


@router.get("/stats")
def get_stats(
    session: Annotated[Session, Depends(get_session)],
    insights: Annotated[InsightService, Depends(get_insights)],
    include_bot: bool = False,
    time_class: Literal["bullet", "blitz", "rapid", "classical", "correspondence"] | None = None,
    color: PlayerColor | None = None,
    days: Annotated[int | None, Query(ge=1)] = None,
) -> StatsRead:
    """Only analysed games count. By default, real games (Lichess, Chess.com, PGN); games
    against the bot only with `include_bot`."""
    result = load_stats(session, StatsFilters(include_bot, time_class, color, days))
    return StatsRead(
        games_finished=result.games_finished,
        games_unanalysed=result.games_unanalysed,
        insights_pending=insights.pending(),
        stats=result.stats,
    )
