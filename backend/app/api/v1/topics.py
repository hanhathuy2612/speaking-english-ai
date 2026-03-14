from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import Topic
from app.models.user import User
from app.schemas.topic import TopicOut

router = APIRouter()


@router.get("", response_model=list[TopicOut])
async def list_topics(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[TopicOut]:
    result = await db.execute(select(Topic))
    topics = result.scalars().all()
    return [TopicOut.model_validate(t) for t in topics]
