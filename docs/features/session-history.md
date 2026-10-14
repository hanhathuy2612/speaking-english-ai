# Lịch sử luyện tập và trang Tiến bộ

Mục đích: biết app có giúp người dùng nói trôi chảy hơn qua các buổi hay không, bằng số đo chứ không bằng cảm giác.
Mỗi lượt trả lời được ghi vào một file SQLite cục bộ. Trang `/history` vẽ xu hướng theo buổi tập.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Lưu và tổng hợp | `backend/app/services/history.py` (`SCHEMA`, `start_session`, `add_turn`, `delete_turn`, `set_completed`, `list_sessions`, `_summarize`; `add_drill`/`list_drills`/`list_readings`, `add_fluency_round`/`list_fluency_rounds`) |
| Ghi mỗi lượt | `handle_user_input()`, `run_turn()`, `_history_id()` trong `backend/app/interview/turn.py` |
| Hoàn tác | nhánh `undo` trong `_on_text()` (`backend/app/api/routes/ws.py`): xóa dòng của lượt vừa rồi |
| API | `backend/app/api/routes/history.py` |
| Trang | `frontend/src/features/history/` (`HistoryPage.tsx`, `LineChart.tsx`), `frontend/src/styles/history.css` |
| Test | `backend/tests/test_history.py` |

## Dữ liệu

File mặc định: `data/history.db` ở thư mục gốc (biến `HISTORY_DB`, để trống thì tắt). Không commit (`/data/` trong `.gitignore`).

- **`sessions`:** một dòng cho mỗi lần làm bài. Chỉ được tạo **khi có câu trả lời đầu tiên**, nên mở bài rồi bỏ đi không để lại phiên rỗng. `completed` = 1 khi đã hỏi hết câu.
- **`turns`:** một dòng cho mỗi lượt trả lời. Ghi: câu hỏi, câu trả lời, nguồn (`voice`/`text`), cờ `unclear`, số từ, tốc độ, số lần ngắt dài, `avg_logprob` và `no_speech` của Whisper, các mẫu câu dùng trong lượt, NOTE, cờ RETRY, độ trễ.
- **`shadows`:** mỗi lần nói lại câu NOTE (xem [shadowing.md](shadowing.md)). Tách khỏi `turns` nên không ảnh hưởng số liệu phỏng vấn.
- **`checks`:** mỗi lần làm bài kiểm tra nói 2 phút (xem [speaking-check.md](speaking-check.md)): đề, chữ nhận dạng, thời lượng, tốc độ, số lần ngập ngừng giữa câu, số tiêu chí đạt. Không gắn với `sessions`.
- **`drills`:** mỗi lần đọc một câu luyện phát âm (xem [pronunciation-drills.md](pronunciation-drills.md)): nhóm, câu mẫu, chữ nghe được, số từ đúng / tổng, số từ trọng tâm đúng / tổng, tên file ghi âm (`audio`, thêm sau nên có migration và ghép bù theo thời gian). `list_readings()` gộp `shadows`, `drills` và `lesson_reads` (theo thời gian, rồi theo bảng và `id`, vì thời gian chỉ chính xác tới giây) để làm nhóm "Câu bạn từng đọc sai".
- **`lesson_reads`, `lessons`:** mỗi lần đọc một câu ở bài giảng (câu mẫu, chữ nghe được, số từ đúng / tổng), và mỗi lần học xong bài giảng của một bài (xem [lesson.md](lesson.md)). Không gắn với `sessions`.
- **`fluency`:** mỗi lần kể trong bài 4–3–2 (xem [fluency-432.md](fluency-432.md)): `run` (id của bài), số lần, giới hạn giây, đề, chữ nhận dạng, thời lượng, tốc độ, ngập ngừng. Một bài gồm 3 dòng cùng `run`.
- **`cards`, `card_reviews`:** thẻ ôn tập và mỗi lần chấm (xem [review.md](review.md)). Thẻ NOTE gắn với `turns` (`ON DELETE CASCADE`), nên hoàn tác hay xóa buổi cũng xóa thẻ.
- Tiêu chí mở giai đoạn của lộ trình được tính từ các bảng trên khi đọc (xem [roadmap.md](roadmap.md)), không lưu sẵn.
- Lượt "máy nghe chưa rõ" hoặc "chưa phải tiếng Anh" cũng được ghi (`unclear` = 1), làm dữ liệu hiệu chỉnh ngưỡng STT.
- Hoàn tác xóa hẳn dòng của lượt vừa rồi và cập nhật lại `completed`.
- Số liệu tổng hợp được tính khi đọc, không lưu sẵn, nên xóa hay hoàn tác không làm lệch số.

Thêm cột mới: thêm vào `SCHEMA` **và** `MIGRATIONS` (`CREATE TABLE IF NOT EXISTS` không tự thêm cột vào bảng đã có; `init()` thêm các cột trong `MIGRATIONS` cho DB cũ).

## Chỉ số trên trang Tiến bộ

| Chỉ số | Cách tính |
|---|---|
| Tốc độ khi nói | Trung bình `wpm_speaking` của các lượt **giọng nói, máy nghe rõ, từ 10 từ trở lên** trong buổi |
| Ngắt dài / 100 từ | Tổng số lần ngắt trên 0,7 giây ÷ tổng số từ × 100, **chỉ trên cùng các lượt đó**. Câu quá ngắn bị loại, vì một câu 2 từ không ngắt sẽ cho ra 0 |
| Mẫu câu | Số mẫu câu khác nhau đã dùng trong buổi / tổng số mẫu câu của bài |
| Đọc đúng khi nói lại | Tổng số từ máy nghe đúng ÷ tổng số từ của câu mẫu × 100, **gộp mọi lần** nói lại trong buổi (`shadow_accuracy`, kèm `shadow_attempts`). Câu dài nặng ký hơn câu ngắn |
| So với buổi đầu | Buổi gần nhất có số liệu trừ buổi đầu tiên có số liệu. Màu xanh khi tốt lên (tốc độ tăng, ngắt giảm) |

Lượt gõ chữ được tính vào số lượt và mẫu câu, nhưng không vào tốc độ hay số lần ngắt.

## API

| Route | Việc |
|---|---|
| `GET /api/history/sessions` | `{enabled, sessions: [...]}`, các buổi có ít nhất 1 lượt trả lời, cũ trước mới sau |
| `GET /api/history/sessions/{id}/turns` | Chi tiết từng lượt của một buổi, kèm `audio_url` khi còn file ghi âm |
| `GET /api/history/audio/{name}` | File ghi âm của một lượt (`audio/webm`). Chỉ nhận tên dạng `YYYYMMDD-HHMMSS-ffffff.webm` trong `SAVE_AUDIO_DIR`, tên khác trả 404 |
| `DELETE /api/history/sessions/{id}` | Xóa một buổi (xóa luôn các lượt) |

## Trang `/history`

- 5 ô số liệu: số buổi, số lượt nói bằng giọng, tốc độ, tỉ lệ ngắt và độ đọc đúng khi nói lại của buổi gần nhất so với buổi đầu.
- 3 biểu đồ đường riêng (không gộp chung một trục vì khác đơn vị; biểu đồ % cố định trục 0–100), vẽ bằng SVG thuần, có đường dóng và chú thích nổi khi rê chuột, nhãn giá trị ở điểm cuối.
- Màu đường biểu đồ là token `--chart-line` trong `base.css`, đã kiểm tra độ tương phản và dải độ sáng ở cả hai chế độ bằng `validate_palette.js` của skill dataviz.
- Bảng các buổi tập (cũng là cách xem số liệu không cần biểu đồ), có nút xóa kèm hộp xác nhận.
- Nút **"Xem"** của mỗi buổi mở thẻ "Chi tiết buổi tập" ngay dưới bảng (`SessionDetail.tsx`, tự cuộn tới khi tải xong; đặt ngoài bảng vì bảng cuộn ngang trên điện thoại): từng câu hỏi, câu bạn trả lời, nút **"Nghe lại"** giọng bạn, tốc độ, NOTE.

## Nghe lại buổi cũ

- File ghi âm chỉ còn khi `SAVE_AUDIO_DIR` được đặt (`.env` của người dùng: `recordings`). Xóa buổi tập **không** xóa file ghi âm.
- Lượt nói mới lưu tên file vào cột `turns.audio` (`stt.kept_name()` → `result["recording"]` trong `ws.py` → `handle_user_input()`).
- Lượt lưu trước khi có cột này được ghép **một lần**, khi mở chi tiết buổi (`match_turns()` trong `services/recordings.py`): file có `.hyp.txt` trùng đúng chữ câu trả lời, ghi trong vòng 10 phút trước lúc lượt được lưu; chọn file gần nhất, mỗi file dùng một lần; kết quả được lưu lại vào `turns.audio`. Đo ngày 11/10/2026 trên lịch sử thật: ghép được 29/29 lượt nói.
- Cột mới trên DB cũ: `init()` chạy `MIGRATIONS` (`ALTER TABLE ... ADD COLUMN` khi cột chưa có).
- App không có đăng nhập: khi chạy cho mạng LAN (`SERVER_HOST=0.0.0.0`), thiết bị cùng mạng cũng nghe được các file này.

## Khi thử nghiệm

Server thử (cổng 8001) **phải** trỏ `HISTORY_DB` sang file tạm hoặc để trống, nếu không sẽ ghi lẫn vào lịch sử thật của người dùng. Xem [dev-environment.md](../dev-environment.md).
