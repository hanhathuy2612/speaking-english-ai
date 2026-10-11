# Lộ trình và bài luyện

Mục đích: người dùng biết nên tập bài nào tiếp theo, thay vì tự chọn trong một danh sách dài. Ý tưởng lấy từ roadmap của app Angular, nhưng chỉ dựa trên lịch sử luyện tập, không có tài khoản hay LLM chấm điểm.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Nội dung: chủ đề và bài | `backend/app/data/units.json` (`topics`, `units`; schema trong [interview-flow.md](interview-flow.md)) |
| Nạp và kiểm tra dữ liệu | `backend/app/interview/units.py` (`validate()`), `backend/tests/test_units.py` |
| Trạng thái từng bài | `unit_stats()` trong `backend/app/services/history.py` |
| API | `GET /api/units` trong `backend/app/api/routes/units.py` |
| Chọn bài mở đầu | `pickUnit()`, `unitState()` trong `frontend/src/lib/roadmap.ts` (+ `roadmap.test.ts`) |
| Trang | `frontend/src/features/roadmap/RoadmapPage.tsx`, `frontend/src/styles/roadmap.css` |

## Nội dung hiện có (12 bài, 4 chủ đề)

| Chủ đề | Bài |
|---|---|
| Giới thiệu bản thân | `tell-me-about-yourself`, `current-project`, `career-goals` |
| Kinh nghiệm kỹ thuật | `java-spring`, `microservices`, `database-performance`, `testing-quality` |
| Tình huống thực tế (STAR) | `solved-a-problem`, `disagreement`, `tight-deadline`, `a-mistake` |
| Cuối buổi phỏng vấn | `expectations` (lương, ngày bắt đầu, câu hỏi cho nhà tuyển dụng) |

Thứ tự trong file là thứ tự lộ trình. Bài `expectations` có câu "Do you have any questions for us?": `scenario` dặn AI trả lời ngắn, chung chung khi người học hỏi về công ty.

## `GET /api/units`

```json
{"topics": [{"id": "intro", "title": "...", "description": "...",
  "units": [{"id": "...", "title": "...", "goal": "...", "questions": 6,
             "sessions": 2, "completed": 1, "last_at": "2026-10-11T10:05:10"}]}]}
```

- `sessions`: số buổi có ít nhất một câu trả lời. `completed`: số buổi hỏi hết câu chính. Lấy từ lịch sử, nên khi `HISTORY_DB` để trống thì mọi bài đều "chưa tập".
- Trạng thái trên giao diện: **Hoàn thành** (`completed > 0`), **Đang tập dở** (có buổi nhưng chưa xong), **Chưa tập**.

## Hành vi

- **Bài tiếp theo** = bài đầu tiên (theo thứ tự lộ trình) chưa hoàn thành. Thẻ của nó có viền màu chính và nút "Bắt đầu"/"Luyện lại" nổi bật. Hoàn thành hết thì không đánh dấu bài nào.
- Nút trên thẻ mở `/?unit=<id>`. Phòng tập mở bài trong `?unit=`; không có (hoặc sai id) thì mở bài tiếp theo.
- Đổi bài trong ô chọn của phòng tập cập nhật `?unit=` (thay thế, không thêm lịch sử trình duyệt), nên tải lại trang vẫn ở bài đó. Ô chọn nhóm bài theo chủ đề (`optgroup`), bài đã hoàn thành có dấu ✓.

## Thêm bài mới

1. Thêm vào `units` trong `units.json`, đặt `topic` là id có trong `topics`, đúng vị trí trong lộ trình.
2. Mỗi câu hỏi cần `ask`, `simple`, `phrases`; mỗi mẫu câu cần ít nhất một câu hỏi nhắm tới.
3. Không dùng từ của ví dụ mẫu trong prompt (`EXAMPLE_WORDS`: logistic, deliver, route, coordinator, driver). So khớp là so chuỗi con, nên "delivery", "router", "JDBC driver" cũng bị tính.
4. `python -m pytest` (test_units bắt các lỗi trên), rồi chạy `scripts/replay.py --unit <id>` với vài câu trả lời mẫu để xem AI phản hồi.
