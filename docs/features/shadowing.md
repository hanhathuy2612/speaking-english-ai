# Nói lại câu mẫu (shadowing)

Hoàn thiện vòng cốt lõi "nói, xem cách nói tốt hơn, **nói lại**". Sau khi NOTE hiện ra, người học bấm **"Nói lại câu này"** rồi giữ micro (hoặc Space) và đọc câu NOTE. App so chữ nhận dạng được với câu mẫu, tô từng từ, và so tốc độ / số lần ngắt với lần trả lời đầu.

Lượt nói lại **không gọi LLM, không chuyển câu hỏi**, không tính vào số lượt phỏng vấn.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Chuẩn hóa, căn chỉnh từ, WER | `backend/app/utils/compare.py` (`word_tokens`, `tokens`, `compare`, `word_errors`, `wer`) |
| Xử lý một lượt nói lại | `handle_shadow()` trong `backend/app/interview/shadow.py` |
| Nhận tin, chọn prompt STT | `_on_text()` (tin `shadow`) và `_on_audio()` trong `backend/app/api/routes/ws.py` |
| Trạng thái | `Session.shadow_target`, `Session.last_speech` trong `backend/app/interview/session.py` |
| Lưu | bảng `shadows`, `add_shadow()` trong `backend/app/services/history.py` |
| Giao diện | `CoachCard.tsx` (`ShadowResult`, tô từng từ bằng `components/WordDiff.tsx`), hành động `beginShadow`/`cancelShadow`/`sendRecording` trong `useInterview.ts` (`frontend/src/features/practice/`); `.shadow-*` trong `frontend/src/styles/practice.css`, `.word-diff`/`.tok.*` trong `base.css` (dùng chung với trang luyện phát âm) |
| Test | `backend/tests/test_compare.py`, `test_shadow_attempts_...` trong `backend/tests/test_history.py` |

## Luồng

1. Bấm "Nói lại câu này": `shadow.waiting = true`, thẻ NOTE có viền nổi bật, nút Hủy hiện ra.
2. Khi thả micro, frontend gửi `{"type": "shadow", "text": NOTE}` **ngay trước** khung âm thanh. Server đặt `shadow_target`.
3. Server nhận dạng **không có `initial_prompt`**. Gợi ý từ vựng sẽ kéo Whisper về đúng các từ trong câu mẫu và che mất lỗi phát âm.
4. `handle_shadow()` gửi `shadow_result`: `target`, `heard`, `compare`, `speech` (chỉ số nói của lần đọc lại), `original` (chỉ số của câu trả lời đã sinh ra NOTE, `null` nếu câu đó gõ chữ). Mỗi yêu cầu chỉ dùng cho **một** lần ghi âm; "Thử lại" gửi lại `shadow`.
5. Gõ chữ, hoàn tác hay có câu trả lời mới đều thoát chế độ nói lại.
6. Kết quả có nút "Nghe lại" để nghe chính lần đọc đó (chỉ trong trình duyệt, xem [frontend.md](frontend.md)).

## So sánh (`compare.py`)

Chuẩn hóa cả hai phía để **khác biệt về cách viết không bị tính là lỗi**:
- Số: "5" thành "five", "30%" thành "thirty percent", "10,000" thành "ten thousand".
- Viết tắt: "I've" thành "i have", "don't" thành "do not"...
- Chữ hoa/thường, dấu câu, gạch nối.

Sau đó căn chỉnh theo khoảng cách Levenshtein mức từ, rồi gộp về từng từ viết của câu mẫu:

| Trạng thái | Nghĩa | Hiển thị |
|---|---|---|
| `ok` | Nghe đúng | Bình thường |
| `wrong` | Nghe thành từ khác (kèm `heard`) | Gạch chân lượn sóng cam, chữ máy nghe được nhỏ bên dưới |
| `miss` | Không nghe thấy | Gạch ngang, màu nhạt |
| `extra` | Người học nói thêm | Nhãn "+ ..." |

Một từ viết thành nhiều token (ví dụ "I'm" thành "i am") mà chỉ khớp một phần thì là `wrong`, không phải `miss`.
`accuracy` = số token đúng / số token của câu mẫu.

`stt_bench.py` cũng dùng `word_errors()` này, nên WER không còn bị tính sai vì cách viết số.

## Giới hạn đã biết

- **Whisper tự "sửa" từ phát âm gần đúng** nhờ mô hình ngôn ngữ. Khi thử, đọc "Jaba" vẫn được nghe thành "Java". Chế độ này bắt được lỗi rõ (mất âm cuối "-s"/"-ed", đọc thành từ khác, bỏ từ) nhưng có thể bỏ sót lỗi nhẹ. Không nên coi 100% là phát âm chuẩn.
- Chỉ số tốc độ của câu dưới 10 từ không được tính (giống lượt phỏng vấn).

## Dữ liệu

Mỗi lần nói lại được lưu một dòng trong bảng `shadows` (câu mẫu, câu nghe được, số token đúng/tổng, số từ, tốc độ, số lần ngắt, `avg_logprob`), tách khỏi `turns` để không làm lệch số liệu phỏng vấn. Câu nào lần nói lại gần nhất còn từ sai sẽ vào nhóm "Câu bạn từng đọc sai" của trang luyện phát âm (xem [pronunciation-drills.md](pronunciation-drills.md)). Trang Tiến bộ hiện tỉ lệ đọc đúng của mỗi buổi (`shadow_accuracy`, xem [session-history.md](session-history.md)).
