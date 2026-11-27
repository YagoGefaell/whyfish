"""online sync: platform games, clocks, accounts, settings, queue attempts (phase 6a)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-27 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STR = sqlmodel.sql.sqltypes.AutoString


def upgrade() -> None:
    with op.batch_alter_table("game", schema=None) as batch_op:
        batch_op.add_column(sa.Column("platform", _STR(), nullable=True))
        batch_op.add_column(sa.Column("external_id", _STR(), nullable=True))
        batch_op.add_column(sa.Column("external_url", _STR(), nullable=True))
        batch_op.add_column(sa.Column("played_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("time_class", _STR(), nullable=True))
        batch_op.add_column(sa.Column("time_control", _STR(), nullable=True))
        batch_op.add_column(sa.Column("white_elo", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("black_elo", sa.Integer(), nullable=True))
        batch_op.create_index("ix_game_platform", ["platform"], unique=False)
        batch_op.create_index("ix_game_played_at", ["played_at"], unique=False)
        batch_op.create_unique_constraint(
            "uq_game_platform_external_id", ["platform", "external_id"]
        )
    with op.batch_alter_table("move", schema=None) as batch_op:
        batch_op.add_column(sa.Column("clock_s", sa.Float(), nullable=True))
    with op.batch_alter_table("analysisjob", schema=None) as batch_op:
        batch_op.add_column(sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "importaccount",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform", _STR(), nullable=False),
        sa.Column("username", _STR(), nullable=False),
        sa.Column("covered_from", sa.DateTime(), nullable=True),
        sa.Column("newest_at", sa.DateTime(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", _STR(), nullable=True),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform"),
    )
    op.create_table(
        "appsetting",
        sa.Column("key", _STR(), nullable=False),
        sa.Column("value", _STR(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("appsetting")
    op.drop_table("importaccount")
    with op.batch_alter_table("analysisjob", schema=None) as batch_op:
        batch_op.drop_column("attempts")
    with op.batch_alter_table("move", schema=None) as batch_op:
        batch_op.drop_column("clock_s")
    with op.batch_alter_table("game", schema=None) as batch_op:
        batch_op.drop_constraint("uq_game_platform_external_id", type_="unique")
        batch_op.drop_index("ix_game_played_at")
        batch_op.drop_index("ix_game_platform")
        for column in (
            "black_elo",
            "white_elo",
            "time_control",
            "time_class",
            "played_at",
            "external_url",
            "external_id",
            "platform",
        ):
            batch_op.drop_column(column)
