"""Talk lessons API (docs/features/talk-lessons.md): the lesson, its teacher audio, reading a sentence,
and two-minute practice talks. No LLM: fixed lines, word comparison and objective metrics only.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps import current_user
from app.assessment.check import stuck_points
from app.assessment.metrics import measure
from app.core import config
from app.core.config import STT_VOCAB
from app.interview import lesson, talks
from app.interview.steps import mark_steps
from app.services import history, stt, tts
from app.utils.compare import compare

router = APIRouter(prefix="/api/talks", tags=["talks"])


def _talk(talk_id: str) -> dict:
    talk = talks.talks_by_id.get(talk_id)
    if not talk:
        raise HTTPException(404)
    return talk


def _finished(uid: int, talk: dict) -> int:
    return history.lesson_counts(uid).get(talks.PREFIX + talk["id"], 0)


@router.get("/{talk_id}")
def get_talk(talk_id: str, user: dict = Depends(current_user)) -> dict:
    """The lesson (as for a unit), the frame, the practice prompts and past practice talks."""
    talk = _talk(talk_id)
    return {
        **talks.public(talk, _finished(user["id"], talk)),
        "attempts": history.list_talk_practice(user["id"], source="talk", ref=talk_id),
    }


@router.get("/{talk_id}/audio/{key}")
async def talk_audio(talk_id: str, key: str) -> Response:
    line = lesson.lines(talks.as_unit(_talk(talk_id))).get(key)
    if not line:
        raise HTTPException(404)
    return Response(await tts.cached_tts(line["en"], voice=config.TTS_TEACHER_VOICE), media_type="audio/mpeg")


async def _transcribe(request: Request, prompt: str) -> dict:
    path = stt.save_recording(await request.body())
    try:
        return await asyncio.to_thread(stt.transcribe, path, prompt)
    finally:
        stt.finish_recording(path, None)


@router.post("/{talk_id}/read/{index}")
async def read_sentence(talk_id: str, index: int, request: Request, user: dict = Depends(current_user)) -> dict:
    talk = _talk(talk_id)
    sentences = talk["lesson"]["sentences"]
    if not 0 <= index < len(sentences):
        raise HTTPException(404)
    target = sentences[index]["say"]
    result = await _transcribe(request, "")  # no prompt: it would hide reading mistakes (lessons.py)
    diff = compare(target, result["text"])
    if result["text"]:
        history.add_lesson_read(
            user["id"],
            {
                "unit_id": talks.PREFIX + talk_id, "sentence": index, "target": target, "heard": result["text"],
                "correct": diff["correct"], "total": diff["total"], "avg_logprob": result["avg_logprob"],
            },
        )  # fmt: skip
    return {"target": target, "heard": result["text"], "compare": diff}


@router.post("/{talk_id}/finish")
def finish(talk_id: str, user: dict = Depends(current_user)) -> dict:
    talk = _talk(talk_id)
    history.finish_lesson(user["id"], talks.PREFIX + talk_id)
    return {"finished": _finished(user["id"], talk)}


@router.post("/{talk_id}/practice/{prompt_id}")
async def practice(talk_id: str, prompt_id: str, request: Request, user: dict = Depends(current_user)) -> dict:
    """A two-minute practice talk with the frame: measured like a check, plus which frame steps were said.
    Stored as practice, never as a check."""
    talk = _talk(talk_id)
    prompt = talks.practice_prompt(talk, prompt_id)
    if not prompt:
        raise HTTPException(404)
    result = await _transcribe(request, STT_VOCAB)
    not_english = stt.unclear_reason(result) == "not_english"
    m = measure(result["words"], not_english)
    steps = mark_steps(talk["frame"], result["text"])
    previous = history.list_talk_practice(user["id"], source="talk", ref=talk_id)
    history.add_talk_practice(
        user["id"],
        {
            "source": "talk", "ref": talk_id, "prompt_id": prompt_id, "prompt": prompt["text"],
            "text": result["text"], "words": m["words"], "duration_s": m["duration_s"],
            "wpm_speaking": m["wpm_speaking"] if m["measurable"] else None, "hesitations": m["hesitations"],
            "hesitations_per_100": m["hesitations_per_100"] if m["measurable"] else None,
            "steps_done": sum(st["done"] for st in steps), "steps_total": len(steps),
        },
    )  # fmt: skip
    return {
        "text": result["text"], **m, "steps": steps, "stuck": stuck_points(result["words"]),
        "previous": previous[-1] if previous else None,
    }  # fmt: skip
