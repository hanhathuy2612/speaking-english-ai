from app.schemas.learning_pack import LearningPackIn
from app.services.learning_pack_service import (
    build_fallback_learning_pack,
    normalize_learning_pack_ai_dict,
    pack_to_prompt_snippet,
    resolve_effective_learning_pack,
    to_learning_pack_json,
)


def test_resolve_prefers_unit_pack() -> None:
    unit_pack = LearningPackIn(
        vocabulary=[{"term": "cohesion", "meaning": "clear linking between ideas"}]
    )
    topic_pack = LearningPackIn(
        vocabulary=[{"term": "fallback", "meaning": "generic topic-level word"}]
    )

    out = resolve_effective_learning_pack(
        unit_pack_raw=to_learning_pack_json(unit_pack),
        topic_pack_raw=to_learning_pack_json(topic_pack),
        fallback_pack=None,
    )

    assert out is not None
    assert out.source == "unit"
    assert out.vocabulary[0].term == "cohesion"


def test_resolve_falls_back_when_no_pack_present() -> None:
    fallback = build_fallback_learning_pack(
        topic_title="Urban Transport",
        topic_level="6.5",
        unit_title=None,
    )
    out = resolve_effective_learning_pack(
        unit_pack_raw=None,
        topic_pack_raw=None,
        fallback_pack=fallback,
    )
    assert out is not None
    assert out.source == "fallback"
    assert len(out.vocabulary) > 0


def test_normalize_vocab_parallel_arrays_to_objects() -> None:
    """Some models return vocabulary as { term: [...], meaning: [...] } instead of a list of rows."""
    raw = {
        "vocabulary": {
            "term": ["hang out", "join in"],
            "meaning": ["Spend leisure time together.", "Take part in an activity."],
        },
        "sentence_patterns": [],
        "idea_prompts": [],
        "common_mistakes": [],
        "model_responses": [],
        "tips": [],
    }
    normalized = normalize_learning_pack_ai_dict(raw)
    pack = LearningPackIn.model_validate(normalized)
    assert len(pack.vocabulary) == 2
    assert pack.vocabulary[0].term == "hang out"
    assert pack.vocabulary[1].meaning == "Take part in an activity."


def test_prompt_snippet_contains_section_headers() -> None:
    fallback = build_fallback_learning_pack(
        topic_title="Technology",
        topic_level=None,
        unit_title="Daily habits",
    )
    snippet = pack_to_prompt_snippet(fallback, max_items_per_section=2)
    assert "Vocabulary:" in snippet
    assert "Sentence patterns:" in snippet
    assert "Tips:" in snippet
