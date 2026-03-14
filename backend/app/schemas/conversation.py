from datetime import datetime

from pydantic import BaseModel


class TurnOut(BaseModel):
    index_in_session: int
    user_text: str
    assistant_text: str
    guideline: str | None = None
    fluency: float | None = None
    vocabulary: float | None = None
    grammar: float | None = None
    overall: float | None = None
    feedback: str | None = None
    created_at: datetime


class SessionOut(BaseModel):
    id: int
    topic_id: int
    topic_title: str
    started_at: datetime
    ended_at: datetime | None
    turn_count: int


class SessionDetailOut(BaseModel):
    id: int
    topic_id: int
    topic_title: str
    started_at: datetime
    ended_at: datetime | None
    turns: list[TurnOut]
