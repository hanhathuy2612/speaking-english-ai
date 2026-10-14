# Speaking app: luyện nói tiếng Anh (giao tiếp, công việc, phỏng vấn), chạy local

Người dùng là lập trình viên Java người Việt, hiểu tiếng Anh tốt nhưng nói chưa trôi chảy.
App tạo các buổi hội thoại có kịch bản (trò chuyện, tình huống công việc, phỏng vấn): học câu với giáo viên (bài giảng),
nghe câu hỏi, nói, xem cách nói tự nhiên hơn (NOTE), nói lại, rồi ôn lại các NOTE theo lịch ngắt quãng. Bài kiểm tra nói 2 phút đo tiến bộ bằng số.
Nhiều người dùng chung một server: mỗi người có tài khoản và lịch sử riêng; quản trị viên quản lý người dùng và soạn bài học trên web (có AI soạn nháp).
Đây là code chính thức của sản phẩm, nhánh `main` trên `hanhathuy2612/speaking-english-ai`.
App Angular cũ được giữ ở nhánh `old_main` của repo đó, chỉ dùng để tham khảo ý tưởng (topic, roadmap, đóng gói Android
bằng Capacitor), không ghép code vào. Không đưa lại các cách làm đã bỏ của app đó: LLM tự dẫn dắt buổi nói, LLM chấm điểm, câu mẫu đọc thành tiếng
(ngoại lệ duy nhất: giáo viên ở phần bài giảng đọc câu cần học để người học đọc theo, xem [lesson.md](docs/features/lesson.md)).

**Stack:** backend FastAPI + WebSocket (Python 3.11), frontend React 19 + TypeScript + Vite (Node 22.12+).
LLM Qwen2.5-7B qua LM Studio, STT faster-whisper `large-v3-turbo` trên GPU, TTS edge-tts. Cấu hình nằm trong `.env` ở thư mục gốc.

## Cấu trúc

```
backend/
  app/
    main.py              # tạo FastAPI app, nạp Whisper lúc khởi động, gắn router, phục vụ frontend
    __main__.py          # python -m app: chạy uvicorn với SERVER_*/SSL_* trong .env (run.cmd ở thư mục gốc gọi file này)
    core/                # config.py (đọc .env, đường dẫn), cuda.py (DLL CUDA trên Windows)
    api/deps.py          # current_user, require_admin, ws_user: đăng nhập và vai trò
    api/routes/          # ws.py (WebSocket /ws), units.py (+ /api/stages), lessons.py (bài giảng), review.py, drills.py, fluency.py, check.py, talks.py, bench.py, history.py (/api/...),
                         #   auth.py (đăng nhập, đăng ký, email), admin_users.py (quản lý người dùng), admin_content.py (sửa bài học)
    services/            # stt.py (Whisper), tts.py (edge-tts + cache), llm.py (LM Studio), db.py (file SQLite), accounts.py (tài khoản, phiên),
                         #   history.py (lịch sử theo user_id), content.py (bài học trong DB), mailer.py (SMTP), recordings.py (file ghi âm cũ)
    interview/           # session.py (trạng thái, next_step), prompts.py, steps.py (ý để nói dài hơn), turn.py (một lượt), shadow.py (nói lại), retell.py (trả lời lại), units.py (nội dung đang dùng + validate), lesson.py (bài giảng), talks.py (bài giảng nói 2 phút), check_review.py (AI viết lại bài kiểm tra), review.py (thẻ ôn), drafts.py (AI soạn nháp bài)
    assessment/          # không dùng LLM: metrics.py (đo), check.py (kiểm tra 2 phút), drills.py (phát âm), fluency.py (4–3–2), stages.py (mở giai đoạn)
    utils/               # parsing.py, compare.py (hàm thuần), ws.py (Conn)
    data/                # units.json (chủ đề + bài gốc, chép vào DB lúc khởi động), stages.json, drills.json, check_prompts.json, talks.json, fluency_prompts.json, bench_sentences.json
  scripts/               # replay.py (so prompt), stt_bench.py (đo STT), make_cert.py (HTTPS cho LAN), create_user.py (tạo tài khoản, admin đầu tiên)
  tests/                 # pytest
  pyproject.toml, requirements*.txt
frontend/                # React + TypeScript + Vite; build vào frontend/dist (backend phục vụ)
  src/
    main.tsx             # React Router: / , /lesson/:unitId , /talk/:talkId[/practice] , /review , /roadmap , /sounds , /fluency , /check , /history , /account ; admin: /bench , /admin/... ;
                         #   chưa đăng nhập: /login , /signup , /forgot , /verify , /reset
    api/                 # types.ts (kiểu dữ liệu API + giao thức WebSocket), http.ts (gọi JSON, 401 thì về trang đăng nhập)
    auth/                # AuthContext (người đang đăng nhập), guards (RequireAuth, RequireAdmin, GuestOnly)
    components/          # AppBar (+ thanh tab trên điện thoại), Icons, ui (Chip, StatusLine), WordDiff, Recorder, Sheet, Lead
    hooks/               # useMic (ghi âm bấm-bấm), useAudioQueue (phát MP3), useTeacherVoice (giọng giáo viên)
    features/            # practice/ (useInterview + các component), lesson/ (bài giảng), review/, roadmap/, sounds/, fluency/, check/, talk/, history/, bench/,
                         #   auth/ (đăng nhập, đăng ký), account/, admin/
    lib/                 # hàm thuần + test Vitest
    styles/              # base.css (token, component chung, bảng), practice.css, lesson.css, review.css, roadmap.css, sounds.css, fluency.css, check.css, talk.css, history.css, bench.css,
                         #   auth.css, admin.css
docs/                    # tài liệu theo tính năng (bảng bên dưới)
recordings/              # giọng nói thật của người dùng, không commit
data/                    # history.db: tài khoản và lịch sử luyện tập của người dùng, không commit
```

Lớp phụ thuộc một chiều: `api` -> `interview` / `assessment` -> `services` / `utils` -> `core`. `utils/parsing.py` không phụ thuộc gì (dễ test).

## Lệnh

Backend (từ `backend/`):

```
..\.venv\Scripts\activate
uvicorn app.main:app --port 8000      # app của người dùng; agent thử nghiệm ở cổng 8001
python -m app                         # như trên nhưng đọc SERVER_HOST/PORT, SSL_* trong .env (LAN + HTTPS); ở thư mục gốc: run
python -m pytest                      # test backend
python -m scripts.create_user you@example.com --admin   # tạo tài khoản (admin đầu tiên nhận lịch sử cũ)
python -m scripts.replay answers.txt --runs 3 --url ws://localhost:8001/ws --email admin@test.local
python -m scripts.stt_bench --config large-v3-turbo,cuda,float16,3 --show
python -m scripts.make_cert 192.168.0.2   # HTTPS cho thiết bị trong LAN, xem docs/dev-environment.md
```

Frontend (từ `frontend/`):

```
npm install
npm run dev        # http://localhost:5173, proxy /api và /ws sang backend (BACKEND_URL, mặc định :8000)
npm run build      # tsc + build vào dist/, backend phục vụ bản này ở :8000
npm test           # Vitest
npm run format     # Prettier; npm run format:check chỉ kiểm tra
```

## Bản đồ tài liệu

Đọc file tương ứng **trước khi** sửa một tính năng.

| Tính năng | Tài liệu | Mã nguồn chính |
|---|---|---|
| Tổng quan, một lượt nói, giao thức WebSocket | [docs/architecture.md](docs/architecture.md) | `api/routes/ws.py`, `interview/turn.py`, `utils/ws.py` |
| Luồng phỏng vấn: câu hỏi, hỏi lại, câu hỏi phụ, hoàn tác, tổng kết | [docs/features/interview-flow.md](docs/features/interview-flow.md) | `data/units.json`, `interview/session.py`, `interview/turn.py` |
| Prompt LLM, định dạng RETRY/SAY/ASK/NOTE, chặn NOTE xấu | [docs/features/llm-prompt.md](docs/features/llm-prompt.md) | `interview/prompts.py`, `services/llm.py`, `utils/parsing.py`, `scripts/replay.py` |
| Nhận dạng giọng nói, GPU, chặn khi nghe không chắc | [docs/features/speech-recognition.md](docs/features/speech-recognition.md) | `services/stt.py`, `core/cuda.py` |
| Giọng đọc, cache, phát âm thanh | [docs/features/tts-audio.md](docs/features/tts-audio.md) | `services/tts.py`, `frontend/src/hooks/useAudioQueue.ts` |
| Nói dài hơn: 2–3 ý cần thêm dưới NOTE, "Trả lời lại dài hơn" so với lần đầu, cắt lý do bịa trong NOTE | [docs/features/answer-steps.md](docs/features/answer-steps.md) | `data/units.json` (`steps`), `interview/steps.py`, `interview/retell.py`, `frontend/src/features/practice/CoachCard.tsx` |
| Bài giảng trước khi đóng vai: giáo viên giảng từng câu, người học đọc theo, rồi mới sang phần đóng vai; bài chỉ xong khi đủ hai phần | [docs/features/lesson.md](docs/features/lesson.md) | `data/units.json` (`lesson`), `interview/lesson.py`, `api/routes/lessons.py`, `frontend/src/features/lesson/` |
| Chỉ số nói, mẫu câu đã dùng | [docs/features/speech-metrics.md](docs/features/speech-metrics.md) | `utils/parsing.py`, `interview/session.py` (`summary`) |
| Nói lại câu mẫu (shadowing): so từng từ, chuẩn hóa số và viết tắt | [docs/features/shadowing.md](docs/features/shadowing.md) | `interview/shadow.py`, `utils/compare.py`, `frontend/src/features/practice/CoachCard.tsx` |
| Lộ trình: 5 giai đoạn mở khóa theo số đo, 6 chủ đề, 24 bài, bài tiếp theo | [docs/features/roadmap.md](docs/features/roadmap.md) | `data/stages.json`, `assessment/stages.py`, `data/units.json`, `api/routes/units.py`, `frontend/src/features/roadmap/` |
| Ôn tập: NOTE và mẫu câu bỏ sót thành thẻ, ôn cuối buổi và ôn ngắt quãng (1, 3, 7, 14, 30, 60 ngày) | [docs/features/review.md](docs/features/review.md) | `interview/review.py`, `api/routes/review.py`, `frontend/src/features/review/` |
| Luyện phát âm theo lỗi đã đo, từ trọng tâm, nhóm câu từng đọc sai | [docs/features/pronunciation-drills.md](docs/features/pronunciation-drills.md) | `data/drills.json`, `assessment/drills.py`, `api/routes/drills.py`, `frontend/src/features/sounds/` |
| Nói dài 4–3–2: kể một chuyện 3 lần, 4/3/2 phút | [docs/features/fluency-432.md](docs/features/fluency-432.md) | `assessment/fluency.py`, `api/routes/fluency.py`, `frontend/src/features/fluency/` |
| Chế độ trò chuyện: AI đóng vai đồng nghiệp, trưởng nhóm, khách hàng… (`role`, `partner`) | [docs/features/conversation-mode.md](docs/features/conversation-mode.md) | `interview/prompts.py`, `data/units.json` (chủ đề `daily`, `workplace`) |
| Bài kiểm tra nói 2 phút: tiêu chí, ngập ngừng giữa câu, trang `/check` | [docs/features/speaking-check.md](docs/features/speaking-check.md) | `assessment/check.py`, `api/routes/check.py`, `frontend/src/features/check/` |
| Bài giảng nói 2 phút theo dạng đề (ý kiến, kể chuyện, giải thích, miêu tả) + luyện đề riêng; học sau bài kiểm tra: chỗ bí, AI viết lại (đánh dấu ý tự thêm), cụm từ thành thẻ ôn, nói lại; đề đã ôn không ra lại | [docs/features/talk-lessons.md](docs/features/talk-lessons.md) | `data/talks.json`, `interview/talks.py`, `interview/check_review.py`, `api/routes/talks.py`, `api/routes/check.py`, `frontend/src/features/talk/`, `frontend/src/features/check/CheckLearn.tsx` |
| Tài khoản: đăng nhập (cookie), vai trò user/admin, đăng ký + xác nhận email, quên mật khẩu, dữ liệu theo từng người, quản lý người dùng | [docs/features/accounts.md](docs/features/accounts.md) | `services/accounts.py`, `api/deps.py`, `api/routes/auth.py`, `api/routes/admin_users.py`, `services/mailer.py`, `frontend/src/auth/`, `frontend/src/features/auth/`, `frontend/src/features/admin/` |
| Quản trị nội dung: sửa/thêm/ẩn bài và chủ đề trên web, AI soạn nháp, nội dung trong DB đồng bộ với `units.json` | [docs/features/content-admin.md](docs/features/content-admin.md) | `services/content.py`, `interview/units.py`, `interview/drafts.py`, `api/routes/admin_content.py`, `frontend/src/features/admin/` |
| Lịch sử luyện tập, trang Tiến bộ, biểu đồ xu hướng | [docs/features/session-history.md](docs/features/session-history.md) | `services/history.py`, `api/routes/history.py`, `frontend/src/features/history/` |
| Đo độ chính xác STT, trang đọc theo câu mẫu | [docs/features/stt-benchmark.md](docs/features/stt-benchmark.md) | `scripts/stt_bench.py`, `api/routes/bench.py`, `frontend/src/features/bench/` |
| Giao diện React: cấu trúc, luồng dữ liệu, hệ thiết kế, cài lên điện thoại (PWA) | [docs/features/frontend.md](docs/features/frontend.md) | `frontend/src/` |
| Biến cấu hình | [docs/configuration.md](docs/configuration.md) | `.env`, `core/config.py` |
| Môi trường Windows, kiểm thử, lỗi thường gặp, mở app từ điện thoại trong LAN (HTTPS) | [docs/dev-environment.md](docs/dev-environment.md) | `scripts/make_cert.py` |

Đường dẫn trong cột mã nguồn tính từ `backend/app/`, trừ khi ghi rõ `frontend/` hay `scripts/`.

## Quy tắc chung

- **App điều khiển luồng phỏng vấn, không phải LLM.** LLM chỉ phản ứng, hỏi tối đa một câu phụ và viết NOTE. Lý do nằm trong interview-flow.md.
- **AI luôn là người đối thoại theo `role` của bài** (người phỏng vấn, đồng nghiệp, trưởng nhóm…), không bao giờ nói thay người học. Lời AI nói ở ngôi thứ hai. Câu mẫu ngôi thứ nhất chỉ nằm trong NOTE (hiện chữ, không đọc). Giáo viên ở phần bài giảng là vai riêng, giọng riêng, và chỉ ở đó mới đọc câu mẫu.
- **Ngôn ngữ:**
  - **Code và comment bằng tiếng Anh:** tên biến/hàm, comment, docstring, log in ra terminal, thông báo `assert`/exception, output và `--help` của script, commit message.
  - **Chữ người dùng nhìn thấy bằng tiếng Việt:** chữ trên giao diện (`frontend/`), các tin `error` gửi qua WebSocket, nhãn hiện trên giao diện. Đây là chuỗi trong code nhưng không phải comment, nên giữ tiếng Việt.
  - **Prompt và lời AI nói bằng tiếng Anh**, không bao giờ có tiếng Việt.
  - **Tài liệu (`docs/`, `AGENTS.md`, `README.md`) bằng tiếng Việt.**
- Không chấm điểm bằng LLM. Chỉ dùng chỉ số khách quan. (LLM soạn nháp bài học cho admin được, vì admin duyệt trước khi lưu.)
- Giữ code đơn giản. Frontend dùng React + TypeScript, không thêm thư viện UI hay state manager khi chưa thật cần; dependency mới phải ghim phiên bản và `npm audit` sạch. Giữ hướng phụ thuộc giữa các lớp backend như trên.
- Đổi prompt thì kiểm chứng bằng `scripts/replay.py`. Đổi STT thì đo bằng `scripts/stt_bench.py`. Đổi frontend thì `npm run format`, rồi `npm run build` + `npm test` phải qua. Không đoán.
- **Cổng 8000 là server của người dùng.** Thử nghiệm ở cổng 8001 với `HISTORY_DB` trỏ sang file tạm (không ghi lẫn vào lịch sử thật), không tắt `python.exe` theo tên, không xóa `recordings/` hay `data/`.
  App cần đăng nhập: tạo tài khoản thử trong DB tạm bằng `scripts/create_user.py` (mật khẩu qua `NEW_USER_PASSWORD`), xem docs/dev-environment.md.
- **Dữ liệu của người học luôn lọc theo `user_id`.** Hàm đọc mới trong `services/history.py` nhận `uid` đầu tiên; route lấy nó từ `Depends(current_user)`. Id do client gửi lên (buổi tập, thẻ, file ghi âm) phải kiểm tra chủ sở hữu.
- **Sửa tính năng nào thì cập nhật file docs tương ứng trong cùng commit.** Thêm tính năng mới thì thêm file trong `docs/features/` và một dòng vào bảng trên.

## Git và commit

Theo [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/). Commit message viết bằng tiếng Anh.

```
<type>(<scope>): <subject>

<body: vì sao thay đổi, không chỉ thay đổi gì>

<footer: BREAKING CHANGE: ..., Refs: ...>
```

- **type:** `feat` (tính năng mới), `fix` (sửa lỗi), `refactor` (đổi cấu trúc, không đổi hành vi), `perf`, `test`, `docs`, `style` (định dạng, không đổi logic), `build` (dependency, requirements), `chore` (việc vặt, cấu hình), `revert`.
- **scope** (không bắt buộc): `backend`, `frontend`, `stt`, `tts`, `llm`, `interview`, `shadowing`, `history`, `bench`, `check`, `drills`, `fluency`, `roadmap`, `review`, `config`, `docs`.
- **subject:** câu mệnh lệnh, chữ thường ở đầu, không dấu chấm cuối, tối đa 72 ký tự. Ví dụ: `fix(stt): fall back to cpu when cuda dlls are missing`.
- **body:** xuống dòng ở khoảng 72 ký tự. Nêu lý do và cách đã kiểm chứng (test, replay, stt_bench).
- **Không thêm dòng `Co-Authored-By`** (hay bất kỳ dòng ghi công AI nào) vào commit message, kể cả khi công cụ tự gợi ý. Lịch sử đã được viết lại để bỏ các dòng này.
- **Thay đổi phá vỡ tương thích** (đổi lệnh chạy, đổi biến `.env`, đổi giao thức WebSocket): thêm `!` sau type (`refactor!: ...`) và footer `BREAKING CHANGE: <mô tả + cách chuyển đổi>`.
- Mỗi commit là một thay đổi logic trọn vẹn. Không gộp việc không liên quan vào một commit.
- Trước khi commit: `python -m pytest` phải qua. Đổi prompt hoặc STT thì ghi kết quả `replay.py` / `stt_bench.py` vào body.
- Không commit `.env`, `recordings/`, file âm thanh (đã có trong `.gitignore`). Thêm biến cấu hình mới thì cập nhật `.env.example` trong cùng commit.
- **Nhánh:** `<type>/<mô-tả-ngắn>`, ví dụ `feat/shadowing-mode`, `fix/stt-unclear-threshold`. Không commit thẳng vào `main`. Chỉ commit, push hay gộp nhánh khi người dùng yêu cầu.
