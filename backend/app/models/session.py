from datetime import datetime
from typing import TYPE_CHECKING

from app.db.session import Base
from app.models.conversation_common import int_pk, utc_now
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.session_message import SessionMessage
    from app.models.topic import Topic
    from app.models.topic_unit import TopicUnit
    from app.models.user import User


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int_pk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    topic_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("topic_units.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opening_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    opening_audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")
    topic: Mapped["Topic"] = relationship(back_populates="sessions")
    topic_unit: Mapped["TopicUnit | None"] = relationship(
        back_populates="sessions",
    )
    messages: Mapped[list["SessionMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
