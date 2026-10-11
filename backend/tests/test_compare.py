"""Word-by-word comparison used by shadowing and the STT benchmark."""

from app.utils.compare import compare, number_words, tokens, wer, invented_facts


def statuses(result):
    return [(i["text"], i["status"], i.get("heard")) for i in result["items"] if i["kind"] == "word"]


def test_number_words():
    assert number_words(5) == ["five"]
    assert number_words(30) == ["thirty"]
    assert number_words(10000) == ["ten", "thousand"]
    assert number_words(125) == ["one", "hundred", "twenty", "five"]


def test_writing_differences_are_not_mistakes():
    assert tokens("I've worked 5 years, 30% faster.") == tokens("I have worked five years thirty percent faster")
    assert tokens("about 10,000 users") == ["about", "ten", "thousand", "users"]
    assert tokens("follow-up") == ["follow", "up"]
    r = compare("I've been working as a Java developer for five years.", "I have been working as a java developer for 5 years")
    assert r["accuracy"] == 1.0 and all(s == "ok" for _, s, _ in statuses(r))


def test_real_mistakes_from_the_users_recordings():
    # dropped plural -s and a mispronounced "cache", both seen in the user's bench recordings
    r = compare("So I decided to add a cache for our customers.", "So I decide to add a kit for our customer.")
    assert statuses(r) == [
        ("So", "ok", None), ("I", "ok", None), ("decided", "wrong", "decide"), ("to", "ok", None),
        ("add", "ok", None), ("a", "ok", None), ("cache", "wrong", "kit"), ("for", "ok", None),
        ("our", "ok", None), ("customers.", "wrong", "customer"),
    ]  # fmt: skip
    assert r["correct"] == 7 and r["total"] == 10


def test_missing_and_extra_words():
    r = compare("It reduced the response time.", "um it reduced response time a lot")
    items = r["items"]
    assert items[0] == {"kind": "extra", "text": "um"}
    assert ("the", "miss", None) in statuses(r)
    assert items[-1] == {"kind": "extra", "text": "a lot"}


def test_contraction_partially_said_is_wrong_not_missing():
    r = compare("I'm responsible for payments.", "I responsible for payments")
    assert statuses(r)[0] == ("I'm", "wrong", "i")


def test_wer_ignores_number_formatting():
    assert wer("about ten thousand users", "about 10,000 users") == 0
    assert wer("I've been working as a developer", "I've been booking a shop") == 3 / 7


def test_invented_facts_finds_changed_days_and_numbers():
    said = "It should be ready by Thursday if the design come tomorrow."
    assert invented_facts("It should be ready by Thursday if the design comes in on Friday.", said) == ["friday"]
    assert invented_facts("It should be ready by Thursday if the design arrives tomorrow.", said) == []


def test_invented_facts_matches_digits_and_words():
    assert invented_facts("It cut late requests by 30% in 5 days.", "thirty percent in five days") == []
    assert invented_facts("We have 12 services.", "we have ten services") == ["twelve"]
    assert invented_facts("One of my main achievements was this.", "nothing numeric") == []  # "one" is ignored
