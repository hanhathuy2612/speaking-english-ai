from datetime import datetime, timezone
from typing import Annotated

from app.db.session import Base
from app.models.conversation import ConversationSession
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

int_pk = Annotated[int, mapped_column(primary_key=True, index=True)]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int_pk]
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=_utc_now)

    sessions: Mapped[list["ConversationSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
