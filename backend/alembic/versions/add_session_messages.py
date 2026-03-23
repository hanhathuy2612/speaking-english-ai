"""add session_messages table

Revision ID: add_session_messages
Revises: add_opening_audio_path
Create Date: 2026-03-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "add_session_messages"
down_revision: Union[str, None] = "add_opening_audio_path"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("session_messages"):
        op.create_table(
            "session_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("index_in_session", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("kind", sa.String(length=40), nullable=False, server_default="chat"),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("audio_path", sa.String(length=512), nullable=True),
            sa.Column("guideline", sa.Text(), nullable=True),
            sa.Column("score_fluency", sa.Float(), nullable=True),
            sa.Column("score_vocabulary", sa.Float(), nullable=True),
            sa.Column("score_grammar", sa.Float(), nullable=True),
            sa.Column("score_overall", sa.Float(), nullable=True),
            sa.Column("score_feedback", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    idx = {x["name"] for x in insp.get_indexes("session_messages")}
    if "ix_session_messages_session_id" not in idx:
        op.create_index(
            "ix_session_messages_session_id",
            "session_messages",
            ["session_id"],
            unique=False,
        )
    if "ix_session_messages_session_index" not in idx:
        op.create_index(
            "ix_session_messages_session_index",
            "session_messages",
            ["session_id", "index_in_session"],
            unique=False,
        )
    if "ix_session_messages_session_role" not in idx:
        op.create_index(
            "ix_session_messages_session_role",
            "session_messages",
            ["session_id", "role"],
            unique=False,
        )
    if "ix_session_messages_session_kind" not in idx:
        op.create_index(
            "ix_session_messages_session_kind",
            "session_messages",
            ["session_id", "kind"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_session_messages_session_kind", table_name="session_messages")
    op.drop_index("ix_session_messages_session_role", table_name="session_messages")
    op.drop_index("ix_session_messages_session_index", table_name="session_messages")
    op.drop_index("ix_session_messages_session_id", table_name="session_messages")
    op.drop_table("session_messages")
