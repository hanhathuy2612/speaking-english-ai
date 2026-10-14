# Nói dài hơn: các ý cần thêm và "Trả lời lại dài hơn"

Câu trả lời của người dùng trung bình 14 từ (36 câu nói trước ngày 12/10/2026), thường chỉ một câu. NOTE chỉ sửa câu đó cho đúng, nên không giúp nói dài hơn. Thẻ gợi ý vì vậy có hai phần:

1. **Cách nói tự nhiên hơn:** NOTE, cả câu trả lời vừa nói được viết lại cho đúng và tự nhiên (đủ mọi ý, cùng thứ tự, không thêm ý), để nghe và nói lại (shadowing, xem [shadowing.md](shadowing.md)). Xem [llm-prompt.md](llm-prompt.md).
2. **Nói dài hơn:** 2–3 ý nên thêm cho câu hỏi này. Mỗi ý có nhãn tiếng Việt cho biết cần nói gì, và câu mở đầu tiếng Anh:

```
Nói dài hơn: trả lời lại và thêm các ý này
  ✓ Vì sao?           That's because ...
  ○ Một lần cụ thể    For example, last week I ...
  ○ Mặt trái          The only downside is that ...
                                     [Trả lời lại dài hơn]
```

Ý nào câu trả lời (hoặc NOTE) đã có thì được đánh dấu ✓. Bấm **"Trả lời lại dài hơn"** rồi bấm micro để trả lời lại cả câu hỏi. Trong lúc đó thanh dưới hiện các ý cần thêm, vì thẻ NOTE có thể đã cuộn khuất. App so với lần đầu: số từ, số ý đã nói, tốc độ, số lần ngắt dài. Lượt này **không gọi LLM, không chuyển câu hỏi**, không tính vào số lượt phỏng vấn. Làm lại một nhiệm vụ nhiều lần là cách tăng độ trôi chảy (cùng ý tưởng với bài 4–3–2, [fluency-432.md](fluency-432.md)).

## Vì sao các ý được viết sẵn, không để LLM viết

- Khi bảo model 7B viết NOTE dài hơn, nó bịa lý do và ví dụ người học chưa nói ("The main reason is that it provides real practice", 3/3 lần replay). Câu mẫu bịa như vậy dạy người học một câu trả lời không phải của họ, và lấy mất phần họ phải tự nghĩ.
- Lần thử thứ hai nối các khung chung ("For example, ... So overall, ...") vào cuối NOTE. Cách này không dùng được: ba chỗ `...` liền nhau không cho biết phải nói gì, khung không hợp với câu hỏi ("Today, I'm going to ... The tricky part was ..."), và nút "Nói lại câu này" bắt đọc cả khung.
- Nay mỗi câu hỏi trong `units.json` có `steps` viết tay theo đúng câu hỏi đó, và các ý hiện tách khỏi NOTE.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Dữ liệu | `questions[].steps` (`hint`, `say`) trong `backend/app/data/units.json`; `validate()` trong `interview/units.py` kiểm tra có `hint` và `say` chứa `...` |
| Đánh dấu ý đã nói, cắt lý do bịa trong NOTE, cắt câu chép lại câu trả lời trước | `mark_steps()`, `trim_invented()`, `drop_earlier()` trong `backend/app/interview/steps.py` |
| Gửi các ý kèm NOTE, lưu câu trả lời đầu | cuối `run_turn()` trong `interview/turn.py` (`Session.retell_base`) |
| Xử lý lượt trả lời lại | `handle_retell()` trong `interview/retell.py`; tin `retell` trong `_on_text()`, nhánh `session.retell` trong `_on_audio()` (`api/routes/ws.py`) |
| Lưu | bảng `retells`, `add_retell()` trong `services/history.py` |
| Giao diện | `Steps`, `RetellResult` trong `frontend/src/features/practice/CoachCard.tsx`; `beginRetell`/`cancelRetell` trong `useInterview.ts`; `.steps`, `.step-*`, `.retell-*` trong `styles/practice.css` |
| Test | `backend/tests/test_steps.py`, `test_retell_attempts_...` trong `test_history.py` |

## Đánh dấu ý đã nói (`mark_steps`)

Một ý được tính là đã nói khi câu trả lời có:
- phần trước `...` của câu mở đầu (ví dụ "the only downside is that"), nếu phần đó có từ 2 từ trở lên. Câu mở đầu chỉ một từ như "I'll ..." quá phổ biến nên không đủ làm bằng chứng;
- hoặc cùng ý bằng từ khác: `because` / `the reason` / `that's why` (lý do), `for example` / `for instance` (ví dụ), `as a result` / `in the end` (kết quả).

Không dùng LLM để chấm. Chỉ đếm theo chữ nên có thể sót khi người học diễn đạt khác hẳn, nhưng không bao giờ "khen" một ý chưa nói.

## Cắt lý do bịa trong NOTE (`trim_invented`)

Sau `safe_note()`, khi không RETRY: câu thứ hai trở đi, hoặc vế `because ...`, có từ nội dung (≥ 4 chữ cái, bỏ đuôi -s/-ed/-ing) phần lớn là mới (≥ 2 từ và ≥ 60%) so với các câu hỏi và câu trả lời trong buổi thì bị cắt. Vế `because ...` để trống model để lại cũng bị cắt. Từ của mẫu câu không tính là mới. Lý do bị cắt sẽ hiện thành ý "Vì sao?" chưa đánh dấu.

## Giao thức

- Tin `note` có thêm `steps: [{hint, say, done}]`. Rỗng khi RETRY hoặc khi lượt đó trả lời câu hỏi phụ (các ý viết cho câu hỏi chính).
- Trình duyệt gửi `{"type":"retell"}` ngay trước khung âm thanh. Server chỉ nhận khi có `retell_base` (câu trả lời đầu của câu hỏi vừa có NOTE).
- Server trả `retell_result`: `heard`, `speech`, `original` (chỉ số nói của lần đầu, `null` nếu gõ chữ), `original_words`, `steps` (đánh dấu theo lần trả lời lại). Rồi `turn_done`.
- Gõ chữ, hoàn tác, hay có câu trả lời mới đều thoát chế độ trả lời lại.

## Kiểm chứng

Trên server thử cổng 8001, bài `opinions`: gõ "I prefer working in the office." (6 từ). Thẻ hiện NOTE "In my opinion, working in the office is better." và 3 ý (Vì sao? / Một lần cụ thể / Mặt trái). Trả lời lại bằng giọng đọc edge-tts (14,7 giây, qua micro giả): 40 từ · lần đầu 6, đủ 3/3 ý, câu hỏi không chuyển, bảng `retells` có một dòng (40, 6, 3/3).
