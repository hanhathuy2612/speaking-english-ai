from datetime import datetime

from pydantic import BaseModel


class TurnOut(BaseModel):
    turn_id: int
    index_in_session: int
    user_text: str
    assistant_text: str
    has_user_audio: bool = False
    has_assistant_audio: bool = False
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


class SessionCreateIn(BaseModel):
    topic_id: int
    topic_unit_id: int | None = None


class SessionCreatedOut(BaseModel):
    id: int
    topic_id: int
    topic_unit_id: int | None = None
    topic_level: str | None = None


class SessionDetailOut(BaseModel):
    id: int
    topic_id: int
    topic_title: str
    started_at: datetime
    ended_at: datetime | None
    opening_message: str | None = None
    has_opening_audio: bool = False
    turns: list[TurnOut]


class TopicUnitSummarySnippet(BaseModel):
    id: int
    title: str
    objective: str


class UnitStepSummaryOut(BaseModel):
    """Aggregated scores for a session tied to a roadmap unit (or any session)."""

    session_id: int
    topic_id: int
    topic_title: str
    topic_unit: TopicUnitSummarySnippet | None
    scored_turns: int
    avg_fluency: float | None
    avg_vocabulary: float | None
    avg_grammar: float | None
    avg_overall: float | None
    min_turns_to_complete: int | None
    min_avg_overall: float | None
    max_scored_turns: int | None
    thresholds_met: bool
