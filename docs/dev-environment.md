# Môi trường phát triển và kiểm thử

Windows 11, Python 3.11 (venv tại `.venv`), Node 22 / npm 12. GPU RTX 3060 12 GB. LM Studio chạy ở cổng 1234.

## Cài MySQL (một lần cho mỗi máy)

App dùng MySQL 8.0 (trên máy này là dịch vụ Windows `MySQL80`). Tạo database và user, rồi điền `DATABASE_URL` vào `.env`:

```sql
CREATE DATABASE speaking CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE USER 'speaking'@'localhost' IDENTIFIED BY '<mật khẩu>';
GRANT ALL PRIVILEGES ON `speaking`.* TO 'speaking'@'localhost';
GRANT ALL PRIVILEGES ON `speaking\_%`.* TO 'speaking'@'localhost';
```

Collation `utf8mb4_bin` là bắt buộc: mặc định của server (`utf8mb4_0900_ai_ci`) coi `a` và `á` là một, trong khi app so sánh nhị phân. Bảng do migration tạo lúc server khởi động (xem [Đổi schema database](#đổi-schema-database-migration)). Quyền thứ hai cho phép tạo `speaking_test` (pytest) và `speaking_tmp` (server thử). Có `data/history.db` cũ thì chuyển một lần bằng `python -m scripts.migrate_sqlite data/history.db` (xem [accounts.md](features/accounts.md)).

## Kiểm thử

| Việc | Lệnh |
|---|---|
| Test backend (không cần model) | `python -m pytest` (trong `backend/`). Test cần DB đọc `TEST_DATABASE_URL` (ví dụ `.../speaking_test`), `conftest.py` xóa và tạo lại database đó mỗi lần chạy; chưa đặt thì các test này bị bỏ qua |
| Test và build frontend | `npm test`, `npm run build` (trong `frontend/`) |
| Kiểm chứng prompt | `python -m scripts.replay answers.txt --runs 3 --url ws://localhost:8001/ws --email admin@test.local` (mật khẩu trong `REPLAY_PASSWORD`) |
| Đo STT | `python -m scripts.stt_bench --config ...` (xem [stt-benchmark.md](features/stt-benchmark.md)) |
| Thử giao diện | `npm run build` rồi mở `http://localhost:8001`, hoặc `BACKEND_URL=http://localhost:8001 npm run dev` rồi mở `http://localhost:5173`. Ô gõ chữ cho phép thử mà không cần micro. |

## Đổi schema database (migration)

Schema nằm trong các file `backend/app/migrations/NNN_mo-ta.sql` (bắt đầu từ `001_initial.sql`, có `IF NOT EXISTS` nên DB đã có bảng chỉ ghi nhận là đã áp dụng). `db.migrate()` chạy lúc server khởi động, trong `scripts/create_user.py` và `scripts/migrate_sqlite.py`: tạo bảng `schema_migrations(version, applied_at)`, áp dụng các file chưa chạy theo thứ tự tên, khóa bằng `GET_LOCK` để hai tiến trình không chạy song song. File lỗi thì raise và không được ghi nhận.

Thêm cột hoặc bảng:

1. Tạo file mới với số kế tiếp, ví dụ `002_add_turns_note.sql`, chứa `ALTER TABLE ...` hoặc `CREATE TABLE ...`.
2. Mỗi file chỉ một thay đổi nhỏ. MySQL tự commit DDL nên file không có tính nguyên tử: file lỗi giữa chừng có thể đã đổi một phần.
3. **Không sửa file đã áp dụng**, luôn thêm file mới.
4. `python -m pytest` dựng database test từ các file này (`conftest.py` chạy migrate một lần, không bao giờ xóa `schema_migrations`), nên test bắt lỗi SQL.
5. Server tự áp dụng khi khởi động. Muốn chạy trước: `python -m scripts.migrate`; xem đã/chưa áp dụng: `python -m scripts.migrate status`.

Sao lưu trước khi migrate trên database thật: `mysqldump -u speaking -p speaking > backup.sql`.

## Quy tắc khi chạy thử

- **Cổng 8000 là server của người dùng.** Không dừng hay khởi động lại server này. Thử nghiệm trên server riêng ở cổng 8001, **trỏ sang database tạm và tắt lưu ghi âm**, để không ghi lẫn vào dữ liệu thật:

```
DATABASE_URL=mysql://speaking:<mật khẩu>@localhost:3306/speaking_tmp SAVE_AUDIO_DIR= uvicorn app.main:app --port 8001
```

  Biến môi trường đặt sẵn được ưu tiên hơn `.env`. `DATABASE_URL` không để trống được (tài khoản lưu ở đó). Database tạm (`speaking_tmp`) tạo bằng `CREATE DATABASE speaking_tmp CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;` và `DROP DATABASE` khi xong; user `speaking` đã có quyền trên mọi database tên `speaking_*` (xem mục cài MySQL).

- **Mọi trang và API đều cần đăng nhập** ([accounts.md](features/accounts.md)). Tạo tài khoản thử trong DB tạm trước khi chạy server, mật khẩu đặt qua biến môi trường để không phải gõ:

```
DATABASE_URL=mysql://speaking:<mật khẩu>@localhost:3306/speaking_tmp NEW_USER_PASSWORD=<mật khẩu thử> python -m scripts.create_user admin@test.local --admin
```

  Thử bằng script thì đăng nhập qua `POST /api/auth/login`, gửi `access_token` trong header `Authorization: Bearer ...`, hoặc trong tin `auth` đầu tiên của WebSocket (`replay.py` đã làm việc này, đăng nhập lại mỗi lượt chạy vì token sống 15 phút). Để trống `SMTP_HOST` và `APP_URL`: email xác nhận in ra log server, link trỏ về chính server thử.

- Chỉ dừng đúng tiến trình đang giữ cổng 8001. **Không bao giờ tắt `python.exe` theo tên** vì có thể tắt cả tiến trình của người dùng:

```
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8001 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
```

- Sao lưu dữ liệu thật bằng `mysqldump -u speaking -p speaking > backup.sql`.
- Server mất khoảng 10 đến 30 giây để nạp Whisper. Chờ `/api/units` trả lời rồi mới thử.
- `recordings/` (giọng nói), `data/` (khóa JWT) và database `speaking` trong MySQL là dữ liệu thật của người dùng. Không xóa, không ghi đè, không `DROP`. File tạo ra khi thử thì tự dọn.
- Editor của người dùng tự định dạng file Python khi lưu (kiểu Black, 88 ký tự, sắp xếp lại import). Đọc lại file trước khi sửa nếu công cụ báo file đã thay đổi.

## Làm việc theo nhóm agent (Claude Code)

Gõ `/team <việc cần làm>` trong Claude Code: khung chat chính thành người điều phối. Nó đọc tài liệu, đưa kế hoạch (chia file cho từng agent, hợp đồng API/WebSocket) và **chờ người dùng đồng ý**, rồi giao việc cho các agent con và tổng hợp kết quả. Không tự commit.

| Agent | Việc | Sửa file |
|---|---|---|
| `backend-dev` | Làm phần `backend/` theo kế hoạch, chạy `pytest` | `backend/` |
| `frontend-dev` | Làm phần `frontend/`, chạy `format`, `build`, `test` | `frontend/` |
| `prompt-tester` | Đổi prompt hoặc parse thì chạy `replay.py` trên server thử cổng 8001, database tạm | Không (chỉ file tạm) |
| `rules-reviewer` | Soát diff theo quy tắc của repo: lọc `user_id`, ngôn ngữ, hướng phụ thuộc, không chấm điểm bằng LLM | Không |
| `docs-sync` | Cập nhật `docs/` và `AGENTS.md` theo thay đổi | Chỉ tài liệu |

Định nghĩa nằm ở `.claude/skills/team/SKILL.md` và `.claude/agents/*.md`. Agent con không thấy cuộc trò chuyện, nên người điều phối phải giao việc đầy đủ (mục tiêu, file, hợp đồng, tiêu chí xong). Cách này tốn token hơn làm một mình nhiều lần, chỉ nên dùng cho việc lớn đụng cả backend lẫn frontend.

## Dùng từ thiết bị khác trong mạng LAN (điện thoại, máy khác)

Mặc định uvicorn chỉ nghe ở `127.0.0.1`, nên chỉ chính máy này vào được. Muốn mở từ thiết bị cùng mạng:

1. **HTTPS là bắt buộc nếu muốn dùng micro.** Trình duyệt chỉ cho ghi âm trên `https://` hoặc `localhost`; mở `http://192.168.x.x:8000` vẫn thấy trang nhưng bấm micro sẽ lỗi. Tạo chứng chỉ tự ký một lần (cần `openssl`, có sẵn trong Git Bash), ghi IP LAN của máy (`ipconfig`):

```
python -m scripts.make_cert 192.168.0.2
```

   Chứng chỉ ở `certs/lan-cert.pem` + `certs/lan-key.pem` (không commit, có khóa riêng), hạn 825 ngày, gồm IP đó + `localhost`. Đổi IP thì chạy lại.

2. **Ghi cấu hình vào `.env`** (đã có trong `.env` của người dùng, mẫu ở `.env.example`):

```
SERVER_HOST=0.0.0.0
SSL_CERTFILE=certs/lan-cert.pem
SSL_KEYFILE=certs/lan-key.pem
```

   Rồi chạy app bằng lệnh ngắn: `run` (file `run.cmd` ở thư mục gốc, trong PowerShell gõ `.\run`; không cần `cd` hay kích hoạt venv), hoặc `python -m app` trong `backend/`. Cả hai đọc `SERVER_HOST`, `SERVER_PORT`, `SSL_*` từ `.env` (`backend/app/__main__.py`) và in sẵn địa chỉ để mở, kể cả địa chỉ LAN. Lệnh `uvicorn ...` trực tiếp **không** đọc các biến này.

   Khi có HTTPS, máy chính cũng phải mở `https://localhost:8000`. Frontend tự chọn `wss://` cho WebSocket khi trang là HTTPS.

3. **Mở cổng 8000 trên Windows Firewall** cho mạng Private (PowerShell chạy quyền Administrator, người dùng tự làm). Mạng Wi-Fi/Ethernet ở nhà phải đặt là Private:

```
New-NetFirewallRule -DisplayName "Speaking app 8000 (LAN)" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
```

4. Trên thiết bị kia mở `https://192.168.0.2:8000`. Trình duyệt cảnh báo chứng chỉ không tin cậy (vì tự ký): chọn "Nâng cao" → "Tiếp tục truy cập". Sau đó cho phép micro.

Không có đăng nhập: ai trong cùng mạng mở được địa chỉ này đều xem và ghi được lịch sử luyện tập. Chỉ bật ở mạng nhà tin cậy; không mở cổng này ra Internet (dùng Tailscale hoặc Cloudflare Tunnel nếu cần truy cập từ ngoài).

Đã thử ngày 11/10/2026 trên server thử (HTTPS, cổng 8001, chạy bằng `.\run.cmd` từ PowerShell với `SERVER_PORT`/`SERVER_HOST` đặt bằng biến môi trường): trang, `/api/stages` và WebSocket `wss://` đều chạy với chứng chỉ này.

Agent không chạy `run.cmd` để thử nếu `.env` có `SERVER_HOST=0.0.0.0` mà không ghi đè: server thử sẽ mở ra mạng LAN. Trong PowerShell, `$env:SAVE_AUDIO_DIR = ""` **xóa** biến chứ không đặt rỗng, nên giá trị trong `.env` lại được dùng; muốn tắt lưu ghi âm thì dùng lệnh `uvicorn` như ở trên.

## Lỗi thường gặp

- **In tiếng Việt lỗi `UnicodeEncodeError: 'charmap'`** khi chuyển output ra file: đặt `PYTHONIOENCODING=utf-8`. `app/main.py` đã tự `reconfigure` stdout, nhưng các script khác thì chưa.
- **Python 3.11** không cho dùng lại cùng loại dấu nháy bên trong f-string lồng nhau.
- **npm 12 chặn script cài đặt** (`install-scripts`). Cảnh báo về esbuild là bình thường, build vẫn chạy.
- **Trình duyệt thử không có micro.** Để thử luồng ghi âm (kể cả nói lại), tạo file MP3 bằng edge-tts rồi gửi thẳng qua WebSocket (`ws://localhost:8001/ws`) bằng script Python, hoặc gửi vào đúng socket của trang.
- **edge-tts báo `WSServerHandshakeError: 403`**, không có giọng đọc: Microsoft đổi cách kiểm tra token, bản edge-tts cũ bị từ chối. Cập nhật (`pip install -U -r requirements.txt`, cần bản 7.3.1 trở lên) rồi khởi động lại server.
- **CRLF:** một số file có thể dùng xuống dòng CRLF, nên thay chuỗi nhiều dòng bằng script dễ không khớp. Dùng công cụ Edit.
- **`cublas64_12.dll` not found:** thiếu gói CUDA trong venv (xem [speech-recognition.md](features/speech-recognition.md)), hoặc quên gọi `add_cuda_dlls()` (`core/cuda.py`) trước khi import faster_whisper.
