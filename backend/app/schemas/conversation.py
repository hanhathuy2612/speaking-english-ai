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
