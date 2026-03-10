from datetime import datetime
from typing import Annotated

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


int_pk = Annotated[int, mapped_column(primary_key=True, index=True)]


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int_pk]
    title: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # A1, A2, B1...

    sessions: Mapped[list["ConversationSession"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )


class ConversationSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int_pk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user = relationship("User", back_populates="sessions")
    topic = relationship("Topic", back_populates="sessions")
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
    user_audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    assistant_audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    session: Mapped["ConversationSession"] = relationship(
        back_populates="turns"
    )
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

