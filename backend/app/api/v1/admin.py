"""Admin-only: user management, topic unit CRUD, and AI draft helpers."""

from backend.app.models.topic_unit import TopicUnit
from app.models.topic_unit import TopicUnit
import difflib
import json
import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.session import Session
from app.models.session_message import SessionMessage
from app.models.topic import Topic
from app.models.topic_unit import TopicUnit
from app.models.role import ROLE_ADMIN, Role, UserRole
from app.models.user import User
from app.schemas.admin import (
    AITopicDraftIn,
    AITopicDraftOut,
    AITopicUnitDraftIn,
    AITopicUnitDraftOut,
    AdminTopicSessionOut,
    AdminTopicSessionsPage,
    AdminUserListOut,
    AdminUserOut,
    AdminUserPatch,
    TopicUnitCreateIn,
    TopicUnitUpdateIn,
)
from app.schemas.learning_pack import LearningPackIn, LearningPackOut
from app.schemas.roadmap import TopicUnitOut
from app.services.lm_client import LMStudioClient
from app.services.learning_pack_service import (
    parse_learning_pack,
    to_learning_pack_json,
)

router = APIRouter()
logger = logging.getLogger(__name__)
ADMIN_USERS_MAX_LIMIT = 500


def _extract_json_object(text: str) -> dict:
    s = text.strip()
    if not s:
        raise ValueError("Empty AI response")
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        raise ValueError("No JSON object found in AI response")
    obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("AI response JSON root must be an object")
    return obj


def _normalize_similarity_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _is_near_duplicate(candidate: str, existing_values: list[str]) -> bool:
    c = _normalize_similarity_text(candidate)
    if not c:
        return True
    for ex in existing_values:
        e = _normalize_similarity_text(ex)
        if not e:
            continue
        if c == e:
            return True
        # Tight enough to catch paraphrased duplicates in short step titles/objectives.
        if difflib.SequenceMatcher(None, c, e).ratio() >= 0.88:
            return True
    return False


def _coerce_json_int(v: object) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def _coerce_json_float(v: object) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _collect_existing_unit_strings(
    existing_units: list[TopicUnit],
) -> tuple[list[str], list[str], str]:
    existing_titles = [
        u.title.strip() for u in existing_units if (u.title or "").strip()
    ]
    existing_objectives = [
        u.objective.strip() for u in existing_units if (u.objective or "").strip()
    ]
    existing_lines = [
        f"- #{idx + 1}: title='{u.title.strip()}', objective='{u.objective.strip()}'"
        for idx, u in enumerate[TopicUnit](existing_units)
        if (u.title or "").strip() and (u.objective or "").strip()
    ]
    existing_block = (
        "\n".join(existing_lines)
        if existing_lines
        else "- (no existing steps yet for this topic)"
    )
    return existing_titles, existing_objectives, existing_block


def _build_topic_unit_draft_prompts(
    topic: Topic, existing_block: str, idea: str
) -> tuple[str, str]:
    prompt = f"""
Generate ONE guided roadmap step for IELTS speaking topic "{topic.title}".
Topic description: "{(topic.description or '').strip()}"
Topic level: "{(topic.level or '').strip()}"
Existing steps in this topic:
{existing_block}

Return STRICT JSON only, no markdown:
{{
  "title": "step title",
  "objective": "clear learner objective",
  "prompt_hint": "short instruction for AI tutor behavior",
  "min_turns_to_complete": 3,
  "min_avg_overall": 6.0,
  "max_scored_turns": 10
}}

Rules:
- objective is learner-facing, simple and actionable.
- prompt_hint is for tutor AI to guide conversation for this step.
- The new step MUST be semantically different from existing steps above.
- Do NOT repeat an existing title wording/pattern.
- Do NOT repeat the same learner objective angle as previous steps.
- min_turns_to_complete should be 2..8.
- min_avg_overall should be null or number 4.0..8.0.
- max_scored_turns should be null or integer 6..20.
- Keep values realistic and compact.

Admin extra idea (optional):
{idea or "No extra idea"}
""".strip()
    retry_prompt = (
        prompt
        + "\n\nImportant retry constraint: previous attempt was too similar to existing steps. "
        "Generate a clearly different step focus (new sub-skill / new speaking scenario)."
    )
    return prompt, retry_prompt


def _unit_draft_is_distinct(
    maybe: dict, existing_titles: list[str], existing_objectives: list[str]
) -> bool:
    cand_title = str(maybe.get("title", "")).strip()
    cand_objective = str(maybe.get("objective", "")).strip()
    if not cand_title or not cand_objective:
        return False
    return not _is_near_duplicate(
        cand_title, existing_titles
    ) and not _is_near_duplicate(cand_objective, existing_objectives)


async def _llm_topic_unit_draft_json(
    prompt: str,
    retry_prompt: str,
    existing_titles: list[str],
    existing_objectives: list[str],
) -> dict:
    attempts = ((prompt, 0.4), (retry_prompt, 0.35))
    n = len(attempts)
    for idx, (attempt_prompt, temp) in enumerate(attempts):
        try:
            async with LMStudioClient() as lm:
                raw = await lm.generate_text(
                    [{"role": "user", "content": attempt_prompt}],
                    temperature=temp,
                    max_tokens=320,
                )
            maybe = _extract_json_object(raw)
        except Exception as exc:
            logger.warning("AI topic unit draft failed (attempt %d): %s", idx + 1, exc)
            if idx == n - 1:
                raise HTTPException(
                    status_code=502, detail="AI could not generate step draft"
                )
            continue
        if _unit_draft_is_distinct(
            maybe, existing_titles, existing_objectives
        ) or idx == n - 1:
            return maybe
    raise HTTPException(status_code=502, detail="AI could not generate step draft")


def _topic_unit_draft_data_to_out(data: dict) -> AITopicUnitDraftOut:
    title = str(data.get("title", "")).strip()
    objective = str(data.get("objective", "")).strip()
    prompt_hint = str(data.get("prompt_hint", "")).strip()
    if not title or not objective or not prompt_hint:
        raise HTTPException(status_code=502, detail="AI returned invalid step draft")
    min_turns = _coerce_json_int(data.get("min_turns_to_complete"))
    min_turns = min(8, max(1, min_turns)) if min_turns is not None else None
    min_avg = _coerce_json_float(data.get("min_avg_overall"))
    min_avg = min(10.0, max(0.0, min_avg)) if min_avg is not None else None
    max_scored = _coerce_json_int(data.get("max_scored_turns"))
    max_scored = min(30, max(1, max_scored)) if max_scored is not None else None
    return AITopicUnitDraftOut(
        title=title[:255],
        objective=objective,
        prompt_hint=prompt_hint,
        min_turns_to_complete=min_turns,
        min_avg_overall=min_avg,
        max_scored_turns=max_scored,
    )


async def _count_distinct_admin_users(db: AsyncSession) -> int:
    q = await db.execute(
        select(func.count(func.distinct(UserRole.user_id)))
        .select_from(UserRole)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.name == ROLE_ADMIN)
    )
    return int(q.scalar() or 0)


async def _user_has_admin(db: AsyncSession, user_id: int) -> bool:
    q = await db.execute(
        select(UserRole.user_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user_id, Role.name == ROLE_ADMIN)
        .limit(1)
    )
    return q.scalar_one_or_none() is not None


async def _admin_topic_session_items_from_rows(
    db: AsyncSession, rows: list[Session]
) -> list[AdminTopicSessionOut]:
    items: list[AdminTopicSessionOut] = []
    for s in rows:
        turns_q = await db.execute(
            select(func.count())
            .select_from(SessionMessage)
            .where(
                SessionMessage.session_id == s.id,
                SessionMessage.kind == "chat",
                SessionMessage.role == "user",
            )
        )
        tc = int(turns_q.scalar() or 0)
        avg_q = await db.execute(
            select(func.avg(SessionMessage.score_overall)).where(
                SessionMessage.session_id == s.id,
                SessionMessage.kind == "chat",
                SessionMessage.role == "assistant",
                SessionMessage.score_overall.is_not(None),
            )
        )
        avg_val = avg_q.scalar()
        u = s.user
        unit = s.topic_unit
        items.append(
            AdminTopicSessionOut(
                id=s.id,
                topic_id=s.topic_id,
                topic_title=s.topic.title if s.topic else "Unknown",
                user_id=s.user_id,
                user_email=u.email if u else "",
                user_username=u.username if u else "",
                topic_unit_title=unit.title if unit else None,
                started_at=s.started_at,
                ended_at=s.ended_at,
                turn_count=tc,
                avg_overall=round(avg_val, 2) if avg_val is not None else None,
            )
        )
    return items


@router.get("/users", response_model=AdminUserListOut)
async def admin_list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=ADMIN_USERS_MAX_LIMIT)] = 20,
) -> AdminUserListOut:
    total_q = await db.execute(select(func.count()).select_from(User))
    total = int(total_q.scalar() or 0)
    offset = (page - 1) * limit
    r = await db.execute(
        select(User)
        .options(selectinload(User.role_memberships).selectinload(UserRole.role))
        .order_by(User.id)
        .offset(offset)
        .limit(limit)
    )
    users = r.scalars().unique().all()
    items = []
    for u in users:
        roles = sorted({m.role.name for m in u.role_memberships})
        items.append(
            AdminUserOut(
                id=u.id,
                email=u.email,
                username=u.username,
                is_active=u.is_active,
                roles=roles,
                created_at=u.created_at.isoformat(),
            )
        )
    return AdminUserListOut(items=items, total=total)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def admin_patch_user(
    user_id: int,
    body: AdminUserPatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> AdminUserOut:
    r = await db.execute(
        select(User)
        .options(selectinload(User.role_memberships).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    target = r.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if body.role_slugs is not None:
        slugs = sorted(set(body.role_slugs))
        if not slugs:
            raise HTTPException(
                status_code=400, detail="role_slugs must include at least one role"
            )
        had_admin = await _user_has_admin(db, user_id)
        will_have_admin = ROLE_ADMIN in slugs
        if had_admin and not will_have_admin:
            if await _count_distinct_admin_users(db) <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot remove the last admin user",
                )
        roles_result = await db.execute(select(Role).where(Role.name.in_(slugs)))
        found = {role.name: role for role in roles_result.scalars().all()}
        missing = [s for s in slugs if s not in found]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown role slugs: {', '.join(missing)}",
            )
        await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        for slug in slugs:
            db.add(UserRole(user_id=user_id, role_id=found[slug].id))
        await db.flush()

    if body.is_active is not None:
        if not body.is_active and user_id == admin.id:
            raise HTTPException(
                status_code=400, detail="You cannot deactivate your own account here"
            )
        target.is_active = body.is_active

    await db.commit()
    await db.refresh(target)
    r2 = await db.execute(
        select(User)
        .options(selectinload(User.role_memberships).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    target = r2.scalar_one()
    roles = sorted({m.role.name for m in target.role_memberships})
    return AdminUserOut(
        id=target.id,
        email=target.email,
        username=target.username,
        is_active=target.is_active,
        roles=roles,
        created_at=target.created_at.isoformat(),
    )


@router.post(
    "/topics/{topic_id}/units",
    response_model=TopicUnitOut,
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


@router.get("/topics/{topic_id}/learning-pack", response_model=LearningPackOut)
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


@router.put("/topics/{topic_id}/learning-pack", response_model=LearningPackOut)
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


@router.get("/topic-units/{unit_id}/learning-pack", response_model=LearningPackOut)
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


@router.put("/topic-units/{unit_id}/learning-pack", response_model=LearningPackOut)
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


@router.patch(
    "/topics/{topic_id}/units/{unit_id}",
    response_model=TopicUnitOut,
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


@router.delete("/topics/{topic_id}/units/{unit_id}", status_code=204)
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
    status_code=204,
    responses={404: {"description": "Topic not found"}},
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


@router.get(
    "/topics/{topic_id}/sessions",
    responses={404: {"description": "Topic not found"}},
)
async def admin_list_topic_sessions(
    topic_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    topic_unit_id: Annotated[
        int | None,
        Query(
            description="If set, only sessions started for this roadmap step (topic unit)."
        ),
    ] = None,
) -> AdminTopicSessionsPage:
    """Paginated sessions for this topic across all users."""
    t = await db.get(Topic, topic_id)
    if not t:
        raise HTTPException(status_code=404, detail="Topic not found")

    conds = [Session.topic_id == topic_id]
    if topic_unit_id is not None:
        unit = await db.get(TopicUnit, topic_unit_id)
        if not unit or unit.topic_id != topic_id:
            raise HTTPException(status_code=404, detail="Topic unit not found")
        conds.append(Session.topic_unit_id == topic_unit_id)

    offset = (page - 1) * limit

    total_q = await db.execute(select(func.count()).select_from(Session).where(*conds))
    total = int(total_q.scalar() or 0)

    recent_q = await db.execute(
        select(Session)
        .options(
            selectinload(Session.topic),
            selectinload(Session.user),
            selectinload(Session.topic_unit),
        )
        .where(*conds)
        .order_by(Session.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = recent_q.scalars().all()
    items = await _admin_topic_session_items_from_rows(db, list(rows))

    return AdminTopicSessionsPage(items=items, total=total)


@router.get(
    "/sessions",
    responses={404: {"description": "User or topic not found"}},
)
async def admin_list_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    user_id: Annotated[
        int | None, Query(ge=1, description="Filter by session owner user id.")
    ] = None,
    topic_id: Annotated[
        int | None, Query(ge=1, description="Filter by topic id.")
    ] = None,
) -> AdminTopicSessionsPage:
    """Paginated sessions across users; optional filters by user and/or topic."""
    conds: list = []
    if user_id is not None:
        u = await db.get(User, user_id)
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        conds.append(Session.user_id == user_id)
    if topic_id is not None:
        t = await db.get(Topic, topic_id)
        if not t:
            raise HTTPException(status_code=404, detail="Topic not found")
        conds.append(Session.topic_id == topic_id)

    offset = (page - 1) * limit

    count_stmt = select(func.count()).select_from(Session)
    data_stmt = (
        select(Session)
        .options(
            selectinload(Session.topic),
            selectinload(Session.user),
            selectinload(Session.topic_unit),
        )
        .order_by(Session.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if conds:
        count_stmt = count_stmt.where(*conds)
        data_stmt = data_stmt.where(*conds)

    total_q = await db.execute(count_stmt)
    total = int(total_q.scalar() or 0)

    recent_q = await db.execute(data_stmt)
    rows = recent_q.scalars().all()
    items = await _admin_topic_session_items_from_rows(db, list(rows))

    return AdminTopicSessionsPage(items=items, total=total)


@router.delete(
    "/topics/{topic_id}/sessions/{session_id}",
    status_code=204,
    responses={404: {"description": "Session not found"}},
)
async def admin_delete_topic_session(
    topic_id: int,
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    sess = await db.get(Session, session_id)
    if not sess or sess.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(sess)
    await db.commit()


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
        data = _extract_json_object(raw)
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
    existing_units = list[TopicUnit](units_q.scalars().all())
    existing_titles, existing_objectives, existing_block = _collect_existing_unit_strings(
        existing_units
    )
    idea = (body.idea or "").strip()
    prompt, retry_prompt = _build_topic_unit_draft_prompts(topic, existing_block, idea)
    data = await _llm_topic_unit_draft_json(
        prompt, retry_prompt, existing_titles, existing_objectives
    )
    return _topic_unit_draft_data_to_out(data)
