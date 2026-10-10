"""Speech recognition with faster-whisper. Swap point: changing the STT library only touches this file."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from app.core import config
from app.core.cuda import add_cuda_dlls

add_cuda_dlls()  # before importing faster_whisper

import numpy as np  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

_model: WhisperModel | None = None
label = ""  # config actually in use, shown in the UI sidebar


def load() -> None:
    """Load Whisper; if the GPU fails (missing CUDA DLLs, ...) fall back to CPU instead of crashing."""
    global _model, label
    c = config
    print(f"Loading Whisper {c.STT_MODEL} ({c.STT_DEVICE}, {c.STT_COMPUTE}, beam {c.STT_BEAM}) ...")
    try:
        model = WhisperModel(
            c.STT_MODEL, device=c.STT_DEVICE, compute_type=c.STT_COMPUTE, cpu_threads=c.STT_THREADS
        )
        list(model.transcribe(np.zeros(16000, dtype=np.float32), beam_size=1)[0])  # smoke test
        _model, label = model, f"{c.STT_MODEL} · {c.STT_DEVICE} · {c.STT_COMPUTE} · beam {c.STT_BEAM}"
    except Exception as e:  # noqa: BLE001
        if c.STT_DEVICE == "cpu":
            raise
        print(f"!! Whisper failed on {c.STT_DEVICE}: {e}\n!! Falling back to CPU int8.")
        _model = WhisperModel(c.STT_MODEL, device="cpu", compute_type="int8", cpu_threads=c.STT_THREADS)
        label = f"{c.STT_MODEL} · cpu (GPU lỗi) · int8 · beam {c.STT_BEAM}"


def transcribe(path: str, prompt: str = "") -> dict:
    assert _model is not None, "call stt.load() first"
    segments, _info = _model.transcribe(
        path,
        language="en",
        beam_size=config.STT_BEAM,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=False,
        initial_prompt=prompt or None,
    )
    words, logprob, no_speech, total = [], 0.0, 0.0, 0.0
    for seg in segments:  # generator: recognition actually runs in this loop
        dur = max(seg.end - seg.start, 0.01)
        logprob += seg.avg_logprob * dur
        no_speech += seg.no_speech_prob * dur
        total += dur
        for w in seg.words or []:
            words.append({"w": w.word.strip(), "s": w.start, "e": w.end, "p": w.probability})
    return {
        "text": " ".join(w["w"] for w in words).strip(),
        "words": words,
        "avg_logprob": round(logprob / total, 3) if total else -9.0,
        "no_speech": round(no_speech / total, 3) if total else 1.0,
    }


def is_unclear(result: dict) -> bool:
    """Low confidence: skip the LLM and ask the learner to repeat."""
    return (
        result["avg_logprob"] < config.STT_MIN_LOGPROB
        or result["no_speech"] > config.STT_MAX_NO_SPEECH
    )


def save_recording(data: bytes) -> str:
    """Write the recording: kept in SAVE_AUDIO_DIR when set, otherwise a temp file."""
    if config.SAVE_AUDIO_DIR:
        folder = config.ROOT_DIR / config.SAVE_AUDIO_DIR
        folder.mkdir(exist_ok=True)
        path = folder / f"{datetime.now():%Y%m%d-%H%M%S-%f}.webm"
        path.write_bytes(data)
        return str(path)
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(data)
        return f.name


def finish_recording(path: str, text: str | None) -> None:
    """After recognition: save the hypothesis next to the recording, or delete the temp file."""
    if not config.SAVE_AUDIO_DIR:
        Path(path).unlink(missing_ok=True)
    elif text is not None:
        Path(path).with_suffix(".hyp.txt").write_text(text, encoding="utf-8")
