from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import ConversationSession, Turn, TurnScore, Topic
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
        .select_from(ConversationSession)
        .where(ConversationSession.user_id == user.id)
    )
    total_sessions = sess_q.scalar() or 0

    # Total turns
    turn_q = await db.execute(
        select(func.count())
        .select_from(Turn)
        .join(ConversationSession, Turn.session_id == ConversationSession.id)
        .where(ConversationSession.user_id == user.id)
    )
    total_turns = turn_q.scalar() or 0

    # Avg scores
    score_q = await db.execute(
        select(
            func.avg(TurnScore.fluency),
            func.avg(TurnScore.vocabulary),
            func.avg(TurnScore.grammar),
            func.avg(TurnScore.overall),
        )
        .join(Turn, TurnScore.turn_id == Turn.id)
        .join(ConversationSession, Turn.session_id == ConversationSession.id)
        .where(ConversationSession.user_id == user.id)
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
        select(ConversationSession)
        .where(
            ConversationSession.user_id == user.id,
            ConversationSession.started_at >= since,
        )
        .order_by(ConversationSession.started_at)
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
        .select_from(ConversationSession)
        .where(ConversationSession.user_id == user.id)
    )
    total = total_q.scalar() or 0

    recent_q = await db.execute(
        select(ConversationSession)
        .options(selectinload(ConversationSession.topic))
        .where(ConversationSession.user_id == user.id)
        .order_by(ConversationSession.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    recent_sessions_db = recent_q.scalars().all()

    recent_out = []
    for s in recent_sessions_db:
        turns_q = await db.execute(
            select(func.count()).select_from(Turn).where(Turn.session_id == s.id)
        )
        tc = turns_q.scalar() or 0
        avg_q = await db.execute(
            select(func.avg(TurnScore.overall))
            .join(Turn, TurnScore.turn_id == Turn.id)
            .where(Turn.session_id == s.id)
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
    session = await db.get(ConversationSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
