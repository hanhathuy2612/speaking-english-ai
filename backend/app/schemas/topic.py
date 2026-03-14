from pydantic import BaseModel, Field


class TopicOut(BaseModel):
    id: int
    title: str
    description: str | None
    level: str | None

    model_config = {"from_attributes": True}


class TopicIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    level: str | None = Field(None, max_length=20)
