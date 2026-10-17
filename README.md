# Phòng tập phỏng vấn tiếng Anh (chạy local)

Buổi phỏng vấn giả để luyện nói: nghe câu hỏi, trả lời bằng giọng nói, xem cách nói tự nhiên hơn, nói lại.
Chạy hoàn toàn trên máy: LM Studio (Qwen2.5-7B), faster-whisper (GPU), edge-tts.

## Cài đặt

Cần: Python 3.11, Node 22.12+, MySQL 8.0, LM Studio đã nạp `qwen2.5-7b-instruct` và bật Local Server (cổng 1234).

Tạo database `speaking` (collation `utf8mb4_bin`) và user MySQL theo [docs/dev-environment.md](docs/dev-environment.md#cài-mysql-một-lần-cho-mỗi-máy).

```
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
pip install -r backend/requirements-gpu.txt     # nếu có GPU NVIDIA (khoảng 1 GB)
copy .env.example .env                          # rồi sửa DATABASE_URL, STT_VOCAB và cấu hình STT

cd frontend
npm install
npm run build                                   # build giao diện React vào frontend/dist
```

Với GPU, đặt trong `.env`: `STT_MODEL=large-v3-turbo`, `STT_DEVICE=cuda`, `STT_COMPUTE=float16`, `STT_BEAM=3`.
Nếu GPU lỗi, server tự chuyển về CPU và ghi "(GPU lỗi)" trên giao diện.

## Chạy

```
cd backend
python -m scripts.create_user ban@example.com --admin   # lần đầu: tạo tài khoản quản trị (hoặc đặt ADMIN_EMAIL/ADMIN_PASSWORD trong .env)
uvicorn app.main:app --port 8000
```

Server tự áp dụng migration database lúc khởi động. Mọi trang đều cần đăng nhập ([docs/features/accounts.md](docs/features/accounts.md)).
Triển khai bằng Docker Compose (MySQL + app trên GPU): xem [docs/deployment.md](docs/deployment.md).

- http://localhost:8000: phòng tập. Bấm nút micro để nói, bấm lần nữa để gửi (trên máy tính có thể giữ phím Space). Có ô gõ chữ để thử không cần micro.
- http://localhost:8000/history: tiến bộ qua các buổi tập.
- http://localhost:8000/bench (chỉ admin): đọc 18 câu mẫu để đo độ chính xác nhận dạng giọng nói.

Sửa giao diện thì build lại (`npm run build` trong `frontend/`) rồi tải lại trang, không cần khởi động lại server.

## Phát triển

```
cd backend
pip install -r requirements-dev.txt
python -m pytest

cd frontend
npm run dev        # http://localhost:5173, tự nạp lại khi sửa, gọi backend ở cổng 8000
npm test
```

Cấu trúc thư mục, quy ước và tài liệu từng tính năng: xem [AGENTS.md](AGENTS.md) và thư mục [docs/](docs/).
