# Speaking demo: luyện phỏng vấn tiếng Anh, chạy local

Người dùng là lập trình viên Java người Việt, hiểu tiếng Anh tốt nhưng nói chưa trôi chảy.
App tạo một buổi phỏng vấn giả: nghe câu hỏi, nói, xem cách nói tự nhiên hơn (NOTE), nói lại.
Đây là bản demo để thử luồng nói, sau đó sẽ ghép vào dự án chính (dự án chính đã có đăng nhập, DB, roadmap).

**Stack:** FastAPI + WebSocket (`server.py`), frontend một file `index.html` (JS thuần). LLM Qwen2.5-7B qua LM Studio,
STT faster-whisper `large-v3-turbo` trên GPU, TTS edge-tts. Cấu hình nằm trong `.env`.

## Lệnh

```
.venv\Scripts\activate
uvicorn server:app --port 8000      # app của người dùng; agent thử nghiệm ở cổng 8001
python test_parsing.py              # test logic thuần
```

## Bản đồ tài liệu

Đọc file tương ứng **trước khi** sửa một tính năng.

| Tính năng | Tài liệu | Mã nguồn chính |
|---|---|---|
| Tổng quan, một lượt nói, giao thức WebSocket | [docs/architecture.md](docs/architecture.md) | `server.py`: `ws_endpoint`, `run_turn`, `Conn` |
| Luồng phỏng vấn: câu hỏi, hỏi lại, câu hỏi phụ, hoàn tác, tổng kết | [docs/features/interview-flow.md](docs/features/interview-flow.md) | `units.json`; `server.py`: `Session`, `next_step`, `start_session`, `summary` |
| Prompt LLM, định dạng RETRY/SAY/ASK/NOTE, chặn NOTE xấu | [docs/features/llm-prompt.md](docs/features/llm-prompt.md) | `server.py`: `SYSTEM_TEMPLATE`, `FEW_SHOT`, `build_user_message`, `safe_note`; `parsing.py`: `split_sections`, `ready_sentences`; `replay.py` |
| Nhận dạng giọng nói, GPU, chặn khi nghe không chắc | [docs/features/speech-recognition.md](docs/features/speech-recognition.md) | `server.py`: `load_whisper`, `transcribe`, `handle_user_input`; `cuda_dlls.py` |
| Giọng đọc, cache, phát âm thanh | [docs/features/tts-audio.md](docs/features/tts-audio.md) | `server.py`: `tts_bytes`, `cached_tts`, `prewarm`; `index.html`: `enqueue`, `playNext` |
| Chỉ số nói, mẫu câu đã dùng | [docs/features/speech-metrics.md](docs/features/speech-metrics.md) | `parsing.py`: `speech_metrics`, `used_phrase_indices` |
| Đo độ chính xác STT, trang đọc theo câu mẫu | [docs/features/stt-benchmark.md](docs/features/stt-benchmark.md) | `stt_bench.py`, `bench.html`, `bench_sentences.json`; `parsing.py`: `word_errors` |
| Giao diện | [docs/features/frontend.md](docs/features/frontend.md) | `index.html` |
| Biến cấu hình | [docs/configuration.md](docs/configuration.md) | `.env`, đầu `server.py` |
| Môi trường Windows, kiểm thử, lỗi thường gặp | [docs/dev-environment.md](docs/dev-environment.md) | |

## Quy tắc chung

- **App điều khiển luồng phỏng vấn, không phải LLM.** LLM chỉ phản ứng, hỏi tối đa một câu phụ và viết NOTE. Lý do nằm trong interview-flow.md.
- **AI luôn là người phỏng vấn.** Lời AI nói ở ngôi thứ hai. Câu mẫu ngôi thứ nhất chỉ nằm trong NOTE (hiện chữ, không đọc).
- Comment, giao diện, thông báo lỗi bằng tiếng Việt. Prompt và lời AI bằng tiếng Anh, không bao giờ có tiếng Việt.
- Không chấm điểm bằng LLM. Chỉ dùng chỉ số khách quan.
- Giữ code đơn giản, không thêm framework hay bước build.
- Đổi prompt thì kiểm chứng bằng `replay.py`. Đổi STT thì đo bằng `stt_bench.py`. Không đoán.
- **Cổng 8000 là server của người dùng.** Thử nghiệm ở cổng 8001, không tắt `python.exe` theo tên, không xóa `recordings/`.
- **Sửa tính năng nào thì cập nhật file docs tương ứng trong cùng lần sửa.** Thêm tính năng mới thì thêm file trong `docs/features/` và một dòng vào bảng trên.
