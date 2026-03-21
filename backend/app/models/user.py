from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated

from app.db.session import Base
from app.models.conversation import ConversationSession
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.conversation import UserTopicUnitProgress
    from app.models.role import UserRole

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now
    )
    # TTS preferences (nullable; fallback to app config)
    tts_voice: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tts_rate: Mapped[str | None] = mapped_column(String(20), nullable=True)

    sessions: Mapped[list["ConversationSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    topic_unit_progress_rows: Mapped[list["UserTopicUnitProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    role_memberships: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="user", cascade="all, delete-orphan"
    )
