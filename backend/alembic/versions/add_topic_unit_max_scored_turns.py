"""Optional max scored turns per roadmap step (hard cap).

Revision ID: add_topic_unit_max_turns
Revises: fix_seed_admin_email
Create Date: 2026-03-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "add_topic_unit_max_turns"
down_revision: Union[str, None] = "fix_seed_admin_email"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "topic_units",
        sa.Column("max_scored_turns", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("topic_units", "max_scored_turns")
