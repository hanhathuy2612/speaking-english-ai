from app.assessment.drills import (
    WINDOW,
    best_reading,
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


def drill(heard, at, target="Our customers book tickets.", audio=None):
    return {"target": target, "heard": heard, "created_at": at, "audio": audio}


def test_the_best_reading_is_kept_not_the_latest():
    focus = ["customers", "tickets"]
    attempts = [
        drill("our customer book ticket", "2026-10-14T10:00:00", audio="a.webm"),
        drill("our customers book tickets", "2026-10-14T10:01:00", audio="b.webm"),  # all right
        drill("how customer book tickets", "2026-10-14T10:02:00", audio="c.webm"),  # worse, but newer
        drill("something else", "2026-10-14T10:03:00", target="Another sentence."),
    ]
    best = best_reading("Our customers book tickets.", focus, attempts)
    assert best["audio"] == "b.webm" and best["focus_correct"] == 2 and best["correct"] == best["total"]
    assert best["attempts"] == 3  # readings of this sentence only
    assert best_reading("Never read.", focus, attempts) is None


def test_focus_words_rank_before_the_whole_sentence_and_a_tie_keeps_the_latest():
    focus = ["tickets"]
    attempts = [
        drill("our customers book ticket", "2026-10-14T10:00:00", audio="a.webm"),  # 3/4 words, focus wrong
        drill("are customer cook tickets", "2026-10-14T10:01:00", audio="b.webm"),  # 1/4 words, focus right
        drill("our customer look tickets", "2026-10-14T10:02:00", audio="c.webm"),  # 2/4 words, focus right
        drill("our customer look tickets", "2026-10-14T10:03:00", audio="d.webm"),  # same score, newer
    ]
    assert best_reading("Our customers book tickets.", focus, attempts)["audio"] == "d.webm"
