"""add topic guidance column for conversation tips panel

Revision ID: add_topic_guidance
Revises: use_timestamptz
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_topic_guidance"
down_revision: Union[str, None] = "use_timestamptz"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column("guidance", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("topics", "guidance")
