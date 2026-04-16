from pydantic import BaseModel, Field, field_validator

MAX_SECTION_ITEMS = 25
_ERR_EMPTY_VALUE = "Value must not be empty"


def _clean_text(value: str) -> str:
    return " ".join((value or "").strip().split())


class LearningPackVocabItem(BaseModel):
    term: str = Field(..., min_length=1, max_length=120)
    meaning: str = Field(..., min_length=1, max_length=400)
    collocations: list[str] = Field(default_factory=list, max_length=8)
    example: str | None = Field(None, max_length=500)

    @field_validator("term", "meaning", mode="before")
    @classmethod
    def _normalize_required(cls, v: str) -> str:
        s = _clean_text(str(v))
        if not s:
            raise ValueError(_ERR_EMPTY_VALUE)
        return s

    @field_validator("example", mode="before")
    @classmethod
    def _normalize_optional(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = _clean_text(str(v))
        return s or None

    @field_validator("collocations", mode="before")
    @classmethod
    def _normalize_collocations(cls, v: list[str] | None) -> list[str]:
        if not v:
            return []
        out: list[str] = []
        for item in v:
            s = _clean_text(str(item))
            if s:
                out.append(s)
        return out


class LearningPackPatternItem(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=240)
    usage: str = Field(..., min_length=1, max_length=500)
    example: str = Field(..., min_length=1, max_length=500)

    @field_validator("pattern", "usage", "example", mode="before")
    @classmethod
    def _normalize(cls, v: str) -> str:
        s = _clean_text(str(v))
        if not s:
            raise ValueError(_ERR_EMPTY_VALUE)
        return s


class LearningPackMistakeItem(BaseModel):
    mistake: str = Field(..., min_length=1, max_length=300)
    fix: str = Field(..., min_length=1, max_length=300)
    note: str | None = Field(None, max_length=400)

    @field_validator("mistake", "fix", mode="before")
    @classmethod
    def _normalize_required(cls, v: str) -> str:
        s = _clean_text(str(v))
        if not s:
            raise ValueError(_ERR_EMPTY_VALUE)
        return s

    @field_validator("note", mode="before")
    @classmethod
    def _normalize_note(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = _clean_text(str(v))
        return s or None


class LearningPackModelResponseItem(BaseModel):
    level: str | None = Field(None, max_length=30)
    text: str = Field(..., min_length=1, max_length=1500)

    @field_validator("level", mode="before")
    @classmethod
    def _normalize_level(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = _clean_text(str(v))
        return s or None

    @field_validator("text", mode="before")
    @classmethod
    def _normalize_text(cls, v: str) -> str:
        s = _clean_text(str(v))
        if not s:
            raise ValueError(_ERR_EMPTY_VALUE)
        return s


class LearningPackIn(BaseModel):
    vocabulary: list[LearningPackVocabItem] = Field(
        default_factory=list, max_length=MAX_SECTION_ITEMS
    )
    sentence_patterns: list[LearningPackPatternItem] = Field(
        default_factory=list, max_length=MAX_SECTION_ITEMS
    )
    idea_prompts: list[str] = Field(default_factory=list, max_length=MAX_SECTION_ITEMS)
    common_mistakes: list[LearningPackMistakeItem] = Field(
        default_factory=list, max_length=MAX_SECTION_ITEMS
    )
    model_responses: list[LearningPackModelResponseItem] = Field(
        default_factory=list, max_length=MAX_SECTION_ITEMS
    )
    tips: list[str] = Field(default_factory=list, max_length=MAX_SECTION_ITEMS)

    @field_validator("idea_prompts", "tips", mode="before")
    @classmethod
    def _normalize_string_list(cls, v: list[str] | None) -> list[str]:
        if not v:
            return []
        out: list[str] = []
        for item in v:
            s = _clean_text(str(item))
            if s:
                out.append(s)
        return out


class LearningPackOut(LearningPackIn):
    source: str | None = Field(
        None, description="unit | topic | fallback when this pack is resolved for learners"
    )

