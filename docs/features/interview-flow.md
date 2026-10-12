# Luồng phỏng vấn

**Nguyên tắc: app điều khiển luồng, LLM không.** Model 7B từng lặp lại "tell me about yourself" sau 7 lượt và không bao giờ chạm tới các câu hỏi cuối, vì lịch sử bị cắt và nó tự nhớ tiến độ. Giờ app giữ trạng thái và chọn câu hỏi.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Dữ liệu bài | `backend/app/data/units.json`, nạp bởi `interview/units.py` |
| Trạng thái phiên | `Session`, `STATE_FIELDS` trong `interview/session.py` |
| Chọn câu tiếp theo | `next_step()` trong `interview/session.py` |
| Bắt đầu bài, lời chào | `start_session()` trong `interview/turn.py` |
| Hoàn tác | nhánh `undo` trong `_on_text()` (`api/routes/ws.py`), `Session.snapshot()` / `restore()` |
| Tiến độ, tổng kết | `progress()`, `summary()` trong `interview/session.py` |

## `data/units.json`

File gồm `topics` (chủ đề, theo thứ tự lộ trình) và `units` (bài, theo thứ tự nên tập). `interview/units.py` kiểm tra dữ liệu khi nạp (`validate()`), `tests/test_units.py` kiểm tra thêm: mỗi mẫu câu có câu hỏi nhắm tới, đọc nguyên mẫu câu thì được tính là đã dùng, không dùng từ của ví dụ mẫu (`EXAMPLE_WORDS`: logistic, deliver, route, coordinator, driver, night shift, warehouse, scanning app).

```json
{
  "id": "...", "topic": "(id trong topics)", "title": "...", "scenario": "...", "goal": "(tiếng Việt, hiện cho người học)",
  "greeting": "...", "closing": "...", "vocab": "(gợi ý từ cho Whisper)",
  "followups": 0,                     (không bắt buộc, mặc định INTERVIEW_FOLLOWUPS)
  "questions": [{ "ask": "...", "phrases": [0], "simple": "(bản dễ hơn để hỏi lại)", "steps": [{ "hint": "Vì sao?", "say": "That's because ..." }] }],
  "phrases": [{ "say": "I'm responsible for ...", "match": ["i'm responsible for", "i am responsible for"] }]
}
```

- `questions[i].phrases` là chỉ số vào `phrases`, dùng làm "Target phrase" cho LLM và làm khung NOTE dự phòng.
- `match` so sau khi `norm()` (chữ thường, bỏ dấu câu, chuẩn hóa dấu nháy).
- `questions[i].steps`: 2–3 ý để nói dài hơn, hiện dưới NOTE (nhãn tiếng Việt + câu mở đầu có `...`), xem [answer-steps.md](answer-steps.md).
- `phrases[i].when` (không bắt buộc): mẫu câu chỉ dùng làm Target phrase khi câu trả lời có một trong các cụm này (mẫu phản đối, xem [llm-prompt.md](llm-prompt.md)). Thêm mẫu câu mới thì thêm vào **cuối** `phrases`, vì thẻ ôn tập lưu theo chỉ số.
- Lời mở đầu là `greeting + questions[0].ask`.

## `next_step()`: quyết định sau mỗi lượt

1. **RETRY = yes và `retries < MAX_RETRIES` (2):** hỏi lại. Nếu đang ở câu chính thì dùng `simple` (có cache TTS). Nếu đang ở câu hỏi phụ thì nhắc lại đúng câu đó.
2. **RETRY = no, ASK là câu hỏi, và `followups < followup_limit(unit)`:** hỏi câu phụ do LLM viết. Giới hạn là `followups` của bài nếu có, không thì `INTERVIEW_FOLLOWUPS`. Các bài STAR đặt 0, xem [llm-prompt.md](llm-prompt.md).
3. **Còn lại:** sang câu chính tiếp theo. Hết câu thì nói `closing`, đặt `done = True`, gửi `summary` (kèm `session_id` để thẻ tổng kết có nút "Ôn lỗi của buổi này", xem [review.md](review.md)).

`next_step()` được gọi ngay khi stream xuất hiện nhãn NOTE (ASK đã viết xong), nên câu hỏi tiếp theo được TTS trong lúc LLM còn viết NOTE.

## Hoàn tác ("Máy nghe sai, nói lại")

- `handle_user_input()` lưu `s.prev = s.snapshot()` trước khi thay đổi trạng thái.
- `undo` khôi phục snapshot (kể cả `done`, `used`, `history`). Chỉ hoàn tác được 1 lượt.
- Frontend xóa tin nhắn của người học và của AI có cùng lượt (`lastMeTurn` trong `useInterview.ts`).
- Lượt bị coi là "nghe chưa rõ" không thay đổi trạng thái, nên không có gì để hoàn tác.

## Khi sửa

- Thêm trường mới vào `Session` thì phải thêm vào `STATE_FIELDS`, nếu không hoàn tác sẽ không khôi phục trường đó.
- Thêm câu hỏi thì phải có đủ `ask`, `phrases`, `simple`.
- Kiểm chứng bằng `scripts/replay.py` (xem [llm-prompt.md](llm-prompt.md)).
