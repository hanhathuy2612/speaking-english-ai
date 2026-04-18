"""Admin session listings and per-topic session deletion."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.admin.supporting import admin_topic_session_items_from_rows
from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.session import Session
from app.models.topic import Topic
from app.models.topic_unit import TopicUnit
from app.models.user import User
from app.schemas.admin import AdminTopicSessionsPage

router = APIRouter()


@router.get(
    "/topics/{topic_id}/sessions",
    responses={404: {"description": "Topic not found"}},
)
async def admin_list_topic_sessions(
    topic_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    topic_unit_id: Annotated[
        int | None,
        Query(
            description="If set, only sessions started for this roadmap step (topic unit)."
        ),
    ] = None,
) -> AdminTopicSessionsPage:
    """Paginated sessions for this topic across all users."""
    t = await db.get(Topic, topic_id)
    if not t:
        raise HTTPException(status_code=404, detail="Topic not found")

    conds = [Session.topic_id == topic_id]
    if topic_unit_id is not None:
        unit = await db.get(TopicUnit, topic_unit_id)
        if not unit or unit.topic_id != topic_id:
            raise HTTPException(status_code=404, detail="Topic unit not found")
        conds.append(Session.topic_unit_id == topic_unit_id)

    offset = (page - 1) * limit

    total_q = await db.execute(select(func.count()).select_from(Session).where(*conds))
    total = int(total_q.scalar() or 0)

    recent_q = await db.execute(
        select(Session)
        .options(
            selectinload(Session.topic),
            selectinload(Session.user),
            selectinload(Session.topic_unit),
        )
        .where(*conds)
        .order_by(Session.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = recent_q.scalars().all()
    items = await admin_topic_session_items_from_rows(db, list(rows))

    return AdminTopicSessionsPage(items=items, total=total)


@router.get(
    "/sessions",
    responses={404: {"description": "User or topic not found"}},
)
async def admin_list_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    user_id: Annotated[
        int | None, Query(ge=1, description="Filter by session owner user id.")
    ] = None,
    topic_id: Annotated[
        int | None, Query(ge=1, description="Filter by topic id.")
    ] = None,
) -> AdminTopicSessionsPage:
    """Paginated sessions across users; optional filters by user and/or topic."""
    conds: list = []
    if user_id is not None:
        u = await db.get(User, user_id)
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        conds.append(Session.user_id == user_id)
    if topic_id is not None:
        t = await db.get(Topic, topic_id)
        if not t:
            raise HTTPException(status_code=404, detail="Topic not found")
        conds.append(Session.topic_id == topic_id)

    offset = (page - 1) * limit

    count_stmt = select(func.count()).select_from(Session)
    data_stmt = (
        select(Session)
        .options(
            selectinload(Session.topic),
            selectinload(Session.user),
            selectinload(Session.topic_unit),
        )
        .order_by(Session.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if conds:
        count_stmt = count_stmt.where(*conds)
        data_stmt = data_stmt.where(*conds)

    total_q = await db.execute(count_stmt)
    total = int(total_q.scalar() or 0)

    recent_q = await db.execute(data_stmt)
    rows = recent_q.scalars().all()
    items = await admin_topic_session_items_from_rows(db, list(rows))

    return AdminTopicSessionsPage(items=items, total=total)


@router.delete(
    "/topics/{topic_id}/sessions/{session_id}",
    status_code=204,
    responses={404: {"description": "Session not found"}},
)
async def admin_delete_topic_session(
    topic_id: int,
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    sess = await db.get(Session, session_id)
    if not sess or sess.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(sess)
    await db.commit()
