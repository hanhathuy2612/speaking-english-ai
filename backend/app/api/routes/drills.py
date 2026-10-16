"""Pronunciation drills API (docs/features/pronunciation-drills.md): no LLM, word comparison only."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps import current_user
from app.assessment import drills
from app.services import history, recordings, stt, tts

router = APIRouter(prefix="/api/drills", tags=["drills"])

MINE_SET = {
    "id": drills.MINE,
    "title": "Câu bạn từng đọc sai",
    "measured": "",
    "tip": "Các câu mà lần đọc gần nhất máy nghe sai ít nhất một từ, lấy từ phòng tập (nói lại câu mẫu) và các nhóm "
    "luyện âm. Từ trọng tâm là những từ bị nghe sai lần đó. Đọc đúng hết thì câu tự ra khỏi danh sách.",
}


def _all_sets(uid: int) -> list[dict]:
    return [*drills.sets, {**MINE_SET, "sentences": drills.personal_sentences(history.list_readings(uid))}]


def _find(uid: int, set_id: str, sentence_id: str) -> dict:
    if set_id == drills.MINE:
        readings = history.list_readings(uid)
        x = next((x for x in drills.personal_sentences(readings) if x["id"] == sentence_id), None)
        if x:
            return x
        # Just read correctly, so it left the set: still allow a retry, with the last failed focus.
        for r in reversed(readings):
            if drills.sentence_id(r["target"]) == sentence_id and r["correct"] < r["total"]:
                return {"id": sentence_id, "text": r["target"],
                        "focus": drills.misheard_words(r["target"], r["heard"])}  # fmt: skip
        raise HTTPException(404)
    s = drills.sets_by_id.get(set_id)
    x = next((x for x in s["sentences"] if x["id"] == sentence_id), None) if s else None
    if not x:
        raise HTTPException(404)
    return x


def _link_old_recordings(attempts: list[dict]) -> None:
    """Readings saved before drills.audio existed: find their recording by time, once."""
    if not any(not a.get("audio") for a in attempts):
        return
    found = recordings.match_by_time(attempts, recordings.untranscribed(), history.recording_names())
    history.set_drill_audio(found)
    for a in attempts:
        a["audio"] = a.get("audio") or found.get(a["id"])


def _best(x: dict, by_text: dict[str, list[dict]]) -> dict | None:
    best = drills.best_reading(x["text"], x["focus"], by_text.get(x["text"], []))
    if best:
        best["target"] = x["text"]
        name = best.pop("audio")
        best["audio_url"] = f"/api/history/audio/{name}" if recordings.path_for(name) else None
    return best


@router.get("")
def drill_state(user: dict = Depends(current_user)) -> dict:
    """Sets with their sentences and, per set, recent focus-word accuracy and the best reading of each
    sentence (`best`: sentence id -> result), so past readings show again when the page opens."""
    attempts = history.list_drills(user["id"])
    _link_old_recordings(attempts)
    by_set: dict[str, list[dict]] = {}
    by_text: dict[str, list[dict]] = {}
    for a in attempts:
        by_set.setdefault(a["set_id"], []).append(a)
        by_text.setdefault(a["target"], []).append(a)
    sets = []
    for s in _all_sets(user["id"]):
        best = {x["id"]: b for x in s["sentences"] if (b := _best(x, by_text))}
        sets.append({**s, **drills.focus_accuracy(by_set.get(s["id"], [])), "best": best})
    return {
        "enabled": history.enabled(),
        "window": drills.WINDOW,
        "recent": drills.focus_accuracy(attempts),
        "sets": sets,
    }


@router.get("/{set_id}/{sentence_id}/audio")
async def drill_audio(
    set_id: str, sentence_id: str, slow: bool = False, user: dict = Depends(current_user)
) -> Response:
    x = _find(user["id"], set_id, sentence_id)
    audio = await tts.cached_tts(x["text"], tts.SLOW_RATE if slow else None)
    return Response(audio, media_type="audio/mpeg")


@router.post("/{set_id}/{sentence_id}")
async def drill_submit(set_id: str, sentence_id: str, request: Request, user: dict = Depends(current_user)) -> dict:
    x = _find(user["id"], set_id, sentence_id)
    path = stt.save_recording(await request.body())
    try:
        # No initial prompt: vocabulary hints would pull Whisper towards the expected words and hide
        # the very mistakes this drill is about (same as shadowing).
        result = await asyncio.to_thread(stt.transcribe, path, "")
    finally:
        stt.finish_recording(path, None)
    report = drills.score(x["text"], x["focus"], result["text"])
    if result["text"]:  # an empty reading is a microphone problem, not a pronunciation result
        history.add_drill(
            user["id"],
            {
                "set_id": set_id,
                "target": x["text"],
                "heard": result["text"],
                "correct": report["correct"],
                "total": report["total"],
                "focus_correct": report["focus_correct"],
                "focus_total": report["focus_total"],
                "avg_logprob": result["avg_logprob"],
                "audio": stt.kept_name(path),
            }
        )
    return {"target": x["text"], "heard": result["text"], **report}
