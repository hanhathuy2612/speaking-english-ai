from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.session import Session
from app.models.session_message import SessionMessage
from app.models.user import User
from app.schemas.conversation import MessageGuidelinePatchIn

from .conversation_audio import resolve_audio_file

router = APIRouter()


@router.patch("/messages/{message_id}/guideline")
async def patch_message_guideline(
    message_id: int,
    body: MessageGuidelinePatchIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """Save guide-panel content for a message."""
    guideline = body.guideline.strip()
    msg_q = await db.execute(
        select(SessionMessage)
        .join(Session, SessionMessage.session_id == Session.id)
        .where(SessionMessage.id == message_id, Session.user_id == user.id)
    )
    msg = msg_q.scalar_one_or_none()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
        )
    msg.guideline = guideline if guideline else None
    await db.commit()
    return {"ok": True}


@router.get("/messages/{message_id}/audio")
async def get_message_audio(
    message_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    kind: Annotated[
        Literal["user", "assistant"],
        Query(..., description="user = learner recording, assistant = TTS mp3"),
    ],
) -> FileResponse:
    """Serve stored audio for a message (same user as session owner only)."""
    msg_q = await db.execute(
        select(SessionMessage)
        .join(Session, SessionMessage.session_id == Session.id)
        .where(SessionMessage.id == message_id, Session.user_id == user.id)
    )
    msg = msg_q.scalar_one_or_none()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
        )
    if (kind == "user" and msg.role != "user") or (
        kind == "assistant" and msg.role != "assistant"
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found"
        )

    path = resolve_audio_file(msg.audio_path)
    media_type = "audio/webm" if kind == "user" else "audio/mpeg"
    return FileResponse(path, media_type=media_type)
