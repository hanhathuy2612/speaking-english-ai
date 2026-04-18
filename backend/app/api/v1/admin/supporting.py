"""Private helpers shared across admin route modules (AI JSON, sessions, drafts)."""

from __future__ import annotations

import difflib
import json
import logging
import re

from fastapi import HTTPException
from openai import OpenAIError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.models.session_message import SessionMessage
from app.core.config import get_settings
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

_LEARNING_PACK_AI_RESPONSE_JSON_SHAPE = """
Required response shape — one JSON object, snake_case keys only, this nesting (fill with real content):

{
  "vocabulary": [
    {
      "term": "phrase or word",
      "meaning": "learner-facing definition",
      "collocations": ["optional", "up to 8 strings per item"],
      "example": "sample sentence or null"
    }
  ],
  "sentence_patterns": [
    {
      "pattern": "sentence frame",
      "usage": "when or how to use it",
      "example": "full spoken-style example"
    }
  ],
  "idea_prompts": ["short question-style prompts"],
  "common_mistakes": [
    {
      "mistake": "typical error",
      "fix": "how to improve",
      "note": "optional extra or null"
    }
  ],
  "model_responses": [
    {
      "level": "optional band label or null",
      "text": "short model answer in natural spoken English"
    }
  ],
  "tips": ["short practical tips"]
}

Hard rule for vocabulary: it MUST be an array of objects (see above). Do NOT output vocabulary as one object with parallel arrays like {"term": [...], "meaning": [...]}.
"""


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
    return not is_near_duplicate(cand_title, existing_titles) and not is_near_duplicate(
        cand_objective, existing_objectives
    )


async def llm_topic_unit_draft_json(
    prompt: str,
    retry_prompt: str,
    existing_titles: list[str],
    existing_objectives: list[str],
) -> dict:
    attempts = ((prompt, 0.4), (retry_prompt, 0.35))
    n = len(attempts)
    for idx, (attempt_prompt, temp) in enumerate[tuple[str, float]](attempts):
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

{_LEARNING_PACK_AI_RESPONSE_JSON_SHAPE}

Target sizes (approximate):
- vocabulary: 8-12 items
- sentence_patterns: 3-5 items
- idea_prompts: 5-8 items
- common_mistakes: 3-5 items
- model_responses: 2-3 short spoken-style samples in English
- tips: 4-6 items

Content must match the topic; English only; suitable for IELTS Speaking practice (Parts 1–3 style).

Aliases to avoid: use "term"/"meaning" not "word"/"definition"; use "text" in model_responses not "response".

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

Use the SAME JSON shape as topic-wide packs (see below), but focus vocabulary, patterns, and examples on THIS step while staying coherent with the topic.

{_LEARNING_PACK_AI_RESPONSE_JSON_SHAPE}

Target sizes: similar to topic packs (roughly 8-12 vocabulary items, 3-5 patterns, etc.), tailored to the step.

Aliases to avoid: use "term"/"meaning" not "word"/"definition"; use "text" in model_responses not "response".

Optional extra instructions from admin:
{idea or "(none)"}
""".strip()


async def generate_learning_pack_via_llm(prompt: str) -> LearningPackIn:
    raw = ""
    try:
        settings = get_settings()
        pack_model = (settings.openai_learning_pack_model or "").strip() or None
        async with LMStudioClient() as lm:
            raw = await lm.generate_text(
                [{"role": "user", "content": prompt}],
                temperature=settings.lm_learning_pack_temperature,
                max_tokens=settings.lm_learning_pack_max_tokens,
                model=pack_model,
            )
        data = extract_json_object(raw)
        data = normalize_learning_pack_ai_dict(data)
        return LearningPackIn.model_validate(data)
    except HTTPException:
        raise
    except OpenAIError as exc:
        err_l = str(exc).lower()
        logger.warning("AI learning pack draft failed (OpenAI-compatible API): %s", exc)
        if "unload" in err_l and "model" in err_l:
            raise HTTPException(
                status_code=503,
                detail="LLM model is not loaded (e.g. LM Studio). Load the model and retry.",
            )
        raise HTTPException(
            status_code=502,
            detail="AI request failed. Check LM Studio is running and the model name in .env.",
        )
    except json.JSONDecodeError as exc:
        tail = raw[-600:] if raw else ""
        logger.warning(
            "AI learning pack JSON parse failed (chars=%s): %s | tail=%r",
            len(raw),
            exc,
            tail,
        )
        raise HTTPException(
            status_code=502,
            detail="AI returned invalid or truncated JSON. Try increasing LM_LEARNING_PACK_MAX_TOKENS or retry.",
        )
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
