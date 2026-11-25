from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel

from app.db import alembic_config, init_db, make_db_engine
from app.models.game import Game, GameSource


def test_migrations_match_the_models(tmp_path: Path) -> None:
    engine = make_db_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    init_db(engine)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
    assert diff == [], f"models and migrations differ: {diff}"


def test_database_created_before_alembic_is_stamped_and_upgraded(tmp_path: Path) -> None:
    """A phase 1-2 database (create_all, no alembic_version) keeps its games."""
    engine = make_db_engine(f"sqlite:///{tmp_path / 'old.db'}")
    config = alembic_config()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, "0001")
        conn.execute(text("DROP TABLE alembic_version"))
        conn.execute(
            text(
                "INSERT INTO game (created_at, player_color, bot_level, initial_fen, allow_undo,"
                " allow_hint, undo_count, hint_count, result) VALUES ('2026-11-25 10:00:00',"
                " 'WHITE', 'CLUB', 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',"
                " 0, 0, 0, 0, '0-1')"
            )
        )

    init_db(engine)

    with Session(engine) as session:
        game = session.get(Game, 1)
        assert game is not None
        assert game.source is GameSource.PLAYED
        assert game.result == "0-1"
    assert "alembic_version" in inspect(engine).get_table_names()
