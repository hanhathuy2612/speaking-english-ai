import subprocess
import tempfile
from pathlib import Path
from typing import Any


class STTService:
    """
    Wrapper around faster-whisper for local speech-to-text.
    Lazy-loads the model on first use to avoid slow startup.
    """

    def __init__(self, model_size: str = "base") -> None:
        self._model_size = model_size
        self._model = None  # Lazy init

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio_path: Path) -> dict[str, Any]:
        """
        Transcribe audio file. Accepts .webm, .wav, .mp3 etc.
        faster-whisper uses ffmpeg internally for format conversion.
        """
        model = self._get_model()
        segments, info = model.transcribe(str(audio_path), beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments)
        return {
            "text": text.strip(),
            "language": info.language,
            "language_probability": info.language_probability,
        }
