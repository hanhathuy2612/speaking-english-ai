from app.interview.session import Session, next_step

QUESTIONS = [
    {"ask": "First question?", "phrases": [0], "simple": "First, simpler?"},
    {"ask": "Second question?", "phrases": [0], "simple": "Second, simpler?"},
]
LLM = {"RETRY": "no", "SAY": "Nice.", "ASK": "What did you learn from that project?"}


def unit(**extra) -> dict:
    return {"questions": QUESTIONS, "phrases": [{"say": "x", "match": ["x"]}], **extra}


def test_follow_up_is_asked_when_allowed():
    s = Session(unit=unit(followups=1), asked=QUESTIONS[0]["ask"])
    assert next_step(s, LLM) == (LLM["ASK"], False)
    assert s.q == 0 and s.followups == 1


def test_unit_can_turn_follow_ups_off():
    s = Session(unit=unit(followups=0), asked=QUESTIONS[0]["ask"])
    assert next_step(s, LLM) == ("Second question?", True)
    assert s.q == 1
