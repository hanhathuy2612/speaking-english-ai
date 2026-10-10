# Cấu hình (`.env`)

`.env` không được commit (đã có trong `.gitignore`). Máy mới thì chép `.env.example` thành `.env` rồi sửa `STT_VOCAB`.
Thêm hoặc đổi biến nào thì cập nhật cả `.env.example`.

Server tự nạp `.env` bằng python-dotenv khi khởi động. Biến môi trường đặt sẵn sẽ được ưu tiên hơn. Mọi biến có giá trị mặc định trong `backend/app/core/config.py`. Đổi `.env` thì phải khởi động lại server.

| Biến | Mặc định trong code | `.env` hiện tại | Ghi chú |
|---|---|---|---|
| `LM_URL` | `http://localhost:1234/v1` | giống mặc định | LM Studio |
| `LM_MODEL` | `qwen2.5-7b-instruct` | giống mặc định | |
| `LM_TEMPERATURE` | `0.35` | `0.35` | |
| `LM_SEED` | trống | tắt | Bật khi so prompt |
| `MAX_REPLY_TOKENS` | `160` | `160` | |
| `MAX_HISTORY` | `3` | `3` | Số cặp hỏi/đáp trước đó gửi cho LLM |
| `INTERVIEW_FOLLOWUPS` | `1` | `1` | `0` để chỉ hỏi câu chính |
| `STT_MODEL` | `small.en` | `large-v3-turbo` | |
| `STT_DEVICE` / `STT_COMPUTE` | `cpu` / `int8` | `cuda` / `float16` | |
| `STT_THREADS` | `8` | `8` | Chỉ dùng khi chạy CPU |
| `STT_BEAM` | `1` | `3` | |
| `STT_VOCAB` | trống | `Hi, I'm Huy.` | Thông tin riêng giúp Whisper nghe đúng tên |
| `STT_MIN_LOGPROB` | `-1.0` | `-1.0` | Ngưỡng "nghe chưa rõ", chưa hiệu chỉnh |
| `STT_MAX_NO_SPEECH` | `0.6` | `0.6` | |
| `SAVE_AUDIO_DIR` | trống | `recordings` | Giữ file ghi âm mỗi lượt (tương đối với thư mục gốc) |
| `TTS_VOICE` / `TTS_RATE` | `en-US-JennyNeural` / `-10%` | giống mặc định | |

`MAX_RETRIES = 2` được viết cứng trong code, không đọc từ `.env`.

Nhãn cấu hình STT đang chạy thật hiện ở cột trái giao diện, để kiểm tra `.env` đã có tác dụng chưa.
