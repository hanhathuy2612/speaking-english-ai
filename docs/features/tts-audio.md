# Giọng đọc (TTS) và phát âm thanh

edge-tts, giọng `en-US-JennyNeural`, tốc độ `-10%`, trả về MP3.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Tạo âm thanh | `tts_bytes()` trong `server.py` (điểm thay thế nếu đổi sang TTS khác) |
| Cache câu cố định | `cached_tts()`, `tts_cache` |
| TTS trước khi cần | `prewarm()`, chạy nền khi bắt đầu bài |
| Hàng đợi trong một lượt | `tts_worker()` trong `run_turn()` |
| Gửi kèm chữ | `Conn.audio()` |
| Phát ở trình duyệt | `enqueue()`, `playNext()`, `appendAi()`, `stopPlayback()` trong `index.html` |

## Chi tiết

- Câu cố định (lời chào, câu hỏi chính, câu `simple`, lời kết) đi qua `cached_tts`. Câu do LLM viết (SAY, câu hỏi phụ) đi qua `tts_bytes`.
- Hàng đợi trong `run_turn` chứa `(câu, có dùng cache không)`, chạy tuần tự để giữ đúng thứ tự, song song với LLM.
- Trình duyệt chỉ thêm chữ của AI vào khung chat **khi câu đó bắt đầu phát**. Nếu người học bấm nói (hoặc gửi chữ) khi audio chưa phát hết, `stopPlayback()` xóa hàng đợi, nên các câu chưa phát sẽ không hiện trong chat.
- Nếu đổi sang TTS trả về WAV/PCM, sửa `type` của Blob trong `enqueue()` (đang là `audio/mpeg`).
