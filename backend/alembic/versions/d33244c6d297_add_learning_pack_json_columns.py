"""add learning pack json columns

Revision ID: d33244c6d297
Revises: drop_turns_scores_tables
Create Date: 2026-04-16 21:58:53.839866

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd33244c6d297'
down_revision: Union[str, None] = 'drop_turns_scores_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("topics", sa.Column("learning_pack_json", sa.JSON(), nullable=True))
    op.add_column("topic_units", sa.Column("learning_pack_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("topic_units", "learning_pack_json")
    op.drop_column("topics", "learning_pack_json")
