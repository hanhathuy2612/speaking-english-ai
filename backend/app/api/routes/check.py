"""Speaking check API (docs/features/speaking-check.md): no LLM in the check itself, objective metrics only.

After a check is scored, the learner can learn from it (docs/features/talk-lessons.md): an AI review
of their own talk, review cards for the phrases they lacked, and a retry of the same question. None
of that changes the check's numbers or counts as a check, and a prompt studied this way is not
given in later checks.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from openai import OpenAIError
from pydantic import BaseModel, Field

from app.api.deps import current_user
from app.assessment import check
from app.assessment.metrics import measure
from app.core.config import STT_VOCAB
from app.interview import check_review, talks
from app.services import history, stt

router = APIRouter(prefix="/api/check", tags=["check"])


def _targets() -> dict:
    return {
        "seconds": check.TARGET_SECONDS,
        "wpm_speaking": check.TARGET_WPM_SPEAKING,
        "hesitations_per_100": check.TARGET_HESITATIONS_PER_100,
    }


def _talk_for(prompt: dict) -> dict | None:
    """The talk lesson for this kind of question."""
    talk = talks.talks_by_id.get(prompt.get("kind", ""))
    return talks.summary(talk) if talk else None


@router.get("")
async def check_state(exclude: str | None = None, user: dict = Depends(current_user)) -> dict:
    """A fresh prompt (least used, not studied, not `exclude`), the targets, past checks and the talk lessons."""
    past = history.list_checks(user["id"])
    used = Counter(c["prompt_id"] for c in past)
    lessons = history.lesson_counts(user["id"])
    practice = Counter(r["ref"] for r in history.list_talk_practice(user["id"], source="talk"))
    return {
        "enabled": history.enabled(),
        "prompt": check.pick_prompt(used, exclude, history.studied_check_prompts(user["id"])),
        "targets": _targets(),
        "checks": past,
        "talks": [
            {**talks.summary(t), "finished": lessons.get(talks.PREFIX + t["id"], 0), "practiced": practice[t["id"]]}
            for t in talks.talks
        ],
    }


async def _transcribe(request: Request) -> dict:
    path = stt.save_recording(await request.body())
    try:
        return await asyncio.to_thread(stt.transcribe, path, STT_VOCAB)
    finally:
        stt.finish_recording(path, None)


@router.post("/{prompt_id}")
async def check_submit(prompt_id: str, request: Request, user: dict = Depends(current_user)) -> dict:
    prompt = check.prompts_by_id.get(prompt_id)
    if not prompt:
        raise HTTPException(404)
    result = await _transcribe(request)
    not_english = stt.unclear_reason(result) == "not_english"
    report = check.evaluate(result["words"], not_english)
    stuck = check.stuck_points(result["words"])
    # Speed and hesitation are only stored when they were judged, so trends compare like with like.
    judged = report["measurable"]
    check_id = history.add_check(
        user["id"],
        {
            "prompt_id": prompt_id,
            "prompt": prompt["text"],
            "text": result["text"],
            "words": report["words"],
            "duration_s": report["duration_s"],
            "wpm": report["wpm"],
            "wpm_speaking": report["wpm_speaking"] if judged else None,
            "hesitations": report["hesitations"],
            "hesitations_per_100": report["hesitations_per_100"] if judged else None,
            "not_english": int(not_english),
            "avg_logprob": result["avg_logprob"],
            "passed": report["passed"],
            "total": len(report["criteria"]),
            "stuck": json.dumps(stuck, ensure_ascii=False),
        },
    )
    return {"id": check_id, "prompt": prompt, "text": result["text"], **report, "stuck": stuck, "talk": _talk_for(prompt)}


# ----- Learning from a check (after it is scored) -----


def _get(check_id: int, user: dict = Depends(current_user)) -> dict:
    row = history.get_check(user["id"], check_id)
    if not row:
        raise HTTPException(404)
    return row


@router.post("/{check_id}/review")
async def review_check(row: dict = Depends(_get)) -> dict:
    """The AI review of this talk, made once and kept. From then on the prompt counts as studied."""
    if row["review"]:
        return row["review"]
    if not row["text"].strip():
        raise HTTPException(400, "Bài nói không có chữ nào để ôn lại.")
    try:
        review = await check_review.review(row["prompt"], row["text"], row["stuck"])
    except (ValueError, KeyError) as e:  # a reply that is not the expected JSON
        raise HTTPException(502, f"AI trả kết quả không đọc được, thử lại nhé ({e}).") from None
    except OpenAIError as e:
        raise HTTPException(502, f"Không gọi được LM Studio: {e}") from None
    history.set_check_review(row["id"], review)
    return review


class Phrases(BaseModel):
    phrases: list[str] = Field(min_length=1, max_length=check_review.MAX_PHRASES + 10)


@router.post("/{check_id}/cards")
async def check_cards(body: Phrases, row: dict = Depends(_get), user: dict = Depends(current_user)) -> dict:
    """Review cards for the chosen phrases of the review (card kind 'talk', docs/features/review.md)."""
    if not row["review"]:
        raise HTTPException(400, "Chưa có bản ôn của bài kiểm tra này.")
    known = {p["say"]: p for p in row["review"]["phrases"]}
    have = {c["target"] for c in history.list_cards(user["id"]) if c["kind"] == "talk"}
    added = 0
    for say in dict.fromkeys(body.phrases):
        if say in known and say not in have:
            card = {
                "kind": "talk", "unit_id": f"check:{row['prompt_id']}", "question": row["prompt"],
                "said": known[say]["vi"], "target": say, "due": date.today().isoformat(),
            }  # fmt: skip
            added += history.add_card(user["id"], card) is not None
    return {"added": added}


@router.post("/{check_id}/retry")
async def check_retry(request: Request, row: dict = Depends(_get), user: dict = Depends(current_user)) -> dict:
    """The same question again after studying it: measured like a check, stored as practice only."""
    result = await _transcribe(request)
    not_english = stt.unclear_reason(result) == "not_english"
    m = measure(result["words"], not_english)
    history.add_talk_practice(
        user["id"],
        {
            "source": "check", "ref": str(row["id"]), "prompt_id": row["prompt_id"], "prompt": row["prompt"],
            "text": result["text"], "words": m["words"], "duration_s": m["duration_s"],
            "wpm_speaking": m["wpm_speaking"] if m["measurable"] else None, "hesitations": m["hesitations"],
            "hesitations_per_100": m["hesitations_per_100"] if m["measurable"] else None,
        },
    )  # fmt: skip
    first = {k: row[k] for k in ("duration_s", "wpm_speaking", "hesitations_per_100", "words")}
    return {"text": result["text"], **m, "stuck": check.stuck_points(result["words"]), "first": first}
