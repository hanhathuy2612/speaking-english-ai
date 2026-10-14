"""Learn from a speaking check you just did (docs/features/talk-lessons.md).

Only after the check is scored: its numbers never change. The LLM rewrites the learner's own talk
in natural English (their points, nothing added), suggests how each sentence they got stuck in
could go on, and picks the phrases they were missing. It writes suggestions, it never grades.
Facts the model added anyway (a number, a day, a time unit) are reported next to the rewrite.
"""

from __future__ import annotations

import json

from app.services import llm
from app.utils.compare import invented_facts
from app.utils.parsing import has_vietnamese

MAX_TOKENS = 1500
MAX_PHRASES = 6

_str = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "better": _str,
        "stuck": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"n": {"type": "integer"}, "say": _str},
                "required": ["n", "say"],
                "additionalProperties": False,
            },
        },
        "phrases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"say": _str, "vi": _str},
                "required": ["say", "vi"],
                "additionalProperties": False,
            },
            "minItems": 3,
            "maxItems": MAX_PHRASES,
        },
    },
    "required": ["better", "stuck", "phrases"],
    "additionalProperties": False,
}

SYSTEM = """You help a Vietnamese software developer who is learning to speak English. They just talked for up to two minutes about a question, and speech recognition wrote down what they said.

Reply with JSON:
- better: their WHOLE talk said again in natural, correct spoken English (B1 to B2 level): every point they made, in the same order, a little longer is fine. Join their ideas with linking phrases (The main reason is that..., For example..., On the other hand..., So overall...). Keep their opinion and every detail exactly. Never add a fact, number, name, example or reason they did not say. A word that makes no sense was probably misheard: use the word the context clearly means.
- stuck: for each numbered place where they stopped in the middle of a sentence, n is its number and say is the complete sentence as they could have finished it, starting with their words before the pause (fixed if wrong), in their own meaning.
- phrases: 3 to 6 useful English phrases or sentence frames that they were missing and can reuse in other talks, like "On the other hand, ..." or "rely on". vi is the meaning in Vietnamese.
All English fields must be English only."""


def _user_message(question: str, text: str, stuck: list[dict]) -> str:
    places = "\n".join(f"{i + 1}. ...{s['before']} [pause {s['pause_s']} s] {s['after']}..." for i, s in enumerate(stuck))
    return f"Question: {question}\n\nWhat they said:\n{text}\n\nPlaces where they got stuck:\n{places or '(none)'}"


def fix(raw: dict, text: str, stuck: list[dict]) -> dict:
    """Keep what the page can show: suggestions matched to real stuck places, English phrases only,
    and the facts the rewrite added that the learner never said."""
    by_n = {s["n"]: s["say"].strip() for s in raw["stuck"] if 1 <= s["n"] <= len(stuck) and s["say"].strip()}
    phrases = [
        {"say": p["say"].strip(), "vi": p["vi"].strip()}
        for p in raw["phrases"]
        if p["say"].strip() and not has_vietnamese(p["say"])
    ][:MAX_PHRASES]
    better = raw["better"].strip()
    return {
        "better": better,
        "stuck": [{**s, "say": by_n.get(i + 1)} for i, s in enumerate(stuck)],
        "phrases": phrases,
        "added_facts": invented_facts(better, text),
    }


async def review(question: str, text: str, stuck: list[dict]) -> dict:
    """{better, stuck: [{before, after, pause_s, say}], phrases: [{say, vi}], added_facts}."""
    raw = await llm.complete_json(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _user_message(question, text, stuck)}],
        SCHEMA,
        MAX_TOKENS,
        temperature=0.4,
    )
    return fix(json.loads(raw), text, stuck)
