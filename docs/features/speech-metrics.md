# Chỉ số nói và mẫu câu

Không chấm điểm bằng LLM. Mọi chỉ số đều lấy khách quan từ mốc thời gian từng từ của Whisper.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Chỉ số mỗi lượt | `speech_metrics()` trong `backend/app/utils/parsing.py` |
| Mẫu câu đã dùng | `used_phrase_indices()`, `norm()` trong `backend/app/utils/parsing.py` |
| Tổng kết phiên | `summary()` trong `backend/app/interview/session.py`, `SummaryCard` trong `frontend/src/features/practice/Chat.tsx` |
| Hiển thị | `SpeechChips` trong `Chat.tsx`, danh sách mẫu câu trong `Sidebar.tsx` (`frontend/src/features/practice/`) |
| Test | `backend/tests/test_parsing.py` |

## `speech_metrics(words)`

| Trường | Ý nghĩa |
|---|---|
| `words` | Số từ. |
| `wpm` | Từ/phút **tính cả ngắt** (từ đầu đến cuối câu). |
| `wpm_speaking` | Từ/phút **khi đang nói**, đã trừ các lần ngắt dài. |
| `long_pauses` | Số lần ngắt dài hơn `LONG_PAUSE_S` (0,7 giây). |
| `low_conf` | Tối đa 6 từ máy nghe chưa chắc (xác suất dưới 0,5), đã bỏ từ chức năng. |

- Câu dưới `SHORT_ANSWER_WORDS` (10 từ) không tính tốc độ (`None`), vì quá nhiễu.
- `FUNCTION_WORDS` (a, the, with...) bị loại khỏi `low_conf`, vì Whisper luôn chấm chúng thấp dù nghe đúng.
- Câu trả lời gõ chữ không có `words`, nên không có chỉ số.

## Mẫu câu đã dùng

- So từng `match` của `data/units.json` với câu nhận dạng sau khi `norm()`. Khớp thì đánh dấu ✓ ở cột trái.
- Chỉ so trên chữ máy nghe được. Nếu máy nghe sai ("I've been booking a shop" thay vì "I've been working as"), mẫu câu sẽ không được tính.
- Lượt "nghe chưa rõ" không được tính.

## Số đo từ phiên đầu (chỉ một phiên, chưa phải kết luận)

Câu quen miệng ("I've been working as...") đạt 115 đến 175 từ/phút. Câu tự nghĩ chỉ 35 đến 66 từ/phút, với 3 đến 7 lần ngắt dài.
