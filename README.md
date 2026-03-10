# SpeakAI – AI English Speaking Practice

A full-stack application to practice spoken English with a local AI (LM Studio).

## Architecture

```
frontend/   Angular 17 SPA
backend/    Python FastAPI + SQLite + WebSocket
LM Studio   Local LLM server (OpenAI-compatible)
```

## Prerequisites

| Tool      | Version | Notes                                         |
| --------- | ------- | --------------------------------------------- |
| Python    | 3.11+   |                                               |
| Node.js   | 18+     |                                               |
| LM Studio | latest  | https://lmstudio.ai                           |
| ffmpeg    | any     | Required by faster-whisper for audio decoding |

## 1. LM Studio setup

1. Download and install **LM Studio** from https://lmstudio.ai
2. Download a model – recommended for English tutoring: `meta-llama-3-8b-instruct` or `mistral-7b-instruct`
3. In LM Studio → **Local Server** tab → click **Start Server** (default port 1234)

## 2. Backend setup (Poetry + poe)

```powershell
cd backend

# 1) Install Poetry (once on your machine)
#    See https://python-poetry.org/docs/#installation

# 2) Install dependencies
poetry install

# 3) Copy and edit .env
copy .env.example .env
#    Open .env and set LMSTUDIO_BASE_URL=http://localhost:1234

# 4) Run the server via a single poe task
poetry run poe dev
```

The API will be available at http://localhost:8000  
Interactive docs: http://localhost:8000/docs

## 3. Frontend setup

```powershell
cd frontend

npm install

npm start
# Opens at http://localhost:4200
```

## 4. Usage flow

1. Open http://localhost:4200
2. Register or log in
3. Choose a conversation topic
4. Hold the microphone button to speak; release to get an AI response
5. View your Fluency / Vocabulary / Grammar scores after each turn
6. Track overall progress in the Progress dashboard

## Project structure

```
SpeakingEnglishApp/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI application
│   │   ├── config.py            Settings (reads .env)
│   │   ├── core/
│   │   │   ├── security.py      JWT + bcrypt helpers
│   │   │   └── deps.py          FastAPI dependency injectors
│   │   ├── db/
│   │   │   └── session.py       Async SQLAlchemy engine + Base
│   │   ├── models/
│   │   │   ├── user.py          User ORM model
│   │   │   └── conversation.py  Topic / Session / Turn / TurnScore models
│   │   ├── routers/
│   │   │   ├── auth.py          POST /auth/register, /auth/login
│   │   │   ├── topics.py        GET /topics
│   │   │   ├── progress.py      GET /progress/summary
│   │   │   └── conversation.py  WebSocket /ws/conversation
│   │   └── services/
│   │       ├── lm_client.py     LM Studio streaming client
│   │       ├── stt_service.py   Speech-to-text (faster-whisper)
│   │       ├── tts_service.py   Text-to-speech (edge-tts)
│   │       └── scoring_service.py  Scoring via LM Studio + heuristics
│   ├── pyproject.toml      # Poetry dependencies
│   ├── requirements.txt    # (legacy, no longer needed if using Poetry)
│   └── .env.example
│
└── frontend/
    └── src/app/
        ├── app.routes.ts
        ├── app.component.ts
        ├── auth/                Login & Register pages
        ├── topics/              Topic selection grid
        ├── conversation/        Full-duplex voice chat
        ├── progress/            Dashboard with charts
        └── services/
            ├── auth.service.ts
            ├── auth.guard.ts
            ├── auth.interceptor.ts
            ├── api.service.ts
            ├── ws.service.ts
            └── audio.service.ts
```

## WebSocket message protocol

See `backend/app/routers/conversation.py` docstring for full details.

## Scoring

After each spoken turn the AI evaluates:
- **Fluency** – words-per-minute relative to native speed
- **Vocabulary** – type-token ratio (word variety)
- **Grammar** – LM Studio evaluates grammatical correctness (0–10)
- **Overall** – holistic score with written feedback
