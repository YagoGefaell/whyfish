from pathlib import Path

from sqlalchemy import Engine as DbEngine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import app.models.analysis
import app.models.game  # noqa: F401


def make_db_engine(url: str) -> DbEngine:
    if not url.startswith("sqlite"):
        return create_engine(url)
    connect_args = {"check_same_thread": False}
    if url in ("sqlite://", "sqlite:///:memory:"):
        # One shared connection so every session sees the same in-memory database.
        return create_engine(url, connect_args=connect_args, poolclass=StaticPool)
    db_path = Path(url.removeprefix("sqlite:///"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, connect_args=connect_args)


def init_db(engine: DbEngine) -> None:
    # No migrations until the schema stabilises (see docs/PROGRESS.md).
    SQLModel.metadata.create_all(engine)
