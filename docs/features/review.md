# Ôn tập (trang `/review`)

Mục đích: lỗi được sửa một lần rồi thôi thì vài ngày sau sẽ nói sai lại. Mỗi NOTE và mỗi mẫu câu bị bỏ sót thành một **thẻ ôn**, quay lại theo lịch giãn dần (ôn ngắt quãng) cho tới khi thành phản xạ. Có hai cách vào:

- **A. Ôn ngay cuối buổi:** thẻ tổng kết ở phòng tập có nút **"Ôn lỗi của buổi này"** (`/review?session=<id>`): mọi thẻ của buổi vừa tập, không cần đến hạn.
- **B. Ôn hằng ngày:** mục **"Ôn tập"** trên thanh điều hướng (huy hiệu cam là số thẻ đến hạn): các thẻ đến hạn hôm nay, mỗi lượt tối đa 15 thẻ (khoảng 5 phút).

**Không dùng LLM để chấm.** Người học tự chấm "Nhớ được" / "Chưa nhớ"; app chỉ gợi ý (nút được tô) bằng phép đo khách quan.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Lịch ôn, tạo thẻ, gợi ý chấm | `backend/app/interview/review.py` (`schedule()`, `worth_a_card()`, `check_attempt()`, `sync()`) |
| API | `backend/app/api/routes/review.py` |
| Lưu | bảng `cards`, `card_reviews`; các hàm dưới mục "Review cards" trong `backend/app/services/history.py` |
| `session_id` trong tin `summary` | `summary()` trong `backend/app/interview/session.py` |
| Trang | `frontend/src/features/review/ReviewPage.tsx`, `frontend/src/styles/review.css`, `fmtDue()`/`localDay()` trong `frontend/src/lib/review.ts` |
| Nút cuối buổi | `SummaryCard` trong `frontend/src/features/practice/Chat.tsx` |
| Huy hiệu số thẻ đến hạn | `AppBar.tsx` (gọi `GET /api/review/count` mỗi lần đổi trang) |
| Test | `backend/tests/test_review.py`, `frontend/src/lib/review.test.ts` |

## Thẻ

| Loại | Nguồn | Mặt trước | Mặt sau | Gợi ý chấm |
|---|---|---|---|---|
| `note` | Lượt trả lời rõ (không `unclear`) có NOTE | Câu hỏi + câu bạn đã nói. Bạn nói lại cho đúng **theo trí nhớ** | NOTE, tô từng từ so với câu vừa nói (`WordDiff`) | "Nhớ được" khi nói trùng ≥ 80% từ của NOTE (`GOOD_OVERLAP`) |
| `phrase` | Mẫu câu không dùng trong một buổi **đã hoàn thành** | Câu hỏi chính nhắm tới mẫu câu + mẫu câu. Bạn trả lời có dùng nó | Có / chưa nghe thấy mẫu câu | "Nhớ được" khi `used_phrase_indices()` tìm thấy mẫu câu |

- Nói khác NOTE chưa chắc là sai (diễn đạt khác vẫn đúng). Vì vậy app chỉ gợi ý, người học quyết định; trang ghi rõ điều này.
- Không tạo thẻ khi NOTE **trùng từng từ** với câu đã nói, hoặc NOTE **dài hơn 30 từ** (`MAX_NOTE_WORDS`): một đoạn dài không thể nói lại theo trí nhớ. Đo ngày 11/10/2026 trên lịch sử thật: 23 NOTE dài 5–19 từ, chỉ một NOTE 38 từ.
- Mỗi mẫu câu của một bài chỉ có một thẻ (`UNIQUE (unit_id, phrase_index)`), dù bỏ sót ở nhiều buổi.
- "Không nhớ, xem đáp án" mở mặt sau mà không cần nói. "Nghe" đọc NOTE (edge-tts, có cache). "Bỏ thẻ này" ẩn thẻ vĩnh viễn (`suspended`), dùng khi NOTE không đáng học (ví dụ NOTE thêm chi tiết bạn không nói).

## Tạo thẻ (`sync()`)

Thẻ được tạo **khi đọc** (`GET /api/review`, `GET /api/review/count`) từ lịch sử, không phải lúc trả lời. Nhờ vậy NOTE có từ trước khi có tính năng này cũng thành thẻ, và **hoàn tác** một lượt sẽ xóa luôn thẻ của nó (`turn_id ... ON DELETE CASCADE`). Thẻ mới đến hạn ngay hôm nay.

## Lịch ôn (`schedule()`, hệ Leitner)

| Chấm | Hộp mới | Hẹn lại |
|---|---|---|
| Nhớ được | hộp + 1 (tối đa 6) | sau 1, 3, 7, 14, 30, 60 ngày ứng với hộp 1…6 (`INTERVALS`) |
| Chưa nhớ | 0 | ngày mai |

- Thẻ chấm "Chưa nhớ" còn quay lại **một lần nữa ở cuối lượt ôn đang làm** (chỉ trên giao diện), để nói lại khi vừa xem đáp án.
- "Đã thuộc" = hộp ≥ 4 (`LEARNED_BOX`: đã qua khoảng cách 14 ngày).
- Ngày tính theo giờ máy chạy server (`date.today()`).

## API

| Route | Việc |
|---|---|
| `GET /api/review` | Thẻ đến hạn hôm nay (tối đa 15, đến hạn sớm trước). `?session=<id>`: mọi thẻ của buổi đó. Kèm `stats`: `due`, `active`, `learned`, `reviews` / `good` / `recall` (% "Nhớ được" trong 30 ngày) |
| `GET /api/review/count` | `{due}` cho huy hiệu |
| `GET /api/review/{id}/audio` | MP3 của NOTE hoặc mẫu câu |
| `POST /api/review/{id}/attempt` | Thân request là âm thanh thô. Nhận dạng có `STT_VOCAB`, trả `{heard, suggest, items/correct/total/accuracy}` (thẻ `note`) hoặc `{heard, phrase_used, suggest}` (thẻ `phrase`). **Không lưu gì** |
| `POST /api/review/{id}/grade` | `{result: "good" \| "again", heard?, correct?, total?}`: cập nhật hộp và ngày hẹn, ghi một dòng `card_reviews` |
| `POST /api/review/{id}/suspend` | Bỏ thẻ |

## Kiểm thử đầu cuối (11/10/2026)

Trên bản sao lịch sử thật (server thử cổng 8001): tạo 30 thẻ (23 NOTE, 7 mẫu câu); giới hạn 30 từ được thêm sau lần chạy này, nên nay NOTE 38 từ không còn thành thẻ. Đọc đúng NOTE "I wish I could avoid traffic delays so I'm not often late for work." (edge-tts): trùng 93%, gợi ý "Nhớ được"; đọc "I want go to work fast because I late.": 20%, gợi ý "Chưa nhớ". Chấm "Nhớ được" chuyển thẻ sang ngày mai, số thẻ đến hạn giảm 1. Ôn cuối buổi (`?session=1`, 4 thẻ): thẻ "Chưa nhớ" quay lại cuối lượt (4 → 5 thẻ), màn hình kết thúc báo thẻ gần nhất quay lại "ngày mai".
