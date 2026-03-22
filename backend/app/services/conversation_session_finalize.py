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
from app.models.conversation import ConversationSession, Turn, TurnScore
from app.services.scoring_service import ScoringService


async def _score_topic_string(db: AsyncSession, session: ConversationSession) -> str:
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
    Verify session owner, score turns missing TurnScore, set ended_at, run roadmap auto-complete.

    Returns a dict suitable for WebSocket session_scores + metadata, or None if session not found.
    Keys: turns, averages, session_feedback, roadmap_unit_completed, topic_unit_id
    """
    r = await db.execute(
        select(ConversationSession)
        .options(
            selectinload(ConversationSession.topic),
            selectinload(ConversationSession.topic_unit),
        )
        .where(
            ConversationSession.id == session_id,
            ConversationSession.user_id == user_id,
        )
    )
    session = r.scalar_one_or_none()
    if session is None:
        return None

    score_topic = await _score_topic_string(db, session)

    r_turns = await db.execute(
        select(Turn)
        .where(Turn.session_id == session_id)
        .order_by(Turn.index_in_session)
        .options(selectinload(Turn.score))
    )
    turns = list(r_turns.scalars().all())

    for t in turns:
        if t.score is not None:
            continue
        sc = await scorer.score(t.user_text, score_topic, 0.0)
        db.add(
            TurnScore(
                turn_id=t.id,
                fluency=sc.get("fluency", 5),
                vocabulary=sc.get("vocabulary", 5),
                grammar=sc.get("grammar", 5),
                overall=sc.get("overall", 5),
                feedback=sc.get("feedback"),
            )
        )
    await db.commit()

    r2 = await db.execute(
        select(Turn)
        .where(Turn.session_id == session_id)
        .order_by(Turn.index_in_session)
        .options(selectinload(Turn.score))
    )
    all_with_scores = [t for t in r2.scalars().all() if t.score is not None]

    turns_out: list[dict[str, Any]] = []
    flu: list[float] = []
    voc: list[float] = []
    gram: list[float] = []
    ovl: list[float] = []
    for t in all_with_scores:
        ts = t.score
        if ts is None:
            continue
        turns_out.append(
            {
                "turnId": t.id,
                "fluency": ts.fluency,
                "vocabulary": ts.vocabulary,
                "grammar": ts.grammar,
                "overall": ts.overall,
                "feedback": ts.feedback or "",
            }
        )
        flu.append(ts.fluency)
        voc.append(ts.vocabulary)
        gram.append(ts.grammar)
        ovl.append(ts.overall)

    averages: dict[str, float] | None = None
    if turns_out:
        n = len(turns_out)
        averages = {
            "fluency": sum(flu) / n,
            "vocabulary": sum(voc) / n,
            "grammar": sum(gram) / n,
            "overall": sum(ovl) / n,
        }

    turn_pairs = [(t.user_text, t.assistant_text) for t in all_with_scores]
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
