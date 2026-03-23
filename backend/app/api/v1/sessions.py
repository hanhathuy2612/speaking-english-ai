import asyncio
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import ConversationSession, SessionMessage, Topic, TopicUnit
from app.models.user import User
from app.services.conversation_session_finalize import finalize_session_scoring
from app.services.lm_client import LMStudioClient
from app.services.scoring_service import ScoringService
import app.services.topic_roadmap_service as roadmap_svc
from app.schemas.conversation import (
    SessionCreateIn,
    SessionCreatedOut,
    SessionDetailOut,
    SessionOut,
    TopicUnitSummarySnippet,
    TurnGuidelinePatchIn,
    TurnOut,
    UnitStepSummaryOut,
)

router = APIRouter(prefix="/conversation", tags=["conversation"])

_AUDIO_ROOT = Path("audio")


def _resolved_audio_file(path_str: str | None) -> Path:
    if not path_str or not str(path_str).strip():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No audio for this turn")
    p = Path(path_str)
    if not p.is_absolute():
        p = Path.cwd() / p
    try:
        p = p.resolve()
    except OSError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    try:
        p.relative_to(_AUDIO_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid audio path")
    if not p.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    return p


def get_scoring_service() -> ScoringService:
    return ScoringService(LMStudioClient())


@router.post("/sessions", response_model=SessionCreatedOut)
async def create_session(
    body: SessionCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionCreatedOut:
    """
    Create an empty conversation session, then open /conversation?sessionId=… for WebSocket resume.
    Matches roadmap / unit rules used by the WebSocket start handler.
    """
    if body.topic_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid topic_id")

    topic_q = await db.execute(select(Topic).where(Topic.id == body.topic_id))
    topic = topic_q.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    topic_unit_id: int | None = None
    if body.topic_unit_id is not None:
        uid = body.topic_unit_id
        if uid <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid topic_unit_id")
        unit = await db.get(TopicUnit, uid)
        if not unit or unit.topic_id != body.topic_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic unit not found")
        if not await roadmap_svc.is_unit_unlocked_for_user(db, user.id, unit):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This step is locked")
        await roadmap_svc.ensure_unit_started(db, user.id, uid)
        topic_unit_id = uid

    sess = ConversationSession(
        user_id=user.id,
        topic_id=body.topic_id,
        topic_unit_id=topic_unit_id,
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)

    return SessionCreatedOut(
        id=sess.id,
        topic_id=sess.topic_id,
        topic_unit_id=sess.topic_unit_id,
        topic_level=topic.level,
    )


@router.get("/sessions/{session_id}/opening-audio")
async def get_session_opening_audio(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    """Serve stored TTS for the session opening line (not a Turn row)."""
    sess_q = await db.execute(
        select(ConversationSession).where(
            ConversationSession.id == session_id,
            ConversationSession.user_id == user.id,
        )
    )
    session = sess_q.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    path = _resolved_audio_file(session.opening_audio_path)
    return FileResponse(path, media_type="audio/mpeg")


@router.patch("/turns/{turn_id}/guideline")
async def patch_turn_guideline(
    turn_id: int,
    body: TurnGuidelinePatchIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    """Save guide-panel content for a turn (e.g. after turn id is known on the client)."""
    g = body.guideline.strip()
    msg_q = await db.execute(
        select(SessionMessage)
        .join(ConversationSession, SessionMessage.session_id == ConversationSession.id)
        .where(SessionMessage.id == turn_id, ConversationSession.user_id == user.id)
    )
    msg = msg_q.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turn not found")
    msg.guideline = g if g else None
    await db.commit()
    return {"ok": True}


@router.get("/turns/{turn_id}/audio")
async def get_turn_audio(
    turn_id: int,
    kind: Literal["user", "assistant"] = Query(..., description="user = learner recording, assistant = TTS mp3"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    """Serve stored audio for a turn (same user as session owner only)."""
    msg_q = await db.execute(
        select(SessionMessage)
        .join(ConversationSession, SessionMessage.session_id == ConversationSession.id)
        .where(SessionMessage.id == turn_id, ConversationSession.user_id == user.id)
    )
    msg = msg_q.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turn not found")
    if (kind == "user" and msg.role != "user") or (kind == "assistant" and msg.role != "assistant"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    path = _resolved_audio_file(msg.audio_path)
    media = "audio/webm" if kind == "user" else "audio/mpeg"
    return FileResponse(path, media_type=media)


@router.post("/sessions/{session_id}/end")
async def end_session_and_score(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    scorer: ScoringService = Depends(get_scoring_service),
) -> dict[str, Any]:
    """
    End session: score any unscored turns, set ended_at, roadmap auto-complete.
    Use when the WebSocket is already closed (e.g. client disconnected first).
    """
    out = await finalize_session_scoring(db, session_id, user.id, scorer)
    # In practice, /end can race with the final WS turn commit on slower environments.
    # Retry briefly before returning "no turns saved" feedback.
    if (
        out is not None
        and not out.get("turns")
        and not out.get("averages")
    ):
        for delay_s in (0.35, 0.65):
            await asyncio.sleep(delay_s)
            out = await finalize_session_scoring(db, session_id, user.id, scorer)
            if out is None:
                break
            if out.get("turns") or out.get("averages"):
                break
    if out is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return out


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
        count_result = await db.execute(
            select(func.count())
            .select_from(SessionMessage)
            .where(
                SessionMessage.session_id == s.id,
                SessionMessage.kind == "chat",
                SessionMessage.role == "user",
            )
        )
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
        )
        .where(ConversationSession.id == session_id, ConversationSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    msg_q = await db.execute(
        select(SessionMessage)
        .where(
            SessionMessage.session_id == session.id,
            SessionMessage.kind == "chat",
        )
        .order_by(SessionMessage.index_in_session, SessionMessage.id)
    )
    messages = list(msg_q.scalars().all())
    turns_out = []
    pending_user: SessionMessage | None = None
    t_idx = 0
    for m in messages:
        if m.role == "user":
            pending_user = m
            continue
        if m.role != "assistant" or pending_user is None:
            continue
        turns_out.append(
            TurnOut(
                turn_id=m.id,
                index_in_session=t_idx,
                user_text=pending_user.text,
                assistant_text=m.text,
                has_user_audio=bool(
                    pending_user.audio_path and str(pending_user.audio_path).strip()
                ),
                has_assistant_audio=bool(m.audio_path and str(m.audio_path).strip()),
                guideline=m.guideline,
                fluency=m.score_fluency,
                vocabulary=m.score_vocabulary,
                grammar=m.score_grammar,
                overall=m.score_overall,
                feedback=m.score_feedback,
                created_at=m.created_at,
            )
        )
        t_idx += 1
        pending_user = None

    recap_q = await db.execute(
        select(SessionMessage)
        .where(
            SessionMessage.session_id == session.id,
            SessionMessage.kind == "score_feedback",
        )
        .order_by(SessionMessage.id.desc())
    )
    recap = recap_q.scalars().first()

    return SessionDetailOut(
        id=session.id,
        topic_id=session.topic_id,
        topic_title=session.topic.title if session.topic else "Unknown",
        started_at=session.started_at,
        ended_at=session.ended_at,
        opening_message=session.opening_message,
        has_opening_audio=bool(
            session.opening_audio_path and str(session.opening_audio_path).strip()
        ),
        turns=turns_out,
        session_feedback=recap.text if recap is not None else None,
    )
