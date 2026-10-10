"""Pure-logic tests, no model or network needed. Run from backend/: python -m pytest"""

from app.utils.parsing import (
    is_question,
    ready_sentences,
    speech_metrics,
    split_sections,
    used_phrase_indices,
)

RAW = (
    "RETRY: no\n"
    "SAY: Great start. I like that you mentioned your team.\n"
    "ASK: What was your biggest challenge?\n"
    "NOTE: I've been working as a developer for five years."
)


def stream_chars(raw: str) -> list[str]:
    """Simulate a character-by-character stream like run_turn."""
    got, emitted = [], 0
    for i in range(1, len(raw) + 1):
        secs = split_sections(raw[:i])
        sents, emitted = ready_sentences(
            secs.get("SAY", ""), "ASK" in secs or "NOTE" in secs, emitted
        )
        got += sents
    secs = split_sections(raw)
    sents, emitted = ready_sentences(secs.get("SAY", ""), True, emitted)
    return got + sents


def test_sections():
    s = split_sections(RAW)
    assert s["RETRY"] == "no"
    assert s["SAY"] == "Great start. I like that you mentioned your team."
    assert s["ASK"] == "What was your biggest challenge?"
    assert s["NOTE"].startswith("I've been working")


def test_stream_emits_each_sentence_once_in_order():
    assert stream_chars(RAW) == [
        "Great start.",
        "I like that you mentioned your team.",
    ]


def test_markdown_labels_are_tolerated():
    s = split_sections("**RETRY:** yes\n**SAY:** Please try again.\n**NOTE:** Try this.")
    assert s["RETRY"] == "yes" and s["SAY"] == "Please try again." and s["NOTE"] == "Try this."


def test_no_labels_means_no_sections():
    assert split_sections("Just some text") == {}


def test_phrases():
    phrases = [
        {"say": "x", "match": ["i've been working as", "i have been working as"]},
        {"say": "y", "match": ["as a result"]},
    ]
    assert used_phrase_indices("I\u2019ve been working as a tester.", phrases) == [0]
    assert used_phrase_indices("As a result, it was faster", phrases) == [1]
    assert used_phrase_indices("nothing here", phrases) == []


def test_metrics_short_answer_has_no_speed():
    words = [
        {"w": "hello", "s": 0.0, "e": 0.4, "p": 0.9},
        {"w": "the", "s": 1.4, "e": 1.6, "p": 0.3},
        {"w": "booking", "s": 1.7, "e": 2.0, "p": 0.3},
    ]
    m = speech_metrics(words)
    assert m["words"] == 3 and m["long_pauses"] == 1 and m["wpm"] is None
    assert m["low_conf"] == ["booking"]  # "the" is a function word, so it is filtered out
    assert speech_metrics([])["words"] == 0


def test_metrics_speaking_rate_excludes_long_pauses():
    # 12 words of 0.4s each, back to back, with one 2s pause in the middle
    words, t = [], 0.0
    for i in range(12):
        if i == 6:
            t += 2.0
        words.append({"w": f"word{i}", "s": t, "e": t + 0.4, "p": 0.9})
        t += 0.4
    m = speech_metrics(words)
    assert m["long_pauses"] == 1
    assert m["wpm"] == round(12 / 6.8 * 60) and m["wpm_speaking"] == round(12 / 4.8 * 60)


def test_low_conf_keeps_content_words_beyond_first_five():
    words = [{"w": w, "s": i, "e": i + 0.3, "p": 0.2} for i, w in enumerate(
        "a with the and to microservices".split())]
    assert speech_metrics(words)["low_conf"] == ["microservices"]


def test_is_question():
    assert is_question("What did you build?")
    assert not is_question("NEXT")
    assert not is_question("That sounds great.")
