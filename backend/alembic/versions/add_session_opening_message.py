"""Persist AI opening greeting on session (resume / history).

Revision ID: add_session_opening_msg
Revises: add_topic_unit_max_turns
Create Date: 2026-03-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "add_session_opening_msg"
down_revision: Union[str, None] = "add_topic_unit_max_turns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("opening_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "opening_message")
