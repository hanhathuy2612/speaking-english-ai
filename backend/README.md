# Speaking English App – Backend

FastAPI backend for the Speaking English app: auth, topics, real-time spoken conversation (STT → LLM → TTS), scoring, and progress. Uses LM Studio for the LLM, faster-whisper for STT, and edge-tts for TTS.

## Setup

1. **Install dependencies** (from `backend/`):

   ```bash
   poetry install
   ```

2. **Database (PostgreSQL)**:

   - Install and start PostgreSQL.
   - Create the app database (one of):
     - **Script (recommended):** from `backend/` run:
       ```bash
       poetry run poe create-db
       ```
       This reads `DATABASE_URL` from `.env` and creates the database if it does not exist.
     - **Manual:** `createdb speaking_english` (Mac/Linux) or in psql: `CREATE DATABASE speaking_english;`
   - Then create tables: `poetry run alembic upgrade head`

3. **Configure environment**:

   ```bash
   cp .env.example .env
   ```

   Edit `.env`: set `DATABASE_URL` (e.g. `postgresql+asyncpg://postgres:postgres@localhost:5432/speaking_english`) and at least `JWT_SECRET_KEY`. For local AI, start LM Studio and load a model (see below).

4. **Run the server**:

   ```bash
   poetry run poe dev
   ```

   Or:

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   API: `http://localhost:8000`  
   Docs: `http://localhost:8000/docs`

## Dependencies

- **LM Studio**: Run LM Studio, load a model, and enable **Local Server** (default port 1234). The app calls its OpenAI-compatible `/v1/chat/completions` endpoint.
- **ffmpeg**: Required for STT when the client sends WebM (browser recording). We convert WebM → WAV before transcribing.
  - **Windows**: Download from https://ffmpeg.org/ (or https://www.gyan.dev/ffmpeg/builds/), unzip, and add the `bin` folder to your system PATH (e.g. `C:\ffmpeg\bin`). Restart the terminal/IDE so that `ffmpeg` is found.
  - If you see "ffmpeg not found" or "The system cannot find the file specified", ffmpeg is not on PATH.

## Project structure

- `app/core/` – config, security, shared dependencies (e.g. `get_db`, `get_current_user`).
- `app/db/` – engine, session, `seed_topics()`.
- `app/models/` – SQLAlchemy models (User, Topic, ConversationSession, Turn, TurnScore).
- `app/schemas/` – Pydantic request/response models.
- `app/api/v1/` – versioned API: auth, topics, progress, conversation (WebSocket), sessions (REST).
- `app/services/` – STT, TTS, LM client, scoring.

All HTTP API routes are under **`/api/v1`** (e.g. `/api/v1/auth/login`, `/api/v1/topics`, `/api/v1/progress/summary`).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (no auth). |
| POST | `/api/v1/auth/register` | Register; returns JWT. |
| POST | `/api/v1/auth/login` | Login; returns JWT. |
| GET | `/api/v1/topics` | List topics (auth). |
| GET | `/api/v1/progress/summary` | User progress summary (auth). |
| GET | `/api/v1/conversation/sessions` | List user’s conversation sessions (auth). |
| GET | `/api/v1/conversation/sessions/{id}` | Session detail with turns (auth). |
| WS | `/api/v1/ws/conversation` | Real-time spoken conversation (token in query). |

## WebSocket protocol (`/api/v1/ws/conversation`)

Connect with `?token=<JWT>`.

**Client → Server (JSON):**

- `{"type": "start", "topicId": <int>}` – Start a session for the given topic. Send first.
- `{"type": "audio_end"}` – End of utterance; process accumulated binary audio (STT → LLM → TTS → score).
- `{"type": "stop"}` – End session and close.

**Client → Server (binary):** Raw WebM/audio bytes. Accumulated until the next `audio_end`.

**Server → Client (JSON):**

- `{"type": "status", "message": "..."}` – e.g. `connected`, `session_started`, `session_stopped`, `idle_timeout`.
- `{"type": "user_transcript", "text": "..."}` – Transcribed user speech.
- `{"type": "assistant_partial", "text": "...", "done": bool}` – Streaming AI text.
- `{"type": "assistant_audio_chunk", "data": "<base64>"}` – TTS audio chunk.
- `{"type": "turn_score", "fluency", "vocabulary", "grammar", "overall", "feedback"}` – Score for the turn.
- `{"type": "error", "message": "..."}` – Error (e.g. topic not found, transcription failed).

**Flow:** Connect → `start` with `topicId` → send binary audio → `audio_end` → receive transcript, assistant text/audio, score → repeat or `stop`.
