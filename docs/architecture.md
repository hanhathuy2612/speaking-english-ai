# Kiến trúc tổng quan

## Một lượt nói

```
Trình duyệt (index.html)                Server (server.py)
  giữ nút -> MediaRecorder (webm) ──bytes──> save_recording -> transcribe (Whisper, GPU)
                                              │ nghe không chắc? -> "transcript" unclear, dừng
                                              v
                                            handle_user_input: lưu snapshot, đếm mẫu câu
                                              v
                                            run_turn: gọi LLM có stream
                                              ├─ SAY: tách từng câu -> TTS -> gửi ngay
                                              ├─ khi thấy NOTE: next_step() chọn câu hỏi tiếp -> TTS (cache)
                                              └─ hết stream: NOTE (qua safe_note), progress, metrics, turn_done
  phát MP3 theo hàng đợi <──json + bytes──
```

- Cả lượt chạy tuần tự trong vòng lặp `ws_endpoint`, nên không có hai lượt chạy chồng nhau.
- TTS chạy song song với LLM: `tts_worker` lấy câu từ hàng đợi theo đúng thứ tự.
- `Conn.audio()` khóa WebSocket để tin JSON `sentence` và khung nhị phân MP3 của nó luôn đi liền nhau.

## Giao thức WebSocket `/ws`

Trình duyệt gửi:

| Tin | Ý nghĩa |
|---|---|
| `{"type":"start","unit":id}` | Bắt đầu bài. Server tạo `Session` mới. |
| khung nhị phân (webm) | Câu trả lời bằng giọng nói. |
| `{"type":"text","text":...}` | Câu trả lời gõ chữ (bỏ qua STT, không có chỉ số nói). |
| `{"type":"undo"}` | "Máy nghe sai": khôi phục `Session.prev`. |
| `{"type":"say_it","text":...}` | Đọc to NOTE (role `model`, không ghi vào chat). |

Server gửi:

| Tin | Ý nghĩa |
|---|---|
| `started` | Thông tin bài (`goal`, `phrases`, `stt` là nhãn cấu hình STT đang chạy). |
| `status` | `transcribing` hoặc `thinking`. |
| `transcript` | Chữ nhận dạng, `speech` (chỉ số), `used` (mẫu câu đã dùng), `unclear`, `conf`. |
| `sentence` + khung nhị phân | Một câu AI nói kèm MP3. `role`: `ai` hoặc `model`. |
| `note` | NOTE và cờ `retry`. |
| `progress` | `q`/`n`, `done`. |
| `metrics` | Độ trễ: `stt_ms`, `llm_first_ms`, `first_audio_ms`, `total_ms`. |
| `summary` | Tổng kết khi hết câu hỏi. |
| `undone` | Đã hoàn tác, kèm `used` mới. |
| `turn_done` | Kết thúc lượt. `can_undo` cho biết có hiện nút "Máy nghe sai" không. |
| `error` | Thông báo lỗi tiếng Việt. |

## HTTP

- `GET /`: `index.html`. `GET /api/units`: danh sách bài.
- `GET /bench`, `GET /api/bench`, `POST /api/bench/{i}`: xem [stt-benchmark.md](features/stt-benchmark.md).
