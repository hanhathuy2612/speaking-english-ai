"""Read-aloud page API: records audio with a known reference text for scripts/stt_bench.py.

See docs/features/stt-benchmark.md.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from app.core.config import BENCH_DIR, DATA_DIR

router = APIRouter(prefix="/api/bench", tags=["bench"])
sentences: list[str] = json.loads((DATA_DIR / "bench_sentences.json").read_text(encoding="utf-8"))


@router.get("")
def bench_list() -> list[dict]:
    return [
        {"text": t, "done": (BENCH_DIR / f"{i:02d}.webm").exists()} for i, t in enumerate(sentences)
    ]


@router.post("/{i}")
async def bench_save(i: int, request: Request) -> dict:
    if not 0 <= i < len(sentences):
        raise HTTPException(404)
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    (BENCH_DIR / f"{i:02d}.webm").write_bytes(await request.body())
    (BENCH_DIR / f"{i:02d}.ref.txt").write_text(sentences[i], encoding="utf-8")
    return {"ok": True}
