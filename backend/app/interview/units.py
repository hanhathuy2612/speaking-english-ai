"""Load practice units from data/units.json (schema: docs/features/interview-flow.md).

Topics are listed in roadmap order, and units in the order they should be practised.
"""

from __future__ import annotations

import json

from app.core.config import DATA_DIR

_data = json.loads((DATA_DIR / "units.json").read_text(encoding="utf-8"))
topics: list[dict] = _data["topics"]
units: list[dict] = _data["units"]
units_by_id: dict[str, dict] = {u["id"]: u for u in units}


def validate(topics: list[dict], units: list[dict]) -> list[str]:
    """Problems in the unit data; an empty list means it is usable."""
    errors: list[str] = []
    topic_ids = {t["id"] for t in topics}
    seen: set[str] = set()
    for u in units:
        uid = u.get("id", "?")
        if uid in seen:
            errors.append(f"{uid}: duplicate id")
        seen.add(uid)
        for key in ("topic", "title", "scenario", "goal", "greeting", "closing", "questions", "phrases"):
            if not u.get(key):
                errors.append(f"{uid}: missing {key}")
        if u.get("topic") not in topic_ids:
            errors.append(f"{uid}: unknown topic {u.get('topic')!r}")
        n = len(u.get("phrases", []))
        for i, q in enumerate(u.get("questions", [])):
            if not (q.get("ask") and q.get("simple") and q.get("phrases")):
                errors.append(f"{uid}: question {i} needs ask, simple and phrases")
            if any(not 0 <= p < n for p in q.get("phrases", [])):
                errors.append(f"{uid}: question {i} points to a missing phrase")
        for i, p in enumerate(u.get("phrases", [])):
            if not (p.get("say") and p.get("match")):
                errors.append(f"{uid}: phrase {i} needs say and match")
    return errors


_errors = validate(topics, units)
if _errors:
    raise ValueError("Invalid units.json:\n" + "\n".join(_errors))
