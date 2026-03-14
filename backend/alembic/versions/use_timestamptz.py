"""use timestamp with time zone for datetime columns

Revision ID: use_timestamptz
Revises: add_tts_prefs
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op


revision: str = "use_timestamptz"
down_revision: Union[str, None] = "add_tts_prefs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL: convert TIMESTAMP WITHOUT TIME ZONE -> WITH TIME ZONE (assume stored as UTC)
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC'"
        )
        op.execute(
            "ALTER TABLE sessions ALTER COLUMN started_at TYPE TIMESTAMP WITH TIME ZONE USING started_at AT TIME ZONE 'UTC'"
        )
        op.execute(
            "ALTER TABLE sessions ALTER COLUMN ended_at TYPE TIMESTAMP WITH TIME ZONE USING ended_at AT TIME ZONE 'UTC'"
        )
        op.execute(
            "ALTER TABLE turns ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE"
        )
        op.execute(
            "ALTER TABLE sessions ALTER COLUMN started_at TYPE TIMESTAMP WITHOUT TIME ZONE"
        )
        op.execute(
            "ALTER TABLE sessions ALTER COLUMN ended_at TYPE TIMESTAMP WITHOUT TIME ZONE"
        )
        op.execute(
            "ALTER TABLE turns ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE"
        )
