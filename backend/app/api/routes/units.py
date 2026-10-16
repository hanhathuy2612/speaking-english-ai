"""Units grouped by topic in roadmap order with practice status, and the stages that unlock them
(docs/features/roadmap.md)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import current_user
from app.assessment import drills, fluency, stages
from app.interview.units import topics, units
from app.services import history

router = APIRouter(prefix="/api", tags=["units"])

NO_STATS = {"sessions": 0, "completed": 0, "last_at": None}

_errors = stages.validate(stages.stages, [t["id"] for t in topics])
if _errors:
    raise ValueError("Invalid stages.json:\n" + "\n".join(_errors))


def _stats(uid: int) -> dict[str, dict]:
    """Practice status per unit. A unit with a lesson is done only when both parts are: the lesson
    was finished once and a role-play reached the last question (docs/features/lesson.md)."""
    stats, lessons = history.unit_stats(uid), history.lesson_counts(uid)
    out = {}
    for u in units:
        st = {**stats.get(u["id"], NO_STATS), "lesson": "lesson" in u, "lesson_done": lessons.get(u["id"], 0)}
        st["done"] = bool(st["completed"]) and (not st["lesson"] or st["lesson_done"] > 0)
        out[u["id"]] = st
    return out


def _topics(stats: dict[str, dict], open_topics: set[str]) -> list[dict]:
    return [
        {
            **t,
            "locked": t["id"] not in open_topics,
            "units": [
                {
                    "id": u["id"],
                    "title": u["title"],
                    "goal": u["goal"],
                    "questions": len(u["questions"]),
                    **stats[u["id"]],
                }
                for u in units
                if u["topic"] == t["id"]
            ],
        }
        for t in topics
    ]


def _report(uid: int, stats: dict[str, dict]) -> list[dict]:
    """Stages evaluated against the user's history."""
    topic_units: dict[str, list[str]] = {}
    for u in units:
        topic_units.setdefault(u["topic"], []).append(u["id"])
    runs = fluency.group_runs(history.list_fluency_rounds(uid))
    evidence = {
        "completed": {uid for uid, st in stats.items() if st["done"]},
        "topic_units": topic_units,
        "drill_attempts": history.list_drills(uid),
        "drill_set_ids": [s["id"] for s in drills.sets],
        "checks": history.list_checks(uid),
        "fluency_runs": sum(r["complete"] for r in runs),
    }
    return stages.evaluate(stages.stages, evidence)


def _next_unit(topic_list: list[dict]) -> str | None:
    """First unit not completed yet in the open stages, in roadmap order."""
    for t in topic_list:
        if not t["locked"]:
            for u in t["units"]:
                if not u["done"]:
                    return u["id"]
    return None


@router.get("/units")
def list_units(user: dict = Depends(current_user)) -> dict:
    stats = _stats(user["id"])
    topic_list = _topics(stats, stages.open_topics(_report(user["id"], stats)))
    return {"topics": topic_list, "next_unit": _next_unit(topic_list)}


@router.get("/stages")
def list_stages(user: dict = Depends(current_user)) -> dict:
    """Stages in order with status and requirements; topics carry their units' status."""
    stats = _stats(user["id"])
    report = _report(user["id"], stats)
    by_id = {t["id"]: t for t in _topics(stats, stages.open_topics(report))}
    return {
        "stages": [{**s, "topics": [by_id[t] for t in s.get("topics", [])]} for s in report],
        "next_unit": _next_unit(list(by_id.values())),
    }
