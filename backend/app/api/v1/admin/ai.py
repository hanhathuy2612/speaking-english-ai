"""Admin AI draft endpoints (topics, units, learning packs)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.supporting import (
    build_topic_unit_draft_prompts,
    collect_existing_unit_strings,
    extract_json_object,
    generate_learning_pack_via_llm,
    learning_pack_ai_prompt_topic,
    learning_pack_ai_prompt_unit,
    llm_topic_unit_draft_json,
    topic_unit_draft_data_to_out,
)
from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.topic import Topic
from app.models.topic_unit import TopicUnit
from app.models.user import User
from app.schemas.admin import (
    AILearningPackDraftIn,
    AITopicDraftIn,
    AITopicDraftOut,
    AITopicUnitDraftIn,
    AITopicUnitDraftOut,
)
from app.schemas.learning_pack import LearningPackIn
from app.services.lm_client import LMStudioClient

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/ai/topics/{topic_id}/learning-pack-draft",
    responses={
        502: {"description": "AI could not generate a valid learning pack"},
        404: {"description": "Topic not found"},
    },
)
async def admin_ai_topic_learning_pack_draft(
    topic_id: int,
    body: AILearningPackDraftIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> LearningPackIn:
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    idea = (body.idea or "").strip()
    prompt = learning_pack_ai_prompt_topic(topic, idea)
    return await generate_learning_pack_via_llm(prompt)


@router.post(
    "/ai/topic-units/{unit_id}/learning-pack-draft",
    responses={
        502: {"description": "AI could not generate a valid learning pack"},
        404: {"description": "Topic or unit not found"},
    },
)
async def admin_ai_topic_unit_learning_pack_draft(
    unit_id: int,
    body: AILearningPackDraftIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> LearningPackIn:
    unit = await db.get(TopicUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Topic unit not found")
    topic = await db.get(Topic, unit.topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    idea = (body.idea or "").strip()
    prompt = learning_pack_ai_prompt_unit(topic, unit, idea)
    return await generate_learning_pack_via_llm(prompt)


@router.post(
    "/ai/topic-draft",
    responses={502: {"description": "AI could not generate topic draft"}},
)
async def admin_ai_topic_draft(
    body: AITopicDraftIn,
    _admin: Annotated[User, Depends(get_current_admin)],
) -> AITopicDraftOut:
    idea = (body.idea or "").strip()
    prompt = f"""
Generate ONE IELTS speaking practice topic draft.
Return STRICT JSON only, no markdown, no code fence:
{{
  "title": "short topic title",
  "description": "1-2 short sentences for learners",
  "level": "optional IELTS band like 6 or 6.5, or null"
}}

Rules:
- Title: concise, practical, natural spoken-English topic.
- Description: friendly, specific practice scope.
- level can be null if not needed.
- Keep output compact and valid JSON.

Idea from admin (optional):
{idea or "General IELTS speaking practice topic"}
""".strip()
    try:
        async with LMStudioClient() as lm:
            raw = await lm.generate_text(
                [{"role": "user", "content": prompt}],
                temperature=0.45,
                max_tokens=220,
            )
        data = extract_json_object(raw)
    except Exception as exc:
        logger.warning("AI topic draft failed: %s", exc)
        raise HTTPException(status_code=502, detail="AI could not generate topic draft")
    title = str(data.get("title", "")).strip()
    desc_val = data.get("description")
    level_val = data.get("level")
    description = None if desc_val is None else str(desc_val).strip() or None
    level = None if level_val is None else str(level_val).strip() or None
    if not title:
        raise HTTPException(status_code=502, detail="AI returned invalid topic draft")
    return AITopicDraftOut(title=title[:255], description=description, level=level)


@router.post(
    "/ai/topics/{topic_id}/unit-draft",
    responses={
        502: {"description": "AI could not generate step draft"},
        404: {"description": "Topic not found"},
    },
)
async def admin_ai_topic_unit_draft(
    topic_id: int,
    body: AITopicUnitDraftIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> AITopicUnitDraftOut:
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    units_q = await db.execute(
        select(TopicUnit)
        .where(TopicUnit.topic_id == topic_id)
        .order_by(TopicUnit.sort_order.asc(), TopicUnit.id.asc())
    )
    existing_units = list(units_q.scalars().all())
    existing_titles, existing_objectives, existing_block = (
        collect_existing_unit_strings(existing_units)
    )
    idea = (body.idea or "").strip()
    prompt, retry_prompt = build_topic_unit_draft_prompts(topic, existing_block, idea)
    data = await llm_topic_unit_draft_json(
        prompt, retry_prompt, existing_titles, existing_objectives
    )
    return topic_unit_draft_data_to_out(data)
