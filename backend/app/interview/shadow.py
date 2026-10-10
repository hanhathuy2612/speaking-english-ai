"""Shadowing: the learner reads the NOTE sentence aloud and sees which words were heard differently.

No LLM call and the interview does not advance. See docs/features/shadowing.md.
"""

from __future__ import annotations

from app.interview.session import Session
from app.services import history
from app.utils.compare import compare
from app.utils.parsing import speech_metrics
from app.utils.ws import Conn


async def handle_shadow(conn: Conn, s: Session, result: dict, stt_ms: int) -> None:
    target, s.shadow_target = s.shadow_target or "", None  # one attempt per request
    diff = compare(target, result["text"])
    speech = speech_metrics(result["words"])
    await conn.json(
        {
            "type": "shadow_result",
            "target": target,
            "heard": result["text"],
            "compare": diff,
            "speech": speech,
            "original": s.last_speech,  # metrics of the answer that produced this NOTE (None if typed)
            "stt_ms": stt_ms,
        }
    )
    if s.history_id is not None:
        history.add_shadow(
            s.history_id,
            {
                "target": target,
                "heard": result["text"],
                "correct": diff["correct"],
                "total": diff["total"],
                "words": speech["words"],
                "wpm_speaking": speech["wpm_speaking"],
                "long_pauses": speech["long_pauses"],
                "avg_logprob": result["avg_logprob"],
            },
        )
    await conn.json({"type": "turn_done", "can_undo": s.prev is not None})
