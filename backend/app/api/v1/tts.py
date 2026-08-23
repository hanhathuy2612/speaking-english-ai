"""TTS API: list voices for UI dropdown and voice preview."""

from typing import Annotated, Any
import edge_tts
from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/tts", tags=["tts"])

_PREVIEW_TEXT = "Hello, this is a sample of this voice."
_PREVIEW_TEXT_VI = "Xin chào, đây là giọng đọc tiếng Việt."


@router.get("/voices")
async def list_voices(_user: Annotated[User, Depends(get_current_user)]) -> list[dict]:
    """Return available TTS voices (ShortName, Gender). English-first for dropdown."""
    raw = await edge_tts.list_voices()
    # Prefer English; include others
    out = []
    seen: set[str] = set()
    for v in raw:
        name = v.get("ShortName") or v.get("Name") or ""
        if not name or name in seen:
            continue
        seen.add(name)
        locale = (v.get("Locale") or "")[:2].lower()
        out.append(
            {
                "id": name,
                "name": name,
                "gender": (v.get("Gender") or "Unknown").lower(),
                "locale": locale,
            }
        )
    # Sort: en first, then by id
    out.sort(key=lambda x: (0 if x["locale"] == "en" else 1, x["id"]))
    return out


@router.get("/preview")
async def preview_voice(
    voice: str,
    rate: str = "-10%",
    _user: Annotated[User | None, Depends(get_current_user)] = None,
) -> Response:
    """Return short TTS audio for the given voice/rate so user can try before selecting."""
    settings = get_settings()
    voice_id = voice or settings.tts_voice
    rate_val = rate or settings.tts_rate
    sample = _PREVIEW_TEXT_VI if voice_id.lower().startswith("vi-") else _PREVIEW_TEXT
    communicate = edge_tts.Communicate(sample, voice_id, rate=rate_val)
    chunks = []
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            chunks.append(chunk["data"])
    if not chunks:
        return Response(status_code=500, content=b"")
    body = b"".join(chunks)
    return Response(content=body, media_type="audio/mpeg")
