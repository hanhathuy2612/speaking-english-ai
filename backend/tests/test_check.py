import random

from app.assessment.check import (
    TARGET_SECONDS,
    TARGET_WPM_SPEAKING,
    evaluate,
    pick_prompt,
    prompts,
)


def steady_words(n: int, seconds_per_word: float, pause_every: int = 0) -> list[dict]:
    """n words, one every `seconds_per_word`, with a 1 s pause after every `pause_every` words."""
    out, t = [], 0.0
    for i in range(n):
        out.append({"w": "word", "s": t, "e": t + seconds_per_word * 0.8, "p": 0.9})
        t += seconds_per_word
        if pause_every and (i + 1) % pause_every == 0:
            t += 1.0
    return out


def by_key(report: dict) -> dict:
    return {c["key"]: c["passed"] for c in report["criteria"]}


def test_fluent_two_minutes_meets_every_target():
    report = evaluate(steady_words(260, 0.5), not_english=False)  # 120 wpm for ~130 s
    assert report["duration_s"] >= TARGET_SECONDS
    assert report["wpm_speaking"] >= TARGET_WPM_SPEAKING
    assert report["passed"] == 4


def test_short_slow_and_hesitant_talk_fails_those_targets():
    report = evaluate(steady_words(60, 0.8, pause_every=10), not_english=False)  # 6 pauses / 60 words
    assert by_key(report) == {"duration": False, "wpm_speaking": False, "hesitations_per_100": False, "english": True}


def test_vietnamese_or_silence_fails_the_english_target():
    vietnamese = evaluate(steady_words(260, 0.5), not_english=True)
    assert vietnamese["passed"] == 1 and by_key(vietnamese)["duration"]  # speed/hesitation not judged
    empty = evaluate([], not_english=False)
    assert empty["passed"] == 0 and empty["words"] == 0


def test_pick_prompt_prefers_unused_topics_and_skips_the_current_one():
    used = {p["id"]: 1 for p in prompts[1:]}  # only the first prompt is unused
    assert pick_prompt(used)["id"] == prompts[0]["id"]
    assert pick_prompt({}, exclude=prompts[0]["id"], rng=random.Random(0))["id"] != prompts[0]["id"]


def test_report_is_json_serializable_with_numpy_timestamps():
    import json

    import numpy as np

    words = [{"w": "w", "s": np.float64(i * 0.5), "e": np.float64(i * 0.5 + 0.4), "p": 0.9} for i in range(30)]
    report = evaluate(words, not_english=False)
    json.dumps(report)  # raises on numpy.bool_
    assert all(type(c["passed"]) is bool for c in report["criteria"])


def test_too_little_speech_is_not_judged_for_speed_or_hesitation():
    report = evaluate(steady_words(40, 0.5), not_english=False)  # 20 s, fast and fluent
    assert report["measurable"] is False
    assert by_key(report) == {"duration": False, "wpm_speaking": False, "hesitations_per_100": False, "english": True}
