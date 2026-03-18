from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from app.core.config import get_settings

log = logging.getLogger(__name__)

_WHISPER_SAMPLE_RATE = 16000


def _get_ffmpeg_exe() -> str:
    """Path to ffmpeg: from FFMPEG_PATH env/config, or from PATH."""
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
        t0 = time.monotonic()
        result = subprocess.run(
            [
                ffmpeg_exe,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-ar",
                str(_WHISPER_SAMPLE_RATE),
                "-ac",
                "1",
                "-f",
                "wav",
                str(wav_path),
            ],
            capture_output=True,
            timeout=30,
        )
        log.debug("ffmpeg convert %.1fs", time.monotonic() - t0)
        if result.returncode != 0:
            err = (result.stderr or b"").decode("utf-8", errors="replace").strip()
            log.warning("ffmpeg stderr: %s", err or "(no message)")
            raise ValueError(
                "Audio conversion failed. The recording may be too short or in an unsupported format."
            ) from None
        return wav_path
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.warning("ffmpeg WebM->WAV failed: %s", e)
        raise ValueError(
            "Audio conversion failed. Ensure ffmpeg is installed and on PATH."
        ) from e


class STTService:
    """
    Wrapper around faster-whisper for local speech-to-text.
    Converts browser WebM to WAV before transcribing when needed.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._model_size = settings.stt_model_size
        self._beam_size = settings.stt_beam_size
        self._device = settings.stt_device
        self._compute_type = settings.stt_compute_type
        self._model = None  # Lazy init

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            log.info(
                "Loading Whisper model=%s device=%s compute=%s",
                self._model_size,
                self._device,
                self._compute_type,
            )
            t0 = time.monotonic()
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            log.info("Whisper model loaded in %.1fs", time.monotonic() - t0)
        return self._model

    def transcribe(self, audio_path: Path) -> dict[str, Any]:
        """
        Transcribe audio file. For .webm (browser), converts to WAV first via ffmpeg.
        """
        t_total = time.monotonic()
        path = Path(audio_path)
        use_temp = path.suffix.lower() == ".webm"
        wav_path = path

        if use_temp:
            wav_path = _webm_to_wav(path)

        try:
            model = self._get_model()
            t_infer = time.monotonic()
            segments, info = model.transcribe(
                str(wav_path), beam_size=self._beam_size
            )
            text = " ".join(seg.text.strip() for seg in segments)
            log.debug(
                "Whisper transcribe %.1fs (total pipeline %.1fs, beam=%d)",
                time.monotonic() - t_infer,
                time.monotonic() - t_total,
                self._beam_size,
            )
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
