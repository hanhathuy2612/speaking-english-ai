"""AI drafts of new units for admins (docs/features/content-admin.md).

The LLM only writes a draft: the admin reads and fixes it in the form before saving, and nothing
it writes is ever used to grade a learner. The model gets one existing unit of the same topic as
the pattern to follow, and LM Studio's structured output forces the reply into the unit's shape;
draft_unit() then fixes what a 7B model tends to get wrong and reports what is still invalid.
"""

from __future__ import annotations

import json
import re

from app.interview import units as catalog
from app.services import content, llm
from app.utils.parsing import norm

MAX_TOKENS = 3000
MIN_CUE_WORDS = 2  # shorter phrase cues are dropped (see _matches)

_str = {"type": "string"}


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def _list(item: dict, lo: int, hi: int) -> dict:
    return {"type": "array", "items": item, "minItems": lo, "maxItems": hi}


UNIT_SCHEMA = _obj(
    {
        "title": _str,
        "role": _str,
        "partner": _str,
        "scenario": _str,
        "goal": _str,
        "greeting": _str,
        "closing": _str,
        "vocab": _str,
        "phrases": _list(_obj({"say": _str, "match": _list(_str, 1, 4)}), 3, 6),
        "questions": _list(
            _obj({"ask": _str, "simple": _str, "phrase": {"type": "integer"}, "steps": _list(_obj({"hint": _str, "say": _str}), 2, 3)}),
            3,
            6,
        ),
    }
)

LESSON_SCHEMA = _obj(
    {
        "intro": _str,
        "intro_vi": _str,
        "vocab": _list(_obj({"word": _str, "vi": _str}), 3, 6),
        "sentences": _list(_obj({"phrase": {"type": "integer"}, "say": _str, "use": _str, "use_vi": _str}), 3, 6),
    }
)

SYSTEM = """You write lesson content for an app where Vietnamese software developers practise spoken English.
A unit is a short scripted conversation: the AI asks the questions in order, the learner answers aloud and should use the unit's phrases.
Follow the example unit exactly in style, length and level. Write a NEW unit about the admin's brief, not a copy of the example.

Field rules:
- title: short English title.
- role: IN ENGLISH, the other person in the conversation, played by the AI (never the learner), in the example's style,
  like "a TEAM LEAD running the daily stand-up meeting" (empty string for a job interview).
- partner: that same person's label IN VIETNAMESE, like "Trưởng nhóm" (empty string for a job interview).
- scenario: one or two English sentences describing the situation.
- goal: one sentence IN VIETNAMESE telling the learner what to practise.
- greeting, closing: one short English sentence each, said by the AI.
- vocab: comma-separated English words the learner may say (helps speech recognition).
- phrases: 3 to 6 sentence starters the LEARNER says in their answers, ending with "...", like "The best part was ...".
  They are first-person statements that answer a question, never questions to the AI.
  match: 1 to 4 lower-case word sequences of 2 to 5 words that prove the learner used the phrase, without "...", like "the best part was".
- questions: one per phrase, in a natural order. ask: the AI's question, which the learner naturally answers with that phrase.
  simple: an easier rewording. phrase: the index (0-based) of the phrase this question practises.
  steps: 2 or 3 ideas to say more. hint: 2 to 4 words IN VIETNAMESE, like "Vì sao?".
  say: a statement starter ending with "...", like "That's because ..." (never a question).
Use simple, natural, spoken English (B1 level)."""

LESSON_SYSTEM = """You write the lesson part of a unit in an app where Vietnamese software developers practise spoken English.
A friendly English teacher explains one full example sentence per phrase, and the learner reads it aloud.

Field rules:
- intro: the teacher's English welcome (2 to 3 sentences) saying what today's sentences are for. intro_vi: its Vietnamese translation.
- vocab: 3 to 6 key English words or short phrases of the unit, with their Vietnamese meaning in vi.
- sentences: one per phrase, in the phrases' order. phrase: the phrase index (0-based).
  say: a complete, natural English sentence built on that phrase, with no "..." left. use: one English sentence from the teacher saying when to use it.
  use_vi: that explanation in Vietnamese."""


def _example(topic_id: str) -> dict:
    """An existing unit to imitate: the first one of the topic, or the first unit at all."""
    pool = [u for u in catalog.units if u["topic"] == topic_id] or catalog.units
    return {k: v for k, v in pool[0].items() if k not in ("id", "topic", "lesson", "followups")}


def slug(title: str) -> str:
    base = "-".join(norm(title).replace("'", "").split())[:40].strip("-") or "unit"
    taken = set(catalog.units_by_id) | {r["id"] for r in content.unit_rows()}  # deleted ones too
    out, n = base, 2
    while out in taken:
        out, n = f"{base}-{n}", n + 1
    return out


def _starter(text: str) -> str:
    text = text.strip()
    return text if "..." in text else f"{text.rstrip('.')} ..."


def _cue(say: str) -> str:
    return norm(say.split("...")[0])


def _matches(phrase: dict) -> list[str]:
    """The model's cues plus the phrase's own start; one-word cues ("recommend") match far too often."""
    cues = dict.fromkeys([_cue(phrase["say"]), *(norm(m) for m in phrase["match"])])
    return [m for m in cues if len(m.split()) >= MIN_CUE_WORDS] or [m for m in cues if m][:1]


def fix_unit(draft: dict, topic_id: str, conversation: bool) -> dict:
    """Turn the model's reply into a unit: ids, phrase links and the small format rules."""
    phrases = [{"say": _starter(p["say"]), "match": _matches(p)} for p in draft["phrases"]]
    n = len(phrases)
    questions = [
        {
            "ask": q["ask"].strip(),
            "simple": q["simple"].strip(),
            "phrases": [min(max(q["phrase"], 0), n - 1)] if n else [],
            "steps": [{"hint": st["hint"].strip(), "say": _starter(st["say"])} for st in q["steps"]],
        }
        for q in draft["questions"]
    ]
    unit = {
        "id": slug(draft["title"]),
        "topic": topic_id,
        "title": draft["title"].strip(),
        **({"role": draft["role"], "partner": draft["partner"]} if conversation and draft["role"] else {}),
        **{k: draft[k].strip() for k in ("scenario", "goal", "greeting", "closing", "vocab")},
        "questions": questions,
        "phrases": phrases,
    }
    return unit


def fix_lesson(draft: dict, n_phrases: int) -> dict:
    sentences = [
        {**s, "phrase": min(max(s["phrase"], 0), n_phrases - 1), "say": re.sub(r"\s*\.\.\.\s*", " ", s["say"]).strip()}
        for s in draft["sentences"]
    ]
    return {**draft, "sentences": sentences}


QUESTION_START = re.compile(r"^(what|how|why|where|when|who|which|do|does|did|have|has|are|is|can|could|would|will)\b", re.I)


def _asks(text: str) -> bool:
    return text.rstrip(" .").endswith("?") or bool(QUESTION_START.match(text.strip()))


def review_notes(unit: dict) -> list[str]:
    """Things a 7B model often gets wrong that are valid but teach the wrong thing, for the admin to
    look at (Vietnamese, shown in the form). In 2 of 2 test drafts a phrase was a question to the AI."""
    notes = [
        f"Mẫu câu {i + 1} \"{p['say']}\" là câu hỏi; người học cần câu để trả lời."
        for i, p in enumerate(unit["phrases"])
        if _asks(p["say"])
    ]
    for i, q in enumerate(unit["questions"]):
        if not q["ask"].rstrip().endswith("?"):
            notes.append(f"Câu hỏi {i + 1} \"{q['ask']}\" không phải câu hỏi.")
        notes += [
            f"Câu hỏi {i + 1}, ý \"{st['hint']}\": \"{st['say']}\" là câu hỏi; ý gợi ý nên là câu kể."
            for st in q["steps"]
            if _asks(st["say"])
        ]
    return notes


async def draft_unit(topic_id: str, brief: str, with_lesson: bool) -> tuple[dict, list[str]]:
    """(unit, problems still left for the admin to fix). Raises ValueError for an unknown topic."""
    topic = next((t for t in catalog.topics if t["id"] == topic_id), None)
    if topic is None:
        raise ValueError(f"unknown topic {topic_id!r}")
    example = _example(topic_id)
    conversation = "role" in example
    user = (
        f"Topic: {topic['title']} ({topic['description']})\n"
        f"Example unit from this topic:\n{json.dumps(example, ensure_ascii=False)}\n\n"
        f"Brief from the admin (may be in Vietnamese): {brief}\n"
        f"{'This topic is a conversation: fill role and partner.' if conversation else 'This topic is a job interview: role and partner are empty strings.'}"
    )
    raw = await llm.complete_json(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], UNIT_SCHEMA, MAX_TOKENS
    )
    unit = fix_unit(json.loads(raw), topic_id, conversation)
    if with_lesson:
        phrases = "\n".join(f"{i}. {p['say']}" for i, p in enumerate(unit["phrases"]))
        user = f"Unit: {unit['title']}. {unit['scenario']}\nPhrases:\n{phrases}"
        raw = await llm.complete_json(
            [{"role": "system", "content": LESSON_SYSTEM}, {"role": "user", "content": user}], LESSON_SCHEMA, MAX_TOKENS
        )
        unit["lesson"] = fix_lesson(json.loads(raw), len(unit["phrases"]))
    return unit, catalog.validate(catalog.topics, [unit])
