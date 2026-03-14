from functools import lru_cache

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Speaking English App API"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # LM Studio (OpenAI-compatible) configuration
    lmstudio_base_url: AnyHttpUrl | None = None
    lmstudio_api_key: str | None = None
    lmstudio_model: str = "local-model"
    # Style: max tokens per AI reply. Default 256 allows natural length.
    lm_conversation_max_tokens: int = 256
    # Optional: append this to the system prompt (e.g. "Use simple words only.")
    lm_system_prompt_extra: str | None = None

    # Auth / JWT
    jwt_secret_key: str = "CHANGE_ME_SECRET_KEY"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Database — change in backend/.env (DATABASE_URL variable). Watch .env.example.
    # Format: postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/speaking_english"
    )
    cors_allowed_origins: list[str] = ["http://localhost:4200"]
    max_audio_upload_mb: int = 10
    request_timeout_seconds: int = 60

    # Optional path to ffmpeg (e.g. when winget installs it but PATH is not updated)
    ffmpeg_path: str | None = None

    # TTS (edge-tts): speech rate. "+0%" = default; "-20%" = slower; "+20%" = faster.
    tts_rate: str = "+0%"
    tts_voice: str = "en-US-JennyNeural"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
