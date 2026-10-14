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
| Kiểm tra dữ liệu, chấm, nhóm câu riêng, lần đọc tốt nhất | `backend/app/assessment/drills.py` (`validate()`, `score()`, `personal_sentences()`, `focus_accuracy()`, `best_reading()`) |
| API | `backend/app/api/routes/drills.py` |
| Lưu | bảng `drills` (cột `audio`: tên file ghi âm), `add_drill()`, `list_drills()`, `list_readings()`, `set_drill_audio()` trong `backend/app/services/history.py` |
| Ghép lần đọc cũ với file ghi âm | `untranscribed()`, `match_by_time()` trong `backend/app/services/recordings.py` |
| Trang | `frontend/src/features/sounds/SoundsPage.tsx`, `frontend/src/styles/sounds.css`, `markFocus()`, `isNewBest()`, `bestTone()` trong `frontend/src/lib/drills.ts` |
| Tô từng từ (dùng chung với nói lại) | `frontend/src/components/WordDiff.tsx`, `.word-diff` / `.tok` trong `base.css` |
| Test | `backend/tests/test_drills.py`, `test_recordings.py`, `test_history.py`, `frontend/src/lib/drills.test.ts` |

## Chấm (`score()`)

- `compare()` của shadowing so câu mẫu với chữ máy nghe được (đã chuẩn hóa số, viết tắt, dấu câu), nên "thirty percent" và "30%" là như nhau, còn "60%" là sai.
- Từ trọng tâm được đánh dấu `focus` và đếm riêng: `focus_correct` / `focus_total`. Cả câu vẫn có `correct` / `total`.
- Nhận dạng **không có `initial_prompt`**, giống lượt nói lại, để gợi ý từ vựng không che lỗi phát âm.
- Lần đọc không nghe được gì (`heard` rỗng) không được lưu: đó là lỗi micro, không phải kết quả phát âm.
- **Giới hạn:** Whisper tự "sửa" từ phát âm gần đúng. Đọc sai thì gần như chắc chắn chưa rõ, nhưng đạt 100% chưa chắc là chuẩn. Trang ghi rõ điều này.

## Lần đọc tốt nhất của mỗi câu

Mỗi câu giữ **lần đọc tốt nhất**, không phải lần gần nhất, để mở lại trang vẫn thấy mình đã đọc câu đó thế nào và nghe lại được:

- `best_reading()` chọn trong mọi lần đọc câu đó (ở bất kỳ nhóm nào): đúng nhiều từ trọng tâm nhất (tỉ lệ), rồi đúng nhiều từ nhất cả câu; bằng nhau thì lấy lần mới hơn. Kết quả được chấm lại bằng từ trọng tâm của nhóm đang xem, nên nhóm "Câu bạn từng đọc sai" (từ trọng tâm là từ từng nghe sai) có thể chọn lần khác với nhóm gốc.
- `GET /api/drills` trả thêm `best` cho mỗi nhóm: id câu -> kết quả (như lúc chấm) + `created_at`, `attempts` (số lần đã đọc câu này), `audio_url`.
- Bản ghi: mỗi lần đọc lưu tên file trong `drills.audio` (khi `SAVE_AUDIO_DIR` bật), phát qua `/api/history/audio/...` như trang Tiến bộ. Lần đọc lưu trước khi có cột này được ghép một lần với file ghi âm theo thời gian (`match_by_time()`: file không có `.hyp.txt`, lưu tối đa 15 giây trước lần đọc, mỗi file dùng một lần). Trên dữ liệu thật ngày 14/10/2026: 114/114 lần đọc ghép được, lệch dưới 1 giây.
- Trang: chưa đọc lại thì hiện "Lần đọc tốt nhất của bạn" (ngày giờ, số lần đọc, tô từng từ, "Nghe lại"). Đọc xong thì hiện kết quả mới kèm "Kết quả tốt nhất mới" (hoặc "Lần đọc đầu tiên của câu này"), hay "Chưa vượt lần tốt nhất: …". Hàng số trên đầu (`.drill-dots`) cho biết từng câu: xanh khi lần tốt nhất đúng hết từ trọng tâm, cam khi còn sai, xám khi chưa đọc; bấm để sang câu đó.
- Tỉ lệ đúng của nhóm và tiêu chí giai đoạn 1 vẫn tính trên 20 lần đọc **gần nhất**, không phải lần tốt nhất: tiêu chí đo mức hiện tại, còn lần tốt nhất chỉ để xem lại.
- Vì có hai con số khác nhau, thẻ nhóm ghi rõ cả hai: **"Đạt 8/8 câu"** (câu có lần tốt nhất đúng hết từ trọng tâm, `passedCount()`) và **"Gần đây đúng 69%"** (20 lần đọc gần nhất, tính cả lần sai). Trước đây thẻ chỉ ghi "Đúng 69% từ trọng tâm" trong khi cả 8 câu đều xanh, nên người dùng tưởng tính sai. Dòng đầu trang cũng ghi "N lần đọc gần nhất (mọi nhóm, tính cả lần sai)" thay vì "N câu", vì đó là số lần đọc, không phải số câu.

## Nhóm "Câu bạn từng đọc sai" (`mine`)

`personal_sentences()` lấy mọi lần đọc có câu mẫu (bảng `shadows` của phòng tập, bảng `drills`, và bảng `lesson_reads` của bài giảng, xem [lesson.md](lesson.md)), giữ những câu mà **lần đọc gần nhất** có ít nhất một từ sai. Từ trọng tâm là những từ bị nghe sai lần đó. Đọc đúng hết thì câu tự ra khỏi nhóm. Tối đa 12 câu, mới nhất trước.

- Id của câu là 10 ký tự đầu của SHA-1 nội dung (`sentence_id()`), nên không đổi khi danh sách thay đổi.
- Trang giữ nguyên danh sách câu đang hiện cho tới khi tải lại, chỉ làm mới số liệu, để vị trí không nhảy khi một câu vừa ra khỏi nhóm.

## API

| Route | Việc |
|---|---|
| `GET /api/drills` | `{enabled, window, recent, sets}`. Mỗi nhóm kèm `attempts`, `accuracy` (% từ trọng tâm đúng trong 20 lần gần nhất của nhóm) và `best` (lần đọc tốt nhất của từng câu). `recent` là con số đó cho mọi nhóm gộp lại |
| `GET /api/drills/{set}/{id}/audio?slow=1` | MP3 câu mẫu (edge-tts, có cache). `slow=1` đọc chậm (`SLOW_RATE` = -30%) |
| `POST /api/drills/{set}/{id}` | Thân request là âm thanh thô. Trả `{target, heard, items, correct, total, accuracy, focus_correct, focus_total}` |

## Tiêu chí qua giai đoạn 1

Xem [roadmap.md](roadmap.md): tập đủ 5 nhóm, và trong **20 câu gần nhất** đọc đúng **từ 90%** từ trọng tâm (`WINDOW` trong `drills.py`).

## Thêm câu hoặc nhóm

Thêm vào `drills.json`. Mỗi từ trong `focus` phải là một từ của câu (so không phân biệt hoa thường và dấu câu); `validate()` chặn lúc khởi động và test bắt lỗi này. Id `mine` là id dành riêng. Ưu tiên lỗi đo được: chạy `stt_bench.py --show` trên bản thu âm mới để xem từ nào bị nghe sai.

## Vì sao cùng một câu lúc đạt lúc không (đo 14/10/2026)

Người dùng báo đọc chuẩn mà kết quả lúc được lúc không. Đã ghép 54 lần đọc (trang Phát âm + bài giảng) với file ghi âm trong `recordings/` và nhận dạng lại:

- **Mất đầu câu do micro mở chậm.** Mỗi lần bấm, trình duyệt mở micro mất vài trăm ms trên điện thoại, nhưng trang đã hiện "Đang ghi âm" ngay lúc bấm. Bằng chứng: 4/5 bản ghi của câu "Our customers book tickets on their phones." có tiếng nói ngay từ 0,1 giây đầu (tức đã nói trước khi thu), một bản chỉ còn "Tickets on their phones". Từ đầu câu bị cắt nên bị chấm sai dù đọc đúng. Cuối câu cũng hay bị cắt (tiếng nói kéo tới tận cuối file).
  - Sửa (`useMic`): micro **mở một lần và giữ mở** khi trang còn hiện (đóng khi ẩn trang hoặc rời trang), nên các lần sau thu ngay lập tức. Chữ "Đang ghi âm" và nút đỏ chỉ hiện khi máy **thật sự** đang thu (`onRecording`, sự kiện `start` của MediaRecorder); trước đó là "Đang mở micro…". Sau khi bấm dừng vẫn thu thêm 350 ms (`TAIL_MS`) để không mất từ cuối.
- **Bản ghi nhỏ tiếng** (đỉnh khoảng −18 đến −27 dBFS), trong khi app ghi âm của điện thoại thu to. Nguyên nhân: micro được xin với mặc định của trình duyệt (khử tiếng vọng, lọc ồn, tự chỉnh âm lượng), nên Chrome trên Android thu như cuộc gọi thoại: nhỏ, lọc ồn làm mờ âm cuối /s/ /t/, và micro kiểu cuộc gọi còn có thể làm nhỏ tiếng phát ra. Sửa: `useMic` xin micro thô (`echoCancellation`, `noiseSuppression`, `autoGainControl` đều `false`), giống app ghi âm. Không cần khử tiếng vọng vì mọi tiếng đang phát đều dừng khi bắt đầu thu.
- **Whisper không ổn định với câu phát âm "gần đúng".** Cùng một file, chỉ đổi nhẹ cách xử lý (thêm 0,5 giây im lặng, tắt VAD) là kết quả đổi: có câu từ 71% lên 100%, có câu từ 100% xuống 71%. Trung bình gần như không đổi (79,2% hiện tại; 79,6% khi tắt VAD và thêm im lặng; 80,6% khi giữ VAD và thêm im lặng), nên **không đổi cấu hình STT**. Một lần đọc là một phép đo có nhiễu: tiêu chí giai đoạn dùng trung bình 20 câu gần nhất là vì vậy. Từ bị nghe sai lặp lại qua nhiều lần đọc mới đáng tin là lỗi phát âm.

## Nghe lại

Kết quả vừa đọc có nút "Nghe lại" phát bản ghi giữ trong trình duyệt. Lần đọc tốt nhất phát file lưu trên server (`audio_url`), nên nghe được cả sau khi tải lại trang.
