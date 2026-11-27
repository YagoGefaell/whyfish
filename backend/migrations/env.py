"""Alembic environment. Migrations run at app startup (app.db.init_db) or via `alembic`."""

from alembic import context
from sqlalchemy import Connection, create_engine
from sqlmodel import SQLModel

import app.models.analysis
import app.models.game
import app.models.insight
import app.models.sync
import app.models.training  # noqa: F401
from app.config import get_settings

target_metadata = SQLModel.metadata


def run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite cannot ALTER most things; batch mode recreates tables
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    engine = create_engine(get_settings().database_url)
    with engine.begin() as conn:
        run(conn)
