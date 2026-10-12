"""Answer the same question again, longer, using the steps shown under the NOTE.

No LLM call and the interview does not advance. See docs/features/answer-steps.md.
"""

from __future__ import annotations

from app.interview.session import Session
from app.interview.steps import mark_steps
from app.services import history
from app.utils.parsing import speech_metrics
from app.utils.ws import Conn


async def handle_retell(conn: Conn, s: Session, result: dict, stt_ms: int) -> None:
    base, s.retell = s.retell_base, False  # one attempt per request
    assert base is not None, "retell without a previous answer"
    speech = speech_metrics(result["words"])
    steps = mark_steps(base["steps"], result["text"])
    first = len(base["answer"].split())
    await conn.json(
        {
            "type": "retell_result",
            "heard": result["text"],
            "speech": speech,
            "original": base["speech"],  # None if the first answer was typed
            "original_words": first,
            "steps": steps,
            "stt_ms": stt_ms,
        }
    )
    if s.history_id is not None:
        history.add_retell(
            s.history_id,
            {
                "question": base["question"],
                "answer": result["text"],
                "words": speech["words"],
                "original_words": first,
                "steps_done": sum(st["done"] for st in steps),
                "steps_total": len(steps),
                "wpm_speaking": speech["wpm_speaking"],
                "long_pauses": speech["long_pauses"],
            },
        )
    await conn.json({"type": "turn_done", "can_undo": s.prev is not None})
