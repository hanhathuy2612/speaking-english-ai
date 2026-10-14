"""Talk lessons and learning after a speaking check (STT and LLM faked)."""

from __future__ import annotations

import asyncio
import json
import random

import pytest
from fastapi.testclient import TestClient

from app.assessment import check
from app.core import config
from app.interview import check_review, lesson, talks
from app.interview.steps import mark_steps
from app.services import accounts, history, llm, stt


def test_every_check_prompt_has_a_talk_lesson_and_practice_never_reuses_a_check_prompt():
    assert talks.validate(talks.talks) == []
    assert {p["kind"] for p in check.prompts} == set(check.KINDS) == set(talks.talks_by_id)
    check_texts = {p["text"].lower() for p in check.prompts}
    for t in talks.talks:
        assert not {p["text"].lower() for p in t["practice"]} & check_texts, t["id"]
        assert len({p["id"] for p in t["practice"]}) == len(t["practice"])


def test_a_talk_lesson_ends_with_its_own_outro():
    lines = lesson.lines(talks.as_unit(talks.talks_by_id["opinion"]))
    assert lines["outro"]["en"].startswith("Well done! Now use these five steps")
    assert lines["s0"]["en"].endswith("too many of them.")


def test_frame_steps_count_other_wordings():
    frame = talks.talks_by_id["explain"]["frame"]
    done = mark_steps(frame, "Basically a cloud is someone else's computer. First of all you upload your code, then")
    assert [st["done"] for st in done] == [True, True, True, False, False]


def words(spec: str) -> list[dict]:
    """'a b | c' -> Whisper-like words, 0.3 s each; '|' is a 1.5 s pause."""
    out, t = [], 0.0
    for tok in spec.split():
        if tok == "|":
            t += 1.5
            continue
        out.append({"w": tok, "s": t, "e": t + 0.3, "p": 0.9})
        t += 0.35
    return out


def test_stuck_points_show_the_words_around_each_hesitation():
    w = words("There are two sides. | Another way, not a side, | it makes developers lazy")
    [point] = check.stuck_points(w)  # the pause after "sides." ends a sentence: not a hesitation
    assert point == {"before": "Another way, not a side,", "after": "it makes developers lazy", "pause_s": 1.5}


def test_studied_prompts_are_not_given_while_others_remain():
    ids = {p["id"] for p in check.prompts}
    studied = ids - {"ai-tools", "degree"}
    picks = {check.pick_prompt({}, None, studied, random.Random(i))["id"] for i in range(20)}
    assert picks == {"ai-tools", "degree"}
    assert check.pick_prompt({}, None, ids)["id"] in ids  # everything studied: any prompt rather than none


def test_review_fix_keeps_real_stuck_places_and_reports_added_facts():
    stuck = [{"before": "not a side,", "after": "it makes", "pause_s": 1.5}]
    raw = {
        "better": "AI tools help us a lot. Five years ago, things were slower.",
        "stuck": [{"n": 1, "say": "On the other hand, it makes developers lazy."}, {"n": 7, "say": "x"}],
        "phrases": [{"say": "On the other hand, ...", "vi": "mặt khác"}, {"say": "mặt trái", "vi": "x"}],
    }
    out = check_review.fix(raw, "AI tools help a lot. Things were slow.", stuck)
    assert out["stuck"] == [{**stuck[0], "say": "On the other hand, it makes developers lazy."}]
    assert out["phrases"] == [{"say": "On the other hand, ...", "vi": "mặt khác"}]
    assert out["added_facts"] == ["five", "years"]


# ----- API -----

TALK = "Nowadays AI tools change the way developers work. | Another way, not a side, | it makes developers lazy."


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.main import app

    monkeypatch.setattr(config, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(config, "HISTORY_DB", "history.db")
    monkeypatch.setattr(config, "SAVE_AUDIO_DIR", "")
    accounts.init()
    history.init()
    accounts.create_user("me@example.com", "Me", "password1")
    w = words(TALK)
    fake = {"text": " ".join(x["w"] for x in w), "words": w, "avg_logprob": -0.2, "no_speech": 0.0, "language": "en"}
    monkeypatch.setattr(stt, "transcribe", lambda path, prompt="", check_language=False: fake)
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": "me@example.com", "password": "password1"}).status_code == 200
    return c


def test_learning_after_a_check_never_changes_or_adds_checks(client, monkeypatch):
    r = client.post("/api/check/ai-tools", content=b"audio").json()
    assert r["talk"]["id"] == "opinion" and len(r["stuck"]) == 1 and r["id"]
    check_id = r["id"]

    calls = []

    async def fake_llm(messages, schema, max_tokens, temperature=0.6):
        calls.append(messages)
        return json.dumps({
            "better": "AI tools change how developers work. On the other hand, they can make us lazy.",
            "stuck": [{"n": 1, "say": "On the other hand, it makes developers lazy."}],
            "phrases": [{"say": "On the other hand, ...", "vi": "mặt khác"}, {"say": "rely on", "vi": "phụ thuộc vào"},
                        {"say": "There are two sides to this.", "vi": "Chuyện này có hai mặt."}],
        })  # fmt: skip

    monkeypatch.setattr(llm, "complete_json", fake_llm)
    review = client.post(f"/api/check/{check_id}/review").json()
    assert review["stuck"][0]["say"].startswith("On the other hand") and len(review["phrases"]) == 3
    assert client.post(f"/api/check/{check_id}/review").json() == review and len(calls) == 1  # kept, not asked again
    assert "[pause 1.5 s]" in calls[0][1]["content"]

    added = client.post(f"/api/check/{check_id}/cards", json={"phrases": ["rely on", "rely on", "invented"]}).json()
    assert added == {"added": 1}
    assert client.post(f"/api/check/{check_id}/cards", json={"phrases": ["rely on"]}).json() == {"added": 0}
    cards = client.get("/api/review").json()["cards"]
    assert [(c["kind"], c["target"], c["unit_title"]) for c in cards] == [("talk", "rely on", "Kiểm tra nói")]

    retry = client.post(f"/api/check/{check_id}/retry", content=b"audio").json()
    assert retry["first"]["words"] == r["words"] and len(retry["stuck"]) == 1
    state = client.get("/api/check").json()
    assert len(state["checks"]) == 1  # the retry is practice, not a check
    assert state["checks"][0]["review"] == review
    for _ in range(10):  # studied: not given again while fresh prompts remain
        assert client.get("/api/check").json()["prompt"]["id"] != "ai-tools"


def test_someone_elses_check_cannot_be_reviewed(client):
    check_id = client.post("/api/check/ai-tools", content=b"audio").json()["id"]
    accounts.create_user("other@example.com", "Other", "password1")
    client.post("/api/auth/login", json={"email": "other@example.com", "password": "password1"})
    assert client.post(f"/api/check/{check_id}/review").status_code == 404
    assert client.post(f"/api/check/{check_id}/retry", content=b"audio").status_code == 404


def test_talk_lesson_and_practice(client):
    talk = client.get("/api/talks/opinion").json()
    assert talk["kind"] == "talk" and len(talk["frame"]) == 5 and talk["finished"] == 0 and talk["attempts"] == []
    assert talk["lines"]["outro"]["en"].startswith("Well done")
    assert client.get("/api/talks/nope").status_code == 404
    assert client.post("/api/talks/opinion/finish").json() == {"finished": 1}
    assert client.get("/api/units").status_code == 200  # "talk:" lesson rows do not disturb unit stats

    first = client.post("/api/talks/opinion/practice/overtime", content=b"audio").json()
    assert first["previous"] is None and len(first["steps"]) == 5
    second = client.post("/api/talks/opinion/practice/social-media", content=b"audio").json()
    assert second["previous"]["prompt_id"] == "overtime"
    assert client.post("/api/talks/opinion/practice/ai-tools", content=b"audio").status_code == 404
    state = client.get("/api/check").json()
    assert state["checks"] == []
    assert next(t for t in state["talks"] if t["id"] == "opinion") | {} == {
        **talks.summary(talks.talks_by_id["opinion"]), "finished": 1, "practiced": 2,
    }  # fmt: skip


def test_reading_a_talk_sentence_feeds_the_personal_drills(client):
    r = client.post("/api/talks/story/read/0", content=b"audio").json()
    assert r["target"].startswith("It happened about two years ago")
    readings = history.list_readings(1)
    assert [x["target"] for x in readings] == [r["target"]]
    assert asyncio.iscoroutinefunction(check_review.review)
