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

Backend phục vụ bản build: `/`, `/lesson/<id>`, `/review`, `/roadmap`, `/sounds`, `/fluency`, `/check`, `/history`, `/bench` đều trả `dist/index.html`, React Router chọn trang; JS/CSS nằm dưới `/assets`; manifest và icon PWA (từ `public/`) nằm ở gốc. Chưa build thì các trang này trả hướng dẫn build (HTTP 503). Xem `backend/app/main.py`.

## Cấu trúc `src/`

```
main.tsx                    # gắn React Router: / , /review , /roadmap , /sounds , /fluency , /check , /history , /bench; import base.css trước các trang
api/types.ts                # kiểu dữ liệu của API và giao thức WebSocket
lib/format.ts               # hàm thuần: fmtDate, fmtNum, niceMax, latestWithDelta (+ format.test.ts)
lib/roadmap.ts              # hàm thuần: allUnits, pickUnit, unitState, unitLink (+ roadmap.test.ts)
lib/lesson.ts               # hàm thuần: afterReading, sentenceKeys (+ lesson.test.ts)
lib/stages.ts               # hàm thuần: requirementText, checkLevelText (+ stages.test.ts)
lib/drills.ts               # hàm thuần: markFocus (+ drills.test.ts)
lib/fluency.ts              # hàm thuần: roundDelta (+ fluency.test.ts)
lib/review.ts               # hàm thuần: fmtDue, localDay (+ review.test.ts)
lib/replay.ts               # một trình phát dùng chung cho "Nghe lại" (playReplay, stopReplay), kiểu WithAudio<T>
lib/check.ts                # hàm thuần: fmtClock, criterionValue (+ check.test.ts)
components/                 # dùng chung: AppBar (thanh trên + điều hướng: menu khi hẹp, thanh tab dưới đáy trên điện thoại), Icons,
                            #   ui (Chip, StatusLine), WordDiff (tô từng từ so với câu mẫu), Recorder (bấm-bấm ghi âm dài, đồng hồ,
                            #   thanh thời gian), ReplayButton ("Nghe lại" giọng của chính bạn), Sheet (bảng trượt từ đáy, thẻ <dialog>),
                            #   Lead (giới thiệu trang: một dòng + "Chi tiết")
hooks/
  useMic.ts                 # ghi âm (MediaRecorder webm/opus): bấm nút để bắt đầu, bấm lần nữa để gửi (toggle), rung nhẹ trên điện thoại; trên máy tính giữ phím Space để nói.
                            #   Micro mở một lần và giữ mở khi trang còn hiện; onRecording báo lúc máy thật sự thu; thu thêm 350 ms sau khi bấm dừng (xem pronunciation-drills.md)
  useAudioQueue.ts          # hàng đợi phát MP3, báo khi một câu bắt đầu phát
  useTeacherVoice.ts        # phát lần lượt các câu của giáo viên ở bài giảng (một thẻ <audio> dùng lại, xem lesson.md)
  useRecordings.ts          # giữ bản ghi dạng object URL cho "Nghe lại", giải phóng khi rời trang
features/
  practice/                 # phòng tập
    useInterview.ts         # WebSocket + reducer trạng thái + hành động (gửi chữ, ghi âm, hoàn tác, nói lại)
    PracticePage.tsx        # bố cục trang, nối hook ghi âm với useInterview
    Sidebar.tsx, Chat.tsx, CoachCard.tsx (thẻ NOTE + kết quả nói lại)
  lesson/                   # LessonPage.tsx: tổng quan bài + bài giảng, ưu tiên điện thoại (xem lesson.md)
  review/                   # ReviewPage.tsx: ôn tập theo thẻ (xem review.md)
  roadmap/                  # RoadmapPage.tsx: giai đoạn, tiêu chí, chủ đề (xem roadmap.md)
  sounds/                   # SoundsPage.tsx: luyện phát âm (xem pronunciation-drills.md)
  fluency/                  # FluencyPage.tsx: nói dài 4–3–2 (xem fluency-432.md)
  check/                    # CheckPage.tsx (xem speaking-check.md)
  history/                  # HistoryPage.tsx, LineChart.tsx (biểu đồ SVG)
  bench/                    # BenchPage.tsx
styles/                     # base.css (token, component chung, bảng), practice.css, lesson.css, review.css, roadmap.css, sounds.css, fluency.css, check.css, history.css, bench.css
```

## Luồng dữ liệu phòng tập (`useInterview.ts`)

- Bài mở đầu: `?unit=` trên URL, nếu không có thì bài tiếp theo của lộ trình (`pickUnit`, xem roadmap.md).
- Một WebSocket cho mỗi lần mở trang. Tin JSON từ server đi vào reducer (`onServer`), trạng thái là `InterviewState`.
- Tin `sentence` không vào reducer: nó được ghép với khung nhị phân MP3 ngay sau đó và đẩy vào `useAudioQueue`. Khi câu **bắt đầu phát**, hook gửi action `aiSentence` để thêm chữ vào tin nhắn AI của lượt đó (chữ đi theo giọng).
- `turnRef` đếm lượt **đồng bộ theo từng tin nhắn**, vì khung âm thanh của một lượt có thể tới trước khi React render lại. Tin `started` đặt lại bộ đếm.
- Hoàn tác (`undone`) gỡ cả tin nhắn của người học và của AI có cùng `lastMeTurn`, cùng thẻ tổng kết nếu có.
- Nói lại: `beginShadow` bật `shadow.waiting`; khi có bản ghi, `sendRecording` gửi `{"type":"shadow"}` ngay trước khung âm thanh. Gõ chữ luôn là câu trả lời phỏng vấn (tắt chế độ nói lại).

## Nghe lại giọng của bạn

Mọi chỗ người học nói đều có nút **"Nghe lại"** (`ReplayButton`, `.btn.replay`) để nghe chính bản ghi vừa gửi:

| Trang | Vị trí nút |
|---|---|
| Phòng tập | Dưới mỗi tin nhắn của bạn (lượt nói, không có ở lượt gõ chữ), và trong kết quả "Nói lại câu này" |
| Phát âm | Đầu hàng kết quả của câu vừa đọc |
| Ôn tập | Cạnh dòng "Máy nghe được" |
| Kiểm tra | "Nghe lại bài nói", cạnh nút "Làm đề khác" |
| Nói dài | Cột "Lần" của bảng, mỗi lần một nút |
| Tiến bộ | Chi tiết buổi tập (nút "Xem"), mỗi lượt nói một nút. Đây là file lưu trên server (`/api/history/audio/...`), nên nghe được cả buổi cũ (xem [session-history.md](session-history.md)) |

- Ngoài trang Tiến bộ, bản ghi chỉ nằm trong trình duyệt (`URL.createObjectURL` của Blob vừa ghi, `useRecordings`). Không gửi thêm, không lưu thêm gì; tải lại trang hay rời trang thì mất. Phòng tập gắn bản ghi vào tin `transcript` hoặc `shadow_result` đến ngay sau nó (`lastRecording` trong `useInterview.ts`).
- Một trình phát dùng chung (`lib/replay.ts`): bật bản ghi khác thì bản đang phát dừng; bấm micro (`useMic`) cũng dừng, để không thu lại tiếng loa.

## Hệ thiết kế (`src/styles/base.css`)

- **Màu:** chỉ dùng token, không viết mã màu trực tiếp. Nền `--bg`, bề mặt `--surface`/`--surface-2`, viền `--border`/`--border-strong`, chữ `--text`/`--text-2`/`--text-3`, màu nhấn `--primary` (+ `-hover`, `-soft`, `--on-primary`), trạng thái `--success`/`--warning`/`--danger` (+ `-soft`), biểu đồ `--chart-line`/`--chart-grid`.
- **Chế độ tối:** định nghĩa lại cùng token trong `@media (prefers-color-scheme: dark)`. Thêm token mới phải khai báo ở cả hai chế độ. Màu biểu đồ phải qua `validate_palette.js` (skill dataviz) ở cả hai chế độ.
- **Component CSS:**
  - `.btn` (biến thể `.btn-primary`, `.btn-ghost`, `.btn-sm`).
  - `.chip` (biến thể `.chip-success`, `.chip-warning`).
  - `.status[data-state]` với `ready` | `busy` | `recording` | `warn` | `error`.
  - `.mic` / `.mic.rec`, `.icon-btn` (nút tròn chỉ có icon), `.card`, `.appbar`, `.nav`, `.tabbar` / `.tab`, `.sheet`, `.lead`.
  - Trên màn hình cảm ứng (`pointer: coarse`) nút cao ít nhất 44px (`.btn-sm` 40px) cho dễ bấm.
  - Bảng: `.table-card`, `.table-wrap`, `table`, `.num` (dùng ở trang Tiến bộ, Kiểm tra, Nói dài).
  - So từng từ: `.word-diff`, `.tok` (`.ok`/`.wrong`/`.miss`/`.extra`, thêm `.focus` cho từ trọng tâm).
  - Ghi âm dài: `.recorder`, `.rec-btn` (`.on` khi đang ghi), `.recorder-bar` (`.reached`).
  - Danh sách đạt/chưa đạt: `.criteria` với `li.pass` / `li.fail`, `.criterion-mark`, `.criterion-label`, `.criterion-value` (kết quả kiểm tra, tiêu chí giai đoạn).
- CSS của mỗi trang được import trong component trang, nhưng Vite gộp tất cả thành một file. Vì vậy:
  - **Tên class là toàn cục**: không đặt trùng tên class giữa các trang với ý nghĩa khác nhau. Ví dụ `.current` của trang đo nhận dạng (chữ 24px) từng làm to chữ của giai đoạn "đang học", nên class trạng thái của lộ trình có tiền tố `stage-`.
  - **Media query cũng toàn cục**: quy tắc chỉ dành cho một trang phải có class gốc của trang đó ở đầu (ví dụ `.app .appbar-spacer` của phòng tập), nếu không sẽ áp lên mọi trang.
  - Quy tắc của trang dùng tên class chung thì giới hạn trong class gốc của trang. Ví dụ `.stage` của lộ trình viết là `.roadmap :where(.stage)`, vì phòng tập cũng có `.stage` (khung hội thoại); trước đây quy tắc lộ trình làm khung hội thoại lệch 18px và có vạch dọc bên trái.
  - **Thứ tự**: `main.tsx` import `base.css` trước các trang, để CSS của trang đứng sau trong file gộp và thắng quy tắc chung cùng độ ưu tiên (ví dụ ẩn `.stt-chip` so với `.chip`).
- Giảm chuyển động khi người dùng bật `prefers-reduced-motion`.

## Bố cục phòng tập

- **Thanh trên:** logo, chọn bài, nút "Bài giảng" (bài có bài giảng), tiến độ, nhãn cấu hình STT (ẩn từ 1500px trở xuống, để đủ chỗ cho các mục điều hướng), điều hướng (`NavLink` tự gắn `aria-current="page"`).
- **Điều hướng** (mọi trang): 7 mục (Phòng tập, Ôn tập, Lộ trình, Phát âm, Nói dài, Kiểm tra, Tiến bộ); "Ôn tập" có huy hiệu `.nav-badge` là số thẻ đến hạn. Khối điều hướng không co (`flex: none`), nên khi thiếu chỗ thì ô chọn bài và tiến độ co lại. Từ 1240px trở xuống thu thành nút menu (`.nav-toggle`, ghi tên trang hiện tại; từ 560px trở xuống chỉ còn icon) mở danh sách thả xuống. Đóng khi chọn trang, bấm ra ngoài hoặc nhấn Esc. Trang Đo nhận dạng là công cụ hiệu chỉnh, mở từ liên kết cuối trang Tiến bộ.
- **Thanh tab dưới đáy** (từ 760px trở xuống, thay nút menu): Lộ trình, Luyện, Ôn tập (huy hiệu), Phát âm, và "Thêm" mở bảng trượt với Nói dài, Kiểm tra, Tiến bộ. Dễ bấm bằng một tay và hợp với app cài lên màn hình chính. Chiều cao thanh nằm trong token `--tabbar-h` (0 khi không có thanh): `body` chừa đáy bằng đúng chiều cao này, và phòng tập cao `100dvh - var(--tabbar-h)`. Trang bài giảng không có `AppBar` nên không có thanh tab (đáy dành cho nút micro).
- **Giới thiệu trang** (Lộ trình, Phát âm, Ôn tập, Nói dài, Kiểm tra): một dòng tóm tắt, phần giải thích đầy đủ sau "Chi tiết" (`Lead`), để nội dung chính nằm gần đầu màn hình điện thoại.
- **Ghi âm** (mọi trang): bấm micro để bắt đầu, bấm lần nữa để gửi (`useMic`). Giữ nút trên điện thoại dễ trượt tay và mỏi, nên không dùng kiểu giữ để nói nữa. Trên máy tính vẫn giữ phím Space để nói.
- **Thẻ nhắc bài giảng:** đầu khung hội thoại, khi bài có bài giảng mà chưa học lần nào (xem [lesson.md](lesson.md)).
- **Cột trái:** mục tiêu, mẫu câu kèm bộ đếm, "Chỉ số kỹ thuật" thu gọn.
- **Giữa:** hội thoại (`.chat`) và thanh dưới (`.dock`).
  - Hội thoại: `.msg.ai` / `.msg.me` (tin của bạn không có ô tròn tên, để bong bóng rộng hơn), `.unclear`, thẻ tổng kết. Dưới tin của bạn: "Nghe lại", nút "Máy nghe sai, nói lại" (chỉ ở câu trả lời cuối cùng, câu mà hoàn tác sẽ gỡ), và **một** chip chỉ số nói gọn ("15 từ · 121 từ/phút", thêm số lần ngắt dài nếu có); bấm chip để xem chi tiết. "Tính cả ngắt" chỉ hiện khi khác tốc độ khi nói.
  - **Thẻ NOTE (`.coach`) nằm cuối hội thoại và cuộn theo hội thoại** (`tail` của `Chat`), không nằm trong thanh dưới. Trước đây thẻ nằm trong thanh dưới dính đáy, nên trên điện thoại che hơn nửa màn hình. Thẻ có `.shadowing` / `.retelling` khi đang chờ nói lại, `.has-result` khi có kết quả.
  - Thanh dưới: khi đang "Nói lại câu này" hoặc "Trả lời lại dài hơn", `.dock-target` hiện câu cần nói (hoặc các ý cần thêm) kèm nút Hủy, vì thẻ NOTE có thể đã cuộn khuất. Dưới đó là khung trả lời (`.composer`).
- **Màn hình hẹp** (từ 960px trở xuống): một cột, chỉ vùng hội thoại cuộn, thanh dưới luôn ở đáy. Cột trái ẩn đi, thay bằng nút "Mẫu câu 0/4" trên hàng tiến độ (`.goals-btn`, xanh khi đủ), mở mục tiêu và mẫu câu trong bảng trượt.
- **Từ 560px trở xuống:** ẩn tên app và khoảng trống của thanh trên (ô chọn bài chiếm chỗ), ẩn ô tròn "AI", ẩn chú giải của kết quả nói lại. Khung trả lời thành: dòng trạng thái, rồi nút micro lớn ở giữa và nút bàn phím bên trái; ô gõ chữ chỉ hiện khi bấm nút bàn phím (`.composer.typing`), và tự đóng khi bắt đầu nói lại.

## Quy ước

- TypeScript `strict`. Kiểu dữ liệu từ server khai báo trong `api/types.ts`; sửa giao thức thì sửa cả file này và `docs/architecture.md`.
- Component là function component + hooks. Logic không phụ thuộc giao diện để trong `lib/` và có test Vitest.
- Mọi chữ hiện cho người dùng bằng tiếng Việt, trừ lời AI và câu mẫu. Code, comment, tên biến bằng tiếng Anh.
- Không dùng `dangerouslySetInnerHTML`. Dữ liệu từ server luôn render qua JSX (React tự escape).
- Nút chỉ có icon phải có `aria-label`. Vùng nội dung thay đổi dùng `aria-live` hoặc `role="status"`.
- Thêm dependency phải ghim phiên bản cụ thể và `npm audit` không còn lỗ hổng.
- Sửa giao diện thì kiểm tra cả chế độ sáng, tối, màn hình 375px, trang không cuộn ngang, và `npm run build` không lỗi.

## Cài lên điện thoại (PWA)

App có manifest để "Thêm vào màn hình chính" và mở như một app riêng (không thanh địa chỉ):

- `public/manifest.webmanifest`: tên, màu, `start_url` là `/roadmap`, `display: standalone`, khóa màn hình dọc.
- Icon: `public/icon.svg`, `favicon.ico` (PNG 192px bọc trong ICO, để trình duyệt không báo 404 khi tự hỏi `/favicon.ico`), `icon-192.png`, `icon-512.png`, `icon-maskable-512.png` (Android), `apple-touch-icon.png` (iOS). PNG được vẽ bằng một script Python nhỏ theo đúng hình `icon.svg`; đổi icon thì vẽ lại cả bộ.
- `index.html` khai báo manifest, `theme-color`, `apple-mobile-web-app-capable`, và `viewport-fit=cover`. Trang bài giảng và thanh tab chừa chỗ cho tai thỏ và thanh home bằng `env(safe-area-inset-*)`.
- `backend/app/main.py` phục vụ các file này ở gốc (`PUBLIC_FILES`), manifest với kiểu `application/manifest+json`.
- **Không có service worker**: app cần server (STT, TTS) mới chạy được, nên chế độ offline không có ích, và cache cũ dễ làm app không nhận bản build mới.
- Cài được khi mở qua HTTPS (cũng là điều kiện để dùng micro), xem phần LAN trong [dev-environment.md](../dev-environment.md). Android Chrome: menu ⋮ → "Thêm vào màn hình chính" / "Cài đặt ứng dụng". iPhone Safari: nút Chia sẻ → "Thêm vào MH chính".
