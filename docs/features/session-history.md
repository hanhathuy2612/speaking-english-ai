# Lịch sử luyện tập và trang Tiến bộ

Mục đích: biết app có giúp người dùng nói trôi chảy hơn qua các buổi hay không, bằng số đo chứ không bằng cảm giác.
Mỗi lượt trả lời được ghi vào một file SQLite cục bộ. Trang `/history` vẽ xu hướng theo buổi tập.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Lưu và tổng hợp | `backend/app/services/history.py` (`SCHEMA`, `start_session`, `add_turn`, `delete_turn`, `set_completed`, `list_sessions`, `_summarize`) |
| Ghi mỗi lượt | `handle_user_input()`, `run_turn()`, `_history_id()` trong `backend/app/interview/turn.py` |
| Hoàn tác | nhánh `undo` trong `_on_text()` (`backend/app/api/routes/ws.py`): xóa dòng của lượt vừa rồi |
| API | `backend/app/api/routes/history.py` |
| Trang | `frontend/history.html`, `frontend/js/history.js`, `frontend/css/history.css` |
| Test | `backend/tests/test_history.py` |

## Dữ liệu

File mặc định: `data/history.db` ở thư mục gốc (biến `HISTORY_DB`, để trống thì tắt). Không commit (`/data/` trong `.gitignore`).

- **`sessions`:** một dòng cho mỗi lần làm bài. Chỉ được tạo **khi có câu trả lời đầu tiên**, nên mở bài rồi bỏ đi không để lại phiên rỗng. `completed` = 1 khi đã hỏi hết câu.
- **`turns`:** một dòng cho mỗi lượt trả lời. Ghi: câu hỏi, câu trả lời, nguồn (`voice`/`text`), cờ `unclear`, số từ, tốc độ, số lần ngắt dài, `avg_logprob` và `no_speech` của Whisper, các mẫu câu dùng trong lượt, NOTE, cờ RETRY, độ trễ.
- Lượt "máy nghe chưa rõ" cũng được ghi (`unclear` = 1). Đây là dữ liệu để hiệu chỉnh `STT_MIN_LOGPROB` sau này.
- Hoàn tác xóa hẳn dòng của lượt vừa rồi và cập nhật lại `completed`.
- Số liệu tổng hợp được tính khi đọc, không lưu sẵn, nên xóa hay hoàn tác không làm lệch số.

Thêm cột mới: thêm vào `SCHEMA` (`CREATE TABLE IF NOT EXISTS` không tự thêm cột vào bảng đã có, nên với DB cũ phải `ALTER TABLE` hoặc xóa file).

## Chỉ số trên trang Tiến bộ

| Chỉ số | Cách tính |
|---|---|
| Tốc độ khi nói | Trung bình `wpm_speaking` của các lượt **giọng nói, máy nghe rõ, từ 10 từ trở lên** trong buổi |
| Ngắt dài / 100 từ | Tổng số lần ngắt trên 0,7 giây ÷ tổng số từ × 100, **chỉ trên cùng các lượt đó**. Câu quá ngắn bị loại, vì một câu 2 từ không ngắt sẽ cho ra 0 |
| Mẫu câu | Số mẫu câu khác nhau đã dùng trong buổi / tổng số mẫu câu của bài |
| So với buổi đầu | Buổi gần nhất có số liệu trừ buổi đầu tiên có số liệu. Màu xanh khi tốt lên (tốc độ tăng, ngắt giảm) |

Lượt gõ chữ được tính vào số lượt và mẫu câu, nhưng không vào tốc độ hay số lần ngắt.

## API

| Route | Việc |
|---|---|
| `GET /api/history/sessions` | `{enabled, sessions: [...]}`, các buổi có ít nhất 1 lượt trả lời, cũ trước mới sau |
| `GET /api/history/sessions/{id}/turns` | Chi tiết từng lượt của một buổi |
| `DELETE /api/history/sessions/{id}` | Xóa một buổi (xóa luôn các lượt) |

## Trang `/history`

- 4 ô số liệu: số buổi, số lượt nói bằng giọng, tốc độ và tỉ lệ ngắt của buổi gần nhất so với buổi đầu.
- 2 biểu đồ đường riêng (không gộp chung một trục vì khác đơn vị), vẽ bằng SVG thuần, có đường dóng và chú thích nổi khi rê chuột, nhãn giá trị ở điểm cuối.
- Màu đường biểu đồ là token `--chart-line` trong `base.css`, đã kiểm tra độ tương phản và dải độ sáng ở cả hai chế độ bằng `validate_palette.js` của skill dataviz.
- Bảng các buổi tập (cũng là cách xem số liệu không cần biểu đồ), có nút xóa kèm hộp xác nhận.

## Khi thử nghiệm

Server thử (cổng 8001) **phải** trỏ `HISTORY_DB` sang file tạm hoặc để trống, nếu không sẽ ghi lẫn vào lịch sử thật của người dùng. Xem [dev-environment.md](../dev-environment.md).
