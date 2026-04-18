"""
HTTP endpoint: get answer suggestions for a given question (for the right-side guide panel).
Optionally save the guideline to a message when message_id is provided.
"""

import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.ielts_levels import format_ielts_band, resolve_ielts_band
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.session import Session
from app.models.session_message import SessionMessage
from app.models.user import User
from app.services.lm_client import LMStudioClient

logger = logging.getLogger(__name__)

router = APIRouter()


class GuidanceRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    message_id: int | None = Field(
        None, description="If set, save the returned guideline to this message"
    )
    turn_id: int | None = Field(None, description="Deprecated alias of message_id")
    level: str | None = Field(
        None,
        max_length=20,
        description="IELTS Speaking target band (e.g. 6, 6.5); empty = default Band 6",
    )
    prior_context: str | None = Field(
        None,
        max_length=12000,
        description="Earlier learner/tutor turns so the model can align suggestions with the chat",
    )


class OptimizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    level: str | None = Field(
        None,
        max_length=20,
        description="IELTS Speaking target band (e.g. 6, 6.5); empty = topic default",
    )
    prior_context: str | None = Field(
        None,
        max_length=12000,
        description="Earlier turns so the rewrite stays consistent with the conversation",
    )


def _level_context_block(level: str | None) -> str:
    n = resolve_ielts_band(level)
    if n is None:
        return (
            "IELTS Speaking target band for this practice session: not specified — use **Band 6** "
            "as default difficulty for all English examples (clear spoken English; Part 1–3 style, not essay tone)."
        )
    disp = format_ielts_band(n)
    return (
        f"IELTS Speaking target band for this practice session: **{disp}**. "
        "Match difficulty of section 5 (example sentences) and the phrases in section 4 to this band:\n"
        "- Bands 4.0–5.0: very short, simple sentences; basic vocabulary.\n"
        "- Bands 5.5–6.0: short natural answers; simple linking (because, so, when).\n"
        "- Bands 6.5–7.0: fuller ideas, some paraphrase; still spoken style.\n"
        "- Bands 7.5–9.0: fluent, nuanced patterns; avoid rare literary words.\n"
        "Trong mục 1 (Hướng trả lời), thêm một câu tiếng Việt ngắn nhắc người học đang luyện IELTS Speaking khoảng band này."
    )


def _guidance_level_tag(level: str | None) -> str:
    n = resolve_ielts_band(level)
    if n is None:
        return "Band 6 (mặc định)"
    return f"Band {format_ielts_band(n)}"


def _prior_block_for_prompt(raw: str | None, intro_line: str) -> str:
    pc = (raw or "").strip()
    if not pc:
        return ""
    return f"{intro_line}\n{pc}\n\n"


# Split model output into one string per section (works even if the model skips blank lines between blocks).
_GUIDANCE_SECTION_LABELS = (
    "Hướng trả lời",
    "Mẫu câu",
    "Ngữ pháp",
    "Từ vựng",
    "Ví dụ",
    # English labels (older prompts / non-compliant models)
    "Answer approach",
    "Sentence patterns",
    "Grammar",
    "Vocabulary",
    "Examples",
)
_GUIDANCE_SECTION_SPLIT_RE = re.compile(
    r"(?m)(?=^\s*(?:"
    + "|".join(re.escape(lbl) for lbl in _GUIDANCE_SECTION_LABELS)
    + r")\s*:)",
)


def _split_guidance_sections(raw: str) -> list[str]:
    text = raw.strip()
    if not text:
        return []
    parts = [p.strip() for p in _GUIDANCE_SECTION_SPLIT_RE.split(text) if p.strip()]
    if len(parts) >= 2:
        return parts[:8]
    # Fallback: blank-line paragraphs, then single non-empty lines
    by_para = [s.strip() for s in re.split(r"\n\s*\n+", text) if s.strip()]
    if len(by_para) >= 2:
        return by_para[:8]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[:8] if lines else []


_GUIDANCE_PROMPT = """{level_block}

{prior_block}The English tutor asked:

"{question}"

You help Vietnamese learners practise IELTS Speaking.

Follow these rules strictly:
- Output must have EXACTLY 5 sections in this order.
- Do NOT use bullet points, numbering, or markdown.
- Each section starts with its label and ":" on a new line.
- Leave ONE blank line between sections.

Language rules:
- "Hướng trả lời" and "Ngữ pháp": Vietnamese only.
- "Mẫu câu": Vietnamese explanation + English sentences in quotes.
- "Từ vựng" and "Ví dụ": English ONLY. No Vietnamese words allowed.
- If any Vietnamese appears in "Từ vựng" or "Ví dụ", rewrite.

Content rules:
- Stay on the topic of the question.
- Keep answers short and natural for speaking.

Section details:

Hướng trả lời:
3–4 short Vietnamese sentences. Only ideas, no full English sentences.

Mẫu câu:
1 short Vietnamese explanation, then 2 English sentence frames in quotes.

Ngữ pháp:
1 short Vietnamese sentence explaining a useful grammar point.

Từ vựng:
Write 5–7 English phrases on ONE SINGLE LINE, separated by commas.

Ví dụ:
Write 2–3 natural English sentences on ONE SINGLE LINE, separated by " · ".

Output format (follow exactly):

Hướng trả lời:
...

Mẫu câu:
...

Ngữ pháp:
...

Từ vựng:
...

Ví dụ:
...
"""


_OPTIMIZE_PROMPT = """{level_block}

{prior_block}

The learner said this in **English** (spoken practice). Quote below — it is NOT Vietnamese:

"{text}"

Your job:
- Improve it for IELTS-style spoken English: fix spelling, grammar, word choice, and natural flow.
- Keep the same meaning and facts. Do not invent new story details.

**Language rules (strict):**
- "Optimized response" and "Extra idea to extend answer": **English only**.
- "Why this is better" and "Common mistakes in this sentence": **Vietnamese only** — short coaching notes for the learner.
- **Never** call the original "a Vietnamese sentence" or mix languages: do **not** add English paraphrases in parentheses after Vietnamese (no bilingual echo like "(The English...)"). Do **not** repeat the optimized English inside the Vietnamese sections.

Output exactly four labeled sections in this order. One blank line between sections. No bullet lists, no numbering.

Optimized response:
Write 1–3 natural English sentences — this is the improved version only.

Why this is better:
Write 2–3 short lines in Vietnamese only: briefly say what you improved and why. No English in this section.

Common mistakes in this sentence:
Write 2–4 short lines in Vietnamese only about problems in the learner's **original English** quote, or say it was already natural. You may quote a wrong English fragment in quotes if needed. No full English sentences and no parentheses with English translations.

Extra idea to extend answer:
Write exactly one English sentence suggesting what the learner could add next.
"""


@router.post("/guidance")
async def get_guidance_for_question(
    body: GuidanceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Given a question (e.g. from the AI tutor), return suggested ways to answer.
    If message_id (or deprecated turn_id) is provided and valid,
    save the guideline to that message.
    Returns: { "suggestions": ["I like to...", "I usually...", ...] }
    """
    question = body.question.strip()
    level_block = _level_context_block(body.level)
    lvl_tag = _guidance_level_tag(body.level)
    prior_block = _prior_block_for_prompt(
        body.prior_context,
        "Earlier in this session (learner ↔ tutor; one line per turn, oldest first). "
        "Use for continuity — do not contradict facts the learner already stated.",
    )

    lm = LMStudioClient()
    guidance_model = (get_settings().openai_guidance_model or "").strip() or None
    messages = [
        {
            "role": "user",
            "content": _GUIDANCE_PROMPT.format(
                level_block=level_block,
                prior_block=prior_block,
                question=question,
            ),
        }
    ]
    try:
        text = await lm.generate_text(
            messages,
            temperature=0.35,
            max_tokens=768,
            model=guidance_model,
        )
    except Exception as e:
        logger.warning("Guidance LM call failed: %s", e)
        suggestions = [
            f"Hướng trả lời: [Mức phiên: {lvl_tag}] Đọc lại câu hỏi, chọn 1–2 từ khóa và dùng lại trong câu đầu (paraphrase). Trả lời thẳng trước, rồi thêm một lý do hoặc ví dụ ngắn trong khoảng 20–40 giây nói; giữ tiếng Anh đúng trình độ bạn chọn.",
            'Mẫu câu: Mở tự nhiên rồi nối ý — dùng khung "Well, …" / "Actually, …" rồi "The main reason is …" hoặc "What I like about it is …"; tránh nối câu chỉ bằng "and".',
            "Ngữ pháp: Thì hiện tại đơn cho thói quen và ý kiến; quá khứ đơn nếu kể một lần; dùng would cho giả định nhẹ. Mỗi câu cần chủ ngữ + động từ rõ — đơn giản hóa nếu band thấp (4–5.5).",
            "Từ vựng: topic, main idea, reason, example, actually, compared to, I would say, to be honest",
            "Ví dụ: I'd say … because … · To be honest, I usually … · If I had to choose, I'd go for …",
        ]
    else:
        raw = text.strip()
        sections = _split_guidance_sections(raw)
        suggestions = (
            sections
            if sections
            else [
                f"Hướng trả lời: [Mức phiên: {lvl_tag}] Nói 2–3 câu tiếng Anh: câu 1 lặp ý câu hỏi, câu 2 trả lời trực tiếp, câu 3 thêm một chi tiết.",
                "Ví dụ: Sure — I'd say … · Actually, for me … · Let me put it this way …",
            ]
        )

    guideline_text = "\n".join(suggestions)
    target_message_id = body.message_id if body.message_id is not None else body.turn_id
    if target_message_id is not None:
        result = await db.execute(
            select(SessionMessage)
            .join(Session, SessionMessage.session_id == Session.id)
            .where(
                SessionMessage.id == target_message_id,
                Session.user_id == user.id,
            )
        )
        msg = result.scalar_one_or_none()
        if msg is not None:
            msg.guideline = guideline_text
            await db.commit()
        # if message not found or not owned, we still return suggestions

    return {"suggestions": suggestions}


@router.post("/guidance/optimize")
async def optimize_user_reply(
    body: OptimizeRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Optimize one learner sentence/short reply:
    - spelling / grammar / natural wording
    - clearer idea
    Returns blocks for right panel rendering.
    """
    del user  # authentication only
    text = body.text.strip()
    level_block = _level_context_block(body.level)
    lvl_tag = _guidance_level_tag(body.level)
    prior_block = _prior_block_for_prompt(
        body.prior_context,
        "Earlier in this session (one line per turn, oldest first). "
        "Use for continuity when improving the learner's reply.",
    )

    lm = LMStudioClient()
    guidance_model = (get_settings().openai_guidance_model or "").strip() or None
    messages = [
        {
            "role": "user",
            "content": _OPTIMIZE_PROMPT.format(
                level_block=level_block,
                prior_block=prior_block,
                text=text,
            ),
        }
    ]
    try:
        raw = await lm.generate_text(
            messages,
            temperature=0.3,
            max_tokens=520,
            model=guidance_model,
        )
        blocks = [s.strip() for s in re.split(r"\n\s*\n+", raw.strip()) if s.strip()]
        if not blocks:
            raise ValueError("empty optimize output")
        suggestions = blocks[:8]
    except Exception as e:
        logger.warning("Optimize LM call failed: %s", e)
        suggestions = [
            f"Mức luyện tập: {lvl_tag}",
            f"Optimized response: {text}",
            "Why this is better: Câu đã được làm mượt hơn về ngữ pháp/chọn từ nhưng vẫn giữ nguyên ý chính.",
            "Common mistakes in this sentence: Hãy kiểm tra thì động từ, mạo từ và collocation.",
            "Extra idea to extend answer: I can also add one specific example to make my answer clearer.",
        ]

    return {"suggestions": suggestions}
