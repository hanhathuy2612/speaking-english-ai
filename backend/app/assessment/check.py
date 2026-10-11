"""Speaking check: talk for two minutes on a familiar topic you have not practised, then compare
objective metrics with fixed targets. No LLM is involved (docs/features/speaking-check.md).
"""

from __future__ import annotations

import json
import random

from app.assessment.metrics import measure, pick_least_used
from app.core.config import DATA_DIR

prompts: list[dict] = json.loads((DATA_DIR / "check_prompts.json").read_text(encoding="utf-8"))
prompts_by_id: dict[str, dict] = {p["id"]: p for p in prompts}

# Targets for "can speak": starting points to recalibrate once there is a baseline.
TARGET_SECONDS = 120  # keep talking for two minutes (first word to last word)
TARGET_WPM_SPEAKING = 110  # words per minute while speaking, long pauses excluded
TARGET_HESITATIONS_PER_100 = 3  # pauses > 0.7 s inside a sentence per 100 words, must stay below


def pick_prompt(used_counts: dict[str, int], exclude: str | None = None, rng=random) -> dict:
    """A prompt from the least used ones, so each check is on a topic you have not prepared."""
    return pick_least_used(prompts, used_counts, exclude, rng)


def evaluate(words: list[dict], not_english: bool) -> dict:
    """Metrics and pass/fail per target. `words` are Whisper words with timestamps."""
    m = measure(words, not_english)
    measurable, per_100 = m["measurable"], m["hesitations_per_100"]
    criteria = [
        {
            "key": "duration",
            "label": "Nói liền 2 phút",
            "value": m["duration_s"],
            "target": TARGET_SECONDS,
            "passed": m["duration_s"] >= TARGET_SECONDS,
        },
        {
            "key": "wpm_speaking",
            "label": f"Tốc độ khi nói từ {TARGET_WPM_SPEAKING} từ/phút",
            "value": m["wpm_speaking"],
            "target": TARGET_WPM_SPEAKING,
            "passed": measurable and (m["wpm_speaking"] or 0) >= TARGET_WPM_SPEAKING,
        },
        {
            "key": "hesitations_per_100",
            "label": f"Dưới {TARGET_HESITATIONS_PER_100} lần ngập ngừng giữa câu / 100 từ",
            "value": per_100,
            "target": TARGET_HESITATIONS_PER_100,
            "passed": measurable and per_100 is not None and per_100 < TARGET_HESITATIONS_PER_100,
        },
        {
            "key": "english",
            "label": "Nói hoàn toàn bằng tiếng Anh",
            "value": not not_english,
            "target": True,
            "passed": not not_english and m["words"] > 0,
        },
    ]
    for c in criteria:
        c["passed"] = bool(c["passed"])
    return {**m, "criteria": criteria, "passed": sum(c["passed"] for c in criteria)}
