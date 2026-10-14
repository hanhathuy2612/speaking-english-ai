"""Talk lessons: how to speak for two minutes on one kind of question (docs/features/talk-lessons.md).

Each kind of speaking-check question (an opinion, a story, an explanation, a description) has a
lesson taught by the same teacher as the units' lessons (interview/lesson.py): a five-step frame
for a two-minute answer and six model sentences on an example topic. Practice afterwards uses the
talk's own prompts, never the check's, so a check stays a talk on a question you have not prepared.
Fixed, reviewed content: nothing here calls the LLM.
"""

from __future__ import annotations

import json

from app.core.config import DATA_DIR
from app.interview import lesson
from app.utils.parsing import has_vietnamese

talks: list[dict] = json.loads((DATA_DIR / "talks.json").read_text(encoding="utf-8"))
talks_by_id: dict[str, dict] = {t["id"]: t for t in talks}
PREFIX = "talk:"  # lesson rows (lesson_reads, lessons) of a talk use unit_id "talk:<id>"


def as_unit(talk: dict) -> dict:
    """The talk in the shape interview/lesson.py expects of a unit."""
    return {"id": PREFIX + talk["id"], "title": talk["title"], "goal": talk["goal"], "partner": "", "lesson": talk["lesson"]}


def validate(talk_list: list[dict]) -> list[str]:
    errors: list[str] = []
    for t in talk_list:
        tid = t.get("id", "?")
        for key in ("title", "title_vi", "goal", "frame", "practice", "lesson"):
            if not t.get(key):
                errors.append(f"{tid}: missing {key}")
        for i, st in enumerate(t.get("frame", [])):
            if not (st.get("hint") and "..." in st.get("say", "")) or has_vietnamese(st.get("say", "")):
                errors.append(f"{tid}: frame step {i} needs a hint and an English say containing '...'")
        for i, p in enumerate(t.get("practice", [])):
            if not (p.get("id") and p.get("text") and p.get("hint")) or has_vietnamese(p.get("text", "")):
                errors.append(f"{tid}: practice prompt {i} needs id, English text and hint")
        les = t.get("lesson", {})
        if has_vietnamese(les.get("outro", "")):
            errors.append(f"{tid}: lesson outro must be in English")
        # lesson.validate() checks the rest; talk sentences are not tied to unit phrases.
        sentences = [{**s, "phrase": 0} for s in les.get("sentences", [])]
        errors += lesson.validate({"id": tid, "phrases": [{}], "lesson": {**les, "sentences": sentences}})
    return errors


def public(talk: dict, finished: int) -> dict:
    """What the talk's lesson page needs: the lesson (as for a unit), the frame and practice prompts."""
    return {
        **lesson.public(as_unit(talk)),
        "id": talk["id"],
        "kind": "talk",
        "title_vi": talk["title_vi"],
        "frame": talk["frame"],
        "practice": talk["practice"],
        "finished": finished,
    }


def summary(talk: dict) -> dict:
    return {k: talk[k] for k in ("id", "title", "title_vi", "goal")}


def practice_prompt(talk: dict, prompt_id: str) -> dict | None:
    return next((p for p in talk["practice"] if p["id"] == prompt_id), None)


_errors = validate(talks)
if _errors:
    raise ValueError("Invalid talks.json:\n" + "\n".join(_errors))
