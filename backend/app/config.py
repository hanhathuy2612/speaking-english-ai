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

    # Auth / JWT
    jwt_secret_key: str = "CHANGE_ME_SECRET_KEY"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Database
    database_url: str = "sqlite+aiosqlite:///./speaking_english.db"
    cors_allowed_origins: list[str] = ["http://localhost:4200"]
    max_audio_upload_mb: int = 10
    request_timeout_seconds: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

