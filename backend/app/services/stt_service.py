import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import logging

logger = logging.getLogger(__name__)

# faster_whisper / PyAV expect 16kHz mono; browser WebM (Opus) often fails
WHISPER_SAMPLE_RATE = 16000


def _get_ffmpeg_exe() -> str:
    """Path to ffmpeg: from FFMPEG_PATH env/config, or from PATH."""
    from app.core.config import get_settings

    settings = get_settings()
    if settings.ffmpeg_path and Path(settings.ffmpeg_path).exists():
        return str(Path(settings.ffmpeg_path).resolve())
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    raise ValueError(
        "ffmpeg not found. Set FFMPEG_PATH in .env to the full path to ffmpeg.exe, "
        "or add ffmpeg to your PATH."
    )


def _webm_to_wav(webm_path: Path) -> Path:
    """Convert WebM (e.g. from browser MediaRecorder) to WAV for faster_whisper."""
    path = Path(webm_path).resolve()
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError(
            "Audio file missing or empty (record something first)."
        ) from None

    ffmpeg_exe = _get_ffmpeg_exe()
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    out.close()
    wav_path = Path(out.name)
    try:
        result = subprocess.run(
            [
                ffmpeg_exe,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-ar",
                str(WHISPER_SAMPLE_RATE),
                "-ac",
                "1",
                "-f",
                "wav",
                str(wav_path),
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            err = (result.stderr or b"").decode("utf-8", errors="replace").strip()
            logger.warning("ffmpeg stderr: %s", err or "(no message)")
            raise ValueError(
                "Audio conversion failed. The recording may be too short or in an unsupported format."
            ) from None
        return wav_path
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("ffmpeg WebM->WAV failed: %s", e)
        raise ValueError(
            "Audio conversion failed. Ensure ffmpeg is installed and on PATH."
        ) from e


class STTService:
    """
    Wrapper around faster-whisper for local speech-to-text.
    Converts browser WebM to WAV before transcribing when needed.
    """

    def __init__(self, model_size: str = "base") -> None:
        self._model_size = model_size
        self._model = None  # Lazy init

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self._model_size, device="cpu", compute_type="int8"
            )
        return self._model

    def transcribe(self, audio_path: Path) -> dict[str, Any]:
        """
        Transcribe audio file. For .webm (browser), converts to WAV first via ffmpeg.
        """
        path = Path(audio_path)
        use_temp = path.suffix.lower() == ".webm"
        wav_path = path

        if use_temp:
            wav_path = _webm_to_wav(path)

        try:
            model = self._get_model()
            segments, info = model.transcribe(str(wav_path), beam_size=5)
            text = " ".join(seg.text.strip() for seg in segments)
            return {
                "text": text.strip(),
                "language": info.language,
                "language_probability": info.language_probability,
            }
        finally:
            if use_temp and wav_path != path and wav_path.exists():
                try:
                    wav_path.unlink()
                except OSError:
                    pass
