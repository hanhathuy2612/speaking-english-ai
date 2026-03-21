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
