from datetime import datetime
from typing import TYPE_CHECKING

from app.db.session import Base
from app.models.conversation_common import int_pk
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.topic_unit import TopicUnit
    from app.models.user import User


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
