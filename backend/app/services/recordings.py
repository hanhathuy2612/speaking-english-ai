"""Recordings kept in SAVE_AUDIO_DIR, for "Nghe lại" on the progress page.

stt.save_recording() names each file after the moment it was saved (YYYYMMDD-HHMMSS-ffffff.webm).
New turns and drill readings store that file name in `turns.audio` / `drills.audio` when they are
saved. Rows saved before those columns existed have no link and simply show no playback: the
folder is shared by every user, so a file is never guessed from its time or its text.
See docs/features/session-history.md.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core import config

# Only names the app creates itself are ever served (no path separators, no other files).
NAME_RE = re.compile(r"^\d{8}-\d{6}-\d{6}\.webm$")


def folder() -> Path | None:
    return config.ROOT_DIR / config.SAVE_AUDIO_DIR if config.SAVE_AUDIO_DIR else None


def path_for(name: str | None) -> Path | None:
    """The recording file for a stored name, or None when the name is invalid or the file is gone."""
    base = folder()
    if not base or not name or not NAME_RE.match(name):
        return None
    path = base / name
    return path if path.is_file() else None
