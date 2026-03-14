"""drop topic guidance column (unused; guide panel uses per-question API)

Revision ID: drop_topic_guidance
Revises: add_topic_guidance
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "drop_topic_guidance"
down_revision: Union[str, None] = "add_topic_guidance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("topics", "guidance")


def downgrade() -> None:
    op.add_column("topics", sa.Column("guidance", sa.Text(), nullable=True))
