"""Recordings kept in SAVE_AUDIO_DIR, for "Nghe lại" on the progress page.

stt.save_recording() names each file after the moment it was saved (YYYYMMDD-HHMMSS-ffffff.webm) and
finish_recording() writes what Whisper heard next to it (.hyp.txt). New turns store the file name
in `turns.audio`; turns saved before that column existed are matched once by text and time.
See docs/features/session-history.md.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.core import config

# Only names the app creates itself are ever served (no path separators, no other files).
NAME_RE = re.compile(r"^\d{8}-\d{6}-\d{6}\.webm$")
MAX_GAP_S = 600  # a turn is saved after STT and the LLM reply, so within minutes of its recording


def folder() -> Path | None:
    return config.ROOT_DIR / config.SAVE_AUDIO_DIR if config.SAVE_AUDIO_DIR else None


def path_for(name: str | None) -> Path | None:
    """The recording file for a stored name, or None when the name is invalid or the file is gone."""
    base = folder()
    if not base or not name or not NAME_RE.match(name):
        return None
    path = base / name
    return path if path.is_file() else None


def saved_at(name: str) -> datetime:
    return datetime.strptime(name[: -len(".webm")], "%Y%m%d-%H%M%S-%f")


def transcripts() -> dict[str, str]:
    """Recording file name -> what Whisper heard, for every kept recording."""
    base = folder()
    if not base or not base.is_dir():
        return {}
    out: dict[str, str] = {}
    for hyp in base.glob("*.hyp.txt"):
        name = hyp.name[: -len(".hyp.txt")] + ".webm"
        if NAME_RE.match(name) and (base / name).is_file():
            out[name] = hyp.read_text(encoding="utf-8").strip()
    return out


def match_turns(turns: list[dict], heard: dict[str, str], taken: set[str]) -> dict[int, str]:
    """Turn id -> recording name for turns without one: same text as the transcript, recorded
    at most MAX_GAP_S before the turn was saved; the closest wins and each file is used once."""
    out: dict[int, str] = {}
    for t in turns:
        if t.get("audio") or t["source"] != "voice":
            continue
        when = datetime.fromisoformat(t["created_at"])
        best: tuple[float, str] | None = None
        for name, text in heard.items():
            if name in taken or text != t["answer"].strip():
                continue
            gap = (when - saved_at(name)).total_seconds()
            if -1 <= gap <= MAX_GAP_S and (best is None or gap < best[0]):
                best = (gap, name)
        if best:
            out[t["id"]] = best[1]
            taken.add(best[1])
    return out
