"""Private helpers shared across admin route modules (AI JSON, sessions, drafts)."""

from __future__ import annotations

import difflib
import json
import logging
import re

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.models.session_message import SessionMessage
from app.models.topic import Topic
from app.models.topic_unit import TopicUnit
from app.schemas.admin import (
    AdminTopicSessionOut,
    AITopicUnitDraftOut,
)
from app.schemas.learning_pack import LearningPackIn
from app.services.lm_client import LMStudioClient
from app.services.learning_pack_service import normalize_learning_pack_ai_dict

logger = logging.getLogger(__name__)


def extract_json_object(text: str) -> dict:
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


def normalize_similarity_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_near_duplicate(candidate: str, existing_values: list[str]) -> bool:
    c = normalize_similarity_text(candidate)
    if not c:
        return True
    for ex in existing_values:
        e = normalize_similarity_text(ex)
        if not e:
            continue
        if c == e:
            return True
        if difflib.SequenceMatcher(None, c, e).ratio() >= 0.88:
            return True
    return False


def coerce_json_int(v: object) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def coerce_json_float(v: object) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def collect_existing_unit_strings(
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
        for idx, u in enumerate(existing_units)
        if (u.title or "").strip() and (u.objective or "").strip()
    ]
    existing_block = (
        "\n".join(existing_lines)
        if existing_lines
        else "- (no existing steps yet for this topic)"
    )
    return existing_titles, existing_objectives, existing_block


def build_topic_unit_draft_prompts(
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


def unit_draft_is_distinct(
    maybe: dict, existing_titles: list[str], existing_objectives: list[str]
) -> bool:
    cand_title = str(maybe.get("title", "")).strip()
    cand_objective = str(maybe.get("objective", "")).strip()
    if not cand_title or not cand_objective:
        return False
    return not is_near_duplicate(
        cand_title, existing_titles
    ) and not is_near_duplicate(cand_objective, existing_objectives)


async def llm_topic_unit_draft_json(
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
            maybe = extract_json_object(raw)
        except Exception as exc:
            logger.warning("AI topic unit draft failed (attempt %d): %s", idx + 1, exc)
            if idx == n - 1:
                raise HTTPException(
                    status_code=502, detail="AI could not generate step draft"
                )
            continue
        if (
            unit_draft_is_distinct(maybe, existing_titles, existing_objectives)
            or idx == n - 1
        ):
            return maybe
    raise HTTPException(status_code=502, detail="AI could not generate step draft")


def topic_unit_draft_data_to_out(data: dict) -> AITopicUnitDraftOut:
    title = str(data.get("title", "")).strip()
    objective = str(data.get("objective", "")).strip()
    prompt_hint = str(data.get("prompt_hint", "")).strip()
    if not title or not objective or not prompt_hint:
        raise HTTPException(status_code=502, detail="AI returned invalid step draft")
    min_turns = coerce_json_int(data.get("min_turns_to_complete"))
    min_turns = min(8, max(1, min_turns)) if min_turns is not None else None
    min_avg = coerce_json_float(data.get("min_avg_overall"))
    min_avg = min(10.0, max(0.0, min_avg)) if min_avg is not None else None
    max_scored = coerce_json_int(data.get("max_scored_turns"))
    max_scored = min(30, max(1, max_scored)) if max_scored is not None else None
    return AITopicUnitDraftOut(
        title=title[:255],
        objective=objective,
        prompt_hint=prompt_hint,
        min_turns_to_complete=min_turns,
        min_avg_overall=min_avg,
        max_scored_turns=max_scored,
    )


def learning_pack_ai_prompt_topic(topic: Topic, idea: str) -> str:
    return f"""You are an IELTS Speaking study-materials author.

Topic title: "{topic.title}"
Topic description: "{(topic.description or '').strip()}"
Topic level (optional): "{(topic.level or '').strip()}"

Produce a learning pack as ONE JSON object only. No markdown, no code fences, no commentary before or after the JSON.

Exact top-level keys (snake_case):
- vocabulary: array of objects with keys: term (string), meaning (string), collocations (array of strings, max 8 per item), example (string or null)
- sentence_patterns: array of objects with keys: pattern, usage, example (all strings)
- idea_prompts: array of short strings
- common_mistakes: array of objects with keys: mistake, fix (strings), note (string or null)
- model_responses: array of objects with keys: level (string or null), text (string)
- tips: array of short strings

Target sizes (approximate):
- vocabulary: 8-12 items
- sentence_patterns: 3-5 items
- idea_prompts: 5-8 items
- common_mistakes: 3-5 items
- model_responses: 2-3 short spoken-style samples in English
- tips: 4-6 items

Content must match the topic; English only; suitable for IELTS Speaking practice (Parts 1–3 style).

Strict key names (do not substitute): vocabulary uses "term" and "meaning" (not "word"/"definition"); model_responses uses "text" (not "response"); every sentence_patterns object must have "pattern", "usage", and "example"; every common_mistakes object must have "mistake" and "fix".

Optional extra instructions from admin:
{idea or "(none)"}
""".strip()


def learning_pack_ai_prompt_unit(topic: Topic, unit: TopicUnit, idea: str) -> str:
    return f"""You are an IELTS Speaking study-materials author.

Topic title: "{topic.title}"
Topic description: "{(topic.description or '').strip()}"
Topic level: "{(topic.level or '').strip()}"

This pack targets ONE guided step within the topic:
- Step title: "{unit.title}"
- Step objective: "{unit.objective.strip()}"

Produce a learning pack as ONE JSON object only. No markdown, no code fences, no commentary before or after the JSON.

Use the SAME key structure as a topic-wide pack, but focus vocabulary, patterns, and examples on THIS step while staying coherent with the topic.

Exact top-level keys (snake_case):
- vocabulary, sentence_patterns, idea_prompts, common_mistakes, model_responses, tips
(same nested shapes as described for topic-wide packs.)

Target sizes: similar to topic packs (roughly 8-12 vocabulary items, 3-5 patterns, etc.), tailored to the step.

Strict key names (do not substitute): vocabulary uses "term" and "meaning" (not "word"/"definition"); model_responses uses "text" (not "response"); every sentence_patterns object must have "pattern", "usage", and "example"; every common_mistakes object must have "mistake" and "fix".

Optional extra instructions from admin:
{idea or "(none)"}
""".strip()


async def generate_learning_pack_via_llm(prompt: str) -> LearningPackIn:
    try:
        async with LMStudioClient() as lm:
            raw = await lm.generate_text(
                [{"role": "user", "content": prompt}],
                temperature=0.35,
                max_tokens=4500,
            )
        data = extract_json_object(raw)
        data = normalize_learning_pack_ai_dict(data)
        return LearningPackIn.model_validate(data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("AI learning pack draft failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="AI could not generate a valid learning pack",
        )


async def count_distinct_admin_users(db: AsyncSession) -> int:
    from app.models.role import ROLE_ADMIN, Role, UserRole

    q = await db.execute(
        select(func.count(func.distinct(UserRole.user_id)))
        .select_from(UserRole)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.name == ROLE_ADMIN)
    )
    return int(q.scalar() or 0)


async def user_has_admin(db: AsyncSession, user_id: int) -> bool:
    from app.models.role import ROLE_ADMIN, Role, UserRole

    q = await db.execute(
        select(UserRole.user_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user_id, Role.name == ROLE_ADMIN)
        .limit(1)
    )
    return q.scalar_one_or_none() is not None


async def admin_topic_session_items_from_rows(
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
