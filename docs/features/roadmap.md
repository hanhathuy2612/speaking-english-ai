# Lộ trình: giai đoạn, chủ đề và bài luyện

Mục đích: người dùng biết nên tập gì tiếp theo, và **biết bằng số đo** khi nào đã đủ để sang bước sau, thay vì tự chọn trong một danh sách dài. Ý tưởng roadmap lấy từ app Angular, nhưng chỉ dựa trên lịch sử luyện tập, không có tài khoản hay LLM chấm điểm.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Giai đoạn và tiêu chí | `backend/app/data/stages.json` |
| Đánh giá giai đoạn (hàm thuần) | `backend/app/assessment/stages.py` (`validate()`, `check_meets()`, `requirements()`, `evaluate()`, `open_topics()`) |
| Nội dung: chủ đề và bài | `backend/app/data/units.json` (`topics`, `units`; schema trong [interview-flow.md](interview-flow.md)) |
| Nạp và kiểm tra bài | `backend/app/interview/units.py` (`validate()`), `backend/tests/test_units.py` |
| Trạng thái từng bài | `unit_stats()`, `lesson_counts()` trong `backend/app/services/history.py`, gộp bởi `_stats()` trong `backend/app/api/routes/units.py` |
| API, gom số liệu cho giai đoạn | `backend/app/api/routes/units.py` (`GET /api/units`, `GET /api/stages`, `_report()`) |
| Chọn bài mở đầu | `pickUnit()`, `unitState()` trong `frontend/src/lib/roadmap.ts` (+ `roadmap.test.ts`) |
| Chữ của tiêu chí | `requirementText()`, `checkLevelText()` trong `frontend/src/lib/stages.ts` (+ `stages.test.ts`) |
| Trang | `frontend/src/features/roadmap/RoadmapPage.tsx`, `frontend/src/styles/roadmap.css` |
| Ô bài kiểm tra nói | `CheckCard` trong `RoadmapPage.tsx`, dữ liệu từ `GET /api/check` (xem [speaking-check.md](speaking-check.md)) |
| Test | `backend/tests/test_stages.py` |

## Năm giai đoạn

Mức bài kiểm tra tăng dần từ số đo đầu vào của người dùng (11/10/2026: nói 25 giây, 47 từ/phút; lần sau 59 giây, 69 từ/phút, 7,5 lần ngập ngừng / 100 từ) tới mức đích của bài kiểm tra ở giai đoạn 4.

| # | Giai đoạn | Luyện | Tiêu chí qua |
|---|---|---|---|
| 1 | Phát âm | Trang `/sounds` ([pronunciation-drills.md](pronunciation-drills.md)) | Tập đủ 5 nhóm âm |
| 2 | Nói về bản thân và cuộc sống | Chủ đề `daily` | Hoàn thành mọi bài; bài kiểm tra nói liền 1:00, từ 80 từ/phút |
| 3 | Tiếng Anh ở công ty | Chủ đề `workplace` | Hoàn thành mọi bài; bài kiểm tra 1:30, từ 95 từ/phút, dưới 5 lần ngập ngừng / 100 từ |
| 4 | Nói dài và mạch lạc | Trang `/fluency` ([fluency-432.md](fluency-432.md)) | Làm trọn 2 bài 4–3–2; bài kiểm tra đạt mức đích: 2:00, từ 110 từ/phút, dưới 3 lần ngập ngừng |
| 5 | Phỏng vấn | Chủ đề `intro`, `technical`, `behavioral`, `closing` | Hoàn thành mọi bài |

Giai đoạn 1 từng yêu cầu thêm "đọc đúng 90% từ trọng tâm trong 20 câu gần nhất" (`drill_accuracy`). Tiêu chí này đã bỏ (14/10/2026): Whisper hay đoán sai từ trọng tâm theo ngữ cảnh (ví dụ "tests" thiếu /s/ cuối bị viết thành "text" vì ngay trước đó có "text"), nên con số này chặn người học lâu hơn mức phát âm thật. Độ chính xác vẫn hiện trên trang `/sounds` để theo dõi. Khóa `drill_accuracy` vẫn dùng được trong `gate`.

## Mở khóa (`evaluate()`)

- Giai đoạn 1 luôn mở. Giai đoạn sau chỉ mở khi giai đoạn trước **đã qua** (mọi tiêu chí đạt). Trạng thái: `passed` (đã qua), `current` (đang học: mở nhưng chưa đạt), `locked` (chưa mở).
- Tiêu chí được tính trên toàn bộ lịch sử, nên một bài kiểm tra tốt làm sớm vẫn được tính khi tới giai đoạn đó. Nhưng nó **không** mở giai đoạn đang bị khóa: phải qua lần lượt (có test).
- Bài kiểm tra đạt một mức (`check_meets()`) khi: nói tiếng Anh, thời lượng đủ, tốc độ đủ (nếu mức có yêu cầu), ngập ngừng dưới ngưỡng (nếu có). Bài không đo được tốc độ (dưới 30 giây) không đạt mức nào có yêu cầu tốc độ.
- **Khóa mềm:** trên trang Lộ trình, bài của giai đoạn chưa mở nằm trong mục thu gọn "Xem trước nội dung", nút ghi "Tập trước". Ở Phòng tập, ô chọn bài vẫn chọn được mọi bài (chủ đề chưa mở có chữ "(chưa mở)"), cho trường hợp cần luyện gấp, ví dụ sắp phỏng vấn. Phòng tập tự mở bài tiếp theo **trong các giai đoạn đã mở**.

Mỗi chủ đề phải thuộc đúng một giai đoạn. `validate()` kiểm tra điều này khi khởi động (trong `api/routes/units.py`) và trong test.

## API

```json
GET /api/units
{"topics": [{"id": "daily", "title": "...", "description": "...", "locked": false,
  "units": [{"id": "...", "title": "...", "goal": "...", "questions": 6,
             "sessions": 2, "completed": 1, "last_at": "2026-10-11T10:05:10",
             "lesson": false, "lesson_done": 0, "done": true}]}],
 "next_unit": "hobbies"}

GET /api/stages
{"stages": [{"id": "sounds", "title": "...", "goal": "...", "practice": "drills", "topics": [],
             "gate": {...}, "status": "current",
             "requirements": [{"kind": "drill_sets", "done": 1, "total": 5, "met": false},
                              {"kind": "drill_accuracy", "target": 90, "window": 20,
                               "attempts": 2, "accuracy": 50, "met": false}]}],
 "next_unit": null}
```

- `sessions`: số buổi có ít nhất một câu trả lời. `completed`: số buổi hỏi hết câu chính. `lesson`: bài có bài giảng không; `lesson_done`: số lần học xong bài giảng. `done`: bài đã xong; với bài có bài giảng thì cần đủ cả hai phần (xem [lesson.md](lesson.md)). Mọi chỗ "hoàn thành bài" (tiêu chí giai đoạn, `next_unit`, chip trạng thái) đều dùng `done`. Lấy từ lịch sử, nên khi không có DB thì mọi bài đều "chưa tập" và chỉ giai đoạn 1 mở.
- `next_unit`: bài đầu tiên chưa hoàn thành trong các chủ đề đã mở; `null` khi chưa mở chủ đề nào (đang ở giai đoạn 1) hoặc đã xong hết.
- Loại tiêu chí (`kind`): `units`, `drill_sets`, `drill_accuracy`, `fluency_runs` (`done`/`total`), `check` (`target` là mức, `latest` là bài kiểm tra đạt mức đó, nếu chưa có thì bài gần nhất).

## Trang Lộ trình

- Đầu trang: thanh "Đã qua X/5 giai đoạn" và ô bài kiểm tra nói (chưa làm thì mời làm bài đầu vào).
- Mỗi giai đoạn: số thứ tự (dấu ✓ khi đã qua, ổ khóa khi chưa mở), mục tiêu, chip trạng thái, danh sách tiêu chí có dấu ✓/✗ kèm chữ và giá trị hiện tại. Giai đoạn đang học có nút "Làm bài kiểm tra nói" khi tiêu chí kiểm tra chưa đạt.
- Nội dung (thẻ mở trang Phát âm / Nói dài, các chủ đề và thẻ bài) hiện sẵn ở giai đoạn đang học; giai đoạn khác thu gọn trong `<details>`.
- Thẻ bài: **Hoàn thành** (`done`), **Đang tập dở** (đã tập hoặc đã học bài giảng), **Chưa tập**; bài tiếp theo có viền màu chính và nút nổi bật. Nút mở trang bài giảng `/lesson/<id>` nếu bài có bài giảng, không thì `/?unit=<id>` (`unitLink()`).
- Class trạng thái có tiền tố (`stage-current`, `stage-step-passed`…): class `.current` đã có nghĩa khác ở trang đo nhận dạng, mà CSS là toàn cục.

## Phòng tập

- Mở bài trong `?unit=`; không có (hoặc sai id) thì mở `next_unit`, rồi tới bài đầu tiên chưa hoàn thành.
- Đổi bài trong ô chọn cập nhật `?unit=` (thay thế, không thêm lịch sử trình duyệt). Ô chọn nhóm bài theo chủ đề (`optgroup`), bài đã hoàn thành có dấu ✓.

## Thêm bài hoặc giai đoạn

Cách nhanh nhất là **Quản trị → Nội dung bài học** trên web (có AI soạn nháp, kiểm tra ngay khi lưu), xem [content-admin.md](content-admin.md). Bài thêm như vậy nằm trong DB, không vào `units.json`. Để bài đi kèm mã nguồn (cho mọi máy), thêm vào file:

1. Thêm bài vào `units` trong `units.json`, đặt `topic` là id có trong `topics`, đúng vị trí trong lộ trình.
2. Mỗi câu hỏi cần `ask`, `simple`, `phrases`; mỗi mẫu câu cần ít nhất một câu hỏi nhắm tới.
3. Không dùng từ của ví dụ mẫu trong prompt (`EXAMPLE_WORDS`: logistic, deliver, route, coordinator, driver, night shift, warehouse, scanning app). So khớp là so chuỗi con, nên "delivery", "router", "JDBC driver" cũng bị tính.
4. Chủ đề mới phải được đưa vào `topics` của một giai đoạn trong `stages.json`. Khóa của `gate`: `drill_sets`, `drill_accuracy`, `fluency_runs`, `check` (`seconds`, `wpm_speaking`, `hesitations_per_100`).
5. `python -m pytest` (test_units và test_stages bắt các lỗi trên), rồi chạy `scripts/replay.py --unit <id>` với vài câu trả lời mẫu để xem AI phản hồi.
