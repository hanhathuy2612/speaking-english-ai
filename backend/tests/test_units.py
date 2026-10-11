"""Checks on the practice content in data/units.json."""

from app.interview.prompts import EXAMPLE_WORDS
from app.interview.units import topics, units, validate
from app.utils.parsing import norm, used_phrase_indices


def test_units_json_is_valid():
    assert validate(topics, units) == []


def test_every_topic_has_units():
    assert {t["id"] for t in topics} == {u["topic"] for u in units}


def test_every_phrase_is_targeted_by_a_question():
    for u in units:
        targeted = {i for q in u["questions"] for i in q["phrases"]}
        assert targeted == set(range(len(u["phrases"]))), u["id"]


def test_reading_a_phrase_template_counts_as_using_it():
    for u in units:
        for i, p in enumerate(u["phrases"]):
            assert i in used_phrase_indices(p["say"], u["phrases"]), (u["id"], p["say"])


def test_content_avoids_few_shot_words():
    # safe_note() treats these words as leaked few-shot content, so real units must not use them.
    for u in units:
        texts = [u["scenario"], u["greeting"], u["closing"], u["vocab"]]
        texts += [q["ask"] for q in u["questions"]] + [q["simple"] for q in u["questions"]]
        texts += [p["say"] for p in u["phrases"]]
        for t in texts:
            assert not any(w in norm(t) for w in EXAMPLE_WORDS), (u["id"], t)
