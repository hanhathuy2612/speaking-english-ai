# Luyện phát âm (trang `/sounds`)

Mục đích: giai đoạn 1 của lộ trình. Sửa đúng các lỗi phát âm **đã đo được trên giọng người dùng**, không luyện chung chung. Mỗi nhóm câu nhắm vào một lỗi, mỗi câu có vài **từ trọng tâm** mang âm đó và được chấm riêng.

**Không dùng LLM.** Chỉ có Whisper (nhận dạng, không có gợi ý từ vựng) và phép so từng từ của [shadowing.md](shadowing.md).

## Lỗi đã đo (`stt_bench.py` trên 18 câu thu âm của người dùng, 11/10/2026)

| Câu mẫu | Máy nghe được | Nhóm luyện |
|---|---|---|
| ...for our customers. | ...for our customer. | `final-s`: âm cuối -s |
| ...by thirty percent. | ...by 60%. | `th-numbers`: âm th và số đếm |
| ...add a cache... | ...add a kit... | `final-consonants`: phụ âm cuối rõ ràng |
| I wrote unit tests and integration tests... | I wrote unise text and integration text... | `clusters`: cụm phụ âm cuối |

Nhóm `final-ed` (âm cuối -ed) dựa trên lỗi mất âm -ed đã ghi ở [speech-recognition.md](speech-recognition.md). Mỗi nhóm có 8 câu theo ngữ cảnh công việc lập trình, dùng lại chính các từ đo sai (customers, thirty, cache, tests).

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Câu luyện | `backend/app/data/drills.json` (`id`, `title`, `measured`, `tip`, `sentences[].text`, `sentences[].focus`) |
| Kiểm tra dữ liệu, chấm, nhóm câu riêng | `backend/app/assessment/drills.py` (`validate()`, `score()`, `personal_sentences()`, `focus_accuracy()`) |
| API | `backend/app/api/routes/drills.py` |
| Lưu | bảng `drills`, `add_drill()`, `list_drills()`, `list_readings()` trong `backend/app/services/history.py` |
| Trang | `frontend/src/features/sounds/SoundsPage.tsx`, `frontend/src/styles/sounds.css`, `markFocus()` trong `frontend/src/lib/drills.ts` |
| Tô từng từ (dùng chung với nói lại) | `frontend/src/components/WordDiff.tsx`, `.word-diff` / `.tok` trong `base.css` |
| Test | `backend/tests/test_drills.py`, `frontend/src/lib/drills.test.ts` |

## Chấm (`score()`)

- `compare()` của shadowing so câu mẫu với chữ máy nghe được (đã chuẩn hóa số, viết tắt, dấu câu), nên "thirty percent" và "30%" là như nhau, còn "60%" là sai.
- Từ trọng tâm được đánh dấu `focus` và đếm riêng: `focus_correct` / `focus_total`. Cả câu vẫn có `correct` / `total`.
- Nhận dạng **không có `initial_prompt`**, giống lượt nói lại, để gợi ý từ vựng không che lỗi phát âm.
- Lần đọc không nghe được gì (`heard` rỗng) không được lưu: đó là lỗi micro, không phải kết quả phát âm.
- **Giới hạn:** Whisper tự "sửa" từ phát âm gần đúng. Đọc sai thì gần như chắc chắn chưa rõ, nhưng đạt 100% chưa chắc là chuẩn. Trang ghi rõ điều này.

## Nhóm "Câu bạn từng đọc sai" (`mine`)

`personal_sentences()` lấy mọi lần đọc có câu mẫu (bảng `shadows` của phòng tập và bảng `drills`), giữ những câu mà **lần đọc gần nhất** có ít nhất một từ sai. Từ trọng tâm là những từ bị nghe sai lần đó. Đọc đúng hết thì câu tự ra khỏi nhóm. Tối đa 12 câu, mới nhất trước.

- Id của câu là 10 ký tự đầu của SHA-1 nội dung (`sentence_id()`), nên không đổi khi danh sách thay đổi.
- Trang giữ nguyên danh sách câu đang hiện cho tới khi tải lại, chỉ làm mới số liệu, để vị trí không nhảy khi một câu vừa ra khỏi nhóm.

## API

| Route | Việc |
|---|---|
| `GET /api/drills` | `{enabled, window, recent, sets}`. Mỗi nhóm kèm `attempts`, `accuracy` (% từ trọng tâm đúng trong 20 lần gần nhất của nhóm). `recent` là con số đó cho mọi nhóm gộp lại |
| `GET /api/drills/{set}/{id}/audio?slow=1` | MP3 câu mẫu (edge-tts, có cache). `slow=1` đọc chậm (`SLOW_RATE` = -30%) |
| `POST /api/drills/{set}/{id}` | Thân request là âm thanh thô. Trả `{target, heard, items, correct, total, accuracy, focus_correct, focus_total}` |

## Tiêu chí qua giai đoạn 1

Xem [roadmap.md](roadmap.md): tập đủ 5 nhóm, và trong **20 câu gần nhất** đọc đúng **từ 90%** từ trọng tâm (`WINDOW` trong `drills.py`).

## Thêm câu hoặc nhóm

Thêm vào `drills.json`. Mỗi từ trong `focus` phải là một từ của câu (so không phân biệt hoa thường và dấu câu); `validate()` chặn lúc khởi động và test bắt lỗi này. Id `mine` là id dành riêng. Ưu tiên lỗi đo được: chạy `stt_bench.py --show` trên bản thu âm mới để xem từ nào bị nghe sai.

## Nghe lại

Kết quả có nút "Nghe lại" để nghe chính bản ghi vừa gửi. Bản ghi chỉ giữ trong trình duyệt tới khi rời trang, không lưu trên server (xem [frontend.md](frontend.md)).
