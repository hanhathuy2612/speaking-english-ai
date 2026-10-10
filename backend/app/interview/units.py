"""Load practice units from data/units.json (schema: docs/features/interview-flow.md)."""

from __future__ import annotations

import json

from app.core.config import DATA_DIR

units: list[dict] = json.loads((DATA_DIR / "units.json").read_text(encoding="utf-8"))
units_by_id: dict[str, dict] = {u["id"]: u for u in units}
