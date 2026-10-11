"""Units grouped by topic in roadmap order, with practice status (docs/features/roadmap.md)."""

from __future__ import annotations

from fastapi import APIRouter

from app.interview.units import topics, units
from app.services import history

router = APIRouter(prefix="/api", tags=["units"])

NO_STATS = {"sessions": 0, "completed": 0, "last_at": None}


@router.get("/units")
async def list_units() -> dict:
    stats = history.unit_stats()
    return {
        "topics": [
            {
                **t,
                "units": [
                    {
                        "id": u["id"],
                        "title": u["title"],
                        "goal": u["goal"],
                        "questions": len(u["questions"]),
                        **stats.get(u["id"], NO_STATS),
                    }
                    for u in units
                    if u["topic"] == t["id"]
                ],
            }
            for t in topics
        ]
    }
