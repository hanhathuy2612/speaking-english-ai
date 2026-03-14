from pydantic import BaseModel


class TopicOut(BaseModel):
    id: int
    title: str
    description: str | None
    level: str | None

    model_config = {"from_attributes": True}
