"""Roles and user_role association (RBAC, extensible)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from app.db.session import Base
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.user import User

int_pk = Annotated[int, mapped_column(primary_key=True, index=True)]

ROLE_USER = "user"
ROLE_ADMIN = "admin"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int_pk]
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    user_memberships: Mapped[list["UserRole"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class UserRole(Base):
    __tablename__ = "user_role"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )

    user: Mapped["User"] = relationship(back_populates="role_memberships")
    role: Mapped["Role"] = relationship(back_populates="user_memberships")
