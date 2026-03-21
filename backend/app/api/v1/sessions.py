from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import ConversationSession, Turn
from app.models.user import User
import app.services.topic_roadmap_service as roadmap_svc
from app.schemas.conversation import (
    SessionDetailOut,
    SessionOut,
    TopicUnitSummarySnippet,
    TurnOut,
    UnitStepSummaryOut,
)

router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SessionOut]:
    if limit < 1 or limit > 100:
        limit = 20
    result = await db.execute(
        select(ConversationSession)
        .options(selectinload(ConversationSession.topic))
        .where(ConversationSession.user_id == user.id)
        .order_by(ConversationSession.started_at.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()
    out = []
    for s in sessions:
        count_result = await db.execute(select(func.count()).select_from(Turn).where(Turn.session_id == s.id))
        turn_count = count_result.scalar() or 0
        out.append(
            SessionOut(
                id=s.id,
                topic_id=s.topic_id,
                topic_title=s.topic.title if s.topic else "Unknown",
                started_at=s.started_at,
                ended_at=s.ended_at,
                turn_count=turn_count,
            )
        )
    return out


@router.get(
    "/sessions/{session_id}/unit-step-summary",
    response_model=UnitStepSummaryOut,
)
async def get_unit_step_summary(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UnitStepSummaryOut:
    """Averages and roadmap thresholds for one session (e.g. after unit auto-complete)."""
    result = await db.execute(
        select(ConversationSession)
        .options(
            selectinload(ConversationSession.topic),
            selectinload(ConversationSession.topic_unit),
        )
        .where(ConversationSession.id == session_id, ConversationSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    cnt, avg_o, avg_f, avg_v, avg_g = await roadmap_svc.scored_turn_averages_for_session(
        db, session_id
    )
    unit = session.topic_unit
    thresholds_met = False
    unit_out: TopicUnitSummarySnippet | None = None
    min_turns = min_avg = max_turns = None
    if unit is not None:
        min_turns = unit.min_turns_to_complete
        min_avg = unit.min_avg_overall
        max_turns = unit.max_scored_turns
        thresholds_met = roadmap_svc.unit_auto_complete_thresholds_met(unit, cnt, avg_o)
        unit_out = TopicUnitSummarySnippet(
            id=unit.id,
            title=unit.title,
            objective=unit.objective,
        )

    return UnitStepSummaryOut(
        session_id=session.id,
        topic_id=session.topic_id,
        topic_title=session.topic.title if session.topic else "Unknown",
        topic_unit=unit_out,
        scored_turns=cnt,
        avg_fluency=avg_f,
        avg_vocabulary=avg_v,
        avg_grammar=avg_g,
        avg_overall=avg_o,
        min_turns_to_complete=min_turns,
        min_avg_overall=min_avg,
        max_scored_turns=max_turns,
        thresholds_met=thresholds_met,
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionDetailOut:
    result = await db.execute(
        select(ConversationSession)
        .options(
            selectinload(ConversationSession.topic),
            selectinload(ConversationSession.turns).selectinload(Turn.score),
        )
        .where(ConversationSession.id == session_id, ConversationSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    turns_out = []
    for t in sorted(session.turns, key=lambda x: x.index_in_session):
        score = t.score
        turns_out.append(
            TurnOut(
                index_in_session=t.index_in_session,
                user_text=t.user_text,
                assistant_text=t.assistant_text,
                guideline=t.guideline,
                fluency=score.fluency if score else None,
                vocabulary=score.vocabulary if score else None,
                grammar=score.grammar if score else None,
                overall=score.overall if score else None,
                feedback=score.feedback if score else None,
                created_at=t.created_at,
            )
        )

    return SessionDetailOut(
        id=session.id,
        topic_id=session.topic_id,
        topic_title=session.topic.title if session.topic else "Unknown",
        started_at=session.started_at,
        ended_at=session.ended_at,
        turns=turns_out,
    )
