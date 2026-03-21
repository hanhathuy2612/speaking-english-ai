from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import Topic, TopicUnit
from app.models.user import User
from app.schemas.roadmap import (
    RoadmapOut,
    RoadmapProgressIn,
    RoadmapProgressOut,
    RoadmapUnitItem,
    TopicUnitOut,
)
from app.schemas.topic import TopicIn, TopicOut, TopicUpdate
import app.services.topic_roadmap_service as roadmap_svc

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


@router.get("/{topic_id:int}/roadmap", response_model=RoadmapOut)
async def get_topic_roadmap(
    topic_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RoadmapOut:
    r = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = r.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    units, statuses, _ = await roadmap_svc.get_roadmap_payload(db, topic_id, user.id)
    items = [
        RoadmapUnitItem(unit=TopicUnitOut.model_validate(u), status=s)
        for u, s in zip(units, statuses, strict=True)
    ]
    return RoadmapOut(topic_id=topic.id, topic_title=topic.title, units=items)


@router.post("/{topic_id:int}/roadmap/progress", response_model=RoadmapProgressOut)
async def post_roadmap_progress(
    topic_id: int,
    payload: RoadmapProgressIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RoadmapProgressOut:
    r = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = r.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if payload.action != "complete":
        raise HTTPException(status_code=400, detail="Unsupported action")
    unit = await db.get(TopicUnit, payload.topic_unit_id)
    if not unit or unit.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Topic unit not found for this topic")
    row = await roadmap_svc.mark_unit_complete(db, user.id, payload.topic_unit_id)
    if row is None:
        raise HTTPException(status_code=403, detail="Step is locked or invalid")
    ca = row.completed_at
    return RoadmapProgressOut(
        ok=True,
        topic_unit_id=payload.topic_unit_id,
        completed_at=ca.isoformat() if ca else None,
    )


@router.patch("/{topic_id:int}", response_model=TopicOut)
async def update_topic(
    topic_id: int,
    payload: TopicUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> TopicOut:
    """Update an existing topic (title, description, level)."""
    result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if payload.title is not None:
        title = payload.title.strip()
        if title:
            existing = await db.execute(select(Topic).where(Topic.title == title, Topic.id != topic_id))
            if existing.scalar_one_or_none() is not None:
                raise HTTPException(status_code=400, detail="A topic with this title already exists")
            topic.title = title
    if payload.description is not None:
        topic.description = payload.description.strip() or None
    if payload.level is not None:
        topic.level = payload.level.strip() or None
    await db.commit()
    await db.refresh(topic)
    return TopicOut.model_validate(topic)
