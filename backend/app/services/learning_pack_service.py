from __future__ import annotations

from app.schemas.learning_pack import MAX_SECTION_ITEMS, LearningPackIn, LearningPackOut


def normalize_learning_pack_ai_dict(raw: object) -> dict:
    """
    Map common LLM JSON aliases to LearningPackIn field names before Pydantic validation.

    Models often return word/definition/response instead of term/meaning/text, or omit usage/fix.
    """
    if not isinstance(raw, dict):
        return {}

    def as_list(key: str) -> list:
        v = raw.get(key)
        if not isinstance(v, list):
            return []
        return v

    out: dict = {}

    # --- vocabulary ---
    vocab_out: list[dict] = []

    def append_vocab_row(
        term: object,
        meaning: object,
        coll: object | None = None,
        ex: object | None = None,
    ) -> None:
        if term is None or meaning is None:
            return
        t = str(term).strip()
        m = str(meaning).strip()
        if not t or not m:
            return
        if isinstance(coll, str):
            coll_list = [coll]
        elif isinstance(coll, list):
            coll_list = coll
        else:
            coll_list = []
        coll_list = [str(x).strip() for x in coll_list if str(x).strip()][:8]
        vocab_out.append(
            {
                "term": t,
                "meaning": m,
                "collocations": coll_list,
                "example": ex if ex is None else str(ex).strip() or None,
            }
        )

    raw_vocab = raw.get("vocabulary")
    # LLMs sometimes return parallel arrays: { "term": [...], "meaning": [...] }
    if isinstance(raw_vocab, dict):
        terms = (
            raw_vocab.get("term")
            or raw_vocab.get("terms")
            or raw_vocab.get("words")
            or raw_vocab.get("phrase")
        )
        meanings = (
            raw_vocab.get("meaning")
            or raw_vocab.get("meanings")
            or raw_vocab.get("definitions")
            or raw_vocab.get("definition")
        )
        colls = raw_vocab.get("collocations")
        examples = raw_vocab.get("example") or raw_vocab.get("examples")
        if isinstance(terms, list) and isinstance(meanings, list):
            n = min(len(terms), len(meanings))
            for i in range(n):
                c = None
                ex_i = None
                if isinstance(colls, list) and i < len(colls):
                    c = colls[i]
                if isinstance(examples, list) and i < len(examples):
                    ex_i = examples[i]
                append_vocab_row(terms[i], meanings[i], c, ex_i)
    elif isinstance(raw_vocab, list):
        for item in raw_vocab:
            if not isinstance(item, dict):
                continue
            term = item.get("term") or item.get("word") or item.get("phrase") or item.get("headword")
            meaning = (
                item.get("meaning")
                or item.get("definition")
                or item.get("gloss")
                or item.get("explain")
                or item.get("description")
            )
            if term is None or meaning is None:
                continue
            coll = item.get("collocations") or item.get("collocation") or []
            ex = item.get("example") or item.get("sample_sentence") or item.get("sample")
            append_vocab_row(term, meaning, coll, ex)
    out["vocabulary"] = vocab_out[:MAX_SECTION_ITEMS]

    # --- sentence_patterns ---
    sp_out: list[dict] = []
    for item in as_list("sentence_patterns"):
        if not isinstance(item, dict):
            continue
        pat = item.get("pattern") or item.get("structure") or item.get("frame")
        usage = (
            item.get("usage")
            or item.get("context")
            or item.get("when_to_use")
            or item.get("description")
            or item.get("explain")
        )
        ex = item.get("example") or item.get("sample") or item.get("sentence")
        if not pat:
            continue
        if not usage:
            usage = "Use this pattern to give a clear, extended spoken answer."
        if not ex:
            ex = str(pat)
        sp_out.append(
            {
                "pattern": str(pat).strip(),
                "usage": str(usage).strip(),
                "example": str(ex).strip(),
            }
        )
    out["sentence_patterns"] = sp_out[:MAX_SECTION_ITEMS]

    # --- idea_prompts ---
    ideas = as_list("idea_prompts")
    out["idea_prompts"] = [
        " ".join(str(x).strip().split())
        for x in ideas
        if isinstance(x, (str, int, float)) and str(x).strip()
    ][:MAX_SECTION_ITEMS]

    # --- common_mistakes ---
    cm_out: list[dict] = []
    for item in as_list("common_mistakes"):
        if not isinstance(item, dict):
            continue
        bad = item.get("mistake") or item.get("error") or item.get("wrong")
        fix = item.get("fix") or item.get("correction") or item.get("better") or item.get("improvement")
        if not bad:
            continue
        if not fix:
            fix = "Rephrase using correct grammar and a full idea."
        note = item.get("note")
        cm_out.append(
            {
                "mistake": str(bad).strip(),
                "fix": str(fix).strip(),
                "note": None if note is None else str(note).strip() or None,
            }
        )
    out["common_mistakes"] = cm_out[:MAX_SECTION_ITEMS]

    # --- model_responses ---
    mr_out: list[dict] = []
    for item in as_list("model_responses"):
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("response") or item.get("answer") or item.get("sample")
        level = item.get("level") or item.get("band")
        if not text:
            continue
        mr_out.append(
            {
                "level": None if level is None else str(level).strip() or None,
                "text": str(text).strip(),
            }
        )
    out["model_responses"] = mr_out[:MAX_SECTION_ITEMS]

    # --- tips ---
    tips = as_list("tips")
    out["tips"] = [
        " ".join(str(x).strip().split())
        for x in tips
        if isinstance(x, (str, int, float)) and str(x).strip()
    ][:MAX_SECTION_ITEMS]

    return out


def parse_learning_pack(raw: object) -> LearningPackOut | None:
    if raw is None:
        return None
    try:
        parsed = LearningPackIn.model_validate(raw)
    except Exception:
        return None
    return LearningPackOut(**parsed.model_dump())


def to_learning_pack_json(pack: LearningPackIn) -> dict:
    return pack.model_dump()


def resolve_effective_learning_pack(
    *,
    unit_pack_raw: object,
    topic_pack_raw: object,
    fallback_pack: LearningPackOut | None = None,
) -> LearningPackOut | None:
    unit_pack = parse_learning_pack(unit_pack_raw)
    if unit_pack is not None:
        unit_pack.source = "unit"
        return unit_pack

    topic_pack = parse_learning_pack(topic_pack_raw)
    if topic_pack is not None:
        topic_pack.source = "topic"
        return topic_pack

    if fallback_pack is not None:
        fallback_pack.source = "fallback"
    return fallback_pack


def build_fallback_learning_pack(
    *,
    topic_title: str,
    topic_level: str | None,
    unit_title: str | None = None,
) -> LearningPackOut:
    level_note = topic_level.strip() if isinstance(topic_level, str) else ""
    focus = unit_title.strip() if isinstance(unit_title, str) and unit_title.strip() else topic_title
    return LearningPackOut(
        vocabulary=[
            {"term": "key point", "meaning": "main idea you want to communicate"},
            {"term": "for example", "meaning": "phrase to introduce supporting details"},
            {"term": "in my opinion", "meaning": "phrase to present your personal view"},
            {"term": "on the one hand", "meaning": "phrase to organize contrasting ideas"},
            {"term": "overall", "meaning": "phrase to summarize your response"},
        ],
        sentence_patterns=[
            {
                "pattern": "I usually ... because ...",
                "usage": "Give a personal habit with a reason.",
                "example": f"I usually prepare ideas before speaking about {focus} because it helps me stay clear.",
            },
            {
                "pattern": "One challenge is ..., so I ...",
                "usage": "Describe a difficulty and your solution.",
                "example": f"One challenge is finding precise words about {focus}, so I use simple but accurate sentences.",
            },
            {
                "pattern": "Compared with ..., I think ...",
                "usage": "Compare two options and state your opinion.",
                "example": "Compared with short answers, I think extended answers show communication skills better.",
            },
        ],
        idea_prompts=[
            f"What is your personal experience with {focus}?",
            f"What is difficult about {focus}, and how do you handle it?",
            f"What advice would you give a beginner about {focus}?",
        ],
        common_mistakes=[
            {"mistake": "Very short answers", "fix": "Add one reason and one example."},
            {"mistake": "Repeating the same word", "fix": "Use simple synonyms or paraphrase."},
            {"mistake": "Unclear structure", "fix": "Use linking phrases: first, then, finally."},
        ],
        model_responses=[
            {
                "level": level_note or None,
                "text": f"In my opinion, {focus} is useful because it helps people communicate more clearly. "
                "For example, when I organize my ideas before speaking, I can explain details and give better reasons.",
            }
        ],
        tips=[
            "Aim for 2-4 sentences per answer.",
            "Use one concrete example in each response.",
            "Self-correct calmly and continue speaking.",
        ],
        source="fallback",
    )


def pack_to_prompt_snippet(pack: LearningPackOut | None, *, max_items_per_section: int = 5) -> str:
    if pack is None:
        return ""
    lines: list[str] = []

    def add_section(title: str, rows: list[str]) -> None:
        if not rows:
            return
        lines.append(title)
        for row in rows[:max_items_per_section]:
            lines.append(f"- {row}")

    add_section(
        "Vocabulary:",
        [f"{item.term}: {item.meaning}" for item in pack.vocabulary],
    )
    add_section(
        "Sentence patterns:",
        [f"{item.pattern} | {item.usage}" for item in pack.sentence_patterns],
    )
    add_section("Idea prompts:", list(pack.idea_prompts))
    add_section(
        "Common mistakes:",
        [f"{item.mistake} -> {item.fix}" for item in pack.common_mistakes],
    )
    add_section("Tips:", list(pack.tips))

    return "\n".join(lines)

