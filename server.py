"""Mini demo luyện phỏng vấn tiếng Anh, chạy local: STT -> LLM (stream) -> TTS.

Chạy:  pip install -r requirements.txt
       uvicorn server:app --port 8000      (LM Studio phải đang bật Local Server)
Mở:    http://localhost:8000

Cách hoạt động:
- App điều khiển luồng phỏng vấn: danh sách câu hỏi nằm trong units.json, app chọn câu tiếp theo.
  LLM chỉ làm 3 việc: phản ứng ngắn với câu trả lời, (có thể) hỏi thêm 1 câu phụ, và viết NOTE.
- Câu hỏi chính, lời chào, lời kết được TTS sẵn và lưu cache.
- Ghi chú (NOTE) chỉ hiện chữ, không đọc thành tiếng.
- Mỗi câu SAY được đưa sang TTS ngay khi LLM viết xong câu đó.
- Nếu Whisper nghe không chắc (avg_logprob thấp), bỏ qua LLM và nhờ người học nói lại.
- Cấu hình đọc từ .env (xem README).
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # log tiếng Việt khi chuyển hướng ra file
BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

import cuda_dlls  # noqa: E402

cuda_dlls.add()  # trước khi nạp faster_whisper

import edge_tts  # noqa: E402
import numpy as np  # noqa: E402
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402

from parsing import (  # noqa: E402
    is_question,
    norm,
    ready_sentences,
    speech_metrics,
    split_sections,
    used_phrase_indices,
)

# ----- Cấu hình (.env hoặc biến môi trường) -----
LM_URL = os.getenv("LM_URL", "http://localhost:1234/v1")
LM_MODEL = os.getenv("LM_MODEL", "qwen2.5-7b-instruct")
LM_TEMPERATURE = float(os.getenv("LM_TEMPERATURE", "0.35"))
LM_SEED = os.getenv("LM_SEED")  # đặt số cố định khi so sánh prompt
MAX_REPLY_TOKENS = int(os.getenv("MAX_REPLY_TOKENS", "160"))
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "3"))  # số cặp hỏi/đáp trước đó gửi cho LLM
FOLLOWUPS = int(os.getenv("INTERVIEW_FOLLOWUPS", "1"))  # câu hỏi phụ tối đa cho mỗi câu chính
MAX_RETRIES = 2  # nói lại tối đa 2 lần rồi chuyển câu, tránh kẹt

STT_MODEL = os.getenv("STT_MODEL", "small.en")
STT_DEVICE = os.getenv("STT_DEVICE", "cpu")
STT_COMPUTE = os.getenv("STT_COMPUTE", "int8")
STT_THREADS = int(os.getenv("STT_THREADS", "8"))
STT_BEAM = int(os.getenv("STT_BEAM", "1"))
STT_VOCAB = os.getenv("STT_VOCAB", "")  # tên riêng, từ nghề nghiệp của bạn
STT_MIN_LOGPROB = float(os.getenv("STT_MIN_LOGPROB", "-1.0"))
STT_MAX_NO_SPEECH = float(os.getenv("STT_MAX_NO_SPEECH", "0.6"))
SAVE_AUDIO_DIR = os.getenv("SAVE_AUDIO_DIR", "")  # vd "recordings" để giữ file ghi âm cho stt_bench.py

TTS_VOICE = os.getenv("TTS_VOICE", "en-US-JennyNeural")
TTS_RATE = os.getenv("TTS_RATE", "-10%")

SYSTEM_TEMPLATE = """You play the INTERVIEWER in a job interview. The candidate is a learner practising spoken English. Each user message gives the current question and the candidate's latest answer.

Never talk about your own job or experience. Never say a first-person sentence that sounds like the candidate's answer. Speak to the candidate as "you".

Scenario: {scenario}

Reply in EXACTLY this format, four lines, no markdown:
RETRY: yes or no
SAY: <one short reaction to the answer, second person, under 15 words, not a question>
ASK: <one question, or NEXT>
NOTE: <one improved version of the candidate's key sentence, first person, under 25 words>

Rules:
- RETRY is yes only if the answer is off-topic, only a few words, not English, or does not make sense (probably misheard). Grammar mistakes do NOT count.
- SAY and ASK respond ONLY to the latest answer, never to earlier ones.
- If RETRY is yes: SAY is a polite "sorry, I didn't quite catch that". ASK is NEXT (the app repeats the question).
- If RETRY is no: ASK is NEXT, unless "Follow-up allowed: yes" and the answer mentions one detail worth asking about. Then ASK is one short follow-up question about that detail.
- NOTE fixes the candidate's grammar and wording, keeps their meaning, and uses the target phrase when it fits. If RETRY is yes, NOTE is a short model answer to the current question using the target phrase.
- NOTE uses ONLY facts the candidate said in this interview. Never invent numbers, names, results or tasks. If a fact is missing, write "..." in its place.
- Never use Vietnamese.

Phrases the candidate is practising:
{phrases}"""

# Ví dụ mẫu cố ý lấy từ nghề khác (logistics) để model không chép nguyên văn vào cuộc nói chuyện thật.
FEW_SHOT = [
    {
        "role": "user",
        "content": "Current question: Could you tell me a little about yourself?\n"
        "Target phrase: I've been working as a ... for ... years.\n"
        "Follow-up allowed: yes\n"
        "Latest answer: I am work in logistic company since four year, I manage the delivery schedule.",
    },
    {
        "role": "assistant",
        "content": "RETRY: no\n"
        "SAY: So you manage delivery schedules, that's an important job.\n"
        "ASK: How many deliveries do you plan in a typical week?\n"
        "NOTE: I've been working at a logistics company for four years, and I manage the delivery schedule.",
    },
    {
        "role": "user",
        "content": "Current question: What is one achievement you're proud of?\n"
        "Target phrase: One of my main achievements was ...\n"
        "Follow-up allowed: no\n"
        "Latest answer: We have problem with late delivery, I change the route plan and late delivery go down thirty percent.",
    },
    {
        "role": "assistant",
        "content": "RETRY: no\n"
        "SAY: Cutting late deliveries by thirty percent is a great result.\n"
        "ASK: NEXT\n"
        "NOTE: One of my main achievements was redesigning our route plan, which cut late deliveries by thirty percent.",
    },
    {
        "role": "user",
        "content": "Earlier in the interview:\n"
        "- Q: Could you tell me a little about yourself? A: I am coordinator in logistic company, four year.\n"
        "Current question: What are you mainly responsible for in your current role?\n"
        "Target phrase: I'm responsible for ...\n"
        "Follow-up allowed: yes\n"
        "Latest answer: Come responsible for the schedule also",
    },
    {
        "role": "assistant",
        "content": "RETRY: yes\n"
        "SAY: Sorry, I didn't quite catch that.\n"
        "ASK: NEXT\n"
        "NOTE: As a logistics coordinator, I'm responsible for ... and ...",
    },
]

app = FastAPI()
units: list[dict] = json.loads((BASE / "units.json").read_text(encoding="utf-8"))
units_by_id = {u["id"]: u for u in units}
lm = AsyncOpenAI(base_url=LM_URL, api_key="lm-studio")


def load_whisper() -> tuple[WhisperModel, str]:
    """Nạp Whisper theo cấu hình; nếu GPU lỗi (thiếu DLL CUDA...) thì về CPU thay vì sập server."""
    print(f"Đang nạp Whisper {STT_MODEL} ({STT_DEVICE}, {STT_COMPUTE}, beam {STT_BEAM}) ...")
    try:
        model = WhisperModel(
            STT_MODEL, device=STT_DEVICE, compute_type=STT_COMPUTE, cpu_threads=STT_THREADS
        )
        list(model.transcribe(np.zeros(16000, dtype=np.float32), beam_size=1)[0])  # chạy thử
        return model, f"{STT_MODEL} · {STT_DEVICE} · {STT_COMPUTE} · beam {STT_BEAM}"
    except Exception as e:  # noqa: BLE001
        if STT_DEVICE == "cpu":
            raise
        print(f"!! Không chạy được Whisper trên {STT_DEVICE}: {e}\n!! Chuyển sang CPU int8.")
        model = WhisperModel(STT_MODEL, device="cpu", compute_type="int8", cpu_threads=STT_THREADS)
        return model, f"{STT_MODEL} · cpu (GPU lỗi) · int8 · beam {STT_BEAM}"


whisper, STT_LABEL = load_whisper()
tts_cache: dict[str, bytes] = {}  # câu cố định (câu hỏi, chào, kết): chỉ TTS lần đầu
background: set[asyncio.Task] = set()


# ----- STT / TTS (điểm thay thế: đổi thư viện chỉ cần sửa các hàm này) -----
def transcribe(path: str, prompt: str = "") -> dict:
    segments, _info = whisper.transcribe(
        path,
        language="en",
        beam_size=STT_BEAM,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=False,
        initial_prompt=prompt or None,
    )
    words, logprob, no_speech, total = [], 0.0, 0.0, 0.0
    for seg in segments:  # generator: nhận dạng thật sự chạy ở vòng lặp này
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


async def tts_bytes(text: str) -> bytes:
    out = bytearray()
    async for chunk in edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE).stream():
        if chunk["type"] == "audio":
            out.extend(chunk["data"])
    return bytes(out)


async def cached_tts(text: str) -> bytes:
    if text not in tts_cache:
        tts_cache[text] = await tts_bytes(text)
    return tts_cache[text]


async def prewarm(unit: dict) -> None:
    questions = unit["questions"]
    texts = [q["ask"] for q in questions[1:]] + [unit["closing"]] + [q["simple"] for q in questions]
    for text in texts:
        try:
            await cached_tts(text)
        except Exception:  # noqa: BLE001  (lần dùng thật sẽ thử lại)
            pass


# ----- Phiên và kết nối -----
STATE_FIELDS = ("q", "asked", "followups", "retries", "done", "history", "used", "speech")


@dataclass
class Session:
    unit: dict
    q: int = 0  # chỉ số câu hỏi chính đang hỏi
    asked: str = ""  # câu đang chờ trả lời (câu chính, câu phụ, hoặc câu hỏi lại)
    followups: int = 0
    retries: int = 0
    done: bool = False
    history: list[dict] = field(default_factory=list)  # [{"q", "a"}]
    used: set[int] = field(default_factory=set)
    speech: list[dict] = field(default_factory=list)  # chỉ số các lượt nói (để tổng kết)
    prev: dict | None = None  # trạng thái trước lượt vừa rồi, cho nút "máy nghe sai"

    def snapshot(self) -> dict:
        return {k: copy.deepcopy(getattr(self, k)) for k in STATE_FIELDS}

    def restore(self, snap: dict) -> None:
        for k, v in snap.items():
            setattr(self, k, v)


class Conn:
    """Bọc WebSocket với khóa để JSON + audio của một câu luôn đi liền nhau."""

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.lock = asyncio.Lock()

    async def json(self, data: dict) -> None:
        async with self.lock:
            await self.ws.send_json(data)

    async def audio(self, text: str, audio: bytes, role: str = "ai") -> None:
        async with self.lock:
            await self.ws.send_json({"type": "sentence", "text": text, "role": role})
            await self.ws.send_bytes(audio)


def build_system(unit: dict) -> str:
    phrases = "\n".join(f"- {p['say']}" for p in unit["phrases"])
    return SYSTEM_TEMPLATE.format(scenario=unit["scenario"], phrases=phrases)


def build_user_message(s: Session, answer: str) -> str:
    q = s.unit["questions"][s.q]
    target = " / ".join(s.unit["phrases"][i]["say"] for i in q["phrases"])
    lines = []
    earlier = s.history[-MAX_HISTORY:] if MAX_HISTORY else []
    if earlier:
        lines.append("Earlier in the interview:")
        lines += [f"- Q: {h['q']} A: {h['a']}" for h in earlier]
    # Câu trả lời mới nhất để cuối cùng: model 7B hay phản ứng với thứ nó đọc sau cùng.
    lines += [
        f"Current question: {s.asked}",
        f"Target phrase: {target}",
        f"Follow-up allowed: {'yes' if s.followups < FOLLOWUPS else 'no'}",
        f"Latest answer: {answer}",
    ]
    return "\n".join(lines)


def next_step(s: Session, secs: dict[str, str]) -> tuple[str, bool]:
    """App (không phải LLM) quyết định câu nói tiếp theo. Trả về (câu, có dùng cache TTS)."""
    retry = secs.get("RETRY", "").lower().startswith("yes")
    ask = secs.get("ASK", "").strip()
    main = s.unit["questions"][s.q]
    if retry and s.retries < MAX_RETRIES:
        # Hỏi lại bằng câu soạn sẵn (không để LLM tự diễn đạt: 7B hay chép câu trong ví dụ mẫu).
        s.retries += 1
        if s.asked in (main["ask"], main["simple"]):
            s.asked = main["simple"]
            return s.asked, True
        return s.asked, False  # đang ở câu hỏi phụ: nhắc lại đúng câu đó
    if not retry and is_question(ask) and s.followups < FOLLOWUPS:
        s.followups += 1
        s.asked = ask
        return ask, False
    s.q, s.followups, s.retries = s.q + 1, 0, 0
    questions = s.unit["questions"]
    if s.q < len(questions):
        s.asked = questions[s.q]["ask"]
        return s.asked, True
    s.q, s.done = len(questions) - 1, True
    return s.unit["closing"], True


def progress(s: Session) -> dict:
    n = len(s.unit["questions"])
    return {"type": "progress", "q": s.q + 1, "n": n, "done": s.done}


def summary(s: Session) -> dict:
    timed = [m for m in s.speech if m["wpm"]]
    avg = lambda k: round(sum(m[k] for m in timed) / len(timed)) if timed else None  # noqa: E731
    phrases = s.unit["phrases"]
    return {
        "type": "summary",
        "turns": len(s.history),
        "questions": len(s.unit["questions"]),
        "phrases_used": [p["say"] for i, p in enumerate(phrases) if i in s.used],
        "phrases_missed": [p["say"] for i, p in enumerate(phrases) if i not in s.used],
        "wpm": avg("wpm"),
        "wpm_speaking": avg("wpm_speaking"),
        "long_pauses": sum(m["long_pauses"] for m in s.speech),
        "spoken_turns": len(s.speech),
    }


async def stream_reply(messages: list[dict]):
    extra = {"seed": int(LM_SEED)} if LM_SEED else {}
    stream = await lm.chat.completions.create(
        model=LM_MODEL,
        messages=messages,
        temperature=LM_TEMPERATURE,
        max_tokens=MAX_REPLY_TOKENS,
        stream=True,
        **extra,
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


EXAMPLE_WORDS = ("logistic", "deliver", "route", "coordinator", "driver")  # từ trong FEW_SHOT


def safe_note(s: Session, q_index: int, note: str, retry: bool) -> str:
    """Chặn NOTE chép từ ví dụ mẫu hoặc tự bịa khi chưa biết gì về người học: thay bằng khung mẫu câu."""
    known = norm(" ".join(h["a"] for h in s.history))
    leaked = any(w in norm(note) and w not in known for w in EXAMPLE_WORDS)
    no_facts = retry and len(s.history) <= 1  # chỉ có câu trả lời vừa rồi (không rõ)
    if note and not leaked and not no_facts:
        return note
    q = s.unit["questions"][q_index]
    return " ".join(s.unit["phrases"][i]["say"] for i in q["phrases"])


async def run_turn(conn: Conn, s: Session, user_text: str, t0: float, t_stt: float | None) -> None:
    q_index = s.q  # next_step có thể chuyển câu, NOTE vẫn thuộc câu này
    messages = [
        {"role": "system", "content": build_system(s.unit)},
        *FEW_SHOT,
        {"role": "user", "content": build_user_message(s, user_text)},
    ]
    s.history.append({"q": s.asked, "a": user_text})

    # (câu, dùng cache?) ; None = hết
    queue: asyncio.Queue[tuple[str, bool] | None] = asyncio.Queue()
    first_audio: dict[str, float] = {}

    async def tts_worker() -> None:
        # Tuần tự để giữ đúng thứ tự câu, nhưng chạy song song với LLM.
        while (item := await queue.get()) is not None:
            text, cached = item
            try:
                audio = await (cached_tts(text) if cached else tts_bytes(text))
            except Exception as e:  # noqa: BLE001
                await conn.json({"type": "error", "msg": f"TTS: {e}"})
                continue
            first_audio.setdefault("t", time.monotonic())
            await conn.audio(text, audio)

    async def say(sentences: list[str]) -> None:
        for sentence in sentences:
            if not sentence.rstrip().endswith("?"):  # câu hỏi do app quyết định, không lấy từ SAY
                await queue.put((sentence, False))

    worker = asyncio.create_task(tts_worker())
    raw, emitted, t_first = "", 0, None
    secs: dict[str, str] = {}
    step: tuple[str, bool] | None = None
    try:
        async for delta in stream_reply(messages):
            t_first = t_first or time.monotonic()
            raw += delta
            secs = split_sections(raw)
            say_done = "ASK" in secs or "NOTE" in secs
            sentences, emitted = ready_sentences(secs.get("SAY", ""), say_done, emitted)
            await say(sentences)
            if step is None and "NOTE" in secs:  # ASK đã đủ: nói câu tiếp theo trong lúc LLM viết NOTE
                step = next_step(s, secs)
                await queue.put(step)
    except Exception as e:  # noqa: BLE001
        await conn.json({"type": "error", "msg": f"LLM: {e}"})
    secs = split_sections(raw)
    if raw.strip() and "SAY" not in secs:
        await conn.json({"type": "error", "msg": "AI trả sai định dạng, app tự chuyển câu hỏi."})
        print("LLM sai định dạng:", raw)
    sentences, emitted = ready_sentences(secs.get("SAY", ""), True, emitted)
    await say(sentences)
    if step is None:
        step = next_step(s, secs)
        await queue.put(step)
    await queue.put(None)
    await worker

    retry = secs.get("RETRY", "").lower().startswith("yes")
    note = safe_note(s, q_index, secs.get("NOTE", ""), retry)
    await conn.json({"type": "note", "text": note, "retry": retry})
    await conn.json(progress(s))
    now = time.monotonic()
    ms = lambda a, b: round((a - b) * 1000) if a and b else 0  # noqa: E731
    await conn.json(
        {
            "type": "metrics",
            "stt_ms": ms(t_stt, t0),
            "llm_first_ms": ms(t_first, t_stt or t0),
            "first_audio_ms": ms(first_audio.get("t"), t0),
            "total_ms": ms(now, t0),
        }
    )
    if s.done:
        await conn.json(summary(s))
    await conn.json({"type": "turn_done", "can_undo": True})


async def handle_user_input(
    conn: Conn,
    s: Session,
    text: str,
    words: list[dict],
    t0: float,
    t_stt: float | None,
    stt: dict | None = None,
) -> None:
    if s.done:
        await conn.json({"type": "error", "msg": "Phiên đã kết thúc. Chọn lại bài để tập tiếp."})
        await conn.json({"type": "turn_done"})
        return
    speech = speech_metrics(words)
    conf = stt["avg_logprob"] if stt else None
    if stt and (stt["avg_logprob"] < STT_MIN_LOGPROB or stt["no_speech"] > STT_MAX_NO_SPEECH):
        # Máy nghe không chắc: không để LLM đoán, nhờ người học nói lại.
        await conn.json(
            {"type": "transcript", "text": text, "speech": speech, "used": sorted(s.used),
             "unclear": True, "conf": conf}
        )
        await conn.json({"type": "metrics", "stt_ms": round(((t_stt or t0) - t0) * 1000)})
        await conn.json({"type": "turn_done", "can_undo": False})
        return
    s.prev = s.snapshot()
    s.used |= set(used_phrase_indices(text, s.unit["phrases"]))
    if words:
        s.speech.append(speech)
    await conn.json(
        {"type": "transcript", "text": text, "speech": speech, "used": sorted(s.used),
         "unclear": False, "conf": conf}
    )
    await conn.json({"type": "status", "msg": "thinking"})
    await run_turn(conn, s, text, t0, t_stt)


async def start_session(conn: Conn, unit: dict) -> Session:
    first = unit["questions"][0]["ask"]
    session = Session(unit=unit, asked=first)
    public = {k: unit[k] for k in ("id", "title", "goal", "scenario")} | {
        "phrases": [{"say": p["say"]} for p in unit["phrases"]],
        "stt": STT_LABEL,
    }
    await conn.json({"type": "started", "unit": public})
    await conn.json(progress(session))
    task = asyncio.create_task(prewarm(unit))
    background.add(task)
    task.add_done_callback(background.discard)
    opening = f"{unit['greeting']} {first}"
    await conn.audio(opening, await cached_tts(opening))
    await conn.json({"type": "turn_done", "can_undo": False})
    return session


def save_recording(data: bytes) -> str:
    if SAVE_AUDIO_DIR:
        folder = BASE / SAVE_AUDIO_DIR
        folder.mkdir(exist_ok=True)
        path = folder / f"{datetime.now():%Y%m%d-%H%M%S-%f}.webm"
        path.write_bytes(data)
        return str(path)
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(data)
        return f.name


# ----- Routes -----
@app.get("/")
async def index() -> FileResponse:
    return FileResponse(BASE / "index.html")


# ----- Đọc theo câu mẫu: thu âm có sẵn đáp án cho stt_bench.py -----
BENCH_DIR = BASE / "recordings" / "bench"
bench_sentences: list[str] = json.loads((BASE / "bench_sentences.json").read_text(encoding="utf-8"))


@app.get("/bench")
async def bench_page() -> FileResponse:
    return FileResponse(BASE / "bench.html")


@app.get("/api/bench")
async def bench_list() -> list[dict]:
    return [
        {"text": t, "done": (BENCH_DIR / f"{i:02d}.webm").exists()}
        for i, t in enumerate(bench_sentences)
    ]


@app.post("/api/bench/{i}")
async def bench_save(i: int, request: Request) -> dict:
    if not 0 <= i < len(bench_sentences):
        raise HTTPException(404)
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    (BENCH_DIR / f"{i:02d}.webm").write_bytes(await request.body())
    (BENCH_DIR / f"{i:02d}.ref.txt").write_text(bench_sentences[i], encoding="utf-8")
    return {"ok": True}


@app.get("/api/units")
async def list_units() -> list[dict]:
    return [{"id": u["id"], "title": u["title"]} for u in units]


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    conn = Conn(ws)
    session: Session | None = None
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break

            if msg.get("text") is not None:
                data = json.loads(msg["text"])
                kind = data.get("type")
                if kind == "start" and data.get("unit") in units_by_id:
                    session = await start_session(conn, units_by_id[data["unit"]])
                elif kind == "text" and session and data.get("text", "").strip():
                    await handle_user_input(
                        conn, session, data["text"].strip(), [], time.monotonic(), None
                    )
                elif kind == "undo" and session:
                    if session.prev is not None:
                        session.restore(session.prev)
                        session.prev = None
                        await conn.json({"type": "undone", "used": sorted(session.used)})
                        await conn.json(progress(session))
                    await conn.json({"type": "turn_done", "can_undo": False})
                elif kind == "say_it" and data.get("text", "").strip():
                    text = data["text"].strip()
                    await conn.audio(text, await tts_bytes(text), role="model")

            elif msg.get("bytes") is not None and session:
                t0 = time.monotonic()
                await conn.json({"type": "status", "msg": "transcribing"})
                path = save_recording(msg["bytes"])
                prompt = f"{STT_VOCAB} {session.unit.get('vocab', '')}".strip()
                try:
                    result = await asyncio.to_thread(transcribe, path, prompt)
                except Exception as e:  # noqa: BLE001
                    await conn.json({"type": "error", "msg": f"STT: {e}"})
                    await conn.json({"type": "turn_done", "can_undo": False})
                    continue
                finally:
                    if not SAVE_AUDIO_DIR:
                        os.unlink(path)
                if SAVE_AUDIO_DIR:
                    Path(path).with_suffix(".hyp.txt").write_text(result["text"], encoding="utf-8")
                t_stt = time.monotonic()
                print(
                    f"STT logprob={result['avg_logprob']} no_speech={result['no_speech']}: {result['text']}"
                )
                if not result["text"]:
                    await conn.json(
                        {"type": "error", "msg": "Không nghe rõ, hãy nói lại gần micro hơn."}
                    )
                    await conn.json({"type": "turn_done", "can_undo": False})
                    continue
                await handle_user_input(
                    conn, session, result["text"], result["words"], t0, t_stt, result
                )
    except WebSocketDisconnect:
        pass
