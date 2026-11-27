from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine as DbEngine
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

import app.models.analysis
import app.models.game
import app.models.insight
import app.models.sync
import app.models.training  # noqa: F401

BACKEND_DIR = Path(__file__).resolve().parents[1]
# Schema of databases created before Alembic was introduced (phases 1-2, via create_all).
BASELINE_REVISION = "0001"


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


def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def init_db(engine: DbEngine) -> None:
    """Bring the schema up to date with Alembic.

    A database created before Alembic (tables but no `alembic_version`) is stamped with the
    baseline revision first, so only the newer migrations run on it.
    """
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        if "game" in tables and "alembic_version" not in tables:
            command.stamp(config, BASELINE_REVISION)
        command.upgrade(config, "head")
