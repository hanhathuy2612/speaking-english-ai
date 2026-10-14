# Bài kiểm tra nói

Mục đích: trả lời câu hỏi "mình đã nói được chưa" bằng số đo, không bằng cảm giác. Người học nói liền 2 phút về một đề quen thuộc nhưng **chưa chuẩn bị**, app đo và so với mức mục tiêu. Lần đầu là bài đầu vào; làm lại sau mỗi chủ đề của lộ trình để xem tiến bộ.

**Không dùng LLM để chấm.** Chỉ có Whisper (nhận dạng) và các phép đo khách quan, đúng quy tắc "không chấm điểm bằng LLM". Sau khi đã chấm, người học có thể nhờ AI viết lại bài nói để học (không đổi kết quả), xem [talk-lessons.md](talk-lessons.md).

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Đề bài | `backend/app/data/check_prompts.json`: 20 đề, 5 đề cho mỗi dạng (`id`, `kind`: `opinion`/`story`/`explain`/`describe`, `text` tiếng Anh, `hint` tiếng Việt) |
| Chọn đề, so mục tiêu, chỗ bí | `backend/app/assessment/check.py` (`pick_prompt()`, `evaluate()`, `stuck_points()`, các hằng `TARGET_*`) |
| Đo (dùng chung với bài 4–3–2) | `measure()`, `pick_least_used()`, `MIN_MEASURED_SECONDS` trong `backend/app/assessment/metrics.py` |
| Đếm ngập ngừng giữa câu | `hesitation_points()`, `hesitation_pauses()` trong `backend/app/utils/parsing.py` |
| API | `backend/app/api/routes/check.py` |
| Lưu kết quả | bảng `checks`, `add_check()`, `list_checks()` trong `backend/app/services/history.py` |
| Trang | `frontend/src/features/check/CheckPage.tsx`, `frontend/src/styles/check.css`, hàm thuần `frontend/src/lib/check.ts`; khối ghi âm `frontend/src/components/Recorder.tsx` |
| Ô trên trang Lộ trình | `CheckCard` trong `frontend/src/features/roadmap/RoadmapPage.tsx` |
| Test | `backend/tests/test_check.py`, `frontend/src/lib/check.test.ts` |

## Tiêu chí (`evaluate()`)

| Tiêu chí | Đạt khi | Ghi chú |
|---|---|---|
| Nói liền 2 phút | từ đầu tiên tới từ cuối cùng ≥ 120 giây | `TARGET_SECONDS` |
| Tốc độ khi nói | `wpm_speaking` ≥ 110 từ/phút | Đã trừ các khoảng nghỉ dài, như ở phòng tập |
| Ngập ngừng giữa câu | dưới 3 lần / 100 từ | `TARGET_HESITATIONS_PER_100` |
| Nói hoàn toàn bằng tiếng Anh | không bị chặn `not_english` (xem [speech-recognition.md](speech-recognition.md)) và có ít nhất 1 từ | |

- **Chỉ chấm tốc độ và ngập ngừng khi đo được** (`measurable`): phải có ít nhất 30 giây tiếng Anh (`MIN_MEASURED_SECONDS`). Một câu tiếng Việt 4 giây từng "đạt" cả hai tiêu chí này. Khi không đo được, hai tiêu chí tính là chưa đạt, trang hiện lời nhắc, và DB lưu `NULL` cho hai số đó để đường xu hướng không bị lệch.
- **Ngập ngừng giữa câu**, không phải mọi khoảng nghỉ dài: khoảng nghỉ trên 0,7 giây sau từ kết thúc bằng `.`, `?`, `!` là nghỉ cuối câu tự nhiên. Đo ngày 11/10/2026: edge-tts đọc 217 từ có 11 khoảng nghỉ dài (5,1/100 từ) nhưng **0** ở giữa câu; trên bản ghi thật của người dùng, cách đếm này chỉ bắt chỗ ngập ngừng thật ("for" … 2,05 giây, "when" … 3,3 giây).
- Các mức mục tiêu là **mức đích** (giai đoạn 4 của lộ trình). Giai đoạn 2 và 3 dùng mức thấp hơn, đặt từ số đo đầu vào của người dùng (xem [roadmap.md](roadmap.md)). Kết quả bài kiểm tra quyết định việc qua giai đoạn 2, 3, 4.

## Chọn đề

`pick_prompt()` lấy ngẫu nhiên trong các đề **ít được làm nhất** (đếm từ bảng `checks`), bỏ đề đang hiện khi bấm "Đổi đề" và bỏ các **đề đã ôn** (đã xem bản ôn của AI hoặc đã nói lại sau bài kiểm tra, `studied_check_prompts()`). Chỉ khi mọi đề đều đã ôn thì mới chọn lại trong tất cả. Mục đích: mỗi lần kiểm tra là một đề chưa luyện trước.

## API

| Route | Việc |
|---|---|
| `GET /api/check?exclude=<id>` | `{enabled, prompt, targets, checks, talks}`: một đề mới, mục tiêu, các lần kiểm tra cũ (cũ trước mới sau, mỗi lần kèm `review` nếu đã ôn), các bài giảng nói 2 phút |
| `POST /api/check/{prompt_id}` | Thân request là âm thanh thô (webm từ MediaRecorder, mp3 cũng được). Trả `{id, prompt, text, words, duration_s, wpm, wpm_speaking, hesitations, hesitations_per_100, not_english, measurable, criteria, passed, stuck, talk}` |
| `POST /api/check/{id}/review`, `/cards`, `/retry` | Học sau bài kiểm tra, xem [talk-lessons.md](talk-lessons.md) |

Âm thanh gửi dạng byte thô như trang đo STT, nên không cần `python-multipart`. Nhận dạng dùng `STT_VOCAB` (tên người dùng), không dùng từ vựng bài.

## Trang `/check`

- Bấm nút micro để bắt đầu, bấm lần nữa để dừng (`useMic` gọi `start()`/`stop()`, tắt phím Space). Mọi trang khác cũng bấm-bấm như vậy.
- Đồng hồ và thanh tiến độ tới 2:00 (chuyển xanh khi đạt), tự dừng ở 2:30.
- Kết quả: từng tiêu chí có dấu ✓/✗ kèm chữ (không chỉ dựa vào màu), giá trị đo, chữ máy nghe được.
- Kết quả còn có danh sách **chỗ bạn ngập ngừng giữa câu** (vài từ trước và sau mỗi khoảng nghỉ, kèm số giây) và gợi ý bài giảng của đúng dạng đề.
- Dưới kết quả là khối "Học từ bài nói này" và "Nói lại đề này"; cuối trang có mục "Học cách nói 2 phút" (xem [talk-lessons.md](talk-lessons.md)).
- Bảng các lần kiểm tra và dòng xu hướng "so với lần đầu" (`latestWithDelta(..., "lần đầu")`).

## Kiểm thử đầu cuối

Không mở được micro trong trình duyệt tự động, nên thay `getUserMedia` và `MediaRecorder` bằng bản giả trả về một file mp3 (edge-tts) rồi bấm nút thật trên trang. Cũng có thể gửi thẳng: `POST /api/check/working-day` với file mp3 làm thân request. Server thử phải dùng `HISTORY_DB` tạm (xem [dev-environment.md](../dev-environment.md)).

## Nghe lại

Kết quả có nút "Nghe lại" để nghe chính bản ghi vừa gửi. Bản ghi chỉ giữ trong trình duyệt tới khi rời trang, không lưu trên server (xem [frontend.md](frontend.md)).
