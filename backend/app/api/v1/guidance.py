"""
HTTP endpoint: get answer suggestions for a given question (for the right-side guide panel).
Optionally save the guideline to a turn when turn_id is provided.
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import ConversationSession, Turn
from app.models.user import User
from app.services.lm_client import LMStudioClient

logger = logging.getLogger(__name__)

router = APIRouter()


class GuidanceRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    turn_id: int | None = Field(
        None, description="If set, save the returned guideline to this turn"
    )


_GUIDANCE_PROMPT = """The English tutor asked the learner this question:

"{question}"

You are writing a short study guide for a Vietnamese learner. Follow this order strictly:

1) **Hướng trả lời** — First, 2–4 sentences in Vietnamese: how to approach the answer (what to include, how long, tone: agree/disagree, describe, compare, etc.). Do not give full English sentences here yet.

2) **Cấu trúc câu** — One line in Vietnamese naming a useful English sentence frame or pattern (e.g. "I think … because …", "I usually + V1 …"). Optionally add one short English skeleton in quotes.

3) **Ngữ pháp** — 1–2 sentences in Vietnamese: one grammar point that fits this question (tense, modal, comparatives, etc.).

4) **Từ vựng** — A single line: 4–8 useful English words or short phrases for this topic; add very short Vietnamese glosses in parentheses where helpful.

5) **Ví dụ** — Last: 2–3 natural spoken English example answers (full sentences). Put them on ONE line, separated by " · " (middle dot). English only in this section.

Formatting rules:
- Use exactly these five section labels at the start of each block: "Hướng trả lời:", "Cấu trúc câu:", "Ngữ pháp:", "Từ vựng:", "Ví dụ:"
- Separate each section from the next with one blank line (double newline).
- No markdown bullets or numbered lists outside the labels above."""


@router.post("/guidance")
async def get_guidance_for_question(
    body: GuidanceRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Given a question (e.g. from the AI tutor), return suggested ways to answer.
    If turn_id is provided and valid (turn belongs to user's session), save the guideline to that turn.
    Returns: { "suggestions": ["I like to...", "I usually...", ...] }
    """
    question = body.question.strip()

    lm = LMStudioClient()
    messages = [{"role": "user", "content": _GUIDANCE_PROMPT.format(question=question)}]
    try:
        text = await lm.generate_text(messages, temperature=0.5, max_tokens=512)
    except Exception as e:
        logger.warning("Guidance LM call failed: %s", e)
        suggestions = [
            "Hướng trả lời: Trả lời ngắn gọn, bám ý câu hỏi; nói quan điểm hoặc kinh nghiệm của bạn.",
            "Cấu trúc câu: Dùng khung I think … because … hoặc In my opinion, … + lý do.",
            "Ngữ pháp: Giữ thì phù hợp (hiện tại / quá khứ kể chuyện); câu đủ S + V + O.",
            "Từ vựng: Ghi lại 3–5 từ khóa từ câu hỏi và thêm từ đồng nghĩa đơn giản.",
            "Ví dụ: I think that … · In my experience, … · For me, …",
        ]
    else:
        raw = text.strip()
        sections = [s.strip() for s in re.split(r"\n\s*\n+", raw) if s.strip()]
        if len(sections) < 2:
            sections = [line.strip() for line in raw.splitlines() if line.strip()]
        suggestions = (
            sections[:8]
            if sections
            else ["Thử trả lời 1–2 câu tiếng Anh ngắn, bám sát câu hỏi."]
        )

    guideline_text = "\n".join(suggestions)
    if body.turn_id is not None:
        result = await db.execute(
            select(Turn)
            .join(ConversationSession, Turn.session_id == ConversationSession.id)
            .where(Turn.id == body.turn_id, ConversationSession.user_id == user.id)
        )
        turn = result.scalar_one_or_none()
        if turn is not None:
            turn.guideline = guideline_text
            await db.commit()
        # if turn not found or not owned, we still return suggestions

    return {"suggestions": suggestions}
