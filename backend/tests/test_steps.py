"""Steps for a longer answer and the NOTE trimming (interview/steps.py)."""

import asyncio

from app.interview import retell
from app.interview.session import Session
from app.interview.steps import drop_earlier, mark_steps, steps_for, trim_invented
from app.interview.units import units, units_by_id

STEPS = [
    {"hint": "Vì sao?", "say": "That's because ..."},
    {"hint": "Một lần cụ thể", "say": "For example, last week I ..."},
    {"hint": "Mặt trái", "say": "The only downside is that ..."},
]


def done(text: str) -> list[bool]:
    return [st["done"] for st in mark_steps(STEPS, text)]


def test_a_step_is_done_when_its_starter_or_the_same_move_is_said():
    assert done("I prefer working from home.") == [False, False, False]
    assert done("I prefer home because I save two hours.") == [True, False, False]
    assert done("For instance, yesterday I finished early.") == [False, True, False]
    assert done("The only downside is that I feel lonely.") == [False, False, True]


def test_a_one_word_starter_is_not_enough_proof():
    steps = [{"hint": "Ai làm gì?", "say": "I'll ..., and you'll ..."}]
    assert mark_steps(steps, "I'll fix it.")[0]["done"] is False


def test_every_question_has_two_or_three_steps():
    for u in units:
        for i in range(len(u["questions"])):
            assert 2 <= len(steps_for(u, i)) <= 3, (u["id"], i)


Q_ENGLISH = "What's the best way to learn to speak English, in your opinion?"


def test_reasons_the_learner_never_gave_are_cut():
    said = f"{Q_ENGLISH} I think the best way is talking with foreigners every day."
    given = "In my opinion, ... The main reason is that ..."
    first = "In my opinion, the best way to learn English is talking with foreigners every day."
    note = f"{first} The main reason is that it provides real practice."
    assert trim_invented(note, said, given) == first
    office = "Do you prefer working from home or in the office? I prefer working in the office."
    note = "I prefer working in the office because it's easier to collaborate with colleagues."
    assert trim_invented(note, office, given) == "I prefer working in the office."


def test_an_empty_because_left_by_the_model_is_cut():
    office = "I prefer working in the office."
    assert trim_invented("I prefer working in the office because ...", office, "") == office
    assert trim_invented("I prefer working in the office, because...", office, "") == office


def test_what_the_learner_said_is_kept_even_when_reworded():
    said = "Do you agree? I think the social media waste too much time. It produces many short videos."
    note = "I totally agree, because short videos on social media make me spend too much time."
    assert trim_invented(note, said, "I totally agree, because ...") == note
    said = "I prefer working from home because I save two hours of commuting."
    note = "In my opinion, working from home is better because it saves me two hours of commuting."
    assert trim_invented(note, said, "In my opinion, ...") == note
    note = "I think AI coding tools are a great way to improve my productivity."
    assert trim_invented(note, "I think a tool for coding is a good way to improve my production.", "") == note


class FakeConn:
    def __init__(self):
        self.sent = []

    async def json(self, data):
        self.sent.append(data)


def test_retell_compares_the_new_answer_with_the_first_one(monkeypatch):
    saved = []
    monkeypatch.setattr(retell.history, "add_retell", lambda sid, row: saved.append((sid, row)))
    unit = units_by_id["opinions"]
    s = Session(unit=unit, asked=unit["questions"][0]["ask"], history_id=7, retell=True)
    s.retell_base = {
        "question": unit["questions"][0]["ask"],
        "answer": "I prefer working in the office.",
        "speech": {"words": 6, "wpm_speaking": None, "long_pauses": 0},
        "steps": steps_for(unit, 0),
    }
    words = [{"w": w, "s": i * 0.4, "e": i * 0.4 + 0.3, "p": 0.9} for i, w in enumerate("x" * 14)]
    heard = "I prefer the office because I can talk to my team. The only downside is that it is far."
    conn = FakeConn()
    asyncio.run(retell.handle_retell(conn, s, {"text": heard, "words": words}, 300))
    result, turn_done = conn.sent
    assert result["type"] == "retell_result" and turn_done["type"] == "turn_done"
    assert result["original_words"] == 6 and result["speech"]["words"] == 14
    assert [st["done"] for st in result["steps"]] == [True, False, True]
    assert s.retell is False  # one attempt per request
    assert saved[0][0] == 7 and saved[0][1]["steps_done"] == 2 and saved[0][1]["steps_total"] == 3


def test_drop_earlier_cuts_a_repeated_earlier_answer():
    earlier = ["A few months ago I went to Da Lat with my girlfriend."]
    latest = "I went there with my girlfriend, we spent lots of time to see the landscape and the sea."
    note = (
        "A few months ago, I went to Da Lat with my girlfriend. "
        "We spent most of the time seeing the landscape and the sea."
    )
    assert drop_earlier(note, latest, earlier) == "We spent most of the time seeing the landscape and the sea."


def test_drop_earlier_keeps_the_latest_answer_and_single_sentences():
    earlier = ["A few months ago I went to Da Lat with my girlfriend."]
    latest = "I went with my girlfriends. We spent most of the time to relax and enjoy the food."
    note = "I went with my girlfriends, and we spent most of the time relaxing and enjoying the food."
    assert drop_earlier(note, latest, earlier) == note
    assert drop_earlier(earlier[0], "It was cold.", earlier) == earlier[0]  # never empty
    assert drop_earlier(note, latest, []) == note
