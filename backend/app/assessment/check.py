"""Speaking check: talk for two minutes on a familiar topic you have not practised, then compare
objective metrics with fixed targets. No LLM is involved (docs/features/speaking-check.md).
"""

from __future__ import annotations

import json
import random

from app.assessment.metrics import measure, pick_least_used
from app.core.config import DATA_DIR
from app.utils.parsing import hesitation_points

prompts: list[dict] = json.loads((DATA_DIR / "check_prompts.json").read_text(encoding="utf-8"))
prompts_by_id: dict[str, dict] = {p["id"]: p for p in prompts}

# Targets for "can speak": starting points to recalibrate once there is a baseline.
TARGET_SECONDS = 120  # keep talking for two minutes (first word to last word)
TARGET_WPM_SPEAKING = 110  # words per minute while speaking, long pauses excluded
TARGET_HESITATIONS_PER_100 = 3  # pauses > 0.7 s inside a sentence per 100 words, must stay below
KINDS = ("opinion", "story", "explain", "describe")  # each kind has a talk lesson (interview/talks.py)
CONTEXT_BEFORE, CONTEXT_AFTER = 8, 5  # words shown around a hesitation


def pick_prompt(
    used_counts: dict[str, int], exclude: str | None = None, studied: set[str] = frozenset(), rng=random
) -> dict:
    """A prompt from the least used ones, so each check is on a topic you have not prepared.
    Prompts you studied after a check (review or retry) are left out while others remain: a check
    on a prepared topic would measure memory, not speaking."""
    fresh = [p for p in prompts if p["id"] not in studied]
    return pick_least_used(fresh or prompts, used_counts, exclude, rng)


def stuck_points(words: list[dict]) -> list[dict]:
    """Where the speaker hesitated inside a sentence: the sentence so far (at most CONTEXT_BEFORE
    words) and the words after each long pause."""
    out = []
    for i in hesitation_points(words):
        start = max(0, i + 1 - CONTEXT_BEFORE)
        for j in range(i - 1, start - 1, -1):  # the sentence started after the last ".", "?" or "!"
            if words[j]["w"].rstrip().endswith((".", "?", "!")):
                start = j + 1
                break
        out.append(
            {
                "before": " ".join(w["w"] for w in words[start : i + 1]),
                "after": " ".join(w["w"] for w in words[i + 1 : i + 1 + CONTEXT_AFTER]),
                "pause_s": round(float(words[i + 1]["s"] - words[i]["e"]), 1),
            }
        )
    return out


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
