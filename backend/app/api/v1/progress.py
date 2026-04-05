from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.session import Session
from app.models.session_message import SessionMessage
from app.models.topic import Topic
from app.models.user import User
from app.schemas.progress import (
    DailyMinutes,
    ProgressSummary,
    RecentSession,
    ScoreAvg,
    SessionsPage,
)

router = APIRouter()


@router.get("/summary", response_model=ProgressSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProgressSummary:
    # Total sessions
    sess_q = await db.execute(
        select(func.count())
        .select_from(Session)
        .where(Session.user_id == user.id)
    )
    total_sessions = sess_q.scalar() or 0

    # Total turns (message-based first, legacy fallback)
    turn_q = await db.execute(
        select(func.count())
        .select_from(SessionMessage)
        .join(Session, SessionMessage.session_id == Session.id)
        .where(
            Session.user_id == user.id,
            SessionMessage.kind == "chat",
            SessionMessage.role == "user",
        )
    )
    total_turns = int(turn_q.scalar() or 0)

    # Avg scores
    score_q = await db.execute(
        select(
            func.avg(SessionMessage.score_fluency),
            func.avg(SessionMessage.score_vocabulary),
            func.avg(SessionMessage.score_grammar),
            func.avg(SessionMessage.score_overall),
        )
        .join(Session, SessionMessage.session_id == Session.id)
        .where(
            Session.user_id == user.id,
            SessionMessage.kind == "chat",
            SessionMessage.role == "assistant",
            SessionMessage.score_overall.is_not(None),
        )
    )
    row = score_q.one_or_none()
    avg_scores: ScoreAvg | None = None
    if row and row[0] is not None:
        avg_scores = ScoreAvg(
            fluency=round(row[0], 2),
            vocabulary=round(row[1], 2),
            grammar=round(row[2], 2),
            overall=round(row[3], 2),
        )

    # Daily minutes (last 30 days)
    since = datetime.now(timezone.utc) - timedelta(days=30)
    sessions_q = await db.execute(
        select(Session)
        .where(
            Session.user_id == user.id,
            Session.started_at >= since,
        )
        .order_by(Session.started_at)
    )
    sessions = sessions_q.scalars().all()

    daily: dict[str, float] = {}
    for s in sessions:
        day = s.started_at.strftime("%Y-%m-%d")
        end = s.ended_at or s.started_at
        minutes = (end - s.started_at).total_seconds() / 60
        daily[day] = daily.get(day, 0) + minutes

    daily_minutes = [
        DailyMinutes(date=d, minutes=round(m, 1)) for d, m in sorted(daily.items())
    ]

    return ProgressSummary(
        total_sessions=total_sessions,
        total_turns=total_turns,
        avg_scores=avg_scores,
        daily_minutes=daily_minutes,
    )


@router.get("/sessions", response_model=SessionsPage)
async def list_sessions(
    page: int = 1,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionsPage:
    """Paginated list of recent sessions. page is 1-based; limit default 10."""
    if page < 1:
        page = 1
    if limit < 1 or limit > 50:
        limit = 10
    offset = (page - 1) * limit

    total_q = await db.execute(
        select(func.count())
        .select_from(Session)
        .where(Session.user_id == user.id)
    )
    total = total_q.scalar() or 0

    recent_q = await db.execute(
        select(Session)
        .options(selectinload(Session.topic))
        .where(Session.user_id == user.id)
        .order_by(Session.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    recent_sessions_db = recent_q.scalars().all()

    recent_out = []
    for s in recent_sessions_db:
        turns_q = await db.execute(
            select(func.count())
            .select_from(SessionMessage)
            .where(
                SessionMessage.session_id == s.id,
                SessionMessage.kind == "chat",
                SessionMessage.role == "user",
            )
        )
        tc = int(turns_q.scalar() or 0)
        avg_q = await db.execute(
            select(func.avg(SessionMessage.score_overall)).where(
                SessionMessage.session_id == s.id,
                SessionMessage.kind == "chat",
                SessionMessage.role == "assistant",
                SessionMessage.score_overall.is_not(None),
            )
        )
        avg_val = avg_q.scalar()
        recent_out.append(
            RecentSession(
                id=s.id,
                topic_id=s.topic_id,
                topic_title=s.topic.title if s.topic else "Unknown",
                started_at=s.started_at,
                ended_at=s.ended_at,
                turn_count=tc,
                avg_overall=round(avg_val, 2) if avg_val is not None else None,
            )
        )

    return SessionsPage(items=recent_out, total=total)


@router.delete("/sessions/{session_id}", response_model=None)
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    session = await db.get(Session, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
