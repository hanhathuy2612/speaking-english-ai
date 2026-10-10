# Giao diện (`frontend/`)

HTML/CSS/JS thuần, không build, không framework, không tải tài nguyên ngoài (font hệ thống, icon SVG viết thẳng trong HTML).
Server phục vụ `/` và `/bench`; file tĩnh nằm dưới `/static/` (xem `backend/app/main.py`).

## File

| File | Vai trò |
|---|---|
| `index.html` | Phòng tập |
| `history.html` | Trang Tiến bộ (xem [session-history.md](session-history.md)) |
| `bench.html` | Trang đọc theo câu mẫu (xem [stt-benchmark.md](stt-benchmark.md)) |
| `css/base.css` | Design token (màu, bo góc, bóng, font), chế độ tối, reset và component dùng chung: `.appbar`, `.brand`, `.card`, `.btn`, `.chip`, `.status`, `.mic`, `.eyebrow` |
| `css/app.css`, `css/history.css`, `css/bench.css` | Bố cục và component riêng từng trang |
| `js/app.js` | Toàn bộ logic phòng tập |
| `js/history.js` | Ô số liệu, biểu đồ đường SVG (đường dóng + chú thích nổi), bảng các buổi tập |
| `js/bench.js` | Thu âm và lưu từng câu mẫu |

## Hệ thiết kế (`css/base.css`)

- **Màu:** chỉ dùng biến token, không viết mã màu trực tiếp trong CSS trang. Nền `--bg`, bề mặt `--surface`/`--surface-2`, viền `--border`/`--border-strong`, chữ `--text`/`--text-2`/`--text-3`, màu nhấn `--primary` (+ `-hover`, `-soft`, `--on-primary`), trạng thái `--success`/`--warning`/`--danger` (+ `-soft`).
- **Chế độ tối:** định nghĩa lại cùng các token trong `@media (prefers-color-scheme: dark)`. Thêm token mới thì phải khai báo ở cả hai chế độ.
- **Biểu đồ:** `--chart-line`, `--chart-grid`. Màu biểu đồ phải qua `validate_palette.js` (skill dataviz) ở cả hai chế độ.
- **Component:**
  - `.btn` (biến thể `.btn-ghost`, `.btn-sm`).
  - `.chip` (biến thể `.chip-success`, `.chip-warning`).
  - `.status` với `data-state` = `ready` | `busy` | `recording` | `warn` | `error`, quyết định màu chấm trạng thái.
  - `.mic`: nút micro tròn, có class `.rec` khi đang ghi âm.
- Giảm chuyển động khi người dùng bật `prefers-reduced-motion`.

## Bố cục `index.html`

- **Thanh trên (`.appbar`):** logo, chọn bài (`#unit`), tiến độ (`#progress` + thanh `#progressFill`), nhãn cấu hình STT (`#sttLabel`, ẩn khi màn hình hẹp hơn 1180px), thanh điều hướng `.nav` (Phòng tập, Tiến bộ, Đo nhận dạng; trang hiện tại có `aria-current="page"`). Cả ba trang dùng chung `.nav`.
- **Cột trái (`.sidebar`):** thẻ mục tiêu (`#goal`), thẻ mẫu câu (`#phrases`, bộ đếm `#phraseCount`), mục thu gọn "Chỉ số kỹ thuật" (`#timing`, `#conf`).
- **Giữa (`.stage`):**
  - Hội thoại (`#chat`): mỗi lượt là một `.msg.ai` hoặc `.msg.me`, gồm avatar, `.who`, `.bubble`, `.meta` (các chip chỉ số nói). Lượt "nghe chưa rõ" có thêm class `.unclear`. Khi hết phiên, thẻ tổng kết `.summary` được thêm vào cuối hội thoại.
  - Thanh dưới (`.dock`): thẻ NOTE (`#coach`, ẩn bằng thuộc tính `hidden`) và khung trả lời (`.composer`), gồm nút micro `#talk`, ô gõ chữ `#typed`, nút hoàn tác `#undo`, trạng thái `#status`.
- **Màn hình hẹp (từ 960px trở xuống):** một cột, trang cuộn bình thường, thanh dưới dính đáy màn hình, cột trái xuống sau hội thoại. Từ 560px trở xuống: ẩn tên ứng dụng, nút hoàn tác xuống dòng dưới ô gõ chữ.

## Hàm chính trong `js/app.js`

| Hàm | Việc |
|---|---|
| `init()`, `loadUnits()`, `startUnit()` | Kết nối WebSocket, tải danh sách bài, bắt đầu bài |
| `onMessage()` | Xử lý mọi tin từ server (xem giao thức trong [architecture.md](../architecture.md)) |
| `setStatus(text, state)` | Dòng trạng thái kèm chấm màu |
| `renderUnit()`, `markUsed()`, `renderProgress()` | Mục tiêu, danh sách mẫu câu kèm bộ đếm, thanh tiến độ |
| `addMessage()`, `speechChips()`, `chip()` | Một tin nhắn trong hội thoại và các chip chỉ số nói |
| `renderCoach()`, `renderSummary()` | Thẻ NOTE và thẻ tổng kết |
| `enqueue()`, `playNext()`, `appendAi()`, `stopPlayback()` | Hàng đợi phát MP3 (xem [tts-audio.md](tts-audio.md)) |
| `startRec()`, `stopRec()` | Ghi âm giữ để nói bằng MediaRecorder (webm/opus). File dưới 3000 byte bị bỏ. |

Giữ nút micro **hoặc phím Space** để nói. Space không có tác dụng khi đang gõ trong ô nhập hay ô chọn.

## Trạng thái `st` trong `js/app.js`

`turn` (đếm lượt), `lines` (tin nhắn AI theo lượt), `lastMe` (tin nhắn gần nhất của người học, dùng cho hoàn tác), `queue`/`playing`/`audio` (phát âm thanh), `pending` (metadata câu đang chờ khung MP3).

## Quy ước

- Mọi chữ hiện cho người dùng bằng tiếng Việt, trừ lời AI và câu mẫu.
- Không dùng `innerHTML` cho dữ liệu từ server. Chỉ dùng `textContent` (`innerHTML` chỉ dành cho khung HTML tĩnh viết sẵn trong code).
- Nút chỉ có icon phải có `aria-label`. Vùng nội dung thay đổi dùng `aria-live` hoặc `role="status"`.
- Đường dẫn trong HTML là tuyệt đối từ gốc server (`/static/css/...`).
- Ẩn/hiện bằng thuộc tính `hidden`, không dùng class riêng.
- Sửa giao diện thì kiểm tra cả chế độ sáng, tối và màn hình 375px, và trang không được cuộn ngang.
