# Nói dài 4–3–2 (trang `/fluency`)

Mục đích: giai đoạn 4 của lộ trình, nói liền vài phút mà không khựng. Kỹ thuật 4/3/2 (Paul Nation): kể **cùng một nội dung ba lần**, thời gian giảm dần 4 phút, 3 phút, 2 phút. Lần sau đã có sẵn ý và từ, nên người học buộc phải nói nhanh và liền hơn, và cách nói trôi chảy đó dần thành thói quen.

**Không dùng LLM.** Mỗi lần kể được đo như bài kiểm tra nói (`measure()` trong `assessment/metrics.py`).

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Đề | `backend/app/data/fluency_prompts.json` (khác đề của bài kiểm tra, để bài kiểm tra luôn là đề chưa luyện) |
| Thời gian từng lần, chọn đề, gộp lần thành bài | `backend/app/assessment/fluency.py` (`ROUNDS`, `pick_prompt()`, `group_runs()`) |
| Đo | `measure()`, `pick_least_used()` trong `backend/app/assessment/metrics.py` (dùng chung với bài kiểm tra) |
| API | `backend/app/api/routes/fluency.py` |
| Lưu | bảng `fluency`, `add_fluency_round()`, `list_fluency_rounds()` trong `backend/app/services/history.py` |
| Trang | `frontend/src/features/fluency/FluencyPage.tsx`, `frontend/src/styles/fluency.css`, `roundDelta()` trong `frontend/src/lib/fluency.ts` |
| Ghi âm (dùng chung với `/check`) | `frontend/src/components/Recorder.tsx`, `.recorder` / `.rec-btn` trong `base.css` |
| Test | `test_group_runs_...` trong `backend/tests/test_stages.py`, `frontend/src/lib/fluency.test.ts` |

## Luồng

1. Trang lấy một đề ít dùng nhất (`GET /api/fluency`). Chỉ đổi đề được trước lần 1.
2. Mỗi lần: bấm micro để bắt đầu, bấm lần nữa để dừng; **tự dừng khi hết giờ** của lần đó (`ROUNDS` = 240, 180, 120 giây).
3. Lần 1 gửi `POST /api/fluency/{prompt}/1`, server tạo `run` (id của bài) và trả về. Lần 2, 3 gửi kèm `?run=`. Thiếu `run` sau lần 1 thì trả 400.
4. "Làm lại lần N" gửi lại cùng số lần; `group_runs()` giữ lần mới nhất của mỗi số.
5. Sau mỗi lần: bảng thời lượng, tốc độ khi nói, ngập ngừng / 100 từ; dòng "Thay đổi" so lần cuối với lần 1 (`roundDelta()`). Một bài **làm trọn** khi có đủ 3 lần.

Như bài kiểm tra: dưới 30 giây tiếng Anh thì không tính tốc độ và ngập ngừng (`measurable`), DB lưu `NULL` cho hai số đó.

## API

| Route | Việc |
|---|---|
| `GET /api/fluency?exclude=<id>` | `{enabled, prompt, rounds, runs}`; `runs` là các bài đã làm (cũ trước), mỗi bài có `rounds` và `complete` |
| `POST /api/fluency/{prompt_id}/{round}?run=<id>` | Thân request là âm thanh thô. Trả `{run, round, limit_s, text, words, duration_s, wpm, wpm_speaking, hesitations, hesitations_per_100, not_english, measurable}` |

## Tiêu chí qua giai đoạn 4

Xem [roadmap.md](roadmap.md): làm trọn 2 bài 4–3–2, và một bài kiểm tra nói đạt mức đích (2 phút, từ 110 từ/phút, dưới 3 lần ngập ngừng / 100 từ).

## Kiểm thử đầu cuối

Như bài kiểm tra (xem [speaking-check.md](speaking-check.md)): thay `getUserMedia` / `MediaRecorder` bằng bản giả trả về mp3 edge-tts. Thử ngày 11/10/2026 với cùng một đoạn 206 từ, đọc chậm (-25%) ở lần 1 và nhanh hơn (+5%) ở lần 2, 3: tốc độ 160 → 209 → 209 từ/phút, dòng "Thay đổi" hiện +49.
