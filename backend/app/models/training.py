"""Training with the user's own errors (phase 6c): exercises (Leitner boxes) and sessions."""

from datetime import date, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class TrainingItem(SQLModel, table=True):
    """An error of the user (?, ?? or ✗) turned into "find the best move"."""

    __table_args__ = (UniqueConstraint("game_id", "ply"),)

    id: int | None = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id", index=True)
    ply: int  # the user's move to find instead (the position is the one before it)
    classification: str  # mistake | blunder | miss
    error_kind: str | None  # main idea of the error (IdeaKind value)
    phase: str
    low_time: bool | None  # the error was made with little time left
    # Never shown: "decided" (win% > 85 or < 15) or "unclear" (several equally good moves).
    excluded: str | None = None
    box: int = 0  # 0 = new; 1-5 = Leitner box
    due_on: date | None = None
    attempts: int = 0
    correct: int = 0
    learned: bool = False
    last_seen_at: datetime | None = None
    created_at: datetime


class TrainingSession(SQLModel, table=True):
    """A day's session: the daily one (counts for the streak) or a filtered one."""

    id: int | None = Field(default=None, primary_key=True)
    day: date = Field(index=True)
    daily: bool
    filter_json: str  # {"error_kind": ..., "phase": ..., "low_time": ...} or {}
    items_json: str  # ordered item ids (a failed one is appended once more at the end)
    results_json: str  # {"<position>": "correct" | "wrong"}
    completed: bool = False
