"""Accounts synchronised from online platforms and app-wide settings (phase 6a)."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class ImportAccount(SQLModel, table=True):
    """One account per platform (Platform value). Its games are imported incrementally."""

    id: int | None = Field(default=None, primary_key=True)
    platform: str = Field(unique=True)
    username: str
    # Range already covered: games played from `covered_from` to `newest_at` are imported.
    covered_from: datetime | None = None
    newest_at: datetime | None = None  # start time of the newest game imported
    last_synced_at: datetime | None = None
    last_error: str | None = None
    imported_count: int = 0


class AppSetting(SQLModel, table=True):
    """Key/value settings changed from the app (e.g. the analysis queue paused)."""

    key: str = Field(primary_key=True)
    value: str
