"""add user tts preferences

Revision ID: add_tts_prefs
Revises: 8f484ecc4ec6
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_tts_prefs"
down_revision: Union[str, None] = "8f484ecc4ec6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("tts_voice", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("tts_rate", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "tts_rate")
    op.drop_column("users", "tts_voice")
