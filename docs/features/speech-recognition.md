# Nhận dạng giọng nói (STT)

faster-whisper `large-v3-turbo`, CUDA float16, beam 3, trên RTX 3060 12 GB.
Khoảng 0,36 giây mỗi câu, 7,0% từ sai trên bộ 18 câu của người dùng (xem [stt-benchmark.md](stt-benchmark.md)).

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Nạp model, chuyển về CPU khi GPU lỗi | `load()` trong `services/stt.py`, gọi từ `lifespan` trong `main.py` |
| Nhận dạng | `transcribe(path, prompt)` trong `services/stt.py` |
| DLL CUDA trên Windows | `core/cuda.py` (gọi `add_cuda_dlls()` trước khi import faster_whisper) |
| Chặn khi nghe không chắc | `is_unclear()` trong `services/stt.py`, dùng ở đầu `handle_user_input()` (`interview/turn.py`) |
| Lưu file ghi âm | `save_recording()`, `finish_recording()` trong `services/stt.py`, gọi từ `_on_audio()` (`api/routes/ws.py`) |

## Chi tiết

- `transcribe()` trả về `text`, `words` (từ, mốc bắt đầu/kết thúc, xác suất), `avg_logprob` và `no_speech` (trung bình có trọng số theo độ dài từng đoạn).
- `initial_prompt` là `STT_VOCAB` (thông tin riêng của người dùng, ví dụ tên "Huy") ghép với `vocab` của bài. Nó giúp nghe đúng tên riêng và từ nghề.
- `vad_filter=True`, `condition_on_previous_text=False`, `language="en"`.
- Lượt **nói lại** (shadowing) nhận dạng **không có** `initial_prompt`, để gợi ý không che mất lỗi phát âm (xem [shadowing.md](shadowing.md)).
- **Nghe không chắc:** khi `avg_logprob < STT_MIN_LOGPROB` (-1.0) hoặc `no_speech > STT_MAX_NO_SPEECH` (0.6), app không gọi LLM, hiện "Máy nghe chưa rõ, bạn nói lại nhé". Ngưỡng này chưa được hiệu chỉnh: server in `STT logprob=... no_speech=...` mỗi lượt để lấy số liệu.
- `load()` chạy thử 1 giây im lặng ngay khi nạp, để lỗi thiếu DLL CUDA lộ ra lúc khởi động chứ không phải ở lượt nói đầu tiên. Khi GPU lỗi, server dùng CPU int8 và nhãn STT trên giao diện ghi "(GPU lỗi)".
- `SAVE_AUDIO_DIR` (đang là `recordings`): giữ file `.webm` và `.hyp.txt` (chữ máy nghe được) của mỗi lượt.

## Cài GPU (đã làm)

```
pip install -r backend/requirements-gpu.txt
```

Chỉ cài vào `.venv`, không động tới Windows hay driver.

## Lưu ý khi đánh giá

Với turbo, phần lớn chỗ lệch so với câu mẫu là cách người dùng phát âm thật (mất âm cuối -s, -ed, "cache" nghe thành "kit", "thirty" thành "sixty"), không phải lỗi máy. Đừng cố "sửa" STT cho những trường hợp đó, vì chúng là tín hiệu hữu ích cho người học.
