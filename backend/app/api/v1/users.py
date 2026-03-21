"""Current user profile and TTS preferences."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, role_slugs_for_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UpdatePreferencesRequest, UserMeResponse

router = APIRouter()


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserMeResponse:
    """Return current user profile, roles, and saved TTS preferences."""
    roles = await role_slugs_for_user(db, user.id)
    return UserMeResponse(
        user_id=user.id,
        email=user.email,
        username=user.username,
        roles=roles,
        tts_voice=user.tts_voice,
        tts_rate=user.tts_rate,
    )


@router.patch("/me", response_model=UserMeResponse)
async def update_me(
    body: UpdatePreferencesRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserMeResponse:
    """Update current user TTS preferences (voice and/or rate)."""
    values: dict = {}
    if body.tts_voice is not None:
        values["tts_voice"] = body.tts_voice
    if body.tts_rate is not None:
        values["tts_rate"] = body.tts_rate
    if values:
        await db.execute(update(User).where(User.id == user.id).values(**values))
        await db.commit()
    # Refetch to return persisted state
    result = await db.execute(select(User).where(User.id == user.id))
    updated = result.scalar_one_or_none()
    u = updated or user
    roles = await role_slugs_for_user(db, u.id)
    return UserMeResponse(
        user_id=u.id,
        email=u.email,
        username=u.username,
        roles=roles,
        tts_voice=u.tts_voice,
        tts_rate=u.tts_rate,
    )
