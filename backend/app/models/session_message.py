from datetime import datetime
from typing import TYPE_CHECKING

from app.db.session import Base
from app.models.conversation_common import int_pk, utc_now
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.session import Session


class SessionMessage(Base):
    __tablename__ = "session_messages"

    id: Mapped[int_pk]
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE")
    )
    index_in_session: Mapped[int]
    role: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(40), default="chat")
    text: Mapped[str] = mapped_column(Text())
    audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    guideline: Mapped[str | None] = mapped_column(Text(), nullable=True)
    score_fluency: Mapped[float | None] = mapped_column(nullable=True)
    score_vocabulary: Mapped[float | None] = mapped_column(nullable=True)
    score_grammar: Mapped[float | None] = mapped_column(nullable=True)
    score_overall: Mapped[float | None] = mapped_column(nullable=True)
    score_feedback: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped["Session"] = relationship(back_populates="messages")
