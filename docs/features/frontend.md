# Giao diện (`frontend/`)

HTML/CSS/JS thuần, không build, không framework. Server phục vụ `/` và `/bench`; file tĩnh nằm dưới `/static/` (xem `backend/app/main.py`).

## File

| File | Vai trò |
|---|---|
| `index.html` | Bố cục phòng tập |
| `bench.html` | Trang đọc theo câu mẫu (xem [stt-benchmark.md](stt-benchmark.md)) |
| `css/base.css` | Biến màu trên `:root`, chế độ tối qua `prefers-color-scheme`, reset, `body`. Dùng chung cho mọi trang |
| `css/app.css`, `css/bench.css` | Style riêng từng trang |
| `js/app.js` | Toàn bộ logic phòng tập |
| `js/bench.js` | Thu âm và lưu từng câu mẫu |

Thêm trang mới thì nạp `base.css` trước rồi mới tới CSS riêng, và chỉ dùng biến màu từ `base.css`.

## Bố cục `index.html`

- **Cột trái (`aside`):** chọn bài, mục tiêu, tiến độ (`#progress`), mẫu câu kèm dấu ✓, bảng độ trễ (`#timing`), độ tin cậy nhận dạng (`#conf`), nhãn cấu hình STT (`#sttLabel`).
- **Cột chính (`main`):** khung chat (`#chat`), tổng kết (`#summary`), NOTE (`#coach` kèm nút "Nghe câu này"), nút "Giữ để nói" (`#talk`), nút "Máy nghe sai, nói lại" (`#undo`), ô gõ chữ (`#typed`), trạng thái (`#status`).

## Hàm chính trong `js/app.js`

| Hàm | Việc |
|---|---|
| `init()`, `loadUnits()`, `startUnit()` | Kết nối WebSocket, tải danh sách bài, bắt đầu bài |
| `onMessage()` | Xử lý mọi tin từ server (xem giao thức trong [architecture.md](../architecture.md)) |
| `renderUnit()`, `markUsed()` | Vẽ mục tiêu, danh sách mẫu câu, dấu ✓ |
| `addLine()` | Thêm một dòng chat kèm chỉ số nói |
| `renderCoach()`, `renderSummary()` | NOTE và tổng kết |
| `enqueue()`, `playNext()`, `appendAi()`, `stopPlayback()` | Hàng đợi phát MP3 (xem [tts-audio.md](tts-audio.md)) |
| `startRec()`, `stopRec()` | Ghi âm giữ để nói bằng MediaRecorder (webm/opus). File dưới 3000 byte bị bỏ. |

## Trạng thái `st` trong `js/app.js`

`turn` (đếm lượt), `lines` (dòng AI theo lượt), `lastMe` (dòng người học gần nhất, dùng cho hoàn tác), `queue`/`playing`/`audio` (phát âm thanh), `pending` (metadata câu đang chờ khung MP3).

## Quy ước

- Mọi chữ hiện cho người dùng bằng tiếng Việt, trừ lời AI và câu mẫu.
- Không dùng `innerHTML` cho dữ liệu từ server. Chỉ dùng `textContent`.
- Đường dẫn trong HTML là tuyệt đối từ gốc server (`/static/css/...`), không dùng đường dẫn tương đối.
