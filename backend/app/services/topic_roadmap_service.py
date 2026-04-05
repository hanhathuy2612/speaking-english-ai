"""Topic unit roadmap: unlock rules, progress rows, auto-complete from session scores."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.session import Session
from app.models.session_message import SessionMessage
from app.models.topic_unit import TopicUnit
from app.models.user_topic_unit_progress import UserTopicUnitProgress

RoadmapUnitStatus = str  # locked | available | in_progress | completed


def unit_auto_complete_thresholds_met(
    unit: TopicUnit, scored_turns: int, avg_overall: float | None
) -> bool:
    min_turns = unit.min_turns_to_complete
    min_avg = unit.min_avg_overall
    turns_ok = min_turns is None or scored_turns >= min_turns
    avg_ok = min_avg is None or (
        avg_overall is not None and float(avg_overall) >= float(min_avg)
    )
    return turns_ok and avg_ok


async def count_scored_turns_in_session(db: AsyncSession, session_id: int) -> int:
    r = await db.execute(
        select(func.count())
        .select_from(SessionMessage)
        .where(
            SessionMessage.session_id == session_id,
            SessionMessage.kind == "chat",
            SessionMessage.role == "assistant",
            SessionMessage.score_overall.is_not(None),
        )
    )
    return int(r.scalar() or 0)


async def count_turns_in_session(db: AsyncSession, session_id: int) -> int:
    """Practice turns (user+assistant rows) in the session, scored or not."""
    r = await db.execute(
        select(func.count())
        .select_from(SessionMessage)
        .where(
            SessionMessage.session_id == session_id,
            SessionMessage.kind == "chat",
            SessionMessage.role == "user",
        )
    )
    return int(r.scalar() or 0)


async def scored_turn_averages_for_session(
    db: AsyncSession, session_id: int
) -> tuple[int, float | None, float | None, float | None, float | None]:
    """Count of scored turns and avg overall / fluency / vocabulary / grammar."""
    r = await db.execute(
        select(
            func.count(SessionMessage.id),
            func.avg(SessionMessage.score_overall),
            func.avg(SessionMessage.score_fluency),
            func.avg(SessionMessage.score_vocabulary),
            func.avg(SessionMessage.score_grammar),
        )
        .where(
            SessionMessage.session_id == session_id,
            SessionMessage.kind == "chat",
            SessionMessage.role == "assistant",
            SessionMessage.score_overall.is_not(None),
        )
    )
    row = r.one()
    cnt = int(row[0] or 0)
    return (
        cnt,
        float(row[1]) if row[1] is not None else None,
        float(row[2]) if row[2] is not None else None,
        float(row[3]) if row[3] is not None else None,
        float(row[4]) if row[4] is not None else None,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def load_ordered_units(db: AsyncSession, topic_id: int) -> list[TopicUnit]:
    r = await db.execute(
        select(TopicUnit)
        .where(TopicUnit.topic_id == topic_id)
        .order_by(TopicUnit.sort_order)
    )
    return list(r.scalars().all())


async def load_progress_map(
    db: AsyncSession, user_id: int, unit_ids: list[int]
) -> dict[int, UserTopicUnitProgress]:
    if not unit_ids:
        return {}
    r = await db.execute(
        select(UserTopicUnitProgress).where(
            UserTopicUnitProgress.user_id == user_id,
            UserTopicUnitProgress.topic_unit_id.in_(unit_ids),
        )
    )
    rows = r.scalars().all()
    return {p.topic_unit_id: p for p in rows}


def compute_unit_status(
    unit: TopicUnit,
    prev_unit_completed: bool,
    progress: UserTopicUnitProgress | None,
) -> RoadmapUnitStatus:
    if progress and progress.completed_at is not None:
        return "completed"
    if not prev_unit_completed:
        return "locked"
    if progress and progress.started_at is not None:
        return "in_progress"
    return "available"


async def get_roadmap_payload(
    db: AsyncSession, topic_id: int, user_id: int
) -> tuple[list[TopicUnit], list[RoadmapUnitStatus], dict[int, UserTopicUnitProgress]]:
    units = await load_ordered_units(db, topic_id)
    if not units:
        return [], [], {}
    p_map = await load_progress_map(db, user_id, [u.id for u in units])
    statuses: list[RoadmapUnitStatus] = []
    for i, u in enumerate(units):
        prev_done = i == 0 or (
            p_map.get(units[i - 1].id) is not None
            and p_map[units[i - 1].id].completed_at is not None
        )
        statuses.append(compute_unit_status(u, prev_done, p_map.get(u.id)))
    return units, statuses, p_map


async def is_unit_unlocked_for_user(
    db: AsyncSession, user_id: int, unit: TopicUnit
) -> bool:
    units = await load_ordered_units(db, unit.topic_id)
    if not units or unit.id not in {x.id for x in units}:
        return False
    idx = next(i for i, x in enumerate(units) if x.id == unit.id)
    if idx == 0:
        return True
    p_map = await load_progress_map(db, user_id, [units[idx - 1].id])
    prev = p_map.get(units[idx - 1].id)
    return prev is not None and prev.completed_at is not None


async def ensure_unit_started(
    db: AsyncSession, user_id: int, unit_id: int
) -> UserTopicUnitProgress:
    r = await db.execute(
        select(UserTopicUnitProgress).where(
            UserTopicUnitProgress.user_id == user_id,
            UserTopicUnitProgress.topic_unit_id == unit_id,
        )
    )
    row = r.scalar_one_or_none()
    now = _utc_now()
    if row is None:
        row = UserTopicUnitProgress(
            user_id=user_id, topic_unit_id=unit_id, started_at=now, completed_at=None
        )
        db.add(row)
    elif row.completed_at is None and row.started_at is None:
        row.started_at = now
    # If already completed, leave progress row unchanged (user may replay the step).
    await db.commit()
    await db.refresh(row)
    return row


async def mark_unit_complete(
    db: AsyncSession, user_id: int, unit_id: int
) -> UserTopicUnitProgress | None:
    unit = await db.get(TopicUnit, unit_id)
    if not unit:
        return None
    if not await is_unit_unlocked_for_user(db, user_id, unit):
        return None
    r = await db.execute(
        select(UserTopicUnitProgress).where(
            UserTopicUnitProgress.user_id == user_id,
            UserTopicUnitProgress.topic_unit_id == unit_id,
        )
    )
    row = r.scalar_one_or_none()
    now = _utc_now()
    if row is None:
        row = UserTopicUnitProgress(
            user_id=user_id,
            topic_unit_id=unit_id,
            started_at=now,
            completed_at=now,
        )
        db.add(row)
    else:
        row.completed_at = now
        if row.started_at is None:
            row.started_at = now
    await db.commit()
    await db.refresh(row)
    return row


async def try_auto_complete_unit_for_session(
    db: AsyncSession, session_id: int, user_id: int
) -> bool:
    """If session is tied to a unit with thresholds, mark complete when met. Returns True if completed."""
    sess = await db.get(
        Session,
        session_id,
        options=[selectinload(Session.topic_unit)],
    )
    if (
        not sess
        or sess.user_id != user_id
        or sess.topic_unit_id is None
        or sess.topic_unit is None
    ):
        return False
    unit = sess.topic_unit
    r = await db.execute(
        select(UserTopicUnitProgress).where(
            UserTopicUnitProgress.user_id == user_id,
            UserTopicUnitProgress.topic_unit_id == unit.id,
        )
    )
    prog = r.scalar_one_or_none()
    if prog and prog.completed_at is not None:
        return False

    scored_turns, avg_overall, _f, _v, _g = await scored_turn_averages_for_session(
        db, session_id
    )

    if not unit_auto_complete_thresholds_met(unit, scored_turns, avg_overall):
        return False

    now = _utc_now()
    if prog is None:
        prog = UserTopicUnitProgress(
            user_id=user_id,
            topic_unit_id=unit.id,
            started_at=now,
            completed_at=now,
        )
        db.add(prog)
    else:
        prog.completed_at = now
        if prog.started_at is None:
            prog.started_at = now
    await db.commit()
    return True
