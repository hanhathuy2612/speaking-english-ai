from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import Topic
from app.models.user import User

router = APIRouter(prefix="/topics", tags=["topics"])


class TopicOut(BaseModel):
    id: int
    title: str
    description: str | None
    level: str | None

    model_config = {"from_attributes": True}


_DEFAULT_TOPICS = [
    Topic(title="Daily Routine", description="Talk about your day, habits, and schedule.", level="A2"),
    Topic(title="Travel & Vacation", description="Discuss travel experiences, destinations and plans.", level="B1"),
    Topic(title="Food & Cooking", description="Talk about your favorite food, recipes and restaurants.", level="A2"),
    Topic(title="Work & Career", description="Discuss jobs, career goals and workplace experiences.", level="B1"),
    Topic(title="Technology & AI", description="Explore tech trends, gadgets and AI in everyday life.", level="B2"),
    Topic(title="Movies & TV Shows", description="Share opinions on films, series and your favorite genres.", level="B1"),
    Topic(title="Health & Wellness", description="Talk about fitness, healthy habits and mental health.", level="B1"),
    Topic(title="Environment", description="Discuss climate change, sustainability and eco-friendly habits.", level="B2"),
    Topic(title="Education", description="Talk about learning experiences, schools and study tips.", level="A2"),
    Topic(title="Culture & Traditions", description="Share cultural backgrounds, festivals and customs.", level="B1"),
]


@router.get("", response_model=list[TopicOut])
async def list_topics(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Topic]:
    result = await db.execute(select(Topic))
    topics = result.scalars().all()

    # Seed default topics if none exist
    if not topics:
        db.add_all(_DEFAULT_TOPICS)
        await db.commit()
        result = await db.execute(select(Topic))
        topics = result.scalars().all()

    return list(topics)
