from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AdminUserOut(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    roles: list[str]
    created_at: str

    model_config = {"from_attributes": True}


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int


class AdminUserPatch(BaseModel):
    is_active: bool | None = None
    role_slugs: list[str] | None = Field(
        None,
        description="Replace all roles with this set (slugs must exist, e.g. user, admin).",
    )


class TopicUnitCreateIn(BaseModel):
    sort_order: int = Field(..., ge=0)
    title: str = Field(..., min_length=1, max_length=255)
    objective: str = Field(..., min_length=1)
    prompt_hint: str = Field(..., min_length=1)
    min_turns_to_complete: int | None = Field(None, ge=1)
    min_avg_overall: float | None = Field(None, ge=0, le=10)
    max_scored_turns: int | None = Field(
        None,
        ge=1,
        description="Optional cap: block new practice turns after this many scored turns in one session.",
    )


class TopicUnitUpdateIn(BaseModel):
    sort_order: int | None = Field(None, ge=0)
    title: str | None = Field(None, min_length=1, max_length=255)
    objective: str | None = None
    prompt_hint: str | None = None
    min_turns_to_complete: int | None = Field(None, ge=1)
    min_avg_overall: float | None = Field(None, ge=0, le=10)
    max_scored_turns: int | None = None

    @field_validator("max_scored_turns")
    @classmethod
    def _max_scored_turns_update(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("max_scored_turns must be >= 1")
        return v


class AITopicDraftIn(BaseModel):
    idea: str | None = Field(
        None,
        max_length=1000,
        description="Optional brief, e.g. 'travel at airports for IELTS band 6.5'",
    )


class AITopicDraftOut(BaseModel):
    title: str
    description: str | None
    level: str | None


class AITopicUnitDraftIn(BaseModel):
    idea: str | None = Field(
        None,
        max_length=1000,
        description="Optional brief for a guided step in this topic.",
    )


class AITopicUnitDraftOut(BaseModel):
    title: str
    objective: str
    prompt_hint: str
    min_turns_to_complete: int | None = Field(None, ge=1)
    min_avg_overall: float | None = Field(None, ge=0, le=10)
    max_scored_turns: int | None = Field(None, ge=1)


class AdminTopicSessionOut(BaseModel):
    """One conversation session on a topic, including owning user (admin list)."""

    id: int
    topic_id: int
    topic_title: str
    user_id: int
    user_email: str
    user_username: str
    topic_unit_title: str | None = None
    started_at: datetime
    ended_at: datetime | None
    turn_count: int
    avg_overall: float | None


class AdminTopicSessionsPage(BaseModel):
    items: list[AdminTopicSessionOut]
    total: int
