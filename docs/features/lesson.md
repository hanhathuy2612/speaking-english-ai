# Bài giảng trước khi đóng vai

Ý tưởng lấy từ app Easy Speak. Mỗi bài có hai phần, đi theo thứ tự:

1. **Bài học (bài giảng):** giáo viên giới thiệu bài và từ vựng, rồi giảng từng câu cần học: câu đó dùng để làm gì, kèm câu đầy đủ in đậm. Sau đó giáo viên bảo người học đọc to câu đó, và app so từng từ.
2. **Đóng vai:** phần hỏi đáp như trước (phòng tập). Các câu hỏi đã nhắm sẵn vào mẫu câu vừa học, nên người học dùng lại ngay.

Bài giảng nói 2 phút theo dạng đề kiểm tra (`/talk/<id>`) dùng lại đúng trang và phần lời giáo viên này, xem [talk-lessons.md](talk-lessons.md).

Cả 24 bài trong `units.json` đều có bài giảng (từ ngày 14/10/2026; trước đó chỉ 3 bài của chủ đề "Giới thiệu bản thân"). Mỗi bài dạy 4–6 câu, mỗi câu một mẫu câu, theo cùng khung: lời mở đầu nêu các câu sẽ học, 4 từ vựng, mỗi câu kèm lời giải thích dùng khi nào. Câu đọc theo ngắn, phần lớn dưới 16 từ, để đọc được một hơi, ví dụ hợp với lập trình viên Java/backend. `test_every_unit_has_a_lesson` giữ điều này cho nội dung đi kèm mã nguồn. Bài admin tạo trên web có thể không có `lesson` và vẫn chạy như cũ.

## Nguyên tắc

- **App dẫn bài giảng, không phải LLM.** Thứ tự câu, lúc nào sang câu sau, lúc nào xong bài đều do app quyết định. Lời giảng viết sẵn trong `units.json` và đã được duyệt, nên không bị Qwen 7B nói sai hay lẫn tiếng Trung, và giọng đọc lấy từ cache.
- **Không chấm bằng LLM.** Đọc đúng hay chưa chỉ dựa trên so từng từ (`utils/compare.py`, giống [shadowing.md](shadowing.md)).
- **Giáo viên là một vai riêng**, khác người phỏng vấn: giọng khác (`TTS_TEACHER_VOICE`) và chỉ xuất hiện trong bài giảng. Giáo viên được đọc câu mẫu ngôi thứ nhất để người học nghe rồi đọc theo. Đây là ngoại lệ có chủ đích của quy tắc "không đọc câu mẫu thành tiếng", và chỉ áp dụng trong bài giảng. Ở phần đóng vai, người phỏng vấn vẫn không bao giờ nói thay người học.
- Giáo viên luôn nói tiếng Anh. Bản dịch tiếng Việt chỉ hiện chữ, khi người học bấm nút "Dịch".

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Nội dung | trường `lesson` của bài trong `backend/app/data/units.json`, hoặc soạn trên web ở phần "Bài giảng" của form sửa bài ([content-admin.md](content-admin.md)) |
| Câu cố định của giáo viên, ghép các câu nói, kiểm tra dữ liệu | `backend/app/interview/lesson.py` (`TEACHER`, `lines()`, `validate()`, `public()`) |
| API | `backend/app/api/routes/lessons.py` |
| Trạng thái "xong bài" | `_stats()` trong `backend/app/api/routes/units.py` |
| Lưu | bảng `lesson_reads`, `lessons`; `add_lesson_read()`, `finish_lesson()`, `lesson_counts()` trong `backend/app/services/history.py` |
| Trang | `frontend/src/features/lesson/LessonPage.tsx`, `frontend/src/styles/lesson.css` |
| Phát giọng giáo viên | `frontend/src/hooks/useTeacherVoice.ts` |
| Ngưỡng đạt, số lần thử | `frontend/src/lib/lesson.ts` (+ `lesson.test.ts`) |
| Liên kết bài | `unitLink()` trong `frontend/src/lib/roadmap.ts` |
| Test | `backend/tests/test_lesson.py`, `test_lesson_reads_...` trong `backend/tests/test_history.py` |

## Dữ liệu (`lesson` trong `units.json`)

```json
"lesson": {
  "intro": "Hi! I'm your English coach. Today we'll learn six sentences ... Are you ready?",
  "intro_vi": "Chào bạn! ...",
  "vocab": [{ "word": "current role", "vi": "vị trí hiện tại" }],
  "sentences": [
    { "phrase": 0,
      "say": "I've been working as a backend developer for five years.",
      "use": "Let's start with who you are today. This sentence gives your job and your experience in one line.",
      "use_vi": "Bắt đầu bằng việc bạn là ai hiện nay. ..." }
  ]
}
```

- `sentences[i].phrase`: chỉ số mẫu câu trong `phrases` mà câu này dạy. Test kiểm tra: đọc nguyên câu `say` thì được tính là đã dùng mẫu câu đó, và mỗi mẫu câu được dạy đúng một lần. Nhờ vậy, dùng lại câu vừa học ở phần đóng vai thì được đánh ✓ ở cột "Mẫu câu cần dùng".
- `say` là câu đầy đủ, không có `...`. Ví dụ hợp với một lập trình viên Java/backend.
- Không dùng từ của ví dụ mẫu trong prompt (`EXAMPLE_WORDS`), giống phần còn lại của bài.
- `validate()` chạy lúc nạp `units.json` và mỗi lần admin lưu bài (cùng `interview/units.py`). Lời giáo viên (`intro`, `use`), câu đọc theo (`say`) và từ (`word`) phải là tiếng Anh vì được đọc to; `intro_vi`, `use_vi`, `vi` là tiếng Việt.

## Các câu giáo viên nói

`lines(unit)` trả về mọi câu giáo viên có thể nói, theo khóa:

| Khóa | Nội dung |
|---|---|
| `intro` | Lời mở đầu của bài |
| `vocab` | "First, here are the key words for today." (kèm thẻ từ vựng) |
| `s<i>` | `use` + `say` của câu i (chữ hiện `use` thường và `say` in đậm) |
| `read` | "Could you please read that sentence aloud?" |
| `good` / `retry` / `move_on` | Nhận xét sau khi đọc |
| `say<i>` | Chỉ câu i, phát lại trước khi người học đọc lại |
| `w<i>` | Từ vựng i |
| `outro` | Kết bài, mời sang phần đóng vai (dùng `lesson.outro` / `outro_vi` nếu bài có, như bài giảng nói 2 phút) |

API chỉ đọc các khóa này, nên không có chữ tùy ý nào đi vào TTS hay cache.

## Luồng trang `/lesson/:unitId`

1. **Tổng quan:** tên bài, mục tiêu, số từ và số câu, hai ô "Bài học" và "Đóng vai", danh sách từ vựng và câu cần học (bấm loa để nghe). Lần đầu, ô "Đóng vai" bị khóa với chữ "Học xong bài giảng để mở". Phòng tập vẫn mở được bài qua ô chọn bài, giống khóa mềm của lộ trình.
2. Bấm "Bài học": giáo viên nói `intro`, người học bấm "Sẵn sàng".
3. Giáo viên nói `vocab` (thẻ từ vựng nằm trong tin nhắn, bấm từ để nghe), rồi tới câu 0: `s0`, `read`.
4. Người học bấm micro, đọc, bấm lần nữa để gửi (bấm-bấm, hợp với điện thoại hơn giữ-để-nói; trên máy tính vẫn giữ được phím Space). App so từng từ và hiện kết quả trong tin nhắn của người học, có nút "Nghe lại".
5. `afterReading()`: đúng từ 80% số từ (`PASS_ACCURACY`) thì `good` và sang câu sau. Chưa đạt lần đầu thì `retry`, phát lại `say<i>` và chờ đọc lại. Chưa đạt lần thứ 2 (`MAX_ATTEMPTS`) thì `move_on` và sang câu sau. Câu đọc sai vẫn vào nhóm "Câu bạn từng đọc sai" của trang Phát âm.
6. Hết câu: giáo viên nói `outro`, app gọi `POST .../finish`, rồi hiện nút "Bắt đầu đóng vai" (mở `/?unit=<id>`) và "Học lại bài giảng".

Mỗi tin nhắn của giáo viên có nút "Dịch" (hiện `vi` ngay dưới) và nút loa (phát lại câu đó). Đọc mà máy không nghe thấy gì thì không tính là một lần thử.

**Phát âm thanh trên điện thoại:** `useTeacherVoice` dùng **một** thẻ `<audio>` cho mọi câu. Lần phát đầu nằm trong cú bấm "Bài học", nên trình duyệt điện thoại (nhất là Safari trên iOS) cho phép phát tiếp các câu sau, kể cả những câu bắt đầu sau khi chờ server chấm.

## API

```
GET  /api/lessons/{unit}            -> {id, title, goal, partner, vocab, sentences, lines, finished}
GET  /api/lessons/{unit}/audio/{key} -> MP3 giọng giáo viên (cache)
POST /api/lessons/{unit}/read/{i}   (thân: bản ghi webm) -> {target, heard, compare}
POST /api/lessons/{unit}/finish     -> {finished}
```

- Bài không có `lesson`, khóa hay chỉ số không tồn tại thì trả 404.
- `read`: nhận dạng **không có `initial_prompt`**, giống phần nói lại câu mẫu, để gợi ý từ vựng không che lỗi phát âm. Lượt đọc có chữ được lưu vào `lesson_reads`.

## Hoàn thành bài và lộ trình

`GET /api/units` thêm cho mỗi bài: `lesson` (có bài giảng không), `lesson_done` (số lần học xong bài giảng) và `done`.

- Bài có bài giảng chỉ `done` khi **cả hai phần** đã xong: học xong bài giảng ít nhất một lần, và có một buổi đóng vai hỏi hết câu chính. Bài không có bài giảng thì `done` = `completed > 0` như trước.
- `next_unit`, tiêu chí "hoàn thành mọi bài" của giai đoạn, dấu ✓ ở ô chọn bài và chip trạng thái trên Lộ trình đều dùng `done`.
- Trên Lộ trình, nút của bài có bài giảng mở `/lesson/<id>` (`unitLink()`), và thẻ bài ghi "Bài giảng + N câu hỏi".
- Phòng tập: thanh trên có nút "Bài giảng" khi bài có bài giảng. Nếu chưa học bài giảng lần nào thì đầu khung hội thoại có thẻ nhắc "Học bài giảng".

## Thêm bài giảng cho một bài

1. Thêm `lesson` vào bài trong `units.json`. Mỗi mẫu câu trong `phrases` cần đúng một câu trong `sentences`.
2. `python -m pytest` (`test_lesson.py` bắt câu không chứa mẫu câu, mẫu câu bị thiếu, từ của ví dụ mẫu).
3. Mở `/lesson/<id>` và nghe thử: lời giảng phải tự nhiên khi đọc to, câu `say` không quá dài để đọc một hơi.
