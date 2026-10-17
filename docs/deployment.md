# Triển khai bằng Docker Compose

`docker-compose.yml` ở thư mục gốc chạy hai container:

| Container | Nội dung |
|---|---|
| `db` | MySQL 8.0, collation `utf8mb4_bin`, dữ liệu trong volume `mysql`. Không mở cổng ra ngoài (máy chủ có thể đã có MySQL ở 3306) |
| `app` | Build bằng `Dockerfile`: build React (`npm ci && npm run build`), rồi chạy `python -m app` trong Python 3.11 với Whisper trên GPU NVIDIA |

LM Studio **không** nằm trong Docker: vẫn chạy trên máy chủ, container gọi qua `host.docker.internal:1234`. edge-tts cần Internet như khi chạy thường.

## Cần có

- Docker Desktop (Windows, backend WSL 2) hoặc Docker Engine + Compose v2 (Linux).
- GPU NVIDIA: driver mới trên Windows (Docker Desktop tự hỗ trợ GPU qua WSL 2), hoặc NVIDIA Container Toolkit trên Linux. Thư viện CUDA (cuBLAS 12, cuDNN 9) cài bằng pip trong image (`requirements-gpu.txt`), không cần base image CUDA.
- LM Studio bật server và **"Serve on Local Network"**: server chỉ nghe `127.0.0.1` thì container không gọi tới được.

## Chạy

1. Thêm vào `.env` (mẫu ở cuối `.env.example`). Mật khẩu chỉ dùng chữ, số, `-` và `_`, vì nó nằm trong URL kết nối:

```
MYSQL_ROOT_PASSWORD=<mật khẩu root>
MYSQL_PASSWORD=<mật khẩu user speaking>
ADMIN_EMAIL=ban@example.com
ADMIN_PASSWORD=<ít nhất 8 ký tự>
```

   Các biến khác trong `.env` (STT, TTS, SMTP, SSL…) được dùng như khi chạy thường. Riêng `DATABASE_URL`, `LM_URL`, `SERVER_HOST`, `SERVER_PORT` bị `docker-compose.yml` đặt lại cho môi trường container.

2. Build và chạy (lần đầu lâu: tải image, thư viện CUDA khoảng 1–2 GB, rồi model Whisper lúc khởi động):

```
docker compose up -d --build
docker compose logs -f app
```

   Lúc khởi động, server áp dụng migration ([dev-environment.md](dev-environment.md#đổi-schema-database-migration)) và tạo admin mặc định vì database mới còn trống ([accounts.md](features/accounts.md)). Log có dòng `Loading Whisper ...`; GPU không dùng được thì có dòng `Falling back to CPU int8`.

3. Mở `http://localhost:8000` (đổi cổng bằng `APP_PORT`). Cổng 8000 trùng với server chạy trực tiếp trên máy: tắt server đó trước, hoặc đặt `APP_PORT` khác.

Cập nhật code: `git pull` rồi `docker compose up -d --build`. Dữ liệu nằm ngoài image nên không mất.

## Dữ liệu

| Ở đâu | Gì |
|---|---|
| volume `mysql` | Tài khoản, lịch sử, bài học |
| `./data` (gắn vào `/app/data`) | `jwt_secret`: mất thì mọi người phải đăng nhập lại |
| `./recordings` | Ghi âm, khi `SAVE_AUDIO_DIR=recordings` |
| `./certs` (chỉ đọc) | Chứng chỉ HTTPS cho `SSL_CERTFILE` / `SSL_KEYFILE` |
| volume `whisper` | Model Whisper tải về, giữ lại để lần sau khỏi tải |

Sao lưu database: `docker compose exec db sh -c 'mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" speaking' > backup.sql`.

**Chuyển dữ liệu đang có trong MySQL của máy chủ vào container** (một lần, trước khi dùng thật): dump từ máy chủ, rồi nạp vào container. Tắt container `app` trong lúc nạp để admin mặc định không bị tạo xen vào:

```
mysqldump -u speaking -p speaking > speaking.sql
docker compose up -d db
docker compose exec -T db sh -c 'mysql -u root -p"$MYSQL_ROOT_PASSWORD" speaking' < speaking.sql
docker compose up -d
```

## HTTPS và mạng LAN

Micro trên thiết bị khác cần HTTPS ([dev-environment.md](dev-environment.md#dùng-từ-thiết-bị-khác-trong-mạng-lan-điện-thoại-máy-khác)). Tạo chứng chỉ trên máy chủ bằng `python -m scripts.make_cert <IP LAN>` (vào `certs/`), đặt `SSL_CERTFILE=certs/lan-cert.pem`, `SSL_KEYFILE=certs/lan-key.pem` trong `.env`, rồi mở `https://<IP LAN>:8000`. Cổng được Docker mở trên mọi địa chỉ của máy, nên vẫn cần mở tường lửa cho mạng Private như hướng dẫn ở đó, và **không mở cổng này ra Internet**.

## Không có GPU

Xóa khối `deploy:` của `app` trong `docker-compose.yml` và đặt `STT_DEVICE=cpu`, `STT_COMPUTE=int8` trong `.env`. Chạy được nhưng chậm hơn nhiều; nên chọn model nhỏ hơn (`STT_MODEL=small.en`).

Chưa thử: Docker Desktop trên máy phát triển chưa chạy khi viết file này, mới kiểm cú pháp bằng `docker compose config`.
