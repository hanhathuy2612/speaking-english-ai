"""add guideline column to turns (saved when user clicks AI question)

Revision ID: add_turn_guideline
Revises: drop_topic_guidance
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "add_turn_guideline"
down_revision: Union[str, None] = "drop_topic_guidance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "turns",
        sa.Column("guideline", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("turns", "guideline")
