from app.assessment.drills import (
    WINDOW,
    focus_accuracy,
    personal_sentences,
    score,
    sentence_id,
    sets,
    validate,
)


def test_drill_data_is_valid_and_every_focus_word_is_in_its_sentence():
    assert validate(sets) == []
    assert validate([{"id": "x", "title": "t", "tip": "t", "sentences": [{"text": "A cat.", "focus": ["dog"]}]}])


def test_drills_cover_the_measured_mistakes():
    words = {f.lower() for s in sets for x in s["sentences"] for f in x["focus"]}
    assert {"customers", "thirty", "cache", "tests"} <= words  # misheard on the user's own recordings


def test_score_counts_focus_words_on_their_own():
    r = score("Our customers book tickets.", ["customers", "tickets"], "our customer book tickets")
    assert (r["focus_correct"], r["focus_total"]) == (1, 2)
    marked = [i["text"] for i in r["items"] if i.get("focus")]
    assert marked == ["customers", "tickets."]


def test_score_accepts_digits_for_number_words():
    r = score("It reduced the time by thirty percent.", ["thirty"], "It reduced the time by 30%.")
    assert r["focus_correct"] == 1 and r["accuracy"] == 1.0
    wrong = score("It reduced the time by thirty percent.", ["thirty"], "It reduced the time by 60%.")
    assert wrong["focus_correct"] == 0


def reading(target, heard, correct, total):
    return {"target": target, "heard": heard, "correct": correct, "total": total}


def test_personal_set_keeps_sentences_whose_latest_reading_had_a_mistake():
    a, b = "I wrote unit tests.", "We use a cache."
    attempts = [
        reading(a, "I wrote unit text", 3, 4),
        reading(b, "We use a kit", 3, 4),
        reading(a, "I wrote unit tests", 4, 4),  # fixed: leaves the set
    ]
    [mine] = personal_sentences(attempts)
    assert mine == {"id": sentence_id(b), "text": b, "focus": ["cache"]}


def test_focus_accuracy_uses_the_recent_window():
    old = [{"focus_correct": 0, "focus_total": 2}] * 5
    recent = [{"focus_correct": 2, "focus_total": 2}] * WINDOW
    assert focus_accuracy(old + recent) == {"attempts": WINDOW, "accuracy": 100}
    assert focus_accuracy([]) == {"attempts": 0, "accuracy": None}
