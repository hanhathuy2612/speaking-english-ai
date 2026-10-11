"""Measurements shared by the speaking check and the 4/3/2 fluency rounds. No LLM involved."""

from __future__ import annotations

import random

from app.utils.parsing import hesitation_pauses, speech_metrics

MIN_MEASURED_SECONDS = 30  # less English speech than this is too little to judge speed or hesitation


def measure(words: list[dict], not_english: bool) -> dict:
    """Length, speed and hesitation of one long answer. `words` are Whisper words with timestamps."""
    speech = speech_metrics(words)
    # float(): Whisper timestamps are numpy floats, whose comparisons give numpy bools that the
    # JSON response cannot serialize.
    duration = round(float(words[-1]["e"] - words[0]["s"]), 1) if words else 0.0
    hesitations = hesitation_pauses(words)
    per_100 = round(hesitations / speech["words"] * 100, 1) if speech["words"] else None
    return {
        "words": speech["words"],
        "duration_s": duration,
        "wpm": speech["wpm"],
        "wpm_speaking": speech["wpm_speaking"],
        "hesitations": hesitations,
        "hesitations_per_100": per_100,
        "not_english": not_english,
        "measurable": bool(not not_english and duration >= MIN_MEASURED_SECONDS),
    }


def pick_least_used(
    prompts: list[dict], used_counts: dict[str, int], exclude: str | None = None, rng=random
) -> dict:
    """A prompt from the least used ones, so each attempt is on a topic you have not prepared."""
    pool = [p for p in prompts if p["id"] != exclude] or prompts
    least = min(used_counts.get(p["id"], 0) for p in pool)
    return rng.choice([p for p in pool if used_counts.get(p["id"], 0) == least])
