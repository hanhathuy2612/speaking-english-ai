from fastapi import APIRouter

from app.api.v1 import admin, auth, conversation, guidance, progress, sessions, topics, tts, users

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
router.include_router(topics.router, prefix="/topics", tags=["topics"])
router.include_router(progress.router, prefix="/progress", tags=["progress"])
router.include_router(sessions.router)
router.include_router(tts.router)
router.include_router(conversation.router, tags=["conversation"])
router.include_router(guidance.router, prefix="/conversation", tags=["conversation"])
