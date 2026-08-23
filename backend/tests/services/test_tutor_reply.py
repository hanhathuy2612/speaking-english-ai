import asyncio

from app.api.v1.conversation_handler import (
    _slices_from_word_timings,
    emit_text_chunks,
)
from app.services.lm_client import (
    first_flushable_sentence,
    format_tutor_display,
    parse_tutor_reply,
    spoken_from_stored_assistant,
    spoken_prefix_from_partial,
    split_tutor_reply,
)
from app.services.tts_service import TtsWordTiming


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


def test_spoken_prefix_from_partial() -> None:
    spoken, done = spoken_prefix_from_partial("SAY:\nNice — football sounds fun.")
    assert spoken.startswith("Nice")
    assert done is False
    spoken, done = spoken_prefix_from_partial(
        "SAY:\nNice — football sounds fun. Where do you play?\n\nNOTE:\nCâu đã ổn."
    )
    assert "Where do you play?" in spoken
    assert done is True


def test_first_flushable_sentence() -> None:
    assert (
        first_flushable_sentence("Nice.", section_done=False) is None
    )
    first = first_flushable_sentence(
        "Nice — football sounds fun. Where do you play?", section_done=False
    )
    assert first is not None
    assert first.startswith("Nice")
    assert first.endswith(".")
    assert (
        first_flushable_sentence("Too short.", section_done=True) == "Too short."
    )


def test_format_retry_note() -> None:
    display = format_tutor_display(
        "Try the same question again.",
        "Hãy nói 2 câu tiếng Anh.",
        retry=True,
    )
    assert "**Thử lại:**" in display
    assert spoken_from_stored_assistant(display) == "Try the same question again."


def test_slices_keep_punctuation() -> None:
    text = "Nice — a more natural way is: I went."
    words = [
        TtsWordTiming("Nice", 0.0, 0.2),
        TtsWordTiming("a", 0.3, 0.1),
        TtsWordTiming("more", 0.4, 0.2),
        TtsWordTiming("natural", 0.6, 0.3),
        TtsWordTiming("way", 0.9, 0.2),
        TtsWordTiming("is", 1.1, 0.1),
        TtsWordTiming("I", 1.3, 0.1),
        TtsWordTiming("went", 1.4, 0.3),
    ]
    slices = _slices_from_word_timings(text, words)
    assert slices is not None
    assert "".join(piece for piece, _ in slices) == text
    assert slices[0][0] == "Nice"
    assert slices[1][0] == " — a"
    assert slices[-1][0].endswith(".")


def test_emit_text_chunks_finish_false_omits_done() -> None:
    sent: list[dict] = []

    async def send(msg: dict) -> None:
        sent.append(msg)

    words = [
        TtsWordTiming("Hello", 0.0, 0.2),
        TtsWordTiming("there", 0.01, 0.2),
    ]
    asyncio.run(
        emit_text_chunks(
            send,
            "Hello there.",
            word_timings=words,
            finish=False,
        )
    )
    assert sent
    assert all(msg.get("done") is False for msg in sent)
    assert "".join(msg["text"] for msg in sent) == "Hello there."
