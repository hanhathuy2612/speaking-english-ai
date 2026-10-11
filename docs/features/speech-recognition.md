# Nhận dạng giọng nói (STT)

faster-whisper `large-v3-turbo`, CUDA float16, beam 3, trên RTX 3060 12 GB.
Khoảng 0,36 giây mỗi câu, 7,0% từ sai trên bộ 18 câu của người dùng (xem [stt-benchmark.md](stt-benchmark.md)).

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Nạp model, chuyển về CPU khi GPU lỗi | `load()` trong `services/stt.py`, gọi từ `lifespan` trong `main.py` |
| Nhận dạng | `transcribe(path, prompt)` trong `services/stt.py` |
| DLL CUDA trên Windows | `core/cuda.py` (gọi `add_cuda_dlls()` trước khi import faster_whisper) |
| Chặn khi không phải tiếng Anh / nghe không chắc | `unclear_reason()` trong `services/stt.py`, `has_vietnamese()` trong `utils/parsing.py`, dùng ở đầu `handle_user_input()` (`interview/turn.py`) |
| Lưu file ghi âm | `save_recording()`, `finish_recording()` trong `services/stt.py`, gọi từ `_on_audio()` (`api/routes/ws.py`) |

## Chi tiết

- `transcribe()` trả về `text`, `words` (từ, mốc bắt đầu/kết thúc, xác suất), `avg_logprob` và `no_speech` (trung bình có trọng số theo độ dài từng đoạn), `language`.
- `initial_prompt` là `STT_VOCAB` (thông tin riêng của người dùng, ví dụ tên "Huy") ghép với `vocab` của bài. Nó giúp nghe đúng tên riêng và từ nghề.
- `vad_filter=True`, `condition_on_previous_text=False`, `language="en"` (trừ khi bật `STT_CHECK_LANGUAGE`, xem dưới).
- Lượt **nói lại** (shadowing) nhận dạng **không có** `initial_prompt`, để gợi ý không che mất lỗi phát âm (xem [shadowing.md](shadowing.md)).
- **Chặn trước khi gọi LLM** (`unclear_reason()`), tin `transcript` mang `reason`:
  - `not_english`: chữ nhận dạng có ký tự riêng của tiếng Việt (ă, đ, ơ, ư, ạ…), hoặc Whisper nhận ra ngôn ngữ khác tiếng Anh (khi bật `STT_CHECK_LANGUAGE`). Giao diện hiện "Hãy trả lời bằng tiếng Anh nhé."
  - `low_confidence`: `avg_logprob < STT_MIN_LOGPROB` (-1.0) hoặc `no_speech > STT_MAX_NO_SPEECH` (0.6). Giao diện hiện "Máy nghe chưa rõ, bạn nói lại nhé."
  - Server in `STT logprob=... no_speech=... lang=...` mỗi lượt.
- `load()` chạy thử 1 giây im lặng ngay khi nạp, để lỗi thiếu DLL CUDA lộ ra lúc khởi động chứ không phải ở lượt nói đầu tiên. Khi GPU lỗi, server dùng CPU int8 và nhãn STT trên giao diện ghi "(GPU lỗi)".
- `SAVE_AUDIO_DIR` (đang là `recordings`): giữ file `.webm` và `.hyp.txt` (chữ máy nghe được) của mỗi lượt.

## Hiệu chỉnh ngưỡng (đo ngày 11/10/2026)

Lịch sử thật chưa có lượt nào, nên đo trên 18 câu của bộ benchmark (giọng người dùng) cộng các bản làm hỏng: thêm nhiễu trắng (SNR 0 dB và -5 dB), cắt còn 40% đầu câu, tiếng Việt (giọng edge-tts), chỉ có nhiễu, tiếng ù 120 Hz.

| Trường hợp | `avg_logprob` | Lỗi từ |
|---|---|---|
| Câu rõ (18 câu) | -0,14 đến -0,78 | 0–27% |
| Nhiễu SNR -5 dB | -0,18 đến -0,98 | 0–100% |
| Cắt còn 40% | -0,20 đến -0,99 | 55–75% |
| Chỉ nhiễu, tiếng ù, im lặng | -9 (VAD bỏ hết, chữ rỗng) | |
| Tiếng Việt, ép `language="en"` | -0,16 và -0,78 | một câu ra chữ tiếng Việt, một câu bị **dịch** sang tiếng Anh |

Kết luận:
- **`avg_logprob` không tách được câu nghe sai khỏi câu rõ.** Câu rõ thấp nhất là -0,78, câu sai 100% vẫn có -0,47. Nâng ngưỡng lên sẽ chặn nhầm câu đúng, nên giữ -1.0 làm lưới an toàn cuối.
- `no_speech` luôn bằng 0 khi có tiếng nói, vì VAD đã cắt phần im lặng. Âm thanh không có tiếng nói ra chữ rỗng và bị chặn trước đó ("Không nghe rõ…").
- Câu bị nghe sai nhưng vẫn là tiếng Anh hợp lệ thì để LLM xử lý (RETRY) và người dùng bấm "Máy nghe sai, nói lại".
- **Phát hiện ngôn ngữ tách hoàn toàn:** giọng tiếng Anh của người dùng cho en ≥ 0,92, tiếng Việt cho vi = 1,00. Độ chính xác không đổi (5,2% lỗi từ cả hai cách), nhưng chậm thêm khoảng 0,24 giây/lượt (335 → 575 ms). Vì vậy `STT_CHECK_LANGUAGE` mặc định tắt; khi tắt vẫn bắt được câu tiếng Việt mà Whisper viết ra chữ có dấu.
- Khi bật mà Whisper nhận ra ngôn ngữ khác nhưng không chắc (< 0,5), app nhận dạng lại với `language="en"`.

## Cài GPU (đã làm)

```
pip install -r backend/requirements-gpu.txt
```

Chỉ cài vào `.venv`, không động tới Windows hay driver.

## Lưu ý khi đánh giá

Với turbo, phần lớn chỗ lệch so với câu mẫu là cách người dùng phát âm thật (mất âm cuối -s, -ed, "cache" nghe thành "kit", "thirty" thành "sixty"), không phải lỗi máy. Đừng cố "sửa" STT cho những trường hợp đó, vì chúng là tín hiệu hữu ích cho người học.
