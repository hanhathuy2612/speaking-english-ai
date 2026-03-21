"""topic units, user progress, session.topic_unit_id

Revision ID: add_topic_roadmap
Revises: add_turn_guideline
Create Date: 2026-03-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "add_topic_roadmap"
down_revision: Union[str, None] = "add_turn_guideline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Support DBs where SQLAlchemy create_all already created topic_* tables but did not ALTER sessions."""
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if not insp.has_table("topic_units"):
        op.create_table(
            "topic_units",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("topic_id", sa.Integer(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("objective", sa.Text(), nullable=False),
            sa.Column("prompt_hint", sa.Text(), nullable=False),
            sa.Column("min_turns_to_complete", sa.Integer(), nullable=True),
            sa.Column("min_avg_overall", sa.Float(), nullable=True),
            sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_topic_units_id", "topic_units", ["id"], unique=False)
        op.create_index("ix_topic_units_topic_id", "topic_units", ["topic_id"], unique=False)
        op.create_unique_constraint(
            "uq_topic_units_topic_sort", "topic_units", ["topic_id", "sort_order"]
        )
    else:
        # create_all may have omitted Alembic-named indexes/constraints; add if missing
        ix_topic = {ix["name"] for ix in insp.get_indexes("topic_units")}
        if "ix_topic_units_id" not in ix_topic:
            op.create_index("ix_topic_units_id", "topic_units", ["id"], unique=False)
        if "ix_topic_units_topic_id" not in ix_topic:
            op.create_index("ix_topic_units_topic_id", "topic_units", ["topic_id"], unique=False)
        uqs = {uc["name"] for uc in insp.get_unique_constraints("topic_units")}
        if "uq_topic_units_topic_sort" not in uqs:
            op.create_unique_constraint(
                "uq_topic_units_topic_sort", "topic_units", ["topic_id", "sort_order"]
            )

    if not insp.has_table("user_topic_unit_progress"):
        op.create_table(
            "user_topic_unit_progress",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("topic_unit_id", sa.Integer(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["topic_unit_id"], ["topic_units.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "topic_unit_id", name="uq_user_topic_unit_progress"),
        )
        op.create_index(
            "ix_user_topic_unit_progress_id", "user_topic_unit_progress", ["id"], unique=False
        )
    else:
        ix_p = {ix["name"] for ix in insp.get_indexes("user_topic_unit_progress")}
        if "ix_user_topic_unit_progress_id" not in ix_p:
            op.create_index(
                "ix_user_topic_unit_progress_id",
                "user_topic_unit_progress",
                ["id"],
                unique=False,
            )

    session_cols = {c["name"] for c in insp.get_columns("sessions")}
    if "topic_unit_id" not in session_cols:
        op.add_column(
            "sessions",
            sa.Column("topic_unit_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_sessions_topic_unit_id",
            "sessions",
            "topic_units",
            ["topic_unit_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.drop_constraint("fk_sessions_topic_unit_id", "sessions", type_="foreignkey")
    op.drop_column("sessions", "topic_unit_id")
    op.drop_index("ix_user_topic_unit_progress_id", table_name="user_topic_unit_progress")
    op.drop_table("user_topic_unit_progress")
    op.drop_constraint("uq_topic_units_topic_sort", "topic_units", type_="unique")
    op.drop_index("ix_topic_units_topic_id", table_name="topic_units")
    op.drop_index("ix_topic_units_id", table_name="topic_units")
    op.drop_table("topic_units")
