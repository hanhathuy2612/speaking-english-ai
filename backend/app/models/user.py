from datetime import datetime
from typing import Annotated

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


int_pk = Annotated[int, mapped_column(primary_key=True, index=True)]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int_pk]
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    sessions: Mapped[list["ConversationSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

