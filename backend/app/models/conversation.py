from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated

from app.db.session import Base
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.user import User

int_pk = Annotated[int, mapped_column(primary_key=True, index=True)]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int_pk]
    title: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    level: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # A1, A2, B1...

    sessions: Mapped[list["ConversationSession"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    units: Mapped[list["TopicUnit"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", order_by="TopicUnit.sort_order"
    )


class TopicUnit(Base):
    __tablename__ = "topic_units"

    id: Mapped[int_pk]
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    sort_order: Mapped[int]
    title: Mapped[str] = mapped_column(String(255))
    objective: Mapped[str] = mapped_column(Text())
    prompt_hint: Mapped[str] = mapped_column(Text())
    min_turns_to_complete: Mapped[int | None] = mapped_column(nullable=True)
    min_avg_overall: Mapped[float | None] = mapped_column(nullable=True)
    max_scored_turns: Mapped[int | None] = mapped_column(nullable=True)

    topic: Mapped["Topic"] = relationship(back_populates="units")
    progress_rows: Mapped[list["UserTopicUnitProgress"]] = relationship(
        back_populates="topic_unit", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["ConversationSession"]] = relationship(
        back_populates="topic_unit",
    )


class UserTopicUnitProgress(Base):
    __tablename__ = "user_topic_unit_progress"

    id: Mapped[int_pk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic_unit_id: Mapped[int] = mapped_column(
        ForeignKey("topic_units.id", ondelete="CASCADE")
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="topic_unit_progress_rows")
    topic_unit: Mapped["TopicUnit"] = relationship(back_populates="progress_rows")


class ConversationSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int_pk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    topic_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("topic_units.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opening_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    opening_audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user = relationship("User", back_populates="sessions")
    topic = relationship("Topic", back_populates="sessions")
    topic_unit: Mapped["TopicUnit | None"] = relationship(
        back_populates="sessions",
    )
    turns: Mapped[list["Turn"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[int_pk]
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    index_in_session: Mapped[int]
    user_text: Mapped[str] = mapped_column(Text())
    assistant_text: Mapped[str] = mapped_column(Text())
    guideline: Mapped[str | None] = mapped_column(Text(), nullable=True)  # hints when user clicks AI question
    user_audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    assistant_audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now
    )

    session: Mapped["ConversationSession"] = relationship(back_populates="turns")
    score: Mapped["TurnScore | None"] = relationship(
        back_populates="turn", uselist=False, cascade="all, delete-orphan"
    )


class TurnScore(Base):
    __tablename__ = "scores"

    id: Mapped[int_pk]
    turn_id: Mapped[int] = mapped_column(ForeignKey("turns.id"), unique=True)
    fluency: Mapped[float]
    vocabulary: Mapped[float]
    grammar: Mapped[float]
    overall: Mapped[float]
    feedback: Mapped[str | None] = mapped_column(Text(), nullable=True)

    turn: Mapped["Turn"] = relationship(back_populates="score")
