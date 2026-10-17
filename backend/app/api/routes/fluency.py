"""4/3/2 fluency exercise API (docs/features/fluency-432.md): no LLM, objective metrics only."""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import current_user
from app.assessment import fluency
from app.assessment.metrics import measure
from app.core.config import STT_VOCAB
from app.services import history, stt

router = APIRouter(prefix="/api/fluency", tags=["fluency"])


@router.get("")
def fluency_state(exclude: str | None = None, user: dict = Depends(current_user)) -> dict:
    """A fresh prompt (least used, not `exclude`), the round lengths and past exercises."""
    runs = fluency.group_runs(history.list_fluency_rounds(user["id"]))
    used = Counter(r["prompt_id"] for r in runs)
    return {
        "enabled": history.enabled(),
        "prompt": fluency.pick_prompt(used, exclude),
        "rounds": fluency.ROUNDS,
        "runs": runs,
    }


@router.post("/{prompt_id}/{round_no}")
async def fluency_submit(
    prompt_id: str, round_no: int, request: Request, run: str | None = Query(None, max_length=100), user: dict = Depends(current_user)
) -> dict:
    """One round. Round 1 starts a new exercise and returns its `run` id; rounds 2 and 3 pass it back."""
    prompt = fluency.prompts_by_id.get(prompt_id)
    if not prompt or not 1 <= round_no <= len(fluency.ROUNDS):
        raise HTTPException(404)
    if round_no > 1 and not run:
        raise HTTPException(400, "run is required after round 1")
    run = run or uuid.uuid4().hex[:12]
    path = stt.save_recording(await request.body())
    try:
        result = await asyncio.to_thread(stt.transcribe, path, STT_VOCAB)
    finally:
        stt.finish_recording(path, None)
    not_english = stt.unclear_reason(result) == "not_english"
    m = measure(result["words"], not_english)
    judged = m["measurable"]
    history.add_fluency_round(
        user["id"],
        {
            "run": run,
            "round": round_no,
            "limit_s": fluency.ROUNDS[round_no - 1],
            "prompt_id": prompt_id,
            "prompt": prompt["text"],
            "text": result["text"],
            "words": m["words"],
            "duration_s": m["duration_s"],
            "wpm_speaking": m["wpm_speaking"] if judged else None,
            "hesitations": m["hesitations"],
            "hesitations_per_100": m["hesitations_per_100"] if judged else None,
            "not_english": int(not_english),
        }
    )
    return {"run": run, "round": round_no, "limit_s": fluency.ROUNDS[round_no - 1], "text": result["text"], **m}
