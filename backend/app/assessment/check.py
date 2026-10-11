"""Speaking check: talk for two minutes on a familiar topic you have not practised, then compare
objective metrics with fixed targets. No LLM is involved (docs/features/speaking-check.md).
"""

from __future__ import annotations

import json
import random

from app.core.config import DATA_DIR
from app.utils.parsing import hesitation_pauses, speech_metrics

prompts: list[dict] = json.loads((DATA_DIR / "check_prompts.json").read_text(encoding="utf-8"))
prompts_by_id: dict[str, dict] = {p["id"]: p for p in prompts}

# Targets for "can speak": starting points to recalibrate once there is a baseline.
TARGET_SECONDS = 120  # keep talking for two minutes (first word to last word)
TARGET_WPM_SPEAKING = 110  # words per minute while speaking, long pauses excluded
MIN_MEASURED_SECONDS = 30  # less English speech than this is too little to judge speed or hesitation
TARGET_HESITATIONS_PER_100 = 3  # pauses > 0.7 s inside a sentence per 100 words, must stay below


def pick_prompt(used_counts: dict[str, int], exclude: str | None = None, rng=random) -> dict:
    """A prompt from the least used ones, so each check is on a topic you have not prepared."""
    pool = [p for p in prompts if p["id"] != exclude] or prompts
    least = min(used_counts.get(p["id"], 0) for p in pool)
    return rng.choice([p for p in pool if used_counts.get(p["id"], 0) == least])


def evaluate(words: list[dict], not_english: bool) -> dict:
    """Metrics and pass/fail per target. `words` are Whisper words with timestamps."""
    speech = speech_metrics(words)
    # float(): Whisper timestamps are numpy floats, whose comparisons give numpy bools that the
    # JSON response cannot serialize.
    duration = round(float(words[-1]["e"] - words[0]["s"]), 1) if words else 0.0
    hesitations = hesitation_pauses(words)
    per_100 = round(hesitations / speech["words"] * 100, 1) if speech["words"] else None
    measurable = not not_english and duration >= MIN_MEASURED_SECONDS
    criteria = [
        {
            "key": "duration",
            "label": "Nói liền 2 phút",
            "value": duration,
            "target": TARGET_SECONDS,
            "passed": duration >= TARGET_SECONDS,
        },
        {
            "key": "wpm_speaking",
            "label": f"Tốc độ khi nói từ {TARGET_WPM_SPEAKING} từ/phút",
            "value": speech["wpm_speaking"],
            "target": TARGET_WPM_SPEAKING,
            "passed": measurable and (speech["wpm_speaking"] or 0) >= TARGET_WPM_SPEAKING,
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
            "passed": not not_english and speech["words"] > 0,
        },
    ]
    for c in criteria:
        c["passed"] = bool(c["passed"])
    return {
        "words": speech["words"],
        "duration_s": duration,
        "wpm": speech["wpm"],
        "wpm_speaking": speech["wpm_speaking"],
        "hesitations": hesitations,
        "hesitations_per_100": per_100,
        "not_english": not_english,
        "measurable": measurable,
        "criteria": criteria,
        "passed": sum(c["passed"] for c in criteria),
    }
