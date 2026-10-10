# Phòng tập phỏng vấn tiếng Anh (chạy local)

Buổi phỏng vấn giả để luyện nói: nghe câu hỏi, trả lời bằng giọng nói, xem cách nói tự nhiên hơn, nói lại.
Chạy hoàn toàn trên máy: LM Studio (Qwen2.5-7B), faster-whisper (GPU), edge-tts.

## Cài đặt

Cần: Python 3.11, LM Studio đã nạp `qwen2.5-7b-instruct` và bật Local Server (cổng 1234).

```
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
pip install -r backend/requirements-gpu.txt     # nếu có GPU NVIDIA (khoảng 1 GB)
copy .env.example .env                          # rồi sửa STT_VOCAB và cấu hình STT
```

Với GPU, đặt trong `.env`: `STT_MODEL=large-v3-turbo`, `STT_DEVICE=cuda`, `STT_COMPUTE=float16`, `STT_BEAM=3`.
Nếu GPU lỗi, server tự chuyển về CPU và ghi "(GPU lỗi)" ở cột trái giao diện.

## Chạy

```
cd backend
uvicorn app.main:app --port 8000
```

- http://localhost:8000: phòng tập. Giữ nút để nói, thả ra để gửi. Có ô gõ chữ để thử không cần micro.
- http://localhost:8000/bench: đọc 18 câu mẫu để đo độ chính xác nhận dạng giọng nói.

## Phát triển

```
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

Cấu trúc thư mục, quy ước và tài liệu từng tính năng: xem [AGENTS.md](AGENTS.md) và thư mục [docs/](docs/).
