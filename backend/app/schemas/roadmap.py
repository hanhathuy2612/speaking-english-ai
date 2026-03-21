from pydantic import BaseModel, Field


class TopicUnitOut(BaseModel):
    id: int
    topic_id: int
    sort_order: int
    title: str
    objective: str
    prompt_hint: str
    min_turns_to_complete: int | None
    min_avg_overall: float | None
    max_scored_turns: int | None

    model_config = {"from_attributes": True}


class RoadmapUnitItem(BaseModel):
    unit: TopicUnitOut
    status: str = Field(
        ...,
        description="locked | available | in_progress | completed",
    )


class RoadmapOut(BaseModel):
    topic_id: int
    topic_title: str
    units: list[RoadmapUnitItem]


class RoadmapProgressIn(BaseModel):
    topic_unit_id: int = Field(..., ge=1)
    action: str = Field(
        ...,
        description="complete — mark step done (MVP)",
    )


class RoadmapProgressOut(BaseModel):
    ok: bool
    topic_unit_id: int
    completed_at: str | None = None
