# Tài khoản, đăng nhập và phân quyền

Từ ngày 14/10/2026 app có tài khoản: mỗi người học có lịch sử, thẻ ôn, lộ trình và bản ghi âm riêng. Có hai vai trò:

| Vai trò | Được làm |
|---|---|
| `user` (người học) | Mọi trang luyện tập, trang Tài khoản (đổi mật khẩu, đăng xuất) |
| `admin` (quản trị viên) | Như người học, thêm trang Quản trị: người dùng (tạo, đổi vai trò, khóa, đặt mật khẩu, xác nhận email) và nội dung bài học ([content-admin.md](content-admin.md)); trang `/bench` |

Mọi API `/api/*` (trừ `/api/auth/*`) và WebSocket `/ws` đều cần đăng nhập. Trang HTML tĩnh vẫn tải được khi chưa đăng nhập, nhưng giao diện chỉ hiện trang đăng nhập.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Bảng `users`, `email_tokens`; băm mật khẩu, token email, `login_state` | `backend/app/services/accounts.py` |
| Ký và đọc JWT (access, refresh), khóa ký | `backend/app/services/tokens.py` |
| Kết nối MySQL dùng chung với lịch sử | `backend/app/services/db.py` |
| Kiểm tra đăng nhập và vai trò (`current_user`, `require_admin`) | `backend/app/api/deps.py`; gắn vào router trong `main.py` |
| Đăng nhập WebSocket (tin `auth` đầu tiên) | `backend/app/api/routes/ws.py` (`_ws_user`) |
| Đăng nhập, làm mới token, đăng ký, xác nhận email, quên/đặt lại mật khẩu, đổi mật khẩu | `backend/app/api/routes/auth.py` |
| Quản lý người dùng (admin) | `backend/app/api/routes/admin_users.py` |
| Gửi email (SMTP) | `backend/app/services/mailer.py` |
| Tạo tài khoản bằng lệnh | `backend/scripts/create_user.py` |
| Dữ liệu theo từng người (`user_id`), chuyển DB cũ | `backend/app/services/history.py` (`OWNED`, `claim_unowned`) |
| Giao diện | `frontend/src/auth/AuthContext.tsx`, `frontend/src/api/http.ts`, `frontend/src/features/auth/` (đăng nhập, đăng ký, link email), `features/account/`, `features/admin/UsersPage.tsx`; `styles/auth.css`, `styles/admin.css` |
| Test | `backend/tests/test_accounts.py`, `test_each_user_sees_only_their_own_history` và `test_an_old_database_is_backed_up_migrated_and_claimed` trong `test_history.py` |

## Bắt đầu: tạo quản trị viên đầu tiên

Chưa có tài khoản nào thì không đăng nhập được. Chạy một lần từ `backend/` (mật khẩu được hỏi, không hiện lên màn hình):

```
python -m scripts.create_user email-cua-ban@example.com --name "Huy" --admin
```

Hoặc đặt `ADMIN_EMAIL` và `ADMIN_PASSWORD` trong `.env`: lúc khởi động, nếu bảng `users` còn trống (database mới), server tự tạo admin này (đã xác nhận email). Đã có người dùng nào thì bỏ qua, nên đổi mật khẩu trên web sau đó vẫn giữ. Mật khẩu không hợp lệ thì server dừng và báo lỗi. Chép `history.db` cũ bằng `migrate_sqlite` thì chạy **trước** lần khởi động đầu tiên, vì script đó từ chối database đã có dữ liệu.

Quản trị viên đầu tiên (tạo bằng lệnh hay bằng `ADMIN_EMAIL`) **nhận toàn bộ lịch sử luyện tập có từ trước khi có tài khoản** (các dòng `user_id` trống). Lệnh in ra số dòng đã nhận. Sau đó những người khác tự đăng ký, hoặc admin tạo tài khoản ở trang Quản trị.

## Đăng nhập: JWT, không lưu phiên trên server

- Đăng nhập bằng email và mật khẩu. Email lưu chữ thường, nên `Me@Example.com` và `me@example.com` là một tài khoản.
- Mật khẩu băm bằng **scrypt** (`hashlib` có sẵn trong Python, không thêm thư viện), muối ngẫu nhiên 16 byte, tham số n=2^14, r=8, p=1 (mức tối thiểu OWASP khuyên cho scrypt, khoảng 50 ms mỗi lần). Mật khẩu tối thiểu 8 ký tự.
- Đăng nhập thành công (mật khẩu, link xác nhận email, link đặt lại mật khẩu, đổi mật khẩu) trả về `{user, access_token, refresh_token, expires_in}`. Cả hai token là JWT ký HS256 (thư viện PyJWT), server **không lưu gì** về lần đăng nhập.
  - **Access token**, sống **15 phút**: chứa `sub` (id), `email`, `name`, `role`. Mọi API gửi nó trong header `Authorization: Bearer <token>`. `current_user` chỉ kiểm chữ ký và hạn, không đọc DB.
  - **Refresh token**, sống **30 ngày**: chỉ chứa `sub` và `pwd`, một dấu (16 ký tự đầu của SHA-256) của mật khẩu đã băm. `POST /api/auth/refresh` đọc dòng `users` một lần (`login_state`): tài khoản phải còn hoạt động, đã xác nhận email, và `pwd` phải khớp mật khẩu hiện tại. Đúng thì trả cặp token mới (refresh mới cũng 30 ngày, nên dùng đều đặn thì không phải đăng nhập lại).
  - Hai loại token có `typ` khác nhau (`access`, `refresh`): dùng nhầm loại thì bị từ chối.
- **Khóa ký:** `JWT_SECRET` trong `.env`. Để trống thì server tự tạo khóa ngẫu nhiên và giữ trong file `data/jwt_secret` (không commit). Đổi khóa hay xóa file đó thì mọi người phải đăng nhập lại.
- **Cái giá của stateless:** server không thu hồi được token trước hạn.
  - Khóa tài khoản, đổi vai trò, đổi mật khẩu có tác dụng **trong tối đa 15 phút**, ở lần làm mới token tiếp theo. Access token đã cấp vẫn dùng được tới hết hạn.
  - Đổi mật khẩu làm mọi refresh token cũ hết tác dụng (dấu `pwd` không khớp nữa). Thiết bị vừa đổi mật khẩu nhận cặp token mới.
  - Đăng xuất chỉ là trình duyệt quên token, không gọi server. Ai đã lấy được refresh token thì vẫn dùng được tới khi người dùng đổi mật khẩu hoặc bị khóa.
- **Vì sao gửi bằng header:** token không đi kèm tự động như cookie, nên trang web khác không gửi request thay người dùng được (không có CSRF). Đổi lại, token nằm trong `localStorage`: nếu trang bị chèn script độc (XSS) thì script đọc được token.
- **Chặn đoán mật khẩu:** sai 5 lần cùng một email, hoặc 20 lần từ cùng một IP, trong 15 phút thì trả 429. Bộ đếm nằm trong bộ nhớ (một server local là đủ) và mất khi khởi động lại. Route đăng nhập là `def` thường, chạy trong threadpool, nên bộ đếm được bảo vệ bằng một khóa luồng (`threading.RLock`), và lần thử được **tính trước** khi kiểm mật khẩu (kiểm và tính trong một bước nguyên tử), để nhiều lần đoán song song không lọt qua giới hạn. Đúng mật khẩu thì lần thử được trả lại; sai vẫn bị tính. Tài khoản bị khóa hoặc chưa xác nhận email mà đúng mật khẩu thì không bị tính. Giới hạn gửi email dùng cùng cách kiểm nguyên tử này. Khi email không tồn tại, server vẫn tính scrypt một lần, để thời gian trả lời không lộ email nào có tài khoản.
- WebSocket `/ws`: trình duyệt không gắn header được cho WebSocket, nên tin đầu tiên phải là `{"type":"auth","token":"<access token>"}`, gửi trong 10 giây. Sai, thiếu hay hết hạn thì server đóng với mã **4401**, giao diện quay về trang đăng nhập. Token chỉ được kiểm lúc mở kết nối; buổi tập dài hơn 15 phút vẫn chạy tiếp.

## Đăng ký và xác nhận email

1. `/signup`: tên, email, mật khẩu. Tài khoản mới có vai trò `user`, `verified_at` trống, **chưa đăng nhập được**.
2. Server gửi email có link `<APP_URL>/verify?token=...`, hết hạn sau 48 giờ, dùng một lần. Gửi lại thì link cũ hết tác dụng.
3. Bấm link: trang `/verify` gửi token lên `POST /api/auth/verify`. Server đánh dấu đã xác nhận và **đăng nhập luôn**, vì người dùng vừa chứng minh họ đọc được hộp thư đó.
4. Đăng nhập khi chưa xác nhận thì trả 403 `{"code": "unverified"}`. Trang đăng nhập hiện link "gửi lại email xác nhận".

**Quên mật khẩu:** `/forgot` gửi link `<APP_URL>/reset?token=...`, hết hạn sau 1 giờ, dùng một lần. Đặt mật khẩu mới xong thì các thiết bị khác bị đăng xuất ở lần làm mới token tiếp theo (tối đa 15 phút), tài khoản được coi là đã xác nhận email, và người dùng được đăng nhập.

**Không để lộ email nào đã có tài khoản:** đăng ký bằng email đã có, gửi lại xác nhận, quên mật khẩu với email lạ đều trả cùng một câu "nếu email có tài khoản thì đã gửi". Email được gửi trong background task sau khi trả lời, nên thời gian trả lời cũng không khác. Đăng ký lại một email chưa xác nhận chỉ gửi lại link, không đổi mật khẩu cũ. Mỗi email nhận tối đa 3 thư, mỗi IP gửi tối đa 10 yêu cầu trong 15 phút.

Admin tạo tài khoản thì không cần xác nhận email. Admin cũng bấm "Xác nhận email" thay người dùng được. `SIGNUP_ENABLED=0` tắt trang đăng ký, khi đó chỉ admin tạo tài khoản.

### Gửi email

Cấu hình SMTP trong `.env` (xem [configuration.md](../configuration.md)). Với Gmail:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=ban@gmail.com
SMTP_PASSWORD=<App Password 16 ký tự>
APP_URL=https://192.168.0.2:8000
```

App Password tạo tại myaccount.google.com/apppasswords (cần bật xác minh 2 bước). Không dùng mật khẩu Gmail thật. Tự điền vào `.env`; agent không nhập mật khẩu hộ.

- **Không có `SMTP_HOST`:** email không được gửi mà in ra terminal của server, kèm link. Đủ dùng khi chỉ một máy, và để thử.
- **Có `SMTP_HOST` thì bắt buộc có `APP_URL`.** Nếu dựng link theo header `Host` của request, kẻ gian gửi "quên mật khẩu" cho email của bạn kèm `Host` giả, và link đặt lại (có token) sẽ trỏ về trang của họ. Thiếu `APP_URL` thì server trả lỗi 500, không gửi.
- Gửi lỗi (sai mật khẩu SMTP, mất mạng): trang vẫn báo "đã gửi" như mọi trường hợp, còn server in `!! Email to ... failed: ...` để admin biết.

## Dữ liệu theo từng người

Các bảng `sessions`, `checks`, `drills`, `fluency`, `cards`, `lesson_reads`, `lessons` có cột `user_id`. `turns`, `shadows`, `retells` thuộc về một `session`, còn `card_reviews` thuộc về một `card`. Mọi hàm đọc trong `history.py` nhận `uid` đầu tiên và chỉ trả dữ liệu của người đó. Route lấy `uid` từ `Depends(current_user)`, WebSocket lấy từ `Session.user_id`. Các trường hợp client gửi id lên cũng được kiểm tra chủ sở hữu:

- Xem hoặc xóa buổi tập (`/api/history/sessions/{id}`): có `AND user_id = ?`.
- Thẻ ôn (`/api/review/{card_id}/...`): `_get` là dependency, thẻ của người khác trả 404.
- File ghi âm (`/api/history/audio/{name}`): chỉ phát khi file thuộc một lượt nói hoặc một lần luyện phát âm của chính người đó (`owns_recording`). File ghi âm vẫn nằm chung thư mục `recordings/` như trước, không phải di chuyển file nào.

Thẻ ôn mẫu câu từng là duy nhất theo `(unit_id, phrase_index)`. Nay là `(user_id, unit_id, phrase_index)`, để hai người cùng bỏ sót một mẫu câu đều có thẻ.

### Dữ liệu từ trước khi có tài khoản

Các dòng lịch sử cũ chưa có `user_id`. Quản trị viên đầu tiên tạo bằng `create_user --admin` nhận chúng (`claim_unowned`).

Lịch sử từ bản SQLite cũ (`data/history.db`) chuyển sang MySQL một lần bằng `python -m scripts.migrate_sqlite data/history.db` (chạy trong `backend/`). Script mở file cũ ở chế độ chỉ đọc, chép mọi bảng vào database của `DATABASE_URL` và giữ nguyên id, rồi in số dòng từng bảng để đối chiếu. Database đích phải trống, có dữ liệu rồi thì script từ chối trừ khi thêm `--force`.

`DATABASE_URL` không được để trống, vì tài khoản lưu trong đó. Server không khởi động nếu biến này trống.

## API

| Route | Cần | Việc |
|---|---|---|
| `POST /api/auth/login` | | `{email, password}` → `{user, access_token, refresh_token, expires_in}` |
| `POST /api/auth/refresh` | | `{refresh_token}` → như trên; 401 khi hết hạn, tài khoản bị khóa hoặc đã đổi mật khẩu |
| `GET /api/auth/me` | đăng nhập | User hiện tại, đọc từ DB (401 nếu chưa) |
| `POST /api/auth/password` | đăng nhập | `{current, password}` → cặp token mới |
| `POST /api/auth/signup` | | `{email, password, name}` |
| `POST /api/auth/resend` | | `{email}` gửi lại link xác nhận |
| `POST /api/auth/verify` | | `{token}` → như login |
| `POST /api/auth/forgot` | | `{email}` gửi link đặt lại |
| `POST /api/auth/reset` | | `{token, password}` → như login |
| `GET/POST /api/admin/users`, `PATCH /api/admin/users/{id}` | admin | Danh sách, tạo, sửa `{name, role, disabled, password, verified}`. Không được bỏ quyền hay khóa admin cuối cùng, cũng không tự khóa mình |

User trả về không bao giờ có mật khẩu băm: `{id, email, name, role, verified, disabled, created_at}`.

## Giao diện

- `AuthProvider`: không có refresh token trong `localStorage` thì hiện trang đăng nhập ngay, không hỏi server; có thì hỏi `GET /api/auth/me` một lần khi mở app. Các route nằm sau ba cổng trong `auth/guards.tsx`:
  - `GuestOnly`: `/login`, `/signup`, `/forgot`. Đã đăng nhập thì chuyển sang `next` (hoặc `/`).
  - `RequireAuth`: mọi trang còn lại. Chưa đăng nhập thì chuyển về `/login?next=<trang đó>`, đăng nhập xong quay lại đúng trang. `next` chỉ nhận đường dẫn trong app (bắt đầu bằng một `/`), không chuyển sang trang web khác được.
  - `RequireAdmin` (bên trong `RequireAuth`): `/bench`, `/admin/...`. Người học gõ địa chỉ này thì về `/`.
  - `/verify`, `/reset` (link trong email) mở được cả khi đã hay chưa đăng nhập.

  Cổng chỉ quyết định hiện trang nào. Quyền thật nằm ở server: mọi route API đều qua `current_user` / `require_admin`.
- Mọi lời gọi API đi qua `api()` / `postAudio()` trong `api/http.ts`, không gọi `fetch` thẳng trong trang. Không dùng axios: gắn header và làm mới token chỉ cần vài chục dòng quanh `fetch`.
  - Token lưu trong `localStorage` (`auth.access`, `auth.refresh`), các tab dùng chung.
  - Trước mỗi lời gọi: access token còn dưới 30 giây thì làm mới trước. Nhiều lời gọi cùng lúc dùng chung một lần làm mới.
  - Server vẫn trả 401 thì làm mới một lần rồi gọi lại. Làm mới thất bại thì quên token, phát sự kiện `auth:expired`, app quay về trang đăng nhập. WebSocket đóng với mã 4401 cũng vậy. Các trang không phải tự xử lý phiên hết hạn.
  - Các route đăng nhập, đăng ký, link email (`/api/auth/login|refresh|signup|resend|verify|forgot|reset`) không gửi token; 401 ở đó là câu trả lời (sai mật khẩu), không phải hết phiên.
  - Lỗi trả về thành `ApiError` với câu tiếng Việt của server; mất kết nối thì báo "Không kết nối được máy chủ."
- **Âm thanh sau đăng nhập** (câu mẫu ôn tập và phát âm, giọng giáo viên, bản ghi trong lịch sử): `<audio src>` không gắn header được, nên `authedAudio()` tải file bằng `fetch` kèm token rồi phát bằng object URL. File đã tải giữ tới khi tải lại trang hoặc đăng xuất.
  - `useTeacherVoice` tải trước câu kế tiếp trong lúc câu hiện tại đang phát.
  - Ở lần bấm đầu tiên, `useTeacherVoice` phát một file WAV rỗng để mở khóa thẻ `<audio>` trên điện thoại (iOS chỉ cho phát khi có thao tác chạm), vì câu đầu thường chưa tải xong.
- Đăng xuất: quên token và các file âm thanh đã tải, không gọi server.
- Thanh trên có nút tài khoản (tên người dùng) dẫn tới `/account`; admin có thêm mục "Quản trị". Trên điện thoại hai mục này nằm trong "Thêm".

## Thử nghiệm (agent)

Server thử ở cổng 8001 dùng database tạm, nên phải tạo tài khoản trong DB đó trước:

```
set DATABASE_URL=mysql://speaking:<mật khẩu>@localhost:3306/speaking_tmp
set NEW_USER_PASSWORD=<mật khẩu thử>
python -m scripts.create_user admin@test.local --admin
```

`scripts/replay.py` cần `--email` và đọc mật khẩu từ `REPLAY_PASSWORD`. Xem [dev-environment.md](../dev-environment.md).

Đã thử ngày 14/10/2026 trên server cổng 8001 (DB tạm, không SMTP):

- Mở `/history` khi chưa đăng nhập thì chuyển sang `/login?next=%2Fhistory`, đăng nhập xong quay lại `/history`.
- Phòng tập mở WebSocket và bắt đầu bài bình thường sau khi đăng nhập. Người học mở `/admin/users` thì về `/`; admin thấy bảng người dùng.
- Đăng ký: API trả `{"ok": true}`, đăng nhập trước khi xác nhận trả `unverified`, email kèm link in ra log server. Mở link thì được đăng nhập và về `/`.
