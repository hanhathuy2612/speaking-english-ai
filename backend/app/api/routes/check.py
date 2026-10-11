"""Speaking check API (docs/features/speaking-check.md): no LLM, objective metrics only."""

from __future__ import annotations

import asyncio
from collections import Counter

from fastapi import APIRouter, HTTPException, Request

from app.assessment import check
from app.core.config import STT_VOCAB
from app.services import history, stt

router = APIRouter(prefix="/api/check", tags=["check"])


def _targets() -> dict:
    return {
        "seconds": check.TARGET_SECONDS,
        "wpm_speaking": check.TARGET_WPM_SPEAKING,
        "hesitations_per_100": check.TARGET_HESITATIONS_PER_100,
    }


@router.get("")
async def check_state(exclude: str | None = None) -> dict:
    """A fresh prompt (least used, not `exclude`), the targets and past checks."""
    past = history.list_checks()
    used = Counter(c["prompt_id"] for c in past)
    return {
        "enabled": history.enabled(),
        "prompt": check.pick_prompt(used, exclude),
        "targets": _targets(),
        "checks": past,
    }


@router.post("/{prompt_id}")
async def check_submit(prompt_id: str, request: Request) -> dict:
    prompt = check.prompts_by_id.get(prompt_id)
    if not prompt:
        raise HTTPException(404)
    path = stt.save_recording(await request.body())
    try:
        result = await asyncio.to_thread(stt.transcribe, path, STT_VOCAB)
    finally:
        stt.finish_recording(path, None)
    not_english = stt.unclear_reason(result) == "not_english"
    report = check.evaluate(result["words"], not_english)
    # Speed and hesitation are only stored when they were judged, so trends compare like with like.
    judged = report["measurable"]
    history.add_check(
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
        }
    )
    return {"prompt": prompt, "text": result["text"], **report}
