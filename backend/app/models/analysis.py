from datetime import datetime
from enum import StrEnum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.game import utcnow


class AnalysisStatus(StrEnum):
    PENDING = "pending"  # queued behind another analysis
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class AnalysisJob(SQLModel, table=True):
    """Latest analysis of a game (one row per game)."""

    id: int | None = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id", unique=True, index=True)
    settings_key: str
    status: AnalysisStatus
    done: int = 0
    total: int = 0
    error: str | None = None
    attempts: int = 0  # background queue: a failed analysis is retried once
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


class PositionAnalysis(SQLModel, table=True):
    """Cache of engine lines per position (+ reversible history) and engine settings."""

    __table_args__ = (UniqueConstraint("key", "settings_key"),)

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(index=True)  # app.analysis.positions.position_key
    settings_key: str
    fen: str  # for debugging only
    lines_json: str
    created_at: datetime = Field(default_factory=utcnow)
