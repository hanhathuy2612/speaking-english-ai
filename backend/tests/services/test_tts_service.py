from app.services.tts_service import (
    looks_vietnamese,
    plan_tts_parts,
    split_spoken_chunks,
    vi_voice_for,
)


def test_split_spoken_chunks_sentences_and_recast() -> None:
    chunks = split_spoken_chunks(
        "Nice. A more natural way is: I went last weekend. What did you do?"
    )
    assert chunks[0] == "Nice."
    assert chunks[1].endswith(":")
    assert "I went last weekend." in chunks
    assert chunks[-1] == "What did you do?"


def test_split_keeps_abbreviation() -> None:
    assert split_spoken_chunks("I like tea, e.g. green tea.") == [
        "I like tea, e.g. green tea."
    ]


def test_looks_vietnamese() -> None:
    assert looks_vietnamese("Câu quá ngắn. Hãy nói hai câu.")
    assert not looks_vietnamese("That sounds great. What happened next?")


def test_plan_inserts_vietnamese_note() -> None:
    parts = plan_tts_parts(
        "That was too short. Try again: What do you usually do?",
        voice="en-US-JennyNeural",
        extra_text="Hãy nói hai câu tiếng Anh.",
        extra_voice="vi-VN-HoaiMyNeural",
    )
    assert len(parts) == 2
    assert parts[0].voice == "en-US-JennyNeural"
    assert parts[-1].voice == "vi-VN-HoaiMyNeural"
    assert parts[-1].text.startswith("Hãy nói")
    assert parts[-1].pause_before_sec > 0


def test_vi_voice_gender() -> None:
    assert vi_voice_for("en-US-JennyNeural") == "vi-VN-HoaiMyNeural"
    assert vi_voice_for("en-US-GuyNeural") == "vi-VN-NamMinhNeural"
