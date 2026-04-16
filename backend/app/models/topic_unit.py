from typing import TYPE_CHECKING, Any

from app.db.session import Base
from app.models.conversation_common import int_pk
from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.session import Session
    from app.models.topic import Topic
    from app.models.user_topic_unit_progress import UserTopicUnitProgress


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
    learning_pack_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    topic: Mapped["Topic"] = relationship(back_populates="units")
    progress_rows: Mapped[list["UserTopicUnitProgress"]] = relationship(
        back_populates="topic_unit", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="topic_unit",
    )
