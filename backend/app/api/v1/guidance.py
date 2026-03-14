"""
HTTP endpoint: get answer suggestions for a given question (for the right-side guide panel).
Optionally save the guideline to a turn when turn_id is provided.
"""

import logging

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
    turn_id: int | None = Field(None, description="If set, save the returned guideline to this turn")


_GUIDANCE_PROMPT = """The English tutor asked the learner this question:

"{question}"

Give 2–4 very short example answers or phrases the learner could say (one per line, in English only). No numbering, no explanation. Keep each line under 15 words."""


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
        text = await lm.generate_text(messages, temperature=0.5, max_tokens=200)
    except Exception as e:
        logger.warning("Guidance LM call failed: %s", e)
        suggestions = [
            "Reply in 1–2 sentences using words from the question.",
            "You can start with: I think that… / In my experience… / For me…",
        ]
    else:
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        suggestions = lines[:6] if lines else ["Try answering in one or two short sentences."]

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
