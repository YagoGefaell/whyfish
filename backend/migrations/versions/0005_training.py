"""training: exercises from the user's errors and sessions (phase 6c)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-27 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STR = sqlmodel.sql.sqltypes.AutoString


def upgrade() -> None:
    op.create_table(
        "trainingitem",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("ply", sa.Integer(), nullable=False),
        sa.Column("classification", _STR(), nullable=False),
        sa.Column("error_kind", _STR(), nullable=True),
        sa.Column("phase", _STR(), nullable=False),
        sa.Column("low_time", sa.Boolean(), nullable=True),
        sa.Column("excluded", _STR(), nullable=True),
        sa.Column("box", sa.Integer(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("learned", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["game.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "ply"),
    )
    with op.batch_alter_table("trainingitem", schema=None) as batch_op:
        batch_op.create_index("ix_trainingitem_game_id", ["game_id"], unique=False)
    op.create_table(
        "trainingsession",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("daily", sa.Boolean(), nullable=False),
        sa.Column("filter_json", _STR(), nullable=False),
        sa.Column("items_json", _STR(), nullable=False),
        sa.Column("results_json", _STR(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("trainingsession", schema=None) as batch_op:
        batch_op.create_index("ix_trainingsession_day", ["day"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("trainingsession", schema=None) as batch_op:
        batch_op.drop_index("ix_trainingsession_day")
    op.drop_table("trainingsession")
    with op.batch_alter_table("trainingitem", schema=None) as batch_op:
        batch_op.drop_index("ix_trainingitem_game_id")
    op.drop_table("trainingitem")
