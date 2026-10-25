"""Settings read from .env at the project root (or environment variables). Every setting has a default."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parents[1]  # backend/app
ROOT_DIR = APP_DIR.parents[1]  # project root
DATA_DIR = APP_DIR / "data"
FRONTEND_DIR = ROOT_DIR / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"  # output of `npm run build` (React app)
RECORDINGS_DIR = ROOT_DIR / "recordings"
BENCH_DIR = RECORDINGS_DIR / "bench"

load_dotenv(ROOT_DIR / ".env")

# ----- LLM (LM Studio) -----
LM_URL = os.getenv("LM_URL", "http://localhost:1234/v1")
LM_MODEL = os.getenv("LM_MODEL", "qwen2.5-7b-instruct")
LM_TEMPERATURE = float(os.getenv("LM_TEMPERATURE", "0.35"))
LM_SEED = os.getenv("LM_SEED")  # set a fixed value when comparing prompts
MAX_REPLY_TOKENS = int(os.getenv("MAX_REPLY_TOKENS", "256"))
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "3"))  # earlier Q/A pairs sent to the LLM

# ----- Interview flow -----
FOLLOWUPS = int(os.getenv("INTERVIEW_FOLLOWUPS", "1"))  # max follow-up questions per main question
MAX_RETRIES = 2  # re-ask at most twice, then move on so the learner never gets stuck

# ----- STT (faster-whisper) -----
STT_MODEL = os.getenv("STT_MODEL", "small.en")
STT_DEVICE = os.getenv("STT_DEVICE", "cpu")
STT_COMPUTE = os.getenv("STT_COMPUTE", "int8")
STT_THREADS = int(os.getenv("STT_THREADS", "8"))
STT_BEAM = int(os.getenv("STT_BEAM", "1"))
STT_VOCAB = os.getenv("STT_VOCAB", "")  # the user's name and job vocabulary
STT_MIN_LOGPROB = float(os.getenv("STT_MIN_LOGPROB", "-1.0"))
STT_MAX_NO_SPEECH = float(os.getenv("STT_MAX_NO_SPEECH", "0.6"))
# Let Whisper detect the language, so Vietnamese answers are caught even when Whisper would
# translate them to English. Costs about 0.24 s per turn on the RTX 3060.
STT_CHECK_LANGUAGE = os.getenv("STT_CHECK_LANGUAGE", "0") == "1"
SAVE_AUDIO_DIR = os.getenv("SAVE_AUDIO_DIR", "")  # relative to the project root, e.g. "recordings"

# ----- Database (MySQL 8): accounts, practice history, lesson content -----
# mysql://user:password@host:3306/database (percent-encode special characters in the password).
# Required: accounts live here, the server refuses to start without it.
DATABASE_URL = os.getenv("DATABASE_URL", "")


def parse_database_url(url: str) -> dict:
    """pymysql connect() arguments from a mysql:// URL."""
    u = urlparse(url)
    if u.scheme != "mysql" or not u.hostname or not u.path.strip("/"):
        raise ValueError("DATABASE_URL must look like mysql://user:password@host:3306/database")
    return {
        "host": u.hostname,
        "port": u.port or 3306,
        "user": unquote(u.username or ""),
        "password": unquote(u.password or ""),
        "database": unquote(u.path.strip("/")),
    }


# ----- Accounts and email (docs/features/accounts.md) -----
SIGNUP_ENABLED = os.getenv("SIGNUP_ENABLED", "1") == "1"  # 0: only admins create accounts
# Default admin, created at startup only while the users table is empty (first start of a new database).
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
# Key that signs login tokens (JWT). Empty: a random key is created in data/jwt_secret and kept.
# Changing it logs everyone out.
JWT_SECRET = os.getenv("JWT_SECRET", "")
# Address the links in emails point to, e.g. https://192.168.0.2:8000. Required when SMTP_HOST is
# set: the request's Host header could be forged to send a reset link to another site.
APP_URL = os.getenv("APP_URL", "").rstrip("/")
SMTP_HOST = os.getenv("SMTP_HOST", "")  # empty: emails are printed to the console instead
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_SECURITY = os.getenv("SMTP_SECURITY", "starttls")  # starttls | ssl | none
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")  # defaults to SMTP_USER

# ----- TTS (edge-tts) -----
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-JennyNeural")
TTS_RATE = os.getenv("TTS_RATE", "-10%")
TTS_TEACHER_VOICE = os.getenv("TTS_TEACHER_VOICE", "en-US-AvaNeural")  # lesson teacher, not the interviewer
TTS_TEACHER_RATE = os.getenv("TTS_TEACHER_RATE", "-10%")  # speaking speed of the lesson teacher

# ----- Server (`python -m app` / `run.cmd`; plain `uvicorn ...` ignores these) -----
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")  # 0.0.0.0: reachable from other devices on the LAN
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
# HTTPS: browsers only allow the microphone on https:// or localhost. Paths relative to the
# project root; create them with `python -m scripts.make_cert <LAN IP>`. Empty: plain HTTP.
SSL_CERTFILE = os.getenv("SSL_CERTFILE", "")
SSL_KEYFILE = os.getenv("SSL_KEYFILE", "")
