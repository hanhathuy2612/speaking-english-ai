from fastapi import APIRouter

from app.api.v1 import auth, conversation, progress, sessions, topics

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(topics.router, prefix="/topics", tags=["topics"])
router.include_router(progress.router, prefix="/progress", tags=["progress"])
router.include_router(sessions.router)
router.include_router(conversation.router, tags=["conversation"])
