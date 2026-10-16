# Kiến trúc tổng quan

## Một lượt nói

```
Trình duyệt (React: useInterview.ts)    Server (backend/app)
  bấm micro -> MediaRecorder (webm) ──bytes──> api/routes/ws.py: stt.save_recording -> stt.transcribe (GPU)
                                              │ không phải tiếng Anh, nghe không chắc? -> "transcript" unclear, dừng
                                              v
                                            interview/turn.py handle_user_input: lưu snapshot, đếm mẫu câu
                                              v
                                            run_turn: gọi LLM có stream
                                              ├─ SAY: tách từng câu -> TTS -> gửi ngay
                                              ├─ khi thấy NOTE: next_step() chọn câu hỏi tiếp -> TTS (cache)
                                              └─ hết stream: NOTE (qua safe_note), progress, metrics,
                                                 ghi 1 dòng vào lịch sử (services/history.py), turn_done
  phát MP3 theo hàng đợi <──json + bytes──
```

- Cả lượt chạy tuần tự trong vòng lặp `ws_endpoint` (`api/routes/ws.py`), nên không có hai lượt chạy chồng nhau.
- TTS chạy song song với LLM: `tts_worker` lấy câu từ hàng đợi theo đúng thứ tự.
- `Conn.audio()` (`utils/ws.py`) khóa WebSocket để tin JSON `sentence` và khung nhị phân MP3 của nó luôn đi liền nhau.

## Giao thức WebSocket `/ws`

Cần đăng nhập: tin đầu tiên phải là `{"type":"auth","token":<access token JWT>}` (trình duyệt không gắn header được cho WebSocket). Thiếu, sai hay hết hạn thì server đóng với mã 4401. Mọi lịch sử của kết nối lưu dưới `user_id` của người đó (`Session.user_id`). Xem [accounts.md](features/accounts.md).

Trình duyệt gửi:

| Tin | Ý nghĩa |
|---|---|
| `{"type":"auth","token":...}` | Luôn là tin đầu tiên: access token. |
| `{"type":"start","unit":id}` | Bắt đầu bài. Server tạo `Session` mới. |
| khung nhị phân (webm) | Câu trả lời bằng giọng nói. |
| `{"type":"text","text":...}` | Câu trả lời gõ chữ (bỏ qua STT, không có chỉ số nói). |
| `{"type":"undo"}` | "Máy nghe sai": khôi phục `Session.prev`. |
| `{"type":"shadow","text":...}` | Gửi ngay trước khung âm thanh: bản ghi kế tiếp là lượt nói lại câu NOTE này (xem [shadowing.md](features/shadowing.md)). |
| `{"type":"retell"}` | Gửi ngay trước khung âm thanh: bản ghi kế tiếp trả lời lại câu hỏi vừa có NOTE, dài hơn (xem [answer-steps.md](features/answer-steps.md)). |
| `{"type":"say_it","text":...}` | Đọc to NOTE (role `model`, không ghi vào chat). |

Server gửi:

| Tin | Ý nghĩa |
|---|---|
| `started` | Thông tin bài (`goal`, `phrases`, `stt` là nhãn cấu hình STT đang chạy, `lesson` cho biết bài có bài giảng không). |
| `status` | `transcribing` hoặc `thinking`. |
| `transcript` | Chữ nhận dạng, `speech` (chỉ số), `used` (mẫu câu đã dùng), `unclear`, `reason` (`not_english` / `low_confidence` / `null`), `conf`. |
| `sentence` + khung nhị phân | Một câu AI nói kèm MP3. `role`: `ai` hoặc `model`. |
| `note` | NOTE, cờ `retry`, và `steps` (các ý để nói dài hơn, xem [answer-steps.md](features/answer-steps.md)). |
| `progress` | `q`/`n`, `done`. |
| `metrics` | Độ trễ: `stt_ms`, `llm_first_ms`, `first_audio_ms`, `total_ms`. |
| `summary` | Tổng kết khi hết câu hỏi. `session_id` (id buổi trong lịch sử, `null` khi tắt lịch sử) mở trang ôn lỗi của buổi, xem [review.md](features/review.md). |
| `shadow_result` | Kết quả nói lại: `target`, `heard`, `compare` (từng từ), `speech`, `original`. |
| `retell_result` | Kết quả trả lời lại: `heard`, `speech`, `original`, `original_words`, `steps`. |
| `undone` | Đã hoàn tác, kèm `used` mới. |
| `turn_done` | Kết thúc lượt. `can_undo` cho biết có hiện nút "Máy nghe sai" không. |
| `error` | Thông báo lỗi tiếng Việt. |

## HTTP

- **`def` hay `async def`:** route HTTP không có `await` viết là `def` thường, để FastAPI chạy trong threadpool. Truy vấn SQLite và băm mật khẩu scrypt (khoảng 57 ms mỗi lần) chạy trên event loop sẽ làm đứng WebSocket và TTS của người khác. Đo với 8 lần đăng nhập đồng thời: tick event loop trễ nhất 459 ms khi dùng `async def`, 14 ms khi dùng `def`. Chỉ route có `await` (STT, LLM, TTS, `request.body`) mới là `async def`; `ws.py` giữ nguyên. Ngoại lệ: các route admin ghi nội dung bài (`admin_content.py`: lưu, ẩn, khôi phục, sắp thứ tự, sửa chủ đề) cố ý để `async def` dù không có `await`, để chúng chạy lần lượt trên event loop: hai admin lưu cùng lúc không chen nhau giữa bước kiểm tra, lưu và nạp lại danh mục. Route `async def` mà phải băm mật khẩu thì gọi qua `asyncio.to_thread`.

- `GET /`, `/lesson/<id>`, `/review`, `/roadmap`, `/sounds`, `/fluency`, `/check`, `/history`, `/bench`: `frontend/dist/index.html` (app React một trang; React Router chọn trang). `/assets/...`: JS/CSS đã build. Chưa build thì trả hướng dẫn (503).
- `/api/history/...`: xem [session-history.md](features/session-history.md).
- `/api/check`: bài kiểm tra nói, xem [speaking-check.md](features/speaking-check.md).
- `GET /api/units`, `GET /api/stages`: chủ đề và bài theo thứ tự lộ trình kèm trạng thái đã tập; các giai đoạn kèm tiêu chí và trạng thái mở khóa (`api/routes/units.py`, xem [roadmap.md](features/roadmap.md)).
- `/api/lessons/...`: bài giảng của một bài (câu của giáo viên, giọng đọc, chấm câu đọc theo, đánh dấu học xong), xem [lesson.md](features/lesson.md).
- `/api/drills`: luyện phát âm, xem [pronunciation-drills.md](features/pronunciation-drills.md).
- `/api/fluency`: bài nói dài 4–3–2, xem [fluency-432.md](features/fluency-432.md).
- `/api/review`: thẻ ôn tập, xem [review.md](features/review.md).
- `GET /bench`, `GET /api/bench`, `POST /api/bench/{i}`: xem [stt-benchmark.md](features/stt-benchmark.md).
