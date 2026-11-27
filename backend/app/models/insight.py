"""Precalculated data of analysed games for the statistics (phase 6b).

Computed when an analysis finishes (and in the background for older ones). `version` is
`app.stats.insights.INSIGHTS_VERSION`: rows of an older version are recalculated, so the
statistics always follow the current classification and facts rules.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class GameInsight(SQLModel, table=True):
    game_id: int = Field(foreign_key="game.id", primary_key=True)
    version: int
    computed_at: datetime
    accuracy: float | None  # the user's (same formula as the review)
    result: str | None  # "win" | "draw" | "loss" from the user's side; None if unknown
    opening_eco: str | None
    opening_name: str | None
    opening_family: str | None  # the name before ":" ("Sicilian Defense")
    user_moves: int
    clock_initial_s: float | None  # base time of the game, if it has a clock


class MoveInsight(SQLModel, table=True):
    """One row per move of the user in an analysed game."""

    id: int | None = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id", index=True)
    ply: int
    san: str
    classification: str  # Classification value
    delta: float  # win% lost by the move (mover's view)
    accuracy: float
    win_before: float
    phase: str  # "opening" | "middlegame" | "endgame"
    error_kind: str | None  # main idea of an error (?!, ?, ??, ✗): IdeaKind value
    clock_s: float | None  # user's remaining time after the move
    low_time: bool | None  # made with little time left (None: no clock)
