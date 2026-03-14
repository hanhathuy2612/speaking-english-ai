from datetime import datetime

from pydantic import BaseModel


class ScoreAvg(BaseModel):
    fluency: float
    vocabulary: float
    grammar: float
    overall: float


class DailyMinutes(BaseModel):
    date: str
    minutes: float


class RecentSession(BaseModel):
    id: int
    topic_title: str
    started_at: datetime
    ended_at: datetime | None
    turn_count: int
    avg_overall: float | None


class ProgressSummary(BaseModel):
    total_sessions: int
    total_turns: int
    avg_scores: ScoreAvg | None
    daily_minutes: list[DailyMinutes]
    recent_sessions: list[RecentSession]
