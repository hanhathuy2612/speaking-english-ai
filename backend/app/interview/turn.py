"""One conversation turn: answer -> LLM (streamed) -> TTS per sentence -> next question.

Details: docs/architecture.md.
"""

from __future__ import annotations

import asyncio
import time

from app.interview.steps import drop_earlier, mark_steps, steps_for, trim_invented
from app.interview.prompts import build_messages, safe_note, target_phrases
from app.interview.session import Session, next_step, progress, summary
from app.services import history, llm, stt, tts
from app.utils.parsing import has_cjk, ready_sentences, speech_metrics, split_sections, used_phrase_indices
from app.utils.ws import Conn

_background: set[asyncio.Task] = set()


async def start_session(conn: Conn, unit: dict) -> Session:
    first = unit["questions"][0]["ask"]
    session = Session(unit=unit, asked=first)
    public = {k: unit[k] for k in ("id", "title", "goal", "scenario")} | {
        "phrases": [{"say": p["say"]} for p in unit["phrases"]],
        "stt": stt.label,
        "partner": unit.get("partner", "Người phỏng vấn"),  # label shown on the AI's messages
        "lesson": "lesson" in unit,  # has a lesson part, linked from the practice room
    }
    await conn.json({"type": "started", "unit": public})
    await conn.json(progress(session))
    task = asyncio.create_task(tts.prewarm(unit))
    _background.add(task)
    task.add_done_callback(_background.discard)
    opening = f"{unit['greeting']} {first}"
    await conn.audio(opening, await tts.cached_tts(opening))
    await conn.json({"type": "turn_done", "can_undo": False})
    return session


def _history_id(s: Session) -> int | None:
    """Create the history row on the first answer, so opening a unit never leaves empty sessions."""
    if s.history_id is None:
        s.history_id = history.start_session(s.unit)
    return s.history_id


async def handle_user_input(
    conn: Conn,
    s: Session,
    text: str,
    words: list[dict],
    t0: float,
    t_stt: float | None,
    stt_result: dict | None = None,
) -> None:
    if s.done:
        await conn.json({"type": "error", "msg": "Phiên đã kết thúc. Chọn lại bài để tập tiếp."})
        await conn.json({"type": "turn_done"})
        return
    speech = speech_metrics(words)
    conf = stt_result["avg_logprob"] if stt_result else None
    used_now = used_phrase_indices(text, s.unit["phrases"])
    record = {
        "question": s.asked,
        "answer": text,
        "source": "voice" if stt_result else "text",
        "words": speech["words"] or None,
        "wpm": speech["wpm"],
        "wpm_speaking": speech["wpm_speaking"],
        "long_pauses": speech["long_pauses"] if words else None,
        "avg_logprob": conf,
        "no_speech": stt_result["no_speech"] if stt_result else None,
        "used_phrases": used_now,
        "audio": stt_result.get("recording") if stt_result else None,
    }
    reason = stt.unclear_reason(stt_result) if stt_result else None
    if reason:
        # Not English, or low STT confidence: do not let the LLM guess, ask the learner to repeat.
        # Still recorded (unclear=1): these rows are the data for calibrating the threshold.
        history.add_turn(
            _history_id(s),
            {**record, "unclear": 1, "used_phrases": [], "stt_ms": round(((t_stt or t0) - t0) * 1000)},
        )
        await conn.json(
            {"type": "transcript", "text": text, "speech": speech, "used": sorted(s.used),
             "unclear": True, "reason": reason, "conf": conf}
        )
        await conn.json({"type": "metrics", "stt_ms": round(((t_stt or t0) - t0) * 1000)})
        await conn.json({"type": "turn_done", "can_undo": False})
        return
    s.prev = s.snapshot()
    s.used |= set(used_now)
    if words:
        s.speech.append(speech)
    s.last_speech = speech if words else None
    await conn.json(
        {"type": "transcript", "text": text, "speech": speech, "used": sorted(s.used),
         "unclear": False, "reason": None, "conf": conf}
    )
    await conn.json({"type": "status", "msg": "thinking"})
    await run_turn(conn, s, text, t0, t_stt, record)


async def run_turn(
    conn: Conn, s: Session, user_text: str, t0: float, t_stt: float | None, record: dict
) -> None:
    q_index = s.q  # next_step may advance; the NOTE still belongs to this question
    main = s.unit["questions"][q_index]
    on_main = s.asked in (main["ask"], main["simple"])  # the steps are written for the main question
    messages = build_messages(s, user_text)
    s.history.append({"q": s.asked, "a": user_text})

    # (text, use_tts_cache); None ends the queue
    queue: asyncio.Queue[tuple[str, bool] | None] = asyncio.Queue()
    first_audio: dict[str, float] = {}

    async def tts_worker() -> None:
        # Sequential to keep sentence order, but runs concurrently with the LLM.
        while (item := await queue.get()) is not None:
            text, cached = item
            try:
                audio = await (tts.cached_tts(text) if cached else tts.tts_bytes(text))
            except Exception as e:  # noqa: BLE001
                await conn.json({"type": "error", "msg": f"TTS: {e}"})
                continue
            first_audio.setdefault("t", time.monotonic())
            await conn.audio(text, audio)

    async def say(sentences: list[str]) -> None:
        for sentence in sentences:
            # Questions come from the app, never from SAY; a sentence in Chinese is never spoken.
            if not sentence.rstrip().endswith("?") and not has_cjk(sentence):
                await queue.put((sentence, False))

    worker = asyncio.create_task(tts_worker())
    raw, emitted, t_first = "", 0, None
    secs: dict[str, str] = {}
    step: tuple[str, bool] | None = None
    try:
        async for delta in llm.stream_reply(messages):
            t_first = t_first or time.monotonic()
            raw += delta
            secs = split_sections(raw)
            say_done = "ASK" in secs or "NOTE" in secs
            sentences, emitted = ready_sentences(secs.get("SAY", ""), say_done, emitted)
            await say(sentences)
            if step is None and "NOTE" in secs:  # ASK is complete: speak the next question while the LLM writes NOTE
                step = next_step(s, secs)
                await queue.put(step)
    except Exception as e:  # noqa: BLE001
        await conn.json({"type": "error", "msg": f"LLM: {e}"})
    secs = split_sections(raw)
    if raw.strip() and not secs:
        await conn.json({"type": "error", "msg": "AI trả sai định dạng, app tự chuyển câu hỏi."})
        print("LLM output did not follow the format:", raw)
    elif raw.strip() and "SAY" not in secs:
        # The model sometimes skips SAY (about 1 turn in 30); the turn still works without a reaction.
        print("LLM output had no SAY:", raw)
    sentences, emitted = ready_sentences(secs.get("SAY", ""), True, emitted)
    await say(sentences)
    if step is None:
        step = next_step(s, secs)
        await queue.put(step)
    await queue.put(None)
    await worker

    retry = secs.get("RETRY", "").lower().startswith("yes")
    note = safe_note(s, q_index, secs.get("NOTE", ""), retry)
    steps: list[dict] = []
    s.retell_base = None
    if not retry:  # a RETRY NOTE is already a model answer to a question the learner did not answer
        said = " ".join(f"{h['q']} {h['a']}" for h in s.history)
        note = drop_earlier(note, user_text, [h["a"] for h in s.history[:-1]])
        note = trim_invented(note, said, " ".join(target_phrases(s.unit, q_index, user_text)))
        if on_main:
            steps = mark_steps(steps_for(s.unit, q_index), f"{user_text} {note}")
            s.retell_base = {
                "question": main["ask"],
                "answer": user_text,
                "speech": s.last_speech,
                "steps": steps_for(s.unit, q_index),
            }
    await conn.json({"type": "note", "text": note, "retry": retry, "steps": steps})
    await conn.json(progress(s))
    now = time.monotonic()
    ms = lambda a, b: round((a - b) * 1000) if a and b else 0  # noqa: E731
    metrics = {
        "type": "metrics",
        "stt_ms": ms(t_stt, t0),
        "llm_first_ms": ms(t_first, t_stt or t0),
        "first_audio_ms": ms(first_audio.get("t"), t0),
        "total_ms": ms(now, t0),
    }
    await conn.json(metrics)
    s.last_turn_id = history.add_turn(
        _history_id(s),
        {
            **record,
            "note": note,
            "retry": int(retry),
            "stt_ms": metrics["stt_ms"] or None,
            "first_audio_ms": metrics["first_audio_ms"] or None,
        },
    )
    if s.done:
        history.set_completed(s.history_id, True)
        await conn.json(summary(s))
    await conn.json({"type": "turn_done", "can_undo": True})
