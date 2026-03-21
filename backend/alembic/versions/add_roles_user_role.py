"""roles table + user_role association

Revision ID: add_roles_user_role
Revises: add_topic_roadmap
Create Date: 2026-03-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "add_roles_user_role"
down_revision: Union[str, None] = "add_topic_roadmap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if not insp.has_table("roles"):
        op.create_table(
            "roles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        op.create_index("ix_roles_id", "roles", ["id"], unique=False)

    if not insp.has_table("user_role"):
        op.create_table(
            "user_role",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id", "role_id"),
        )

    op.execute(
        sa.text(
            "INSERT INTO roles (name) SELECT 'user' WHERE NOT EXISTS "
            "(SELECT 1 FROM roles WHERE name = 'user')"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO roles (name) SELECT 'admin' WHERE NOT EXISTS "
            "(SELECT 1 FROM roles WHERE name = 'admin')"
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO user_role (user_id, role_id)
            SELECT u.id, r.id
            FROM users u
            JOIN roles r ON r.name = 'user'
            WHERE NOT EXISTS (
                SELECT 1 FROM user_role ur WHERE ur.user_id = u.id
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_table("user_role")
    op.drop_index("ix_roles_id", table_name="roles")
    op.drop_table("roles")
