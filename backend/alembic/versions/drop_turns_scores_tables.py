"""drop legacy turns/scores tables

Revision ID: drop_turns_scores_tables
Revises: add_session_messages
Create Date: 2026-03-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "drop_turns_scores_tables"
down_revision: Union[str, None] = "add_session_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("scores"):
        op.drop_table("scores")
    if insp.has_table("turns"):
        op.drop_table("turns")


def downgrade() -> None:
    op.create_table(
        "turns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("index_in_session", sa.Integer(), nullable=False),
        sa.Column("user_text", sa.Text(), nullable=False),
        sa.Column("assistant_text", sa.Text(), nullable=False),
        sa.Column("guideline", sa.Text(), nullable=True),
        sa.Column("user_audio_path", sa.String(length=512), nullable=True),
        sa.Column("assistant_audio_path", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_turns_id", "turns", ["id"], unique=False)

    op.create_table(
        "scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("turn_id", sa.Integer(), nullable=False),
        sa.Column("fluency", sa.Float(), nullable=False),
        sa.Column("vocabulary", sa.Float(), nullable=False),
        sa.Column("grammar", sa.Float(), nullable=False),
        sa.Column("overall", sa.Float(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("turn_id"),
    )
    op.create_index("ix_scores_id", "scores", ["id"], unique=False)
