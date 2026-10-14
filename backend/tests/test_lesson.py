"""Lesson part of a unit (docs/features/lesson.md): content checks, teacher lines, status."""

from app.interview import lesson
from app.interview.prompts import EXAMPLE_WORDS
from app.interview.units import units
from app.utils.parsing import norm, used_phrase_indices

LESSON_UNITS = [u for u in units if "lesson" in u]


def test_some_units_have_a_lesson():
    assert {"tell-me-about-yourself", "current-project", "career-goals"} <= {u["id"] for u in LESSON_UNITS}


def test_each_lesson_sentence_uses_its_phrase():
    # Reading the sentence in the lesson must count as using the phrase in the role-play.
    for u in LESSON_UNITS:
        for s in u["lesson"]["sentences"]:
            assert s["phrase"] in used_phrase_indices(s["say"], u["phrases"]), (u["id"], s["say"])


def test_lessons_teach_every_phrase_once():
    for u in LESSON_UNITS:
        taught = [s["phrase"] for s in u["lesson"]["sentences"]]
        assert sorted(taught) == list(range(len(u["phrases"]))), u["id"]


def test_lesson_content_avoids_few_shot_words():
    for u in LESSON_UNITS:
        les = u["lesson"]
        texts = [les["intro"]] + [w["word"] for w in les["vocab"]]
        texts += [t for s in les["sentences"] for t in (s["say"], s["use"])]
        for t in texts:
            assert not any(w in norm(t) for w in EXAMPLE_WORDS), (u["id"], t)


def test_lines_cover_every_key_the_page_plays():
    u = LESSON_UNITS[0]
    keys = set(lesson.lines(u))
    n, m = len(u["lesson"]["sentences"]), len(u["lesson"]["vocab"])
    assert set(lesson.TEACHER) | {"intro"} <= keys
    assert {f"s{i}" for i in range(n)} | {f"say{i}" for i in range(n)} | {f"w{i}" for i in range(m)} <= keys
    s0 = u["lesson"]["sentences"][0]
    assert lesson.lines(u)["s0"]["en"].endswith(s0["say"])  # the explanation is followed by the sentence


def test_validate_reports_broken_lessons():
    unit = {"id": "x", "phrases": [{"say": "a ...", "match": ["a"]}]}
    assert lesson.validate(unit) == []  # no lesson is fine
    bad = {
        **unit,
        "lesson": {
            "intro": "Hi",
            "intro_vi": "Chào",
            "vocab": [{"word": "a"}],
            "sentences": [{"phrase": 3, "say": "A ...", "use": "Use it.", "use_vi": "Dùng."}],
        },
    }
    errors = lesson.validate(bad)
    assert "x: lesson word 0 needs word and vi" in errors
    assert "x: lesson sentence 0 must be a full sentence, not a template" in errors
    assert "x: lesson sentence 0 points to a missing phrase" in errors


def test_a_unit_with_a_lesson_is_done_only_after_both_parts(monkeypatch):
    from app.api.routes import units as route
    from app.services import history

    played = {"sessions": 1, "completed": 1, "last_at": "2026-10-14T10:00:00"}
    monkeypatch.setattr(history, "unit_stats", lambda: {"tell-me-about-yourself": played, "weekend": played})
    monkeypatch.setattr(history, "lesson_counts", lambda: {})
    stats = route._stats()
    assert stats["weekend"]["done"] is True  # no lesson: the role-play is enough
    assert stats["tell-me-about-yourself"]["done"] is False
    assert stats["current-project"]["done"] is False and stats["current-project"]["lesson"] is True
    monkeypatch.setattr(history, "lesson_counts", lambda: {"tell-me-about-yourself": 1})
    assert route._stats()["tell-me-about-yourself"]["done"] is True
