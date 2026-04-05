"""
Finalize a conversation session: score turns, set ended_at, roadmap auto-complete.
Shared by WebSocket handle_stop and HTTP POST .../sessions/{id}/end.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import app.services.topic_roadmap_service as roadmap_svc
from app.models.session import Session
from app.models.session_message import SessionMessage
from app.services.scoring_service import ScoringService


async def _score_topic_string(db: AsyncSession, session: Session) -> str:
    """Same context string as ConversationHandler._topic_context_for_llm (for scoring)."""
    topic = session.topic
    if topic is None:
        return "English practice"
    parts: list[str] = [topic.title]
    u = session.topic_unit
    sid = session.id
    if u is not None:
        parts.append(f"Step: {u.title}. Learner goal: {u.objective}")
        if (u.prompt_hint or "").strip():
            parts.append(f"Tutor focus: {u.prompt_hint.strip()}")
        if sid is not None:
            n = await roadmap_svc.count_turns_in_session(db, sid)
            prog_bits: list[str] = [
                f"Learner practice turns so far in this session: {n}. "
                "(Each turn is one learner utterance plus your reply; scoring runs when the session ends.)"
            ]
            if u.min_turns_to_complete is not None:
                prog_bits.append(
                    f"The step auto-completes after at least {u.min_turns_to_complete} "
                    "such turns in this session once scores are computed (and any average-score rule below)."
                )
            if u.min_avg_overall is not None:
                prog_bits.append(
                    "When the turn count is met, average overall score for the session "
                    f"must be at least {u.min_avg_overall}."
                )
            parts.append(" ".join(prog_bits))
            parts.append(
                "Stay focused on the learner goal; keep replies concise. "
                "If the learner is close to finishing the required practice, end naturally with brief encouragement."
            )
    return " ".join(parts)


async def finalize_session_scoring(
    db: AsyncSession,
    session_id: int,
    user_id: int,
    scorer: ScoringService,
) -> dict[str, Any] | None:
    """
    Verify session owner, score unscored message pairs, set ended_at, run roadmap auto-complete.

    Returns a dict suitable for WebSocket session_scores + metadata, or None if session not found.
    Keys: turns, averages, session_feedback, roadmap_unit_completed, topic_unit_id
    """
    r = await db.execute(
        select(Session)
        .options(
            selectinload(Session.topic),
            selectinload(Session.topic_unit),
        )
        .where(
            Session.id == session_id,
            Session.user_id == user_id,
        )
    )
    session = r.scalar_one_or_none()
    if session is None:
        return None

    score_topic = await _score_topic_string(db, session)

    r_messages = await db.execute(
        select(SessionMessage)
        .where(
            SessionMessage.session_id == session_id,
            SessionMessage.kind == "chat",
        )
        .order_by(SessionMessage.index_in_session, SessionMessage.id)
    )
    chat_messages = list(r_messages.scalars().all())

    turns_out: list[dict[str, Any]] = []
    flu: list[float] = []
    voc: list[float] = []
    gram: list[float] = []
    ovl: list[float] = []
    turn_pairs: list[tuple[str, str]] = []

    pending_user: SessionMessage | None = None
    for m in chat_messages:
        if m.role == "user":
            pending_user = m
            continue
        if m.role != "assistant":
            continue
        if pending_user is None:
            continue
        if m.score_overall is None:
            sc = await scorer.score(pending_user.text, score_topic, 0.0)
            m.score_fluency = float(sc.get("fluency", 5))
            m.score_vocabulary = float(sc.get("vocabulary", 5))
            m.score_grammar = float(sc.get("grammar", 5))
            m.score_overall = float(sc.get("overall", 5))
            m.score_feedback = sc.get("feedback")
        if m.score_overall is not None:
            turns_out.append(
                {
                    "turnId": m.id,
                    "fluency": m.score_fluency or 0.0,
                    "vocabulary": m.score_vocabulary or 0.0,
                    "grammar": m.score_grammar or 0.0,
                    "overall": m.score_overall or 0.0,
                    "feedback": m.score_feedback or "",
                }
            )
            flu.append(float(m.score_fluency or 0.0))
            voc.append(float(m.score_vocabulary or 0.0))
            gram.append(float(m.score_grammar or 0.0))
            ovl.append(float(m.score_overall or 0.0))
            turn_pairs.append((pending_user.text, m.text))
        pending_user = None
    await db.commit()

    averages: dict[str, float] | None = None
    if turns_out:
        n = len(turns_out)
        averages = {
            "fluency": sum(flu) / n,
            "vocabulary": sum(voc) / n,
            "grammar": sum(gram) / n,
            "overall": sum(ovl) / n,
        }

    session_feedback = ""
    if averages is not None and turn_pairs:
        session_feedback = await scorer.session_feedback_message(
            score_topic, turn_pairs, averages
        )
    elif not turns_out:
        session_feedback = (
            "Chưa có lượt nói nào được lưu trong phiên này (mỗi lượt = bạn nói + AI trả lời xong), "
            "nên chưa có điểm hay nhận xét chi tiết. "
            "Nếu bạn đã thấy chữ nhận dạng giọng nói nhưng AI báo lỗi, hãy thử nói lại hoặc kiểm tra kết nối tới máy chủ AI."
        )

    if session_feedback.strip():
        recap_q = await db.execute(
            select(SessionMessage)
            .where(
                SessionMessage.session_id == session_id,
                SessionMessage.kind == "score_feedback",
            )
            .order_by(SessionMessage.id.desc())
        )
        recap = recap_q.scalars().first()
        if recap is None:
            max_idx = max((m.index_in_session for m in chat_messages), default=-1)
            recap = SessionMessage(
                session_id=session_id,
                index_in_session=max_idx + 1,
                role="assistant",
                kind="score_feedback",
                text=session_feedback,
            )
            db.add(recap)
        else:
            recap.text = session_feedback

    session.ended_at = datetime.now(timezone.utc)
    await db.commit()

    unit_completed = await roadmap_svc.try_auto_complete_unit_for_session(
        db, session_id, user_id
    )
    topic_unit_id: int | None = None
    if unit_completed and session.topic_unit is not None:
        topic_unit_id = session.topic_unit.id

    return {
        "turns": turns_out,
        "averages": averages,
        "session_feedback": session_feedback,
        "roadmap_unit_completed": unit_completed,
        "topic_unit_id": topic_unit_id,
    }
