from app.models.conversation import Topic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_DEFAULT_TOPICS = [
    {
        "title": "Daily Routine",
        "description": "Talk about your day, habits, and schedule.",
        "level": "A2",
    },
    {
        "title": "Travel & Vacation",
        "description": "Discuss travel experiences, destinations and plans.",
        "level": "B1",
    },
    {
        "title": "Food & Cooking",
        "description": "Talk about your favorite food, recipes and restaurants.",
        "level": "A2",
    },
    {
        "title": "Work & Career",
        "description": "Discuss jobs, career goals and workplace experiences.",
        "level": "B1",
    },
    {
        "title": "Technology & AI",
        "description": "Explore tech trends, gadgets and AI in everyday life.",
        "level": "B2",
    },
    {
        "title": "Movies & TV Shows",
        "description": "Share opinions on films, series and your favorite genres.",
        "level": "B1",
    },
    {
        "title": "Health & Wellness",
        "description": "Talk about fitness, healthy habits and mental health.",
        "level": "B1",
    },
    {
        "title": "Environment",
        "description": "Discuss climate change, sustainability and eco-friendly habits.",
        "level": "B2",
    },
    {
        "title": "Education",
        "description": "Talk about learning experiences, schools and study tips.",
        "level": "A2",
    },
    {
        "title": "Culture & Traditions",
        "description": "Share cultural backgrounds, festivals and customs.",
        "level": "B1",
    },
]


async def seed_topics(session: AsyncSession) -> None:
    """Insert default topics if none exist."""
    result = await session.execute(select(Topic).limit(1))
    if result.scalar_one_or_none() is not None:
        return
    for item in _DEFAULT_TOPICS:
        session.add(Topic(**item))
    await session.commit()
