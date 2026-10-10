# Giọng đọc (TTS) và phát âm thanh

edge-tts, giọng `en-US-JennyNeural`, tốc độ `-10%`, trả về MP3.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Tạo âm thanh | `tts_bytes()` trong `services/tts.py` (điểm thay thế nếu đổi sang TTS khác) |
| Cache câu cố định | `cached_tts()` trong `services/tts.py` |
| TTS trước khi cần | `prewarm()` trong `services/tts.py`, chạy nền từ `start_session()` |
| Hàng đợi trong một lượt | `tts_worker()` trong `run_turn()` (`interview/turn.py`) |
| Gửi kèm chữ | `Conn.audio()` trong `utils/ws.py` |
| Phát ở trình duyệt | `useAudioQueue` (`frontend/src/hooks/useAudioQueue.ts`), ghép chữ với âm thanh trong `useInterview.ts` |

## Chi tiết

- Câu cố định (lời chào, câu hỏi chính, câu `simple`, lời kết) đi qua `cached_tts`. Câu do LLM viết (SAY, câu hỏi phụ) đi qua `tts_bytes`.
- Hàng đợi trong `run_turn` chứa `(câu, có dùng cache không)`, chạy tuần tự để giữ đúng thứ tự, song song với LLM.
- Trình duyệt chỉ thêm chữ của AI vào khung chat **khi câu đó bắt đầu phát**. Nếu người học bấm nói (hoặc gửi chữ) khi audio chưa phát hết, `stop()` của hàng đợi xóa các câu chưa phát, nên các câu chưa phát sẽ không hiện trong chat.
- Nếu đổi sang TTS trả về WAV/PCM, sửa `type` của Blob trong `enqueue` (`frontend/src/hooks/useAudioQueue.ts`, đang là `audio/mpeg`).
