"""Admin topic units (roadmap steps) and topic deletion."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.topic import Topic
from app.models.topic_unit import TopicUnit
from app.models.user import User
from app.schemas.admin import TopicUnitCreateIn, TopicUnitUpdateIn
from app.schemas.roadmap import TopicUnitOut

router = APIRouter()


@router.post(
    "/topics/{topic_id}/units",
    responses={404: {"description": "Topic not found"}},
    status_code=201,
)
async def admin_create_topic_unit(
    topic_id: int,
    body: TopicUnitCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> TopicUnitOut:
    t = await db.get(Topic, topic_id)
    if not t:
        raise HTTPException(status_code=404, detail="Topic not found")
    unit = TopicUnit(
        topic_id=topic_id,
        sort_order=body.sort_order,
        title=body.title.strip(),
        objective=body.objective.strip(),
        prompt_hint=body.prompt_hint.strip(),
        min_turns_to_complete=body.min_turns_to_complete,
        min_avg_overall=body.min_avg_overall,
        max_scored_turns=body.max_scored_turns,
    )
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    return TopicUnitOut.model_validate(unit)


@router.patch(
    "/topics/{topic_id}/units/{unit_id}",
    responses={404: {"description": "Topic unit not found"}},
)
async def admin_update_topic_unit(
    topic_id: int,
    unit_id: int,
    body: TopicUnitUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> TopicUnitOut:
    unit = await db.get(TopicUnit, unit_id)
    if not unit or unit.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Topic unit not found")
    if body.sort_order is not None:
        unit.sort_order = body.sort_order
    if body.title is not None:
        unit.title = body.title.strip()
    if body.objective is not None:
        unit.objective = body.objective.strip()
    if body.prompt_hint is not None:
        unit.prompt_hint = body.prompt_hint.strip()
    if body.min_turns_to_complete is not None:
        unit.min_turns_to_complete = body.min_turns_to_complete
    if body.min_avg_overall is not None:
        unit.min_avg_overall = body.min_avg_overall
    patch_data = body.model_dump(exclude_unset=True)
    if "max_scored_turns" in patch_data:
        unit.max_scored_turns = patch_data["max_scored_turns"]
    await db.commit()
    await db.refresh(unit)
    return TopicUnitOut.model_validate(unit)


@router.delete(
    "/topics/{topic_id}/units/{unit_id}",
    status_code=204,
    responses={404: {"description": "Topic unit not found"}},
)
async def admin_delete_topic_unit(
    topic_id: int,
    unit_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    unit = await db.get(TopicUnit, unit_id)
    if not unit or unit.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Topic unit not found")
    await db.delete(unit)
    await db.commit()


@router.delete(
    "/topics/{topic_id}",
    responses={404: {"description": "Topic not found"}},
    status_code=204,
)
async def admin_delete_topic(
    topic_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    await db.delete(topic)
    await db.commit()
