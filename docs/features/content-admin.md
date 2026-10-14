# Quản trị nội dung bài học

Quản trị viên (vai trò `admin`, xem [accounts.md](accounts.md)) sửa và thêm bài học ngay trên web, ở **Quản trị → Nội dung bài học** (`/admin/content`), không cần sửa `units.json` hay khởi động lại server. Có thể nhờ AI (Qwen qua LM Studio) soạn nháp một bài mới rồi sửa lại.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Lưu nội dung trong DB, đồng bộ từ `units.json` | `backend/app/services/content.py` (bảng `content_topics`, `content_units`) |
| Nội dung đang dùng, kiểm tra hợp lệ, nạp lại | `backend/app/interview/units.py` (`validate`, `load_content`, `use_content`) |
| API cho admin | `backend/app/api/routes/admin_content.py` |
| AI soạn nháp | `backend/app/interview/drafts.py`, `complete_json()` trong `services/llm.py` |
| Giao diện | `frontend/src/features/admin/ContentPage.tsx` (danh sách), `UnitEditor.tsx` (form + soạn nháp); `lib/content.ts` (+ test); `styles/admin.css` |
| Test | `backend/tests/test_content.py` |

## Nội dung nằm ở đâu

- `backend/app/data/units.json` vẫn là **nội dung gốc** đi kèm mã nguồn, và vẫn được kiểm tra khi import (test dùng nó).
- Khi server khởi động (`load_content()` trong lifespan), mọi chủ đề và bài trong file được chép vào DB (cùng file `HISTORY_DB`). Sau đó app chỉ đọc từ DB.
- Mỗi dòng có `source`:
  - `file`: chưa ai sửa trên web. Khi `units.json` trong repo đổi, lần khởi động sau dòng này cập nhật theo. Bài mới trong file được thêm vào cuối.
  - `admin`: đã sửa trên web. File không ghi đè nữa, vì sửa của admin quan trọng hơn.
- **Xóa là ẩn** (`deleted = 1`): bài biến khỏi lộ trình và phòng tập, nhưng lịch sử luyện tập của bài vẫn còn, file không đưa bài trở lại, và admin khôi phục được.
- `topics`, `units`, `units_by_id` trong `interview/units.py` được thay **tại chỗ** (`use_content`) sau mỗi lần lưu. Mọi module đã import chúng (WebSocket, lộ trình, ôn tập, bài giảng) thấy nội dung mới ngay ở buổi tập sau, không cần khởi động lại. Buổi đang tập dở vẫn dùng bản cũ.

## Admin làm được gì

| Việc | Ghi chú |
|---|---|
| Sửa mọi trường của bài | Theo đúng schema của `units.json` ([interview-flow.md](interview-flow.md)): thông tin chung, vai AI (`role`, `partner`), mẫu câu (`say`, `match`, `when`), câu hỏi (`ask`, `simple`, mẫu câu luyện, ý gợi ý `steps`), bài giảng (`lesson`) |
| Thêm bài | Nút "Thêm bài" ở mỗi chủ đề. Bài mới đứng cuối chủ đề |
| Đổi thứ tự bài trong chủ đề | Nút ↑ ↓. Thứ tự này là thứ tự trên lộ trình và "bài tiếp theo" |
| Xóa / khôi phục bài | Không xóa được bài cuối cùng của một chủ đề (giai đoạn mở chủ đề đó cần có bài để tập) |
| Sửa tên và mô tả chủ đề | Không thêm hay bớt chủ đề trên web: việc giai đoạn nào mở chủ đề nào nằm trong `stages.json` |
| Thử bài | Nút "Thử bài này" mở phòng tập với `?unit=<id>` |

**Mã bài (`id`) không đổi được sau khi lưu**, vì lịch sử, thẻ ôn và bài giảng đã học đều ghi theo mã này. Bài mới tự lấy mã từ tên tiếng Anh (`slugify`), chữ thường nối bằng `-`, và không trùng mã của bài nào, kể cả bài đã xóa.

**Mỗi lần lưu đều kiểm tra** bằng đúng `validate()` dùng cho `units.json`, cùng `stages.validate()`. Lỗi trả về 400 `{"code": "invalid", "errors": [...]}`, form liệt kê từng lỗi (ví dụ `weekend: missing greeting`, `x: question 0 needs steps with hint and a say containing '...'`). Không lưu được nội dung làm hỏng app. Ngoài các trường bắt buộc, `validate()` kiểm tra những luật ảnh hưởng tới cách app chạy (trước đây chỉ có trong `test_units.py`, nay áp dụng cho cả bài admin tạo):

- `role`, `scenario`, `greeting`, `closing`, `vocab`, câu hỏi, mẫu câu, lời giáo viên và câu đọc theo ở bài giảng **không có tiếng Việt**: chúng được đọc to hoặc gửi cho AI. `goal`, `partner`, nhãn ý gợi ý, `intro_vi`, `use_vi`, nghĩa của từ thì là tiếng Việt.
- Mỗi mẫu câu có ít nhất một câu hỏi luyện nó, và đọc nguyên mẫu câu thì được nhận là đã dùng (`match` có phần đầu của mẫu câu).
- Không dùng từ của ví dụ trong prompt (`EXAMPLE_WORDS`: logistic, deliver, route...): `safe_note()` coi chúng là chép từ ví dụ và bỏ NOTE.

**Luật mới chặt hơn bài đã lưu:** lúc khởi động hoặc sau mỗi lần lưu, bài không qua `validate()` bị **tạm bỏ ra** khỏi app (`usable()`), server in `!! Unit ... left out until an admin fixes it` kèm lỗi, và danh sách quản trị hiện chip "Có lỗi, đang tạm ẩn". Server không dừng vì một bài lỗi. Admin mở bài, sửa, lưu lại là bài quay về.

## AI soạn nháp

Ở trang thêm bài, admin mô tả bài muốn tạo (tiếng Việt hay tiếng Anh đều được), chọn có soạn bài giảng không, rồi bấm "Soạn nháp". Bản nháp **chưa được lưu**: nó điền vào form để admin đọc, sửa rồi mới bấm Lưu.

AI chỉ **soạn nội dung**, không chấm điểm hay dẫn dắt buổi nói, nên vẫn đúng quy tắc "không chấm điểm bằng LLM" của dự án.

Cách làm (`drafts.py`):

1. Gửi cho model **một bài có sẵn của cùng chủ đề** làm mẫu (bài đầu tiên của chủ đề, bỏ `id`, `lesson`), cùng mô tả của admin. Model 7B viết theo mẫu tốt hơn nhiều so với chỉ đọc luật.
2. Dùng **structured output** của LM Studio (`response_format` kiểu `json_schema`, `strict`): model buộc phải trả JSON đúng hình dạng bài (3–6 mẫu câu, 3–6 câu hỏi, mỗi câu 2–3 ý). Không cần đoán JSON hỏng.
3. Bài giảng (nếu chọn) là **lần gọi thứ hai** với danh sách mẫu câu vừa có, để mỗi lần gọi ngắn và chắc hơn.
4. `fix_unit()` sửa những lỗi hay gặp: thêm `...` cho câu mở đầu thiếu, đưa chỉ số mẫu câu về trong khoảng, tạo `match` từ chính mẫu câu, **bỏ các `match` chỉ có một từ** ("recommend", "thinking": khớp quá nhiều câu trả lời), bỏ `...` trong câu bài giảng, bỏ `role`/`partner` ở chủ đề phỏng vấn.
5. Trả về `{unit, errors, notes}`: `errors` là lỗi sẽ chặn khi lưu; `notes` (`review_notes()`) là chỗ hợp lệ nhưng **dạy sai**, hiện thành khung vàng "Nên xem lại": mẫu câu hay ý gợi ý là câu hỏi (người học cần câu để trả lời), câu hỏi không có dấu `?`.

Prompt bằng tiếng Anh, nhưng yêu cầu các trường người học đọc (`goal`, nhãn ý gợi ý, bản dịch bài giảng) viết bằng tiếng Việt.

### Đã đo (14/10/2026, Qwen2.5-7B, RTX 3060, chủ đề `daily`, mô tả "gọi món ăn trưa với đồng nghiệp...")

| Lần | Thời gian | Kết quả |
|---|---|---|
| Prompt đầu | 78 giây (có bài giảng) | Hợp lệ. Mẫu câu "What do you recommend? ..." là câu hỏi người học hỏi lại; `match` một từ ("thinking", "recommend") |
| Sau khi sửa prompt + bỏ `match` một từ, 2 lần | khoảng 80 giây mỗi lần | Hợp lệ, hết `match` một từ. Vẫn có mẫu câu dạng câu hỏi ở 2/2 lần ("Have you tried the ...?"), một "câu hỏi" là câu kể. Model 7B không theo được luật này ổn định, nên chuyển thành `notes` để admin sửa |
| Chủ đề `workplace`, "xin nghỉ phép với trưởng nhóm..." | khoảng 80 giây | `role` viết bằng tiếng Việt và tả người học ("Nhân viên IT muốn nghỉ phép"). Nay `validate()` chặn tiếng Việt ở các trường gửi cho AI, prompt nói rõ `role` là người AI đóng, bằng tiếng Anh |
| Cùng mô tả, sau khi sửa | 35 giây (không bài giảng) | `role` "a TEAM LEAD discussing leave with the learner", `partner` "Trưởng nhóm", 3 mẫu câu đều là câu kể, không lỗi, không cảnh báo |

Kết luận: bản nháp đủ khung và đúng schema, tiết kiệm phần lớn công gõ, nhưng **luôn cần người đọc lại** trước khi lưu.

## API (cần vai trò admin)

| Route | Việc |
|---|---|
| `GET /api/admin/content` | Chủ đề, mọi bài (kể cả đã xóa) kèm tóm tắt và người sửa cuối, giai đoạn mở từng chủ đề |
| `GET /api/admin/units/{id}` | Toàn bộ JSON của bài |
| `PUT /api/admin/units/{id}` | Tạo (mã mới) hoặc thay bài. `id` trong body phải trùng địa chỉ. Bài đã xóa phải khôi phục trước (409) |
| `DELETE /api/admin/units/{id}` | Ẩn bài |
| `POST /api/admin/units/{id}/restore` | Khôi phục (kiểm tra lại hợp lệ) |
| `POST /api/admin/order` | `{ids}`: thứ tự mới; các bài không có trong danh sách giữ thứ tự cũ, đứng sau |
| `PUT /api/admin/topics/{id}` | `{title, description}` |
| `POST /api/admin/draft` | `{topic, brief, lesson}` → `{unit, errors, notes}`, không lưu. 502 nếu không gọi được LM Studio |

## Thử nghiệm

Đã thử ngày 14/10/2026 trên server cổng 8001 (DB tạm):

- `/admin/content` liệt kê 6 chủ đề, 24 bài; form sửa bài mở đủ các phần. Màn hình 375px không cuộn ngang, thanh "Lưu bài" dính đáy phía trên thanh tab.
- Thêm bài: "Soạn nháp" điền form, "Lưu bài" chuyển địa chỉ sang `/admin/units/requesting-leave`, bài xuất hiện cuối chủ đề `workplace` trong `/api/units` của người học.
- Khởi động lại khi DB có bài vi phạm luật mới (`role` tiếng Việt): server vẫn chạy, in cảnh báo, bài tạm ẩn. Lưu bản đã sửa thì bài quay về.
- `scripts/replay.py --unit requesting-leave` (đăng nhập bằng tài khoản admin thử): AI chào, hỏi đủ 3 câu của bài mới, có NOTE và ý gợi ý.
