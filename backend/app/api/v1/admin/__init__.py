"""Admin API: user management, topic units, learning packs, sessions, AI drafts."""

from fastapi import APIRouter

from app.api.v1.admin import ai, learning_packs, sessions, topics, users

router = APIRouter()
router.include_router(users.router)
router.include_router(learning_packs.router)
router.include_router(topics.router)
router.include_router(sessions.router)
router.include_router(ai.router)

__all__ = ["router"]
