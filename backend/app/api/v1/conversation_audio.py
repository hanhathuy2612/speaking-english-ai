from pathlib import Path

from fastapi import HTTPException, status

_AUDIO_ROOT = Path("audio")


def resolve_audio_file(path_str: str | None) -> Path:
    if not path_str or not str(path_str).strip():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No audio for this turn")

    path = Path(path_str)
    if not path.is_absolute():
        path = Path.cwd() / path

    try:
        path = path.resolve()
    except OSError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")

    try:
        path.relative_to(_AUDIO_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid audio path")

    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")

    return path
