from __future__ import annotations

from app.schemas.learning_pack import LearningPackIn, LearningPackOut


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

