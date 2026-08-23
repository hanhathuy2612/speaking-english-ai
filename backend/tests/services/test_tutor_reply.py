from app.services.lm_client import (
    format_tutor_display,
    parse_tutor_reply,
    spoken_from_stored_assistant,
    split_tutor_reply,
)


def test_split_tutor_reply_say_note() -> None:
    spoken, note = split_tutor_reply(
        "SAY:\nNice — a more natural way is: I went last weekend. What did you do?\n\n"
        "NOTE:\nDùng quá khứ \"went\" vì có last weekend."
    )
    assert spoken.startswith("Nice")
    assert "went" in spoken
    assert "Dùng quá khứ" in note


def test_split_tutor_reply_without_say_label() -> None:
    spoken, note = split_tutor_reply(
        "That sounds fun. Where did you go?\n\nNOTE: Câu đã ổn. Thử thêm because để nói lý do."
    )
    assert spoken == "That sounds fun. Where did you go?"
    assert "because" in note


def test_split_tutor_reply_plain_text() -> None:
    spoken, note = split_tutor_reply("Hi! What would you like to talk about?")
    assert spoken == "Hi! What would you like to talk about?"
    assert note == ""


def test_format_and_strip_stored_note() -> None:
    display = format_tutor_display(
        "Nice idea. What happened next?",
        'Nên nói "I went" vì đây là quá khứ.',
    )
    assert display.startswith("Nice idea.")
    assert "**Lưu ý:**" in display
    assert spoken_from_stored_assistant(display) == "Nice idea. What happened next?"


def test_parse_tutor_reply_retry() -> None:
    spoken, note, retry = parse_tutor_reply(
        "SAY:\nThat was too short. Try again: What do you usually do on weekends?\n\n"
        "NOTE:\nCâu quá ngắn. Hãy nói 2 câu: việc bạn làm + một lý do. "
        'Ví dụ: "I usually play football because it is fun."\n\n'
        "RETRY:\nyes"
    )
    assert "Try again" in spoken
    assert "Câu quá ngắn" in note
    assert retry is True


def test_parse_tutor_reply_no_retry() -> None:
    spoken, note, retry = parse_tutor_reply(
        "SAY:\nNice — football sounds fun. Where do you play?\n\n"
        "NOTE:\nCâu đã đủ ý. Có thể thêm where/when.\n\n"
        "RETRY:\nno"
    )
    assert spoken.startswith("Nice")
    assert retry is False
    assert "RETRY" not in note


def test_format_retry_note() -> None:
    display = format_tutor_display(
        "Try the same question again.",
        "Hãy nói 2 câu tiếng Anh.",
        retry=True,
    )
    assert "**Thử lại:**" in display
    assert spoken_from_stored_assistant(display) == "Try the same question again."
