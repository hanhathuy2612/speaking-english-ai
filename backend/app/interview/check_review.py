"""Learn from a speaking check you just did (docs/features/talk-lessons.md).

Only after the check is scored: its numbers never change. The LLM rewrites the learner's own talk
in natural English (their points, nothing added), suggests how each sentence they got stuck in
could go on, and picks the phrases they were missing. It writes suggestions, it never grades.
Each rewritten sentence must quote the words it comes from. A sentence whose quote was never said,
or that shares too few words with its quote, is marked `unsure` (the model probably added an idea),
and facts it added anyway (a number, a day, a time unit) are reported next to the rewrite.
"""

from __future__ import annotations

import json
import re

from app.services import llm
from app.utils.compare import invented_facts, tokens
from app.utils.parsing import has_vietnamese

MAX_TOKENS = 1500
MAX_PHRASES = 6
# A rewritten sentence needs this share of its content words in the words it quotes (stems: 4 letters).
# Real review of 14/10/2026: an added "AI can generate code quickly, which saves a lot of time" had 0%,
# real rewrites like "we need to be cautious and review the generated code" had 33% or more.
MIN_SUPPORT = 0.25
QUOTE_FOUND = 0.6  # share of the quote's words that must be in the talk

# Small words and linking words the rewrite is asked to add; they say nothing about the content.
FILLER = set(
    """a an the and or but so if then than that this these those there here it its it's is are was were be been being
    am do does did have has had will would can could should must might may i we you they he she me us them my our your
    their his her of in on at to for from with by about as into over not no very really just also too more most much
    many some any all lot lots one way ways thing things think believe feel say said get got make makes made because
    which who what when where why how while however instance example overall reason main hand other another first
    second finally actually well quite like such both even still need needs""".split()
)

_str = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"say": _str, "from": _str},
                "required": ["say", "from"],
                "additionalProperties": False,
            },
        },
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
    "required": ["sentences", "stuck", "phrases"],
    "additionalProperties": False,
}

SYSTEM = """You help a Vietnamese software developer who is learning to speak English. They just talked for up to two minutes about a question, and speech recognition wrote down what they said.

Reply with JSON:
- sentences: their WHOLE talk said again in natural, correct spoken English (B1 to B2 level), one item per sentence: every point they made, in the same order. say is the new sentence. from is the exact words from what they said that this sentence is based on. Join their ideas with linking phrases (The main reason is that..., For example..., On the other hand..., So overall...). Keep their opinion and every detail exactly. Never add a fact, number, name, example or reason they did not say: every sentence must come from their words. A word that makes no sense was probably misheard: use the word the context clearly means.
- stuck: for each numbered place where they stopped in the middle of a sentence, n is its number and say is the complete sentence as they could have finished it, starting with their words before the pause (fixed if wrong), in their own meaning.
- phrases: 3 to 6 useful English phrases or sentence frames that they were missing and can reuse in other talks, like "On the other hand, ..." or "rely on". vi is the meaning in Vietnamese.
All English fields must be English only."""


def _user_message(question: str, text: str, stuck: list[dict]) -> str:
    places = "\n".join(f"{i + 1}. ...{s['before']} [pause {s['pause_s']} s] {s['after']}..." for i, s in enumerate(stuck))
    return f"Question: {question}\n\nWhat they said:\n{text}\n\nPlaces where they got stuck:\n{places or '(none)'}"


def _stems(text: str) -> set[str]:
    return {t[:4] for t in tokens(text) if t not in FILLER and len(t) > 2}


def supported(say: str, quote: str, text: str) -> bool:
    """True when `quote` is really in the talk and `say` keeps enough of its words."""
    said, quoted, new = _stems(text), _stems(quote), _stems(say)
    if not quoted or len(quoted & said) < QUOTE_FOUND * len(quoted):
        return False
    return not new or len(new & quoted) >= MIN_SUPPORT * len(new)


def spaced(phrase: str) -> str:
    """"On one hand,..." -> "On one hand, ..." so a frame always ends with a space before the dots."""
    return re.sub(r"\s*(\.\.\.|…)$", " ...", phrase.strip())


def fix(raw: dict, text: str, stuck: list[dict]) -> dict:
    """Keep what the page can show: suggestions matched to real stuck places, English phrases only,
    and the facts the rewrite added that the learner never said."""
    says = {s["n"]: re.sub(r"^(\.\.\.|…)\s*", "", s["say"].strip()) for s in raw["stuck"]}  # "...copy the code" -> "copy the code"
    by_n = {n: say for n, say in says.items() if 1 <= n <= len(stuck) and say}
    phrases = [
        {"say": spaced(p["say"]), "vi": spaced(p["vi"])}
        for p in raw["phrases"]
        if p["say"].strip() and not has_vietnamese(p["say"])
    ][:MAX_PHRASES]
    sentences = [s for s in raw["sentences"] if s["say"].strip()]
    better = " ".join(s["say"].strip() for s in sentences)
    return {
        "better": better,
        "unsure": [s["say"].strip() for s in sentences if not supported(s["say"], s["from"], text)],
        "stuck": [{**s, "say": by_n.get(i + 1)} for i, s in enumerate(stuck)],
        "phrases": phrases,
        "added_facts": invented_facts(better, text),
    }


async def review(question: str, text: str, stuck: list[dict]) -> dict:
    """{better, unsure, stuck: [{before, after, pause_s, say}], phrases: [{say, vi}], added_facts}."""
    raw = await llm.complete_json(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _user_message(question, text, stuck)}],
        SCHEMA,
        MAX_TOKENS,
        temperature=0.4,
    )
    return fix(json.loads(raw), text, stuck)
