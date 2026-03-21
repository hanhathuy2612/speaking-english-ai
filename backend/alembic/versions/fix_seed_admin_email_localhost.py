"""Use admin@example.com for seeded admin (EmailStr rejects admin@localhost).

Revision ID: fix_seed_admin_email
Revises: seed_admin_user
Create Date: 2026-03-21

Login/register use Pydantic EmailStr; domains without a period (e.g. localhost) fail validation.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "fix_seed_admin_email"
down_revision: Union[str, None] = "seed_admin_user"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT 1 FROM users WHERE email = 'admin@example.com' LIMIT 1")
    ).fetchone()
    if row is not None:
        return
    conn.execute(
        sa.text(
            "UPDATE users SET email = 'admin@example.com' "
            "WHERE email = 'admin@localhost'"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT 1 FROM users WHERE email = 'admin@localhost' LIMIT 1")
    ).fetchone()
    if row is not None:
        return
    conn.execute(
        sa.text(
            "UPDATE users SET email = 'admin@localhost' "
            "WHERE email = 'admin@example.com' AND username = 'admin'"
        )
    )
