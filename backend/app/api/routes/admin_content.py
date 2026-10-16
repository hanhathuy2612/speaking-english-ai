"""Content editing for admins: units and topic texts, AI drafts (docs/features/content-admin.md).

Every save is checked by the same validate() as units.json and against stages.json before it is
stored; then the content in use is reloaded, so the next session or page load sees it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAIError
from pydantic import BaseModel, Field

from app.api.deps import require_admin
from app.assessment import stages
from app.interview import drafts
from app.interview import units as catalog
from app.services import content

router = APIRouter(prefix="/api/admin", tags=["admin"])


# The five write routes below stay `async def`: they run on the event loop one at a time, so two
# admins cannot interleave check -> save -> reload (each takes a few ms). Reads are plain `def`.
def _reload() -> None:
    catalog.use_content(*catalog.usable(*content.load()))


def _check(units: list[dict], topics: list[dict] | None = None) -> None:
    topics = topics if topics is not None else catalog.topics
    errors = catalog.validate(topics, units) + stages.validate(stages.stages, [t["id"] for t in topics])
    if errors:
        raise HTTPException(400, detail={"code": "invalid", "msg": "Nội dung chưa hợp lệ.", "errors": errors})


@router.get("/content")
def content_list() -> dict:
    """Topics, every unit (deleted ones too) with a short summary, and which stage opens each topic."""
    return {
        "topics": catalog.topics,
        "stages": [{"id": s["id"], "title": s["title"], "topics": s.get("topics", [])} for s in stages.stages],
        "units": [
            {
                "id": r["id"],
                "topic": r["data"]["topic"],
                "title": r["data"]["title"],
                "questions": len(r["data"]["questions"]),
                "lesson": "lesson" in r["data"],
                "source": r["source"],
                "deleted": r["deleted"],
                "invalid": not r["deleted"] and r["id"] not in catalog.units_by_id,  # left out, see units.usable()
                "updated_at": r["updated_at"],
                "updated_by": r["updated_by_name"],
            }
            for r in content.unit_rows()
        ],
    }


@router.get("/units/{unit_id}")
def get_unit(unit_id: str) -> dict:
    row = content.get_unit(unit_id)
    if not row:
        raise HTTPException(404)
    return row["data"]


def _with(unit: dict) -> list[dict]:
    """The units in use with `unit` added or replacing the one with its id."""
    return [*(u for u in catalog.units if u["id"] != unit["id"]), unit]


@router.put("/units/{unit_id}")
async def save_unit(unit_id: str, unit: dict, admin: dict = Depends(require_admin)) -> dict:
    """Create (unknown id) or replace a unit. The id never changes: history rows refer to it."""
    if unit.get("id") != unit_id:
        raise HTTPException(400, "Mã bài (id) không khớp với địa chỉ.")
    row = content.get_unit(unit_id)
    if row and row["deleted"]:
        raise HTTPException(409, "Bài này đã bị xóa. Khôi phục trước khi sửa.")
    _check(_with(unit))
    content.save_unit(unit, admin["id"])
    _reload()
    return unit


@router.delete("/units/{unit_id}")
async def delete_unit(unit_id: str, admin: dict = Depends(require_admin)) -> dict:
    """Hide a unit (its history stays). The last unit of a topic stays: a stage needs something to practise."""
    unit = catalog.units_by_id.get(unit_id)
    if not unit:
        raise HTTPException(404)
    if sum(u["topic"] == unit["topic"] for u in catalog.units) <= 1:
        raise HTTPException(400, "Không xóa được bài cuối cùng của một chủ đề.")
    content.set_deleted(unit_id, True, admin["id"])
    _reload()
    return {"ok": True}


@router.post("/units/{unit_id}/restore")
async def restore_unit(unit_id: str, admin: dict = Depends(require_admin)) -> dict:
    row = content.get_unit(unit_id)
    if not row:
        raise HTTPException(404)
    _check(_with(row["data"]))  # its topic may be gone, or the rules may have changed since
    content.set_deleted(unit_id, False, admin["id"])
    _reload()
    return {"ok": True}


class Order(BaseModel):
    ids: list[str]


@router.post("/order")
async def set_order(body: Order) -> dict:
    """Roadmap order: units are practised in this order inside their topic."""
    if set(body.ids) - {r["id"] for r in content.unit_rows()}:
        raise HTTPException(400, "Có mã bài không tồn tại.")
    content.set_order(body.ids)
    _reload()
    return {"ok": True}


class TopicText(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


@router.put("/topics/{topic_id}")
async def save_topic(topic_id: str, body: TopicText, admin: dict = Depends(require_admin)) -> dict:
    """Rename a topic. Adding or removing topics is done in units.json and stages.json, which decide
    which stage opens which topic."""
    topic = next((t for t in catalog.topics if t["id"] == topic_id), None)
    if not topic:
        raise HTTPException(404)
    new = {**topic, "title": body.title.strip(), "description": body.description.strip()}
    content.save_topic(new, admin["id"])
    _reload()
    return new


class DraftRequest(BaseModel):
    topic: str
    brief: str = Field(min_length=3, max_length=2000)
    lesson: bool = False


@router.post("/draft")
async def draft(body: DraftRequest) -> dict:
    """An AI draft of a new unit, not saved: {unit, errors, notes}. Takes up to a minute or two.
    errors: what would refuse the save; notes: valid but worth a look (drafts.review_notes)."""
    try:
        unit, errors = await drafts.draft_unit(body.topic, body.brief.strip(), body.lesson)
    except (ValueError, KeyError) as e:  # unknown topic, or a reply that is not the expected JSON
        raise HTTPException(400, f"Không soạn được bản nháp: {e}") from None
    except OpenAIError as e:
        raise HTTPException(502, f"Không gọi được LM Studio: {e}") from None
    return {"unit": unit, "errors": errors, "notes": drafts.review_notes(unit)}

