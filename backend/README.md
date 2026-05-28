# Speaking English App Backend

FastAPI backend for auth, topics, conversation (STT -> LLM -> TTS), scoring, and progress.

## Requirements

- Python 3.11+
- PostgreSQL
- ffmpeg (required for audio transcription)
- LM Studio (or another OpenAI-compatible endpoint)

## Quick Start (bootstrap venv -> Poetry)

Run from the `backend/` folder.

### 1) Bootstrap: create venv and install Poetry

- Windows (PowerShell):
```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install poetry
```

- macOS/Linux:
```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install poetry
```

### 2) Install project dependencies with Poetry

```bash
poetry install
```

### 3) Configure environment

- macOS/Linux:
```bash
cp .env.example .env
```
- Windows (PowerShell):
```powershell
Copy-Item .env.example .env
```

Update `.env` at least:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `LMSTUDIO_BASE_URL` (default `http://localhost:1234`)
- `LMSTUDIO_MODEL` (must match loaded model in LM Studio)

### 4) Create DB schema

```bash
poetry run alembic upgrade head
```

### 5) Run server

```bash
poetry run poe dev
```

API base: `http://localhost:8000`  
Swagger docs: `http://localhost:8000/docs`

## LM Studio Notes

1. Open LM Studio.
2. Load a chat model.
3. Start Local Server (OpenAI-compatible API).
4. Ensure model names in `.env` are correct (`LMSTUDIO_MODEL`, optional `LMSTUDIO_LEARNING_PACK_MODEL`).

If logs show `Model unloaded`, reload model in LM Studio and retry.

## Useful Commands (Poetry)

```bash
# Lint
poetry run ruff check app

# Format
poetry run black app

# Run tests
poetry run pytest
```

## Docker

Build local image:

```bash
docker build -t speakai-backend:local -f Dockerfile .
```

Run:

```bash
docker run --rm -p 8000:8000 speakai-backend:local
```

GHCR build/push is automated via `.github/workflows/docker-ghcr.yml`.
