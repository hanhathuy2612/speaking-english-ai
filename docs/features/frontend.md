# Giao diện (`frontend/`)

React 19 + TypeScript + Vite, định tuyến bằng React Router 7. Không có thư viện UI hay state manager: style là CSS thuần dùng chung token (`src/styles/`), trạng thái phòng tập là một `useReducer`. Không tải tài nguyên ngoài lúc chạy (font hệ thống, icon SVG viết trong code), nên app chạy offline.

## Lệnh (trong `frontend/`, cần Node 22.12+)

| Lệnh | Việc |
|---|---|
| `npm install` | Cài dependency (lần đầu, hoặc khi `package.json` đổi) |
| `npm run dev` | Dev server ở http://localhost:5173, tự nạp lại khi sửa code. Chuyển `/api` và `/ws` sang backend (mặc định cổng 8000, đổi bằng biến `BACKEND_URL`) |
| `npm run build` | Kiểm tra kiểu (`tsc -b`) rồi build vào `frontend/dist/`. Backend phục vụ thư mục này |
| `npm run typecheck` | Chỉ kiểm tra kiểu |
| `npm test` | Vitest (hàm thuần trong `src/lib/`) |

Backend phục vụ bản build: `/`, `/roadmap`, `/history`, `/bench` đều trả `dist/index.html`, React Router chọn trang; JS/CSS nằm dưới `/assets`. Chưa build thì các trang này trả hướng dẫn build (HTTP 503). Xem `backend/app/main.py`.

## Cấu trúc `src/`

```
main.tsx                    # gắn React Router: / , /roadmap , /check , /history , /bench
api/types.ts                # kiểu dữ liệu của API và giao thức WebSocket
lib/format.ts               # hàm thuần: fmtDate, fmtNum, niceMax, latestWithDelta (+ format.test.ts)
lib/roadmap.ts              # hàm thuần: allUnits, pickUnit, unitState (+ roadmap.test.ts)
lib/check.ts                # hàm thuần: fmtClock, criterionValue (+ check.test.ts)
components/                 # dùng chung: AppBar (thanh trên + điều hướng), Icons, ui (Chip, StatusLine)
hooks/
  useHoldToTalk.ts          # ghi âm giữ để nói (MediaRecorder webm/opus) + giữ phím Space; trang /check gọi start()/stop() để bấm-bấm
  useAudioQueue.ts          # hàng đợi phát MP3, báo khi một câu bắt đầu phát
features/
  practice/                 # phòng tập
    useInterview.ts         # WebSocket + reducer trạng thái + hành động (gửi chữ, ghi âm, hoàn tác, nói lại)
    PracticePage.tsx        # bố cục trang, nối hook ghi âm với useInterview
    Sidebar.tsx, Chat.tsx, CoachCard.tsx (thẻ NOTE + kết quả nói lại)
  roadmap/                  # RoadmapPage.tsx (xem roadmap.md)
  check/                    # CheckPage.tsx (xem speaking-check.md)
  history/                  # HistoryPage.tsx, LineChart.tsx (biểu đồ SVG)
  bench/                    # BenchPage.tsx
styles/                     # base.css (token, component chung, bảng), practice.css, roadmap.css, check.css, history.css, bench.css
```

## Luồng dữ liệu phòng tập (`useInterview.ts`)

- Bài mở đầu: `?unit=` trên URL, nếu không có thì bài tiếp theo của lộ trình (`pickUnit`, xem roadmap.md).
- Một WebSocket cho mỗi lần mở trang. Tin JSON từ server đi vào reducer (`onServer`), trạng thái là `InterviewState`.
- Tin `sentence` không vào reducer: nó được ghép với khung nhị phân MP3 ngay sau đó và đẩy vào `useAudioQueue`. Khi câu **bắt đầu phát**, hook gửi action `aiSentence` để thêm chữ vào tin nhắn AI của lượt đó (chữ đi theo giọng).
- `turnRef` đếm lượt **đồng bộ theo từng tin nhắn**, vì khung âm thanh của một lượt có thể tới trước khi React render lại. Tin `started` đặt lại bộ đếm.
- Hoàn tác (`undone`) gỡ cả tin nhắn của người học và của AI có cùng `lastMeTurn`, cùng thẻ tổng kết nếu có.
- Nói lại: `beginShadow` bật `shadow.waiting`; khi có bản ghi, `sendRecording` gửi `{"type":"shadow"}` ngay trước khung âm thanh. Gõ chữ luôn là câu trả lời phỏng vấn (tắt chế độ nói lại).

## Hệ thiết kế (`src/styles/base.css`)

- **Màu:** chỉ dùng token, không viết mã màu trực tiếp. Nền `--bg`, bề mặt `--surface`/`--surface-2`, viền `--border`/`--border-strong`, chữ `--text`/`--text-2`/`--text-3`, màu nhấn `--primary` (+ `-hover`, `-soft`, `--on-primary`), trạng thái `--success`/`--warning`/`--danger` (+ `-soft`), biểu đồ `--chart-line`/`--chart-grid`.
- **Chế độ tối:** định nghĩa lại cùng token trong `@media (prefers-color-scheme: dark)`. Thêm token mới phải khai báo ở cả hai chế độ. Màu biểu đồ phải qua `validate_palette.js` (skill dataviz) ở cả hai chế độ.
- **Component CSS:**
  - `.btn` (biến thể `.btn-primary`, `.btn-ghost`, `.btn-sm`).
  - `.chip` (biến thể `.chip-success`, `.chip-warning`).
  - `.status[data-state]` với `ready` | `busy` | `recording` | `warn` | `error`.
  - `.mic` / `.mic.rec`, `.card`, `.appbar`, `.nav`.
  - Bảng: `.table-card`, `.table-wrap`, `table`, `.num` (dùng ở trang Tiến bộ và Kiểm tra).
- CSS của mỗi trang được import trong component trang, nhưng Vite gộp tất cả thành một file. Vì vậy **tên class là toàn cục**: không đặt trùng tên class giữa các trang với ý nghĩa khác nhau.
- Giảm chuyển động khi người dùng bật `prefers-reduced-motion`.

## Bố cục phòng tập

- **Thanh trên:** logo, chọn bài, tiến độ, nhãn cấu hình STT (ẩn khi màn hình hẹp hơn 1180px), điều hướng (`NavLink` tự gắn `aria-current="page"`).
- **Cột trái:** mục tiêu, mẫu câu kèm bộ đếm, "Chỉ số kỹ thuật" thu gọn.
- **Giữa:** hội thoại (`.msg.ai` / `.msg.me`, chip chỉ số nói, `.unclear`; thẻ tổng kết ở cuối) và thanh dưới (`.dock`): thẻ NOTE (`.coach`, thêm `.shadowing` khi chờ đọc lại, `.has-result` khi có kết quả) và khung trả lời (`.composer`).
- **Màn hình hẹp** (từ 960px trở xuống): một cột, thanh dưới dính đáy. Từ 560px trở xuống: ẩn tên app, nút hoàn tác xuống dòng, ẩn chú giải của kết quả nói lại.

## Quy ước

- TypeScript `strict`. Kiểu dữ liệu từ server khai báo trong `api/types.ts`; sửa giao thức thì sửa cả file này và `docs/architecture.md`.
- Component là function component + hooks. Logic không phụ thuộc giao diện để trong `lib/` và có test Vitest.
- Mọi chữ hiện cho người dùng bằng tiếng Việt, trừ lời AI và câu mẫu. Code, comment, tên biến bằng tiếng Anh.
- Không dùng `dangerouslySetInnerHTML`. Dữ liệu từ server luôn render qua JSX (React tự escape).
- Nút chỉ có icon phải có `aria-label`. Vùng nội dung thay đổi dùng `aria-live` hoặc `role="status"`.
- Thêm dependency phải ghim phiên bản cụ thể và `npm audit` không còn lỗ hổng.
- Sửa giao diện thì kiểm tra cả chế độ sáng, tối, màn hình 375px, trang không cuộn ngang, và `npm run build` không lỗi.
