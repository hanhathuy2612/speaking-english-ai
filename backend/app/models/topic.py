from typing import TYPE_CHECKING

from app.db.session import Base
from app.models.conversation_common import int_pk
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.session import Session
    from app.models.topic_unit import TopicUnit


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int_pk]
    title: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    level: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # IELTS Speaking target band e.g. "6", "6.5" (legacy CEFR strings still accepted at runtime)

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )
    units: Mapped[list["TopicUnit"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", order_by="TopicUnit.sort_order"
    )
