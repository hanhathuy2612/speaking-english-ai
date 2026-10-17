"""Lesson content in the database: syncing units.json, the admin API, and AI drafts (LLM faked)."""

from __future__ import annotations

import asyncio
import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.interview import drafts
from app.interview import units as catalog
from app.services import accounts, content, history, llm


@pytest.fixture
def db(mysql):
    catalog.load_content()
    yield
    catalog.use_content(catalog.file_topics, catalog.file_units)  # other tests see the shipped content


def test_the_file_is_copied_in_and_later_file_changes_reach_untouched_units(db):
    topics, units = content.load()
    assert [u["id"] for u in units] == [u["id"] for u in catalog.file_units]
    assert topics == catalog.file_topics

    file_units = copy.deepcopy(catalog.file_units)
    file_units[0]["title"] = "Changed in the repo"
    file_units[1]["title"] = "Also changed in the repo"
    file_units.append({**copy.deepcopy(file_units[2]), "id": "new-in-repo"})
    admin = accounts.create_user("a@example.com", "A", "password1", "admin")["id"]
    content.save_unit({**catalog.file_units[1], "title": "Edited by the admin"}, admin)
    content.set_deleted(file_units[2]["id"], True, admin)
    content.init(catalog.file_topics, file_units)

    _topics, units = content.load()
    by_id = {u["id"]: u for u in units}
    assert by_id[file_units[0]["id"]]["title"] == "Changed in the repo"
    assert by_id[file_units[1]["id"]]["title"] == "Edited by the admin"  # the admin's edit wins
    assert file_units[2]["id"] not in by_id  # deleted stays deleted
    assert units[-1]["id"] == "new-in-repo"


@pytest.fixture
def client(db):
    from app.main import app

    accounts.create_user("admin@example.com", "Admin", "password1", "admin")
    accounts.create_user("user@example.com", "User", "password1")
    c = TestClient(app)
    return c


def login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "password1"})
    assert r.status_code == 200
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"


def unit_ids(client) -> list[str]:
    return [u["id"] for t in client.get("/api/units").json()["topics"] for u in t["units"]]


def test_learners_cannot_edit_content(client):
    login(client, "user@example.com")
    assert client.get("/api/admin/content").status_code == 403
    assert client.put("/api/admin/units/weekend", json={}).status_code == 403


def test_admin_edits_creates_hides_and_restores_units(client):
    login(client, "admin@example.com")
    weekend = client.get("/api/admin/units/weekend").json()

    bad = {**weekend, "greeting": ""}
    r = client.put("/api/admin/units/weekend", json=bad)
    assert r.status_code == 400 and "weekend: missing greeting" in r.json()["detail"]["errors"]
    assert client.put("/api/admin/units/weekend", json={**weekend, "id": "other"}).status_code == 400

    r = client.put("/api/admin/units/weekend", json={**weekend, "title": "Weekend chat"})
    assert r.status_code == 200 and catalog.units_by_id["weekend"]["title"] == "Weekend chat"

    new = {**weekend, "id": "my-new-unit", "title": "A new unit"}
    assert client.put("/api/admin/units/my-new-unit", json=new).status_code == 200
    ids = unit_ids(client)
    assert ids.index("my-new-unit") == ids.index("opinions") + 1  # last of its topic, before the next topic

    assert client.delete("/api/admin/units/my-new-unit").status_code == 200
    assert "my-new-unit" not in unit_ids(client)
    listed = {u["id"]: u for u in client.get("/api/admin/content").json()["units"]}
    assert listed["my-new-unit"]["deleted"] is True and listed["weekend"]["source"] == "admin"
    assert client.put("/api/admin/units/my-new-unit", json=new).status_code == 409
    assert client.post("/api/admin/units/my-new-unit/restore").status_code == 200
    assert "my-new-unit" in unit_ids(client)


def test_the_last_unit_of_a_topic_cannot_be_deleted(client):
    login(client, "admin@example.com")
    closing = [u["id"] for u in catalog.units if u["topic"] == "closing"]
    for uid in closing[:-1]:
        assert client.delete(f"/api/admin/units/{uid}").status_code == 200
    assert client.delete(f"/api/admin/units/{closing[-1]}").status_code == 400


def test_order_and_topic_texts(client):
    login(client, "admin@example.com")
    daily = [u["id"] for u in catalog.units if u["topic"] == "daily"]
    assert client.post("/api/admin/order", json={"ids": daily[::-1]}).status_code == 200
    assert [u["id"] for u in catalog.units if u["topic"] == "daily"] == daily[::-1]
    assert client.post("/api/admin/order", json={"ids": ["nope"]}).status_code == 400
    r = client.put("/api/admin/topics/daily", json={"title": "Chuyện hằng ngày", "description": "Mô tả mới."})
    assert r.status_code == 200 and catalog.topics[0]["title"] == "Chuyện hằng ngày"
    assert client.put("/api/admin/topics/nope", json={"title": "x", "description": "y"}).status_code == 404


DRAFT = {
    "title": "Ordering food",
    "role": "a friendly COLLEAGUE at lunch",
    "partner": "Đồng nghiệp",
    "scenario": "Two colleagues order lunch together.",
    "goal": "Gọi món và nói món mình thích.",
    "greeting": "Hey, are you hungry?",
    "closing": "That was good. Let's head back.",
    "vocab": "noodles, rice, spicy",
    "phrases": [
        {"say": "I'd like to order", "match": ["I'd like to order"]},
        {"say": "My favourite dish is ...", "match": ["My favourite dish is ..."]},
        {"say": "It tastes ...", "match": []},
    ],
    "questions": [
        {"ask": "What will you have?", "simple": "What do you want?", "phrase": 0,
         "steps": [{"hint": "Vì sao?", "say": "Because"}, {"hint": "Thêm món", "say": "I'll also have ..."}]},
        {"ask": "What's your favourite dish?", "simple": "What food do you like?", "phrase": 7,
         "steps": [{"hint": "Ở đâu?", "say": "I usually eat it at ..."}, {"hint": "Vì sao?", "say": "That's because ..."}]},
        {"ask": "How is it?", "simple": "Is it good?", "phrase": 2,
         "steps": [{"hint": "So sánh", "say": "It's better than ..."}, {"hint": "Lần sau", "say": "Next time, I ..."}]},
    ],
}  # fmt: skip
LESSON = {
    "intro": "Hi! Today we learn how to order lunch.",
    "intro_vi": "Chào bạn! Hôm nay mình học cách gọi món.",
    "vocab": [{"word": "dish", "vi": "món ăn"}, {"word": "spicy", "vi": "cay"}, {"word": "order", "vi": "gọi món"}],
    "sentences": [
        {"phrase": 0, "say": "I'd like to order the noodles ...", "use": "Use it to order.", "use_vi": "Dùng để gọi món."},
        {"phrase": 1, "say": "My favourite dish is pho.", "use": "Say what you like.", "use_vi": "Nói món bạn thích."},
        {"phrase": 9, "say": "It tastes great.", "use": "Say how it is.", "use_vi": "Nói món ăn thế nào."},
    ],
}  # fmt: skip


def test_a_draft_is_fixed_up_and_checked(db, monkeypatch):
    replies = iter([json.dumps(DRAFT), json.dumps(LESSON)])
    calls = []

    async def fake(messages, schema, max_tokens, temperature=0.6):
        calls.append(messages[1]["content"])
        return next(replies)

    monkeypatch.setattr(llm, "complete_json", fake)
    unit, errors = asyncio.run(drafts.draft_unit("daily", "gọi món ăn trưa với đồng nghiệp", with_lesson=True))
    assert errors == ["ordering-food: phrase 1 is not practised by any question"]  # its question pointed past the end
    assert unit["id"] == "ordering-food" and unit["topic"] == "daily" and unit["partner"] == "Đồng nghiệp"
    assert unit["phrases"][0] == {"say": "I'd like to order ...", "match": ["i'd like to order"]}
    assert unit["phrases"][2]["match"] == ["it tastes"]  # derived from the phrase when the model gave none
    assert unit["questions"][1]["phrases"] == [2]  # out of range: clamped
    assert unit["questions"][0]["steps"][0]["say"] == "Because ..."
    assert unit["lesson"]["sentences"][0]["say"] == "I'd like to order the noodles"
    assert unit["lesson"]["sentences"][2]["phrase"] == 2
    assert '"title": "Your weekend"' in calls[0]  # the topic's first unit is the pattern

    monkeypatch.setattr(llm, "complete_json", fake)
    replies = iter([json.dumps({**DRAFT, "role": "", "partner": ""})])
    unit, _ = asyncio.run(drafts.draft_unit("behavioral", "a time you helped a teammate", with_lesson=False))
    assert "role" not in unit and "lesson" not in unit  # interview topics have no role


def test_draft_ids_never_reuse_an_existing_unit(db):
    assert drafts.slug("Your weekend!") == "your-weekend"
    assert drafts.slug("Weekend") == "weekend-2"


def test_one_word_phrase_cues_are_dropped():
    assert drafts._matches({"say": "I'd recommend ...", "match": ["recommend", "I would recommend"]}) == [
        "i'd recommend",
        "i would recommend",
    ]
    assert drafts._matches({"say": "Sure ...", "match": ["sure"]}) == ["sure"]  # better than nothing


def test_review_notes_flag_questions_where_statements_belong():
    unit = {
        "phrases": [{"say": "Have you tried the ...?"}, {"say": "I usually order ..."}, {"say": "What do you recommend ..."}],
        "questions": [
            {"ask": "I usually order the soup.", "steps": [{"hint": "Đồng ý?", "say": "What do you think ..."}]},
            {"ask": "What's good here?", "steps": [{"hint": "Vì sao?", "say": "That's because ..."}]},
        ],
    }
    notes = drafts.review_notes(unit)
    assert len(notes) == 4
    assert notes[0].startswith("Mẫu câu 1") and notes[1].startswith("Mẫu câu 3")
    assert "Câu hỏi 1 " in notes[2] and "ý \"Đồng ý?\"" in notes[3]


def test_spoken_and_prompt_fields_must_be_english(db):
    weekend = {**catalog.units_by_id["weekend"], "role": "Nhân viên IT muốn nghỉ phép"}
    weekend["questions"] = [{**weekend["questions"][0], "simple": "Bạn đi đâu?"}, *weekend["questions"][1:]]
    errors = catalog.validate(catalog.topics, [weekend])
    assert "weekend: role must be in English (it is spoken or sent to the AI)" in errors
    assert "weekend: question 0 must be asked in English" in errors
    assert catalog.validate(catalog.topics, [catalog.units_by_id["weekend"]]) == []  # partner, goal: Vietnamese is fine


def test_a_saved_unit_that_breaks_a_newer_rule_is_left_out_not_fatal(client):
    login(client, "admin@example.com")
    admin = accounts.user_by_email("admin@example.com")["id"]
    content.save_unit({**catalog.units_by_id["weekend"], "role": "Nhân viên"}, admin)  # saved before the rule
    catalog.load_content()
    assert "weekend" not in catalog.units_by_id and "hometown" in catalog.units_by_id
    listed = {u["id"]: u for u in client.get("/api/admin/content").json()["units"]}
    assert listed["weekend"]["invalid"] is True and listed["hometown"]["invalid"] is False
    fixed = {**client.get("/api/admin/units/weekend").json(), "role": "a friendly COLLEAGUE"}
    assert client.put("/api/admin/units/weekend", json=fixed).status_code == 200
    assert "weekend" in catalog.units_by_id


def test_content_rules_that_affect_the_app_apply_to_admin_units(db):
    weekend = catalog.units_by_id["weekend"]
    bad = {
        **weekend,
        "greeting": "Did the delivery driver come?",
        "questions": [{**q, "phrases": [0]} for q in weekend["questions"]],
        "phrases": [weekend["phrases"][0], {**weekend["phrases"][1], "match": ["something else"]}, *weekend["phrases"][2:]],
    }
    errors = catalog.validate(catalog.topics, [bad])
    assert "weekend: phrase 1 is not practised by any question" in errors
    assert "weekend: phrase 1: saying it is not detected, add its start to match" in errors
    assert "weekend: uses words reserved for the prompt's examples: deliver, driver" in errors


def test_ids_and_titles_must_fit_their_columns(db):
    weekend = catalog.units_by_id["weekend"]
    long_id = "a" * (catalog.MAX_ID + 1)
    errors = catalog.validate(catalog.topics, [{**weekend, "id": long_id, "title": "t" * (catalog.MAX_TITLE + 1)}])
    assert any("id must be at most" in e for e in errors)
    assert any("title must be at most" in e for e in errors)
    long_topic = {**catalog.topics[0], "id": long_id}
    assert any("id must be at most" in e for e in catalog.validate([long_topic], []))
    assert catalog.validate(catalog.topics, [weekend]) == []
