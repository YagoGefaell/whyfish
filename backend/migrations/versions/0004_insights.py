"""insights: precalculated data of analysed games for the statistics (phase 6b)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-27 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STR = sqlmodel.sql.sqltypes.AutoString


def upgrade() -> None:
    op.create_table(
        "gameinsight",
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("result", _STR(), nullable=True),
        sa.Column("opening_eco", _STR(), nullable=True),
        sa.Column("opening_name", _STR(), nullable=True),
        sa.Column("opening_family", _STR(), nullable=True),
        sa.Column("user_moves", sa.Integer(), nullable=False),
        sa.Column("clock_initial_s", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["game.id"]),
        sa.PrimaryKeyConstraint("game_id"),
    )
    op.create_table(
        "moveinsight",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("ply", sa.Integer(), nullable=False),
        sa.Column("san", _STR(), nullable=False),
        sa.Column("classification", _STR(), nullable=False),
        sa.Column("delta", sa.Float(), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=False),
        sa.Column("win_before", sa.Float(), nullable=False),
        sa.Column("phase", _STR(), nullable=False),
        sa.Column("error_kind", _STR(), nullable=True),
        sa.Column("clock_s", sa.Float(), nullable=True),
        sa.Column("low_time", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["game.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("moveinsight", schema=None) as batch_op:
        batch_op.create_index("ix_moveinsight_game_id", ["game_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("moveinsight", schema=None) as batch_op:
        batch_op.drop_index("ix_moveinsight_game_id")
    op.drop_table("moveinsight")
    op.drop_table("gameinsight")
