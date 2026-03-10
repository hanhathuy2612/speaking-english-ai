from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import ConversationSession, Turn, TurnScore, Topic
from app.models.user import User

router = APIRouter(prefix="/progress", tags=["progress"])


class ScoreAvg(BaseModel):
    fluency: float
    vocabulary: float
    grammar: float
    overall: float


class DailyMinutes(BaseModel):
    date: str
    minutes: float


class RecentSession(BaseModel):
    id: int
    topic_title: str
    started_at: datetime
    ended_at: datetime | None
    turn_count: int
    avg_overall: float | None


class ProgressSummary(BaseModel):
    total_sessions: int
    total_turns: int
    avg_scores: ScoreAvg | None
    daily_minutes: list[DailyMinutes]
    recent_sessions: list[RecentSession]


@router.get("/summary", response_model=ProgressSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProgressSummary:
    # Total sessions
    sess_q = await db.execute(
        select(func.count()).select_from(ConversationSession).where(ConversationSession.user_id == user.id)
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

    # Daily minutes (last 30 days) – approximated from session duration
    since = datetime.utcnow() - timedelta(days=30)
    sessions_q = await db.execute(
        select(ConversationSession)
        .where(ConversationSession.user_id == user.id, ConversationSession.started_at >= since)
        .order_by(ConversationSession.started_at)
    )
    sessions = sessions_q.scalars().all()

    daily: dict[str, float] = {}
    for s in sessions:
        day = s.started_at.strftime("%Y-%m-%d")
        end = s.ended_at or s.started_at
        minutes = (end - s.started_at).total_seconds() / 60
        daily[day] = daily.get(day, 0) + minutes

    daily_minutes = [DailyMinutes(date=d, minutes=round(m, 1)) for d, m in sorted(daily.items())]

    # Recent sessions
    recent_q = await db.execute(
        select(ConversationSession)
        .where(ConversationSession.user_id == user.id)
        .order_by(ConversationSession.started_at.desc())
        .limit(10)
    )
    recent_sessions_db = recent_q.scalars().all()

    recent_out: list[RecentSession] = []
    for s in recent_sessions_db:
        topic_q = await db.execute(select(Topic).where(Topic.id == s.topic_id))
        topic = topic_q.scalar_one_or_none()

        turns_q = await db.execute(select(func.count()).select_from(Turn).where(Turn.session_id == s.id))
        tc = turns_q.scalar() or 0

        avg_q = await db.execute(
            select(func.avg(TurnScore.overall))
            .join(Turn, TurnScore.turn_id == Turn.id)
            .where(Turn.session_id == s.id)
        )
        avg_overall = avg_q.scalar()

        recent_out.append(
            RecentSession(
                id=s.id,
                topic_title=topic.title if topic else "Unknown",
                started_at=s.started_at,
                ended_at=s.ended_at,
                turn_count=tc,
                avg_overall=round(avg_overall, 2) if avg_overall else None,
            )
        )

    return ProgressSummary(
        total_sessions=total_sessions,
        total_turns=total_turns,
        avg_scores=avg_scores,
        daily_minutes=daily_minutes,
        recent_sessions=recent_out,
    )
