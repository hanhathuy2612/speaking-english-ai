"""IELTS Speaking target bands (stored on topics / WS level override)."""

from __future__ import annotations

# Official half-band scale from 4.0 to 9.0 (typical practice range).
IELTS_SPEAKING_BANDS: tuple[float, ...] = (
    4.0,
    4.5,
    5.0,
    5.5,
    6.0,
    6.5,
    7.0,
    7.5,
    8.0,
    8.5,
    9.0,
)
_IELTS_BAND_SET = frozenset(IELTS_SPEAKING_BANDS)


def parse_ielts_band(raw: str | None) -> float | None:
    """Return band as float if string matches a valid IELTS band, else None."""
    if raw is None:
        return None
    s = raw.strip().replace(",", ".")
    if not s:
        return None
    try:
        n = float(s)
    except ValueError:
        return None
    # Snap to nearest half band then validate
    snapped = round(n * 2) / 2
    if snapped not in _IELTS_BAND_SET:
        return None
    return snapped


def format_ielts_band(n: float) -> str:
    """Canonical string for API / UI (6.0 -> '6', 6.5 -> '6.5')."""
    if n % 1 == 0:
        return str(int(n))
    return f"{n:.1f}".rstrip("0").rstrip(".")


# Old topics may still store CEFR labels — map to a rough IELTS target for prompts.
_LEGACY_CEFR_TO_BAND: dict[str, str] = {
    "a1": "4",
    "a2": "5",
    "b1": "6",
    "b2": "6.5",
    "c1": "7.5",
}


def resolve_ielts_band(raw: str | None) -> float | None:
    """Parse IELTS band, or map legacy CEFR topic levels to an approximate band."""
    n = parse_ielts_band(raw)
    if n is not None:
        return n
    if raw is None or not str(raw).strip():
        return None
    mapped = _LEGACY_CEFR_TO_BAND.get(str(raw).strip().lower())
    if mapped is not None:
        return parse_ielts_band(mapped)
    return None


def canonical_ielts_level_key(raw: str | None) -> str | None:
    """Lowercase key for lookups, e.g. '6.5'."""
    n = resolve_ielts_band(raw)
    if n is None:
        return None
    return format_ielts_band(n).lower()


def display_level_label(raw: str | None) -> str | None:
    """Show canonical IELTS band when input is valid or legacy-mapped; else raw."""
    if raw is None or not str(raw).strip():
        return None
    n = resolve_ielts_band(raw)
    if n is not None:
        return format_ielts_band(n)
    return str(raw).strip()
