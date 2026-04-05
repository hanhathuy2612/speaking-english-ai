"""
HTTP endpoint: get answer suggestions for a given question (for the right-side guide panel).
Optionally save the guideline to a message when message_id is provided.
"""

import logging
import re

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
    turn_id: int | None = Field(
        None, description="Deprecated alias of message_id"
    )
    level: str | None = Field(
        None,
        max_length=20,
        description="IELTS Speaking target band (e.g. 6, 6.5); empty = default Band 6",
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

The English tutor asked the learner this question:

"{question}"

You help Vietnamese learners practise **spoken English**. Use **bilingual output**: short Vietnamese for thinking/strategy; **English** for phrases they will actually say.

**Facts:** If the question mentions real places, people, or facts, use accurate English in sections 4–5. Do not invent nonsense names or mix Vietnamese inside English sentences.

Write **exactly five sections** in this order. Each section is **one block** (a few sentences max). **Do not** use "1." / "2." numbering, markdown bullets, or "(a)(b)(c)" lists — write flowing sentences only.

**Hướng trả lời:** — 3–5 short sentences in **Vietnamese only**. Strategy only: mở bài (nhắc ý câu hỏi rất ngắn), mấy ý, độ dài khi nói (2–4 câu tiếng Anh), một hướng nếu câu hỏi mở. **Không** viết câu tiếng Anh hoàn chỉnh ở mục này (chỉ gợi ý cách làm).

**Mẫu câu:** — 1–2 câu **tiếng Việt** giải thích khung, rồi **1–2 khung tiếng Anh** trong ngoặc kép (ví dụ "Well, …" hoặc "Compared to …, I find …").

**Ngữ pháp:** — 1–2 câu **tiếng Việt**: một điểm ngữ pháp khớp loại câu hỏi.

**Từ vựng:** — **Một dòng** gồm 5–8 cụm **tiếng Anh** (phân tách bằng dấu phẩy). Không tiếng Việt trong dòng này.

**Ví dụ:** — **Một dòng**: 2–3 câu tiếng Anh hoàn chỉnh, tự nhiên khi nói, cách nhau bằng " · ". Chỉ tiếng Anh; đúng ngữ pháp và hợp lý.

Formatting (strict):
- Mỗi khối bắt đầu **đúng một dòng mới** với nhãn và dấu hai chấm ASCII: Hướng trả lời: / Mẫu câu: / Ngữ pháp: / Từ vựng: / Ví dụ:
- Giữa hai khối liền kề: **một dòng trống** (xuống dòng hai lần).
- Không dùng ** hoặc markdown khác ngoài nhãn trên."""


@router.post("/guidance")
async def get_guidance_for_question(
    body: GuidanceRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
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

    lm = LMStudioClient()
    guidance_model = (get_settings().lmstudio_guidance_model or "").strip() or None
    messages = [
        {
            "role": "user",
            "content": _GUIDANCE_PROMPT.format(
                level_block=level_block,
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
