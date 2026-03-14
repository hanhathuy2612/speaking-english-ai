from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import Topic
from app.models.user import User
from app.schemas.topic import TopicIn, TopicOut

router = APIRouter()


@router.get("", response_model=list[TopicOut])
async def list_topics(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[TopicOut]:
    result = await db.execute(select(Topic).order_by(Topic.id))
    topics = result.scalars().all()
    return [TopicOut.model_validate(t) for t in topics]


@router.post("", response_model=TopicOut, status_code=201)
async def create_topic(
    payload: TopicIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> TopicOut:
    """Create a new topic (saved to database)."""
    existing = await db.execute(
        select(Topic).where(Topic.title == payload.title.strip())
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="A topic with this title already exists")
    topic = Topic(
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        level=payload.level.strip() if payload.level else None,
    )
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return TopicOut.model_validate(topic)
