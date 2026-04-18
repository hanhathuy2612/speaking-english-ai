"""Admin CRUD for topic / topic-unit learning packs (JSON)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.topic import Topic
from app.models.topic_unit import TopicUnit
from app.models.user import User
from app.schemas.learning_pack import LearningPackIn, LearningPackOut
from app.services.learning_pack_service import parse_learning_pack, to_learning_pack_json

router = APIRouter()


@router.get(
    "/topics/{topic_id}/learning-pack",
    responses={404: {"description": "Topic not found"}},
)
async def admin_get_topic_learning_pack(
    topic_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> LearningPackOut:
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    pack = parse_learning_pack(topic.learning_pack_json)
    if pack is None:
        pack = LearningPackOut()
    pack.source = "topic"
    return pack


@router.put(
    "/topics/{topic_id}/learning-pack",
    responses={404: {"description": "Topic not found"}},
)
async def admin_put_topic_learning_pack(
    topic_id: int,
    body: LearningPackIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> LearningPackOut:
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    topic.learning_pack_json = to_learning_pack_json(body)
    await db.commit()
    out = LearningPackOut(**body.model_dump())
    out.source = "topic"
    return out


@router.get(
    "/topic-units/{unit_id}/learning-pack",
    responses={404: {"description": "Topic unit not found"}},
)
async def admin_get_topic_unit_learning_pack(
    unit_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> LearningPackOut:
    unit = await db.get(TopicUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Topic unit not found")
    pack = parse_learning_pack(unit.learning_pack_json)
    if pack is None:
        pack = LearningPackOut()
    pack.source = "unit"
    return pack


@router.put(
    "/topic-units/{unit_id}/learning-pack",
    responses={404: {"description": "Topic unit not found"}},
)
async def admin_put_topic_unit_learning_pack(
    unit_id: int,
    body: LearningPackIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> LearningPackOut:
    unit = await db.get(TopicUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Topic unit not found")
    unit.learning_pack_json = to_learning_pack_json(body)
    await db.commit()
    out = LearningPackOut(**body.model_dump())
    out.source = "unit"
    return out
