import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_env_files() -> tuple[str, ...] | None:
    """
    Load env files from backend/ (next to app/).
    Order: .env → .env.{APP_ENV} → .env.local (later overrides earlier).
    APP_ENV defaults to development. Set APP_ENV=production for prod-specific file.
    """
    root = Path(__file__).resolve().parent.parent.parent
    app_env = (os.getenv("APP_ENV") or "development").strip().lower()
    paths: list[str] = []
    for name in (".env", f".env.{app_env}", ".env.local"):
        p = root / name
        if p.is_file():
            paths.append(str(p))
    return tuple(paths) if paths else None


class Settings(BaseSettings):
    app_name: str = "Speaking English App API"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # OpenAI (or compatible endpoint) configuration.
    # Backward-compatible: still accepts LMSTUDIO_* env names.
    openai_base_url: AnyHttpUrl = Field(
        default="http://localhost:1234/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "LMSTUDIO_BASE_URL"),
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "LMSTUDIO_API_KEY"),
    )
    openai_model: str = Field(
        default="qwen2.5-7b-instruct",
        validation_alias=AliasChoices("OPENAI_MODEL", "LMSTUDIO_MODEL"),
    )
    # If set, POST /conversation/guidance uses this model instead of openai_model.
    openai_guidance_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_GUIDANCE_MODEL", "LMSTUDIO_GUIDANCE_MODEL"),
    )
    # If set, scoring + end-session feedback use this model instead of openai_model.
    # Keeps backward compatibility with legacy SCORE_MODEL env.
    openai_score_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OPENAI_SCORE_MODEL", "LMSTUDIO_SCORE_MODEL", "SCORE_MODEL"
        ),
    )
    # Style: max tokens per AI reply. Default 256 allows natural length.
    lm_conversation_max_tokens: int = 256
    # Optional: append this to the system prompt (e.g. "Use simple words only.")
    lm_system_prompt_extra: str | None = None
    # After STT: optional LLM “cleanup” (can still drift). Default off — user sees raw STT text.
    # Set LM_NORMALIZE_TRANSCRIPT=true in .env if you want light ASR fixes (keep min_similarity high).
    lm_normalize_transcript: bool = False
    lm_normalize_temperature: float = 0.05
    lm_normalize_max_tokens: int = 200
    # If True, the topic is sent to the normalizer (often primes wrong / scripted text). Keep False.
    lm_normalize_include_topic_context: bool = False
    # Reject LLM output if too unlike raw STT. ~0.65+ when normalization is enabled.
    lm_normalize_min_similarity: float = 0.65

    # Auth / JWT
    jwt_secret_key: str = "CHANGE_ME_SECRET_KEY"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    # Database — change in backend/.env (DATABASE_URL variable). Watch .env.example.
    # Format: postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/speaking_english"
    )
    # Web: ng serve. Capacitor Android/iOS serves the app from localhost / custom schemes — preflight
    # sends that Origin, not http://10.0.2.2 (that is only the API host from the emulator).
    cors_allowed_origins: list[str] = [
        "http://localhost:4200",
        "http://192.168.1.44:4200",
        "http://10.0.2.2:4200",
        "http://localhost",
        "https://localhost",
        "capacitor://localhost",
        "ionic://localhost",
    ]
    max_audio_upload_mb: int = 10
    # LLM + OpenAI-compatible HTTP calls (local models may need more than 60s on long prompts).
    request_timeout_seconds: int = 120
    # How long to wait for the next WebSocket frame before closing the connection (e.g. user types a long message).
    websocket_idle_timeout_seconds: int = 1800

    # Optional path to ffmpeg (e.g. when winget installs it but PATH is not updated)
    ffmpeg_path: str | None = None

    # STT (faster-whisper) — defaults favor accuracy over speed (override in .env).
    stt_model_size: str = "small"
    stt_beam_size: int = 5
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"

    # TTS (edge-tts): speech rate. "+0%" = default; "-20%" = slower; "+20%" = faster.
    tts_rate: str = "+0%"
    tts_voice: str = "en-US-JennyNeural"

    # Comma-separated emails that receive the "admin" role on app startup (must match registered users).
    bootstrap_admin_emails: str = ""

    model_config = SettingsConfigDict(
        env_file=_resolve_env_files(),
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
