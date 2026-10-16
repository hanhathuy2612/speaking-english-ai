"""Lesson part of a unit (docs/features/lesson.md): teacher lines, their audio, and reading a sentence aloud.

No LLM: the page plays fixed lines and each reading is judged by word comparison only.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps import current_user
from app.core import config
from app.interview import lesson
from app.interview.units import units_by_id
from app.services import history, stt, tts
from app.utils.compare import compare

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


def _unit(unit_id: str) -> dict:
    unit = units_by_id.get(unit_id)
    if not unit or "lesson" not in unit:
        raise HTTPException(404)
    return unit


@router.get("/{unit_id}")
def get_lesson(unit_id: str, user: dict = Depends(current_user)) -> dict:
    unit = _unit(unit_id)
    return {**lesson.public(unit), "finished": history.lesson_counts(user["id"]).get(unit_id, 0)}


@router.get("/{unit_id}/audio/{key}")
async def lesson_audio(unit_id: str, key: str) -> Response:
    line = lesson.lines(_unit(unit_id)).get(key)
    if not line:
        raise HTTPException(404)
    audio = await tts.cached_tts(line["en"], voice=config.TTS_TEACHER_VOICE)
    return Response(audio, media_type="audio/mpeg")


@router.post("/{unit_id}/read/{index}")
async def read_sentence(unit_id: str, index: int, request: Request, user: dict = Depends(current_user)) -> dict:
    sentences = _unit(unit_id)["lesson"]["sentences"]
    if not 0 <= index < len(sentences):
        raise HTTPException(404)
    target = sentences[index]["say"]
    path = stt.save_recording(await request.body())
    try:
        # No initial prompt: it would pull Whisper towards the expected words (same as shadowing).
        result = await asyncio.to_thread(stt.transcribe, path, "")
    finally:
        stt.finish_recording(path, None)
    diff = compare(target, result["text"])
    if result["text"]:  # an empty reading is a microphone problem, not a pronunciation result
        history.add_lesson_read(
            user["id"],
            {
                "unit_id": unit_id,
                "sentence": index,
                "target": target,
                "heard": result["text"],
                "correct": diff["correct"],
                "total": diff["total"],
                "avg_logprob": result["avg_logprob"],
            }
        )
    return {"target": target, "heard": result["text"], "compare": diff}


@router.post("/{unit_id}/finish")
def finish(unit_id: str, user: dict = Depends(current_user)) -> dict:
    _unit(unit_id)
    history.finish_lesson(user["id"], unit_id)
    return {"finished": history.lesson_counts(user["id"]).get(unit_id, 0)}
