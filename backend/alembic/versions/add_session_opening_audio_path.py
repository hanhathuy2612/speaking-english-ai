"""Store opening greeting TTS path on session.

Revision ID: add_opening_audio_path
Revises: add_session_opening_msg
Create Date: 2026-03-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "add_opening_audio_path"
down_revision: Union[str, None] = "add_session_opening_msg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("opening_audio_path", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "opening_audio_path")
