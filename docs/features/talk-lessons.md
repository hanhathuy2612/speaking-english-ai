# Bài giảng nói 2 phút và học sau bài kiểm tra

Bài kiểm tra nói ([speaking-check.md](speaking-check.md)) cho biết bạn ngập ngừng ở đâu, nhưng chưa dạy cách nói tiếp. Người dùng thường bí vì thiếu từ và thiếu cấu trúc câu để nối ý. Tính năng này có hai phần:

- **A. Bài giảng theo dạng đề:** mỗi dạng câu hỏi của bài kiểm tra (nêu ý kiến, kể chuyện, giải thích, miêu tả) có một bài giảng: dàn ý 2 phút gồm 5 bước, 6 câu mẫu để đọc theo, rồi luyện nói 2 phút với **đề luyện riêng**.
- **B. Học sau bài kiểm tra:** sau khi có kết quả, người học xem các chỗ bị bí, nhờ AI viết lại chính bài nói của mình, thêm cụm từ còn thiếu vào thẻ ôn, rồi nói lại đề đó.

## Bài kiểm tra vẫn là bài kiểm tra

- **Đo trước, học sau.** Kết quả bài kiểm tra được lưu ngay khi chấm. Việc học sau đó không bao giờ sửa số của nó.
- **Nói lại chỉ là luyện tập.** Lần nói lại lưu vào bảng `talk_practice` (`source = 'check'`), không vào `checks`, nên không tính vào lộ trình hay đường xu hướng.
- **Đề đã ôn không ra lại.** Một đề tính là đã ôn khi người học đã xem bản ôn của nó hoặc đã nói lại nó (`studied_check_prompts()`). `pick_prompt()` bỏ các đề đó. Nếu mọi đề đều đã ôn thì mới chọn lại trong tất cả.
- **Đề luyện của bài giảng không bao giờ là đề kiểm tra.** Mỗi bài giảng có 4 đề luyện riêng trong `talks.json`, khác 20 đề kiểm tra.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Nội dung 4 bài giảng | `backend/app/data/talks.json` |
| Nạp, kiểm tra dữ liệu, chuyển sang dạng bài để dùng lại phần bài giảng | `backend/app/interview/talks.py` (`as_unit()`, `validate()`, `public()`, `practice_prompt()`) |
| Dạng đề của từng đề kiểm tra | trường `kind` trong `backend/app/data/check_prompts.json` (5 đề mỗi dạng) |
| Chỗ bí giữa câu | `stuck_points()` trong `backend/app/assessment/check.py`, `hesitation_points()` trong `backend/app/utils/parsing.py` |
| AI viết lại và gợi ý | `backend/app/interview/check_review.py` |
| Đánh dấu bước dàn ý đã nói | `mark_steps()` trong `backend/app/interview/steps.py` (thêm `also`: các cách nói khác của một bước) |
| API | `backend/app/api/routes/talks.py`, các route học sau bài kiểm tra trong `backend/app/api/routes/check.py` |
| Lưu | bảng `talk_practice`, cột `stuck` và `review` của `checks`; `add_talk_practice()`, `list_talk_practice()`, `get_check()`, `set_check_review()`, `studied_check_prompts()` trong `backend/app/services/history.py` |
| Trang bài giảng | `frontend/src/features/lesson/LessonPage.tsx` (dùng chung với bài giảng của bài, xem [lesson.md](lesson.md)) |
| Trang luyện nói | `frontend/src/features/talk/TalkPracticePage.tsx`, phần dùng chung `TalkParts.tsx` (ghi âm, bảng so sánh, danh sách chỗ bí, dàn ý) |
| Học sau bài kiểm tra | `frontend/src/features/check/CheckLearn.tsx`, mục "Học cách nói 2 phút" trong `CheckPage.tsx` |
| Hàm thuần | `frontend/src/lib/talks.ts` (`nextPrompt`, `compareTalks`, `splitUnsure`) + `talks.test.ts` |
| Giao diện | `frontend/src/styles/talk.css`, phần cuối `check.css`, `.lesson-frame` trong `lesson.css` |
| Test | `backend/tests/test_talks.py` |

## A. Bài giảng theo dạng đề

| `id` | Tên | Dàn ý 5 bước | Chủ đề câu mẫu |
|---|---|---|---|
| `opinion` | Nêu ý kiến hai mặt | ý kiến, lý do chính, ví dụ của bạn, mặt trái, kết luận | họp online |
| `story` | Kể một trải nghiệm | bối cảnh, vấn đề, bạn đã làm gì, kết quả, bài học | laptop hỏng trước buổi demo |
| `explain` | Giải thích một việc | tóm tắt một câu, bước đầu, bước sau, ví dụ đời thường, vì sao quan trọng | thanh toán online |
| `describe` | Miêu tả một nơi, một thói quen | giới thiệu, chi tiết thứ nhất, chi tiết thứ hai, điều bạn thích, tóm lại | quán cà phê |

### Dữ liệu (`talks.json`)

```json
{
  "id": "opinion", "title": "Giving your opinion", "title_vi": "Nêu ý kiến hai mặt", "goal": "...",
  "frame": [{ "hint": "Ý kiến của bạn", "say": "In my opinion, ...", "also": ["i think", "i believe"] }],
  "practice": [{ "id": "overtime", "text": "Should developers work overtime ...?", "hint": "..." }],
  "lesson": { "intro": "...", "intro_vi": "...", "outro": "...", "outro_vi": "...",
              "vocab": [{ "word": "downside", "vi": "mặt trái" }],
              "sentences": [{ "say": "...", "use": "...", "use_vi": "..." }] }
}
```

- `frame[i].say` là khung câu tiếng Anh có `...`. `also` là các cách nói khác của cùng bước, viết thường; nói một trong số đó cũng tính là đã nói bước này.
- `lesson` có cùng dạng với bài giảng của bài trong `units.json`, thêm `outro`/`outro_vi` riêng (mời sang phần luyện nói 2 phút thay vì đóng vai). Câu mẫu không có trường `phrase` vì bài giảng này không có phần đóng vai.
- `validate()` chạy lúc nạp: thiếu trường, khung câu không có `...`, chữ tiếng Việt trong phần đọc to hoặc trong đề luyện đều làm server không khởi động.

### Luồng

1. Trang `/check` có mục **"Học cách nói 2 phút"** với 4 thẻ bài giảng. Kết quả bài kiểm tra cũng gợi ý bài giảng của đúng dạng đề vừa làm.
2. `/talk/<id>`: trang bài giảng như của bài (giáo viên giảng, người học đọc theo, so từng từ), có thêm khung "Dàn ý 2 phút" ở phần tổng quan. Ô thứ hai là "Luyện nói 2 phút", mở khi học xong bài giảng. Lượt đọc lưu vào `lesson_reads` và việc học xong lưu vào `lessons` với `unit_id = "talk:<id>"`.
3. `/talk/<id>/practice`: một đề luyện (ưu tiên đề chưa làm, `nextPrompt()`), dàn ý hiện trên màn hình. Sau khi nói: bước dàn ý nào đã nói (✓), số đo như bài kiểm tra so với lần luyện trước, các chỗ bí, chữ máy nghe được, và bảng các lần luyện.

Phần này **không dùng LLM**: lời giảng viết sẵn, chấm đọc bằng so từng từ, luyện nói chỉ có số đo khách quan.

## B. Học sau bài kiểm tra

### Chỗ bí (`stuck_points()`)

Mỗi khoảng nghỉ trên 0,7 giây **giữa câu** (đúng các khoảng được đếm là ngập ngừng) thành một chỗ bí: `before` là tối đa 8 từ trước chỗ nghỉ, chỉ tính từ đầu câu đang nói; `after` là tối đa 5 từ sau đó; `pause_s` là độ dài khoảng nghỉ. Danh sách lưu vào cột `stuck` của `checks` và hiện ngay trong kết quả bài kiểm tra.

### AI viết lại (`check_review.py`)

Bấm **"Học từ bài nói này"** thì Qwen nhận câu hỏi, chữ máy nghe được và các chỗ bí, trả JSON (structured output):

- `sentences`: cả bài nói viết lại bằng tiếng Anh tự nhiên, **mỗi câu kèm `from`**, là đoạn người học đã nói mà câu đó dựa vào. App ghép các câu thành `better`.
- `stuck`: với mỗi chỗ bí, câu hoàn chỉnh mà người học có thể đã nói.
- `phrases`: 3–6 cụm từ hoặc khung câu nên học, kèm nghĩa tiếng Việt.

Đây là gợi ý, không chấm điểm. App lọc lại trước khi lưu (`fix()`):

- **Đánh dấu ý AI tự thêm** (`unsure`). Một câu bị đánh dấu khi đoạn `from` không có trong bài nói (dưới 60% từ khớp, `QUOTE_FOUND`), hoặc câu mới giữ dưới 25% từ nội dung của đoạn đó (`MIN_SUPPORT`). Từ được so theo 4 chữ cái đầu, bỏ các từ nối và từ nhỏ (`FILLER`). Trang tô vàng các câu này và nhắc người học đừng học thuộc chúng.
  Đo ngày 14/10/2026 trên một bài nói thật về công cụ AI: trước khi có `from`, Qwen thêm câu "AI can generate code quickly, which saves a lot of time" (giữ 0% từ của đoạn gốc, bị đánh dấu), còn các câu viết lại thật giữ từ 33% trở lên. Sau khi bắt buộc `from`, Qwen không thêm ý nào trong lần chạy thử (khoảng 50 giây trên Qwen2.5-7B).
- `added_facts`: số, ngày, đơn vị thời gian có trong bản viết lại mà người học không nói (`invented_facts()`, giống NOTE).
- Gợi ý ở chỗ bí chỉ giữ khi khớp một chỗ bí thật; bỏ dấu `...` ở đầu.
- Cụm từ có chữ tiếng Việt ở phần tiếng Anh thì bỏ; khung câu luôn có một dấu cách trước `...` (`spaced()`: `On one hand,...` thành `On one hand, ...`).

Bản ôn lưu vào cột `review` của `checks`, gọi lại thì trả bản đã lưu, không hỏi AI lần nữa. Lỗi LM Studio trả 502 với lời nhắn tiếng Việt.

### Thẻ ôn

Người học chọn cụm từ và bấm "Thêm vào thẻ ôn". Mỗi cụm thành một thẻ loại `talk` (xem [review.md](review.md)) với `unit_id = "check:<prompt_id>"`; cụm đã có thẻ thì bỏ qua.

### Nói lại đề

Khối "Nói lại đề này" ghi âm và đo như bài kiểm tra, rồi so với lần kiểm tra (`first`) và hiện các chỗ còn bí. Lưu vào `talk_practice` với `source = 'check'`, `ref` = id bài kiểm tra.

## API

| Route | Việc |
|---|---|
| `GET /api/check` | Thêm `talks`: `[{id, title, title_vi, goal, finished, practiced}]` |
| `POST /api/check/{prompt_id}` | Thêm `id` (bài kiểm tra vừa lưu), `stuck`, `talk` (bài giảng của dạng đề) |
| `POST /api/check/{check_id}/review` | Bản ôn `{better, unsure, stuck, phrases, added_facts}`. 400 khi bài nói không có chữ, 502 khi lỗi AI |
| `POST /api/check/{check_id}/cards` | Thân `{phrases: [...]}`, chỉ nhận cụm có trong bản ôn. Trả `{added}` |
| `POST /api/check/{check_id}/retry` | Thân là âm thanh thô. Trả số đo, `stuck`, `first` |
| `GET /api/talks/{id}` | Bài giảng (như `/api/lessons/{unit}`), `frame`, `practice`, `finished`, `attempts` |
| `GET /api/talks/{id}/audio/{key}` | Giọng giáo viên |
| `POST /api/talks/{id}/read/{i}` | Đọc theo câu i, so từng từ |
| `POST /api/talks/{id}/finish` | Học xong bài giảng |
| `POST /api/talks/{id}/practice/{prompt_id}` | Thân là âm thanh thô. Trả số đo, `steps`, `stuck`, `previous` |

`check_id` của người khác trả 404. Mọi route cần đăng nhập.

## Kiểm thử

- `backend/tests/test_talks.py`: dữ liệu hợp lệ, `outro`, `also` của dàn ý, chỗ bí, bỏ đề đã ôn, lọc bản ôn, cả luồng API với STT và LLM giả (số của bài kiểm tra không đổi, không thêm dòng `checks`), quyền sở hữu, luyện nói.
- Đầu cuối ngày 14/10/2026 (server thử cổng 8001, `DATABASE_URL` tạm): file WAV ghép từ edge-tts với 4 khoảng lặng 1,6 giây giữa câu cho 3 chỗ bí (Whisper đặt dấu chấm ở chỗ thứ tư); bản ôn thật của Qwen như trên; trang `/check`, `/talk/opinion`, `/talk/opinion/practice` không tràn ngang ở bề rộng 375px.
