from __future__ import annotations

from fastapi import APIRouter

from app.interview.units import units

router = APIRouter(prefix="/api", tags=["units"])


@router.get("/units")
async def list_units() -> list[dict]:
    return [{"id": u["id"], "title": u["title"]} for u in units]
