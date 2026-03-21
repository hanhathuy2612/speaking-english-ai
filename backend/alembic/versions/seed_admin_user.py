"""Seed default admin user (roles user + admin).

Revision ID: seed_admin_user
Revises: add_roles_user_role
Create Date: 2026-03-21

Optional env (only read when this migration runs):
  ALEMBIC_ADMIN_EMAIL     default admin@example.com (must pass EmailStr / RFC-style domain)
  ALEMBIC_ADMIN_USERNAME  default admin
  ALEMBIC_ADMIN_PASSWORD  default AdminDev123!  — change immediately in production

If a user with the same email already exists, only missing user_role rows are added.
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import bcrypt
import sqlalchemy as sa
from alembic import op

revision: str = "seed_admin_user"
down_revision: Union[str, None] = "add_roles_user_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BCRYPT_MAX = 72

_DEFAULT_EMAIL = "admin@example.com"
_DEFAULT_USERNAME = "admin"
_DEFAULT_PASSWORD = "AdminDev123!"


def _hash_password(plain: str) -> str:
    b = plain.encode("utf-8")
    if len(b) > _BCRYPT_MAX:
        b = b[:_BCRYPT_MAX]
    return bcrypt.hashpw(b, bcrypt.gensalt()).decode("utf-8")


def upgrade() -> None:
    email = os.environ.get("ALEMBIC_ADMIN_EMAIL", _DEFAULT_EMAIL).strip()
    username = os.environ.get("ALEMBIC_ADMIN_USERNAME", _DEFAULT_USERNAME).strip()
    password = os.environ.get("ALEMBIC_ADMIN_PASSWORD", _DEFAULT_PASSWORD)
    password_hash = _hash_password(password)

    conn = op.get_bind()

    row = conn.execute(
        sa.text("SELECT id FROM users WHERE email = :email"), {"email": email}
    ).fetchone()
    if row is None:
        conn.execute(
            sa.text(
                """
                INSERT INTO users (
                    email, username, password_hash, is_active, created_at
                )
                VALUES (
                    :email, :username, :password_hash, true, NOW()
                )
                """
            ),
            {
                "email": email,
                "username": username,
                "password_hash": password_hash,
            },
        )

    for role_name in ("user", "admin"):
        conn.execute(
            sa.text(
                """
                INSERT INTO user_role (user_id, role_id)
                SELECT u.id, r.id
                FROM users u
                JOIN roles r ON r.name = :role_name
                WHERE u.email = :email
                AND NOT EXISTS (
                    SELECT 1 FROM user_role ur
                    WHERE ur.user_id = u.id AND ur.role_id = r.id
                )
                """
            ),
            {"email": email, "role_name": role_name},
        )


def downgrade() -> None:
    email = os.environ.get("ALEMBIC_ADMIN_EMAIL", _DEFAULT_EMAIL).strip()
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM user_role
            WHERE user_id IN (SELECT id FROM users WHERE email = :email)
            """
        ),
        {"email": email},
    )
    conn.execute(
        sa.text("DELETE FROM users WHERE email = :email"),
        {"email": email},
    )
