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


def test_star_units_turn_follow_ups_off():
    # Their main questions already cover Situation, Task, Action, Result (docs/features/roadmap.md).
    for u in units:
        if u["topic"] == "behavioral":
            assert u.get("followups") == 0, u["id"]


def test_interview_prompt_is_unchanged_by_the_role_field():
    from app.interview.prompts import SYSTEM_TEMPLATE, build_messages
    from app.interview.session import Session

    u = next(u for u in units if "role" not in u)
    system = build_messages(Session(unit=u, asked="Q?"), "answer")[0]["content"]
    assert system.startswith("You play the INTERVIEWER in a job interview. The candidate")
    assert "{role}" in SYSTEM_TEMPLATE


def test_conversation_units_name_the_partner():
    for u in units:
        if "role" in u:
            assert u.get("partner"), u["id"]


def test_safe_note_rejects_a_note_that_changes_the_learners_facts():
    from app.interview.prompts import safe_note, target_phrases
    from app.interview.session import Session

    u = next(u for u in units if u["id"] == "standup")
    s = Session(unit=u, asked=u["questions"][3]["ask"])
    s.history = [{"q": "Q?", "a": "It should be ready by Thursday if the design come tomorrow."}]
    good = "It should be ready by Thursday if the design comes tomorrow."
    assert safe_note(s, 3, good, retry=False) == good
    bad = "It should be ready by Thursday if the design comes in on Friday."
    assert safe_note(s, 3, bad, retry=False) == " ".join(target_phrases(u, 3))


def test_follow_up_turns_send_no_target_phrase():
    from app.interview.prompts import build_user_message, target_phrases
    from app.interview.session import Session

    u = next(u for u in units if u["id"] == "microservices")
    s = Session(unit=u, asked=u["questions"][1]["ask"])
    s.q = 1
    assert f"Target phrase: {target_phrases(u, 1)[0]}" in build_user_message(s, "a")
    s.asked = "Why did you pick Kafka?"  # a follow-up written by the LLM
    assert "Target phrase: none (follow-up question)" in build_user_message(s, "a")


def test_safe_note_rejects_chinese():
    from app.interview.prompts import safe_note, target_phrases
    from app.interview.session import Session

    u = next(u for u in units if u["id"] == "microservices")
    s = Session(unit=u, asked=u["questions"][3]["ask"])
    s.history = [{"q": "Q?", "a": "It is hard to debug because the log is in many place."}]
    note = "The main trade-off is that debugging can be harder due to logs being分散在多个地方。"
    assert safe_note(s, 3, note, retry=False) == " ".join(target_phrases(u, 3))


def test_safe_note_rejects_second_person_notes():
    from app.interview.prompts import safe_note, target_phrases
    from app.interview.session import Session

    u = next(u for u in units if u["id"] == "tell-me-about-yourself")
    s = Session(unit=u, asked=u["questions"][3]["ask"])
    s.history = [{"q": "Q?", "a": "I enjoy most when I solve difficult bug in production."}]
    note = "You enjoy solving difficult bugs in production."
    assert safe_note(s, 3, note, retry=False) == " ".join(target_phrases(u, 3))


def test_agree_or_disagree_phrase_follows_the_answer():
    from app.interview.prompts import target_phrases

    u = next(u for u in units if u["id"] == "opinions")
    q = next(i for i, q in enumerate(u["questions"]) if "Do you agree" in q["ask"])
    assert target_phrases(u, q, "Yes, it wastes too much time.") == ["I totally agree, because ..."]
    assert target_phrases(u, q, "I don't agree, it helps me learn.") == ["I see your point, but I think ..."]
    assert target_phrases(u, q) == ["I totally agree, because ..."]
