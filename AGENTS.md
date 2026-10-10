# Speaking demo: luyện phỏng vấn tiếng Anh, chạy local

Người dùng là lập trình viên Java người Việt, hiểu tiếng Anh tốt nhưng nói chưa trôi chảy.
App tạo một buổi phỏng vấn giả: nghe câu hỏi, nói, xem cách nói tự nhiên hơn (NOTE), nói lại.
Đây là bản demo để thử luồng nói, sau đó sẽ ghép vào dự án chính (dự án chính đã có đăng nhập, DB, roadmap).

**Stack:** backend FastAPI + WebSocket (Python 3.11), frontend HTML/CSS/JS thuần (không build).
LLM Qwen2.5-7B qua LM Studio, STT faster-whisper `large-v3-turbo` trên GPU, TTS edge-tts. Cấu hình nằm trong `.env` ở thư mục gốc.

## Cấu trúc

```
backend/
  app/
    main.py              # tạo FastAPI app, nạp Whisper lúc khởi động, gắn router, phục vụ frontend
    core/                # config.py (đọc .env, đường dẫn), cuda.py (DLL CUDA trên Windows)
    api/routes/          # ws.py (WebSocket /ws), units.py, bench.py, history.py (/api/...)
    services/            # stt.py (Whisper), tts.py (edge-tts + cache), llm.py (LM Studio), history.py (SQLite)
    interview/           # session.py (trạng thái, next_step), prompts.py, turn.py (một lượt), units.py
    utils/               # parsing.py (hàm thuần), ws.py (Conn)
    data/                # units.json (bài tập), bench_sentences.json
  scripts/               # replay.py (so prompt), stt_bench.py (đo STT)
  tests/                 # pytest
  pyproject.toml, requirements*.txt
frontend/
  index.html, history.html, bench.html
  css/                   # base.css (biến màu, component dùng chung), app.css, history.css, bench.css
  js/                    # app.js, history.js, bench.js
docs/                    # tài liệu theo tính năng (bảng bên dưới)
recordings/              # giọng nói thật của người dùng, không commit
data/                    # history.db: lịch sử luyện tập của người dùng, không commit
```

Lớp phụ thuộc một chiều: `api` -> `interview` -> `services` / `utils` -> `core`. `utils/parsing.py` không phụ thuộc gì (dễ test).

## Lệnh (chạy từ thư mục `backend/`)

```
..\.venv\Scripts\activate
uvicorn app.main:app --port 8000      # app của người dùng; agent thử nghiệm ở cổng 8001
python -m pytest                      # test logic thuần
python -m scripts.replay answers.txt --runs 3 --url ws://localhost:8001/ws
python -m scripts.stt_bench --config large-v3-turbo,cuda,float16,3 --show
```

## Bản đồ tài liệu

Đọc file tương ứng **trước khi** sửa một tính năng.

| Tính năng | Tài liệu | Mã nguồn chính |
|---|---|---|
| Tổng quan, một lượt nói, giao thức WebSocket | [docs/architecture.md](docs/architecture.md) | `api/routes/ws.py`, `interview/turn.py`, `utils/ws.py` |
| Luồng phỏng vấn: câu hỏi, hỏi lại, câu hỏi phụ, hoàn tác, tổng kết | [docs/features/interview-flow.md](docs/features/interview-flow.md) | `data/units.json`, `interview/session.py`, `interview/turn.py` |
| Prompt LLM, định dạng RETRY/SAY/ASK/NOTE, chặn NOTE xấu | [docs/features/llm-prompt.md](docs/features/llm-prompt.md) | `interview/prompts.py`, `services/llm.py`, `utils/parsing.py`, `scripts/replay.py` |
| Nhận dạng giọng nói, GPU, chặn khi nghe không chắc | [docs/features/speech-recognition.md](docs/features/speech-recognition.md) | `services/stt.py`, `core/cuda.py` |
| Giọng đọc, cache, phát âm thanh | [docs/features/tts-audio.md](docs/features/tts-audio.md) | `services/tts.py`, `frontend/js/app.js` |
| Chỉ số nói, mẫu câu đã dùng | [docs/features/speech-metrics.md](docs/features/speech-metrics.md) | `utils/parsing.py`, `interview/session.py` (`summary`) |
| Lịch sử luyện tập, trang Tiến bộ, biểu đồ xu hướng | [docs/features/session-history.md](docs/features/session-history.md) | `services/history.py`, `api/routes/history.py`, `frontend/history.html` |
| Đo độ chính xác STT, trang đọc theo câu mẫu | [docs/features/stt-benchmark.md](docs/features/stt-benchmark.md) | `scripts/stt_bench.py`, `api/routes/bench.py`, `frontend/bench.html` |
| Giao diện | [docs/features/frontend.md](docs/features/frontend.md) | `frontend/` |
| Biến cấu hình | [docs/configuration.md](docs/configuration.md) | `.env`, `core/config.py` |
| Môi trường Windows, kiểm thử, lỗi thường gặp | [docs/dev-environment.md](docs/dev-environment.md) | |

Đường dẫn trong cột mã nguồn tính từ `backend/app/`, trừ khi ghi rõ `frontend/` hay `scripts/`.

## Quy tắc chung

- **App điều khiển luồng phỏng vấn, không phải LLM.** LLM chỉ phản ứng, hỏi tối đa một câu phụ và viết NOTE. Lý do nằm trong interview-flow.md.
- **AI luôn là người phỏng vấn.** Lời AI nói ở ngôi thứ hai. Câu mẫu ngôi thứ nhất chỉ nằm trong NOTE (hiện chữ, không đọc).
- **Ngôn ngữ:**
  - **Code và comment bằng tiếng Anh:** tên biến/hàm, comment, docstring, log in ra terminal, thông báo `assert`/exception, output và `--help` của script, commit message.
  - **Chữ người dùng nhìn thấy bằng tiếng Việt:** chữ trên giao diện (`frontend/`), các tin `error` gửi qua WebSocket, nhãn hiện trên giao diện. Đây là chuỗi trong code nhưng không phải comment, nên giữ tiếng Việt.
  - **Prompt và lời AI nói bằng tiếng Anh**, không bao giờ có tiếng Việt.
  - **Tài liệu (`docs/`, `AGENTS.md`, `README.md`) bằng tiếng Việt.**
- Không chấm điểm bằng LLM. Chỉ dùng chỉ số khách quan.
- Giữ code đơn giản, không thêm framework hay bước build cho frontend. Giữ hướng phụ thuộc giữa các lớp như trên.
- Đổi prompt thì kiểm chứng bằng `scripts/replay.py`. Đổi STT thì đo bằng `scripts/stt_bench.py`. Không đoán.
- **Cổng 8000 là server của người dùng.** Thử nghiệm ở cổng 8001 với `HISTORY_DB` trỏ sang file tạm (không ghi lẫn vào lịch sử thật), không tắt `python.exe` theo tên, không xóa `recordings/` hay `data/`.
- **Sửa tính năng nào thì cập nhật file docs tương ứng trong cùng commit.** Thêm tính năng mới thì thêm file trong `docs/features/` và một dòng vào bảng trên.

## Git và commit

Theo [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/). Commit message viết bằng tiếng Anh.

```
<type>(<scope>): <subject>

<body: vì sao thay đổi, không chỉ thay đổi gì>

<footer: BREAKING CHANGE: ..., Refs: ..., Co-Authored-By: ...>
```

- **type:** `feat` (tính năng mới), `fix` (sửa lỗi), `refactor` (đổi cấu trúc, không đổi hành vi), `perf`, `test`, `docs`, `style` (định dạng, không đổi logic), `build` (dependency, requirements), `chore` (việc vặt, cấu hình), `revert`.
- **scope** (không bắt buộc): `backend`, `frontend`, `stt`, `tts`, `llm`, `interview`, `bench`, `config`, `docs`.
- **subject:** câu mệnh lệnh, chữ thường ở đầu, không dấu chấm cuối, tối đa 72 ký tự. Ví dụ: `fix(stt): fall back to cpu when cuda dlls are missing`.
- **body:** xuống dòng ở khoảng 72 ký tự. Nêu lý do và cách đã kiểm chứng (test, replay, stt_bench).
- **Thay đổi phá vỡ tương thích** (đổi lệnh chạy, đổi biến `.env`, đổi giao thức WebSocket): thêm `!` sau type (`refactor!: ...`) và footer `BREAKING CHANGE: <mô tả + cách chuyển đổi>`.
- Mỗi commit là một thay đổi logic trọn vẹn. Không gộp việc không liên quan vào một commit.
- Trước khi commit: `python -m pytest` phải qua. Đổi prompt hoặc STT thì ghi kết quả `replay.py` / `stt_bench.py` vào body.
- Không commit `.env`, `recordings/`, file âm thanh (đã có trong `.gitignore`). Thêm biến cấu hình mới thì cập nhật `.env.example` trong cùng commit.
- **Nhánh:** `<type>/<mô-tả-ngắn>`, ví dụ `feat/shadowing-mode`, `fix/stt-unclear-threshold`. Không commit thẳng vào `main`. Chỉ commit, push hay gộp nhánh khi người dùng yêu cầu.
