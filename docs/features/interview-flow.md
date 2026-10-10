# Luồng phỏng vấn

**Nguyên tắc: app điều khiển luồng, LLM không.** Model 7B từng lặp lại "tell me about yourself" sau 7 lượt và không bao giờ chạm tới các câu hỏi cuối, vì lịch sử bị cắt và nó tự nhớ tiến độ. Giờ app giữ trạng thái và chọn câu hỏi.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Dữ liệu bài | `units.json` |
| Trạng thái phiên | `Session`, `STATE_FIELDS` trong `server.py` |
| Chọn câu tiếp theo | `next_step()` |
| Bắt đầu bài, lời chào | `start_session()` |
| Hoàn tác | nhánh `undo` trong `ws_endpoint`, `Session.snapshot()` / `restore()` |
| Tiến độ, tổng kết | `progress()`, `summary()` |

## `units.json`

```json
{
  "id": "...", "title": "...", "scenario": "...", "goal": "(tiếng Việt, hiện cho người học)",
  "greeting": "...", "closing": "...", "vocab": "(gợi ý từ cho Whisper)",
  "questions": [{ "ask": "...", "phrases": [0], "simple": "(bản dễ hơn để hỏi lại)" }],
  "phrases": [{ "say": "I'm responsible for ...", "match": ["i'm responsible for", "i am responsible for"] }]
}
```

- `questions[i].phrases` là chỉ số vào `phrases`, dùng làm "Target phrase" cho LLM và làm khung NOTE dự phòng.
- `match` so sau khi `norm()` (chữ thường, bỏ dấu câu, chuẩn hóa dấu nháy).
- Lời mở đầu là `greeting + questions[0].ask`.

## `next_step()`: quyết định sau mỗi lượt

1. **RETRY = yes và `retries < MAX_RETRIES` (2):** hỏi lại. Nếu đang ở câu chính thì dùng `simple` (có cache TTS). Nếu đang ở câu hỏi phụ thì nhắc lại đúng câu đó.
2. **RETRY = no, ASK là câu hỏi, và `followups < INTERVIEW_FOLLOWUPS`:** hỏi câu phụ do LLM viết.
3. **Còn lại:** sang câu chính tiếp theo. Hết câu thì nói `closing`, đặt `done = True`, gửi `summary`.

`next_step()` được gọi ngay khi stream xuất hiện nhãn NOTE (ASK đã viết xong), nên câu hỏi tiếp theo được TTS trong lúc LLM còn viết NOTE.

## Hoàn tác ("Máy nghe sai, nói lại")

- `handle_user_input()` lưu `s.prev = s.snapshot()` trước khi thay đổi trạng thái.
- `undo` khôi phục snapshot (kể cả `done`, `used`, `history`). Chỉ hoàn tác được 1 lượt.
- Frontend xóa dòng của người học và dòng AI của lượt đó (`st.lastMe`, `st.lines[turn]`).
- Lượt bị coi là "nghe chưa rõ" không thay đổi trạng thái, nên không có gì để hoàn tác.

## Khi sửa

- Thêm trường mới vào `Session` thì phải thêm vào `STATE_FIELDS`, nếu không hoàn tác sẽ không khôi phục trường đó.
- Thêm câu hỏi thì phải có đủ `ask`, `phrases`, `simple`.
- Kiểm chứng bằng `replay.py` (xem [llm-prompt.md](llm-prompt.md)).
