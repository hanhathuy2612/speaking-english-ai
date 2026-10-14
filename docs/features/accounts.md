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
| Bảng `users`, `auth_sessions`, `email_tokens`; băm mật khẩu, phiên, token email | `backend/app/services/accounts.py` |
| File SQLite dùng chung với lịch sử | `backend/app/services/db.py` |
| Kiểm tra đăng nhập và vai trò (`current_user`, `require_admin`, `ws_user`) | `backend/app/api/deps.py`; gắn vào router trong `main.py` |
| Đăng nhập, đăng xuất, đăng ký, xác nhận email, quên/đặt lại mật khẩu, đổi mật khẩu | `backend/app/api/routes/auth.py` |
| Quản lý người dùng (admin) | `backend/app/api/routes/admin_users.py` |
| Gửi email (SMTP) | `backend/app/services/mailer.py` |
| Tạo tài khoản bằng lệnh | `backend/scripts/create_user.py` |
| Dữ liệu theo từng người (`user_id`), chuyển DB cũ | `backend/app/services/history.py` (`OWNED`, `init`, `claim_unowned`) |
| Giao diện | `frontend/src/auth/AuthContext.tsx`, `frontend/src/api/http.ts`, `frontend/src/features/auth/` (đăng nhập, đăng ký, link email), `features/account/`, `features/admin/UsersPage.tsx`; `styles/auth.css`, `styles/admin.css` |
| Test | `backend/tests/test_accounts.py`, `test_each_user_sees_only_their_own_history` và `test_an_old_database_is_backed_up_migrated_and_claimed` trong `test_history.py` |

## Bắt đầu: tạo quản trị viên đầu tiên

Chưa có tài khoản nào thì không đăng nhập được. Chạy một lần từ `backend/` (mật khẩu được hỏi, không hiện lên màn hình):

```
python -m scripts.create_user email-cua-ban@example.com --name "Huy" --admin
```

Quản trị viên đầu tiên **nhận toàn bộ lịch sử luyện tập có từ trước khi có tài khoản** (các dòng `user_id` trống). Lệnh in ra số dòng đã nhận. Sau đó những người khác tự đăng ký, hoặc admin tạo tài khoản ở trang Quản trị.

## Đăng nhập và phiên

- Đăng nhập bằng email và mật khẩu. Email lưu chữ thường, nên `Me@Example.com` và `me@example.com` là một tài khoản.
- Mật khẩu băm bằng **scrypt** (`hashlib` có sẵn trong Python, không thêm thư viện), muối ngẫu nhiên 16 byte, tham số n=2^14, r=8, p=1 (mức tối thiểu OWASP khuyên cho scrypt, khoảng 50 ms mỗi lần). Mật khẩu tối thiểu 8 ký tự.
- Đăng nhập thành công thì server đặt cookie `sid`: chuỗi ngẫu nhiên 32 byte, `HttpOnly` (JavaScript của trang không đọc được), `SameSite=Lax` (trang web khác không gửi kèm được trong POST hay WebSocket), `Secure` khi chạy HTTPS, sống 30 ngày. Trong DB chỉ lưu SHA-256 của cookie, nên có bản sao DB cũng không dùng được để đăng nhập.
- **Dùng cookie, không dùng JWT:** frontend và backend cùng một địa chỉ, nên trình duyệt tự gửi cookie, kể cả khi mở WebSocket. Đăng xuất, đổi mật khẩu hay khóa tài khoản xóa phiên trong DB và có tác dụng ngay. JWT không làm được việc này nếu không có thêm danh sách thu hồi.
- Đổi mật khẩu (trang Tài khoản hoặc link đặt lại) và khóa tài khoản sẽ **kết thúc mọi phiên** của người đó. Riêng thiết bị vừa đổi mật khẩu được cấp cookie mới.
- **Chặn đoán mật khẩu:** sai 5 lần cùng một email, hoặc 20 lần từ cùng một IP, trong 15 phút thì trả 429. Bộ đếm nằm trong bộ nhớ (một server local là đủ) và mất khi khởi động lại. Khi email không tồn tại, server vẫn tính scrypt một lần, để thời gian trả lời không lộ email nào có tài khoản.
- WebSocket `/ws` đọc cookie lúc bắt tay. Không có phiên hợp lệ thì server đóng với mã **4401**, giao diện quay về trang đăng nhập. Header `Origin` phải trùng `Host`, để trang web khác không mở được WebSocket bằng cookie của người dùng.

## Đăng ký và xác nhận email

1. `/signup`: tên, email, mật khẩu. Tài khoản mới có vai trò `user`, `verified_at` trống, **chưa đăng nhập được**.
2. Server gửi email có link `<APP_URL>/verify?token=...`, hết hạn sau 48 giờ, dùng một lần. Gửi lại thì link cũ hết tác dụng.
3. Bấm link: trang `/verify` gửi token lên `POST /api/auth/verify`. Server đánh dấu đã xác nhận và **đăng nhập luôn**, vì người dùng vừa chứng minh họ đọc được hộp thư đó.
4. Đăng nhập khi chưa xác nhận thì trả 403 `{"code": "unverified"}`. Trang đăng nhập hiện link "gửi lại email xác nhận".

**Quên mật khẩu:** `/forgot` gửi link `<APP_URL>/reset?token=...`, hết hạn sau 1 giờ, dùng một lần. Đặt mật khẩu mới xong thì mọi phiên cũ kết thúc, tài khoản được coi là đã xác nhận email, và người dùng được đăng nhập.

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

### Chuyển DB cũ

Lần đầu server (hoặc `create_user`) mở một `history.db` có từ trước khi có tài khoản:

1. Chép file sang `history.db.before-accounts` (chỉ một lần, không ghi đè bản đã có).
2. Thêm cột `user_id` (để trống) vào các bảng trên, tạo index.
3. Dựng lại bảng `cards` với ràng buộc duy nhất mới. SQLite không sửa được ràng buộc `UNIQUE` tại chỗ, nên app chép sang bảng mới. Trong lúc đó tạm tắt khóa ngoại để `card_reviews` không bị xóa theo.
4. Dữ liệu cũ thuộc về quản trị viên đầu tiên tạo bằng `create_user --admin` (`claim_unowned`).

`HISTORY_DB` không được để trống nữa, vì tài khoản lưu trong đó. Server không khởi động nếu biến này trống.

## API

| Route | Cần | Việc |
|---|---|---|
| `POST /api/auth/login` | | `{email, password}` → user, đặt cookie |
| `POST /api/auth/logout` | | Xóa phiên và cookie |
| `GET /api/auth/me` | đăng nhập | User hiện tại (401 nếu chưa) |
| `POST /api/auth/password` | đăng nhập | `{current, password}` |
| `POST /api/auth/signup` | | `{email, password, name}` |
| `POST /api/auth/resend` | | `{email}` gửi lại link xác nhận |
| `POST /api/auth/verify` | | `{token}` → user, đặt cookie |
| `POST /api/auth/forgot` | | `{email}` gửi link đặt lại |
| `POST /api/auth/reset` | | `{token, password}` → user, đặt cookie |
| `GET/POST /api/admin/users`, `PATCH /api/admin/users/{id}` | admin | Danh sách, tạo, sửa `{name, role, disabled, password, verified}`. Không được bỏ quyền hay khóa admin cuối cùng, cũng không tự khóa mình |

User trả về không bao giờ có mật khẩu băm: `{id, email, name, role, verified, disabled, created_at}`.

## Giao diện

- `AuthProvider` hỏi `GET /api/auth/me` một lần khi mở app. Các route nằm sau ba cổng trong `auth/guards.tsx`:
  - `GuestOnly`: `/login`, `/signup`, `/forgot`. Đã đăng nhập thì chuyển sang `next` (hoặc `/`).
  - `RequireAuth`: mọi trang còn lại. Chưa đăng nhập thì chuyển về `/login?next=<trang đó>`, đăng nhập xong quay lại đúng trang. `next` chỉ nhận đường dẫn trong app (bắt đầu bằng một `/`), không chuyển sang trang web khác được.
  - `RequireAdmin` (bên trong `RequireAuth`): `/bench`, `/admin/...`. Người học gõ địa chỉ này thì về `/`.
  - `/verify`, `/reset` (link trong email) mở được cả khi đã hay chưa đăng nhập.

  Cổng chỉ quyết định hiện trang nào. Quyền thật nằm ở server: mọi route API đều qua `current_user` / `require_admin`.
- Mọi lời gọi API đi qua `api()` / `postAudio()` trong `api/http.ts`, không gọi `fetch` thẳng trong trang. Không dùng axios: đăng nhập là cookie HttpOnly trình duyệt tự gửi, không có token để gắn, nên wrapper `fetch` là đủ. API trả 401 (trừ `/api/auth/...`, nơi 401 là sai mật khẩu) thì phát sự kiện `auth:expired`, app quay về trang đăng nhập. WebSocket đóng với mã 4401 cũng vậy. Các trang không phải tự xử lý phiên hết hạn. Lỗi trả về thành `ApiError` với câu tiếng Việt của server; mất kết nối thì báo "Không kết nối được máy chủ."
- Thanh trên có nút tài khoản (tên người dùng) dẫn tới `/account`; admin có thêm mục "Quản trị". Trên điện thoại hai mục này nằm trong "Thêm".

## Thử nghiệm (agent)

Server thử ở cổng 8001 dùng DB tạm, nên phải tạo tài khoản trong DB đó trước:

```
set HISTORY_DB=<thư mục tạm>\hist.db
set NEW_USER_PASSWORD=<mật khẩu thử>
python -m scripts.create_user admin@test.local --admin
```

`scripts/replay.py` cần `--email` và đọc mật khẩu từ `REPLAY_PASSWORD`. Xem [dev-environment.md](../dev-environment.md).

Đã thử ngày 14/10/2026 trên server cổng 8001 (DB tạm, không SMTP):

- Mở `/history` khi chưa đăng nhập thì chuyển sang `/login?next=%2Fhistory`, đăng nhập xong quay lại `/history`.
- Phòng tập mở WebSocket và bắt đầu bài bình thường sau khi đăng nhập. Người học mở `/admin/users` thì về `/`; admin thấy bảng người dùng.
- Đăng ký: API trả `{"ok": true}`, đăng nhập trước khi xác nhận trả `unverified`, email kèm link in ra log server. Mở link thì được đăng nhập và về `/`.
