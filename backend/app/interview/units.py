"""Practice units (schema: docs/features/interview-flow.md).

Topics are listed in roadmap order, and units in the order they should be practised. The shipped
content is data/units.json; once the server starts, the content comes from the database, where
admins edit it (services/content.py, docs/features/content-admin.md). `topics`, `units` and
`units_by_id` are updated in place by use_content(), so modules that imported them see the change.
"""

from __future__ import annotations

import json
import re

from app.core.config import DATA_DIR
from app.interview import lesson
from app.interview.prompts import EXAMPLE_WORDS
from app.services import content
from app.utils.parsing import has_vietnamese, norm, used_phrase_indices

_data = json.loads((DATA_DIR / "units.json").read_text(encoding="utf-8"))
file_topics: list[dict] = _data["topics"]
file_units: list[dict] = _data["units"]
topics: list[dict] = list(file_topics)
units: list[dict] = list(file_units)
units_by_id: dict[str, dict] = {u["id"]: u for u in units}

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Spoken by TTS or sent to the LLM, so English only (AGENTS.md: prompts and AI speech never Vietnamese).
ENGLISH_FIELDS = ("role", "scenario", "greeting", "closing", "vocab")


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
        if not ID_RE.match(str(u.get("id", ""))):
            errors.append(f"{uid}: id must be lower-case words joined by '-'")
        for key in ("topic", "title", "scenario", "goal", "greeting", "closing", "questions", "phrases"):
            if not u.get(key):
                errors.append(f"{uid}: missing {key}")
        if u.get("topic") not in topic_ids:
            errors.append(f"{uid}: unknown topic {u.get('topic')!r}")
        for key in ENGLISH_FIELDS:
            if has_vietnamese(str(u.get(key, ""))):
                errors.append(f"{uid}: {key} must be in English (it is spoken or sent to the AI)")
        if not isinstance(u.get("followups", 0), int) or u.get("followups", 0) < 0:
            errors.append(f"{uid}: followups must be a non-negative integer")
        n = len(u.get("phrases", []))
        for i, q in enumerate(u.get("questions", [])):
            if not (q.get("ask") and q.get("simple") and q.get("phrases")):
                errors.append(f"{uid}: question {i} needs ask, simple and phrases")
            if has_vietnamese(f"{q.get('ask', '')} {q.get('simple', '')}"):
                errors.append(f"{uid}: question {i} must be asked in English")
            if any(not (st.get("hint") and "..." in st.get("say", "")) for st in q.get("steps", [])):
                errors.append(f"{uid}: question {i} needs steps with hint and a say containing '...'")
            if any(not 0 <= p < n for p in q.get("phrases", [])):
                errors.append(f"{uid}: question {i} points to a missing phrase")
        targeted = {i for q in u.get("questions", []) for i in q.get("phrases", [])}
        for i, p in enumerate(u.get("phrases", [])):
            if not (p.get("say") and p.get("match")):
                errors.append(f"{uid}: phrase {i} needs say and match")
                continue
            if has_vietnamese(p["say"]):
                errors.append(f"{uid}: phrase {i} must be in English")
            if i not in targeted:
                errors.append(f"{uid}: phrase {i} is not practised by any question")
            if i not in used_phrase_indices(p["say"], u["phrases"]):
                errors.append(f"{uid}: phrase {i}: saying it is not detected, add its start to match")
        # safe_note() treats these words as leaked few-shot content and drops the NOTE.
        spoken = [u.get(k, "") for k in ("scenario", "greeting", "closing", "vocab")]
        spoken += [q.get(k, "") for q in u.get("questions", []) for k in ("ask", "simple")]
        spoken += [p.get("say", "") for p in u.get("phrases", [])]
        if found := sorted({w for w in EXAMPLE_WORDS for t in spoken if w in norm(str(t))}):
            errors.append(f"{uid}: uses words reserved for the prompt's examples: {', '.join(found)}")
        errors += lesson.validate(u)
    return errors


def use_content(new_topics: list[dict], new_units: list[dict]) -> None:
    """Make this the content every module sees (in place: other modules hold these objects)."""
    # Other threads read these while an admin saves: never clear() first, so a reader cannot see an
    # empty or half-filled catalog. Slice assignment replaces a list in one step.
    fresh = {u["id"]: u for u in new_units}
    topics[:] = new_topics
    units[:] = new_units
    units_by_id.update(fresh)
    for stale in units_by_id.keys() - fresh.keys():
        units_by_id.pop(stale, None)


def load_content() -> None:
    """At startup: bring units.json into the database, then serve the database's content."""
    content.init(file_topics, file_units)
    use_content(*usable(*content.load()))


def usable(topics: list[dict], units: list[dict]) -> tuple[list[dict], list[dict]]:
    """The content minus units that fail validate(), say after a rule got stricter than what an admin
    saved: those are left out (and printed) instead of stopping the server. The admin page still
    lists them, and saving one again checks it."""
    ok = []
    for u in units:
        if errors := validate(topics, [u]):
            print(f"!! Unit {u.get('id')} left out until an admin fixes it:\n   " + "\n   ".join(errors), flush=True)
        else:
            ok.append(u)
    return topics, ok


_errors = validate(topics, units)
if _errors:
    raise ValueError("Invalid units.json:\n" + "\n".join(_errors))
