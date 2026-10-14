# Môi trường phát triển và kiểm thử

Windows 11, Python 3.11 (venv tại `.venv`), Node 22 / npm 12. GPU RTX 3060 12 GB. LM Studio chạy ở cổng 1234.

## Kiểm thử

| Việc | Lệnh |
|---|---|
| Test backend (không cần model) | `python -m pytest` (trong `backend/`) |
| Test và build frontend | `npm test`, `npm run build` (trong `frontend/`) |
| Kiểm chứng prompt | `python -m scripts.replay answers.txt --runs 3 --url ws://localhost:8001/ws` |
| Đo STT | `python -m scripts.stt_bench --config ...` (xem [stt-benchmark.md](features/stt-benchmark.md)) |
| Thử giao diện | `npm run build` rồi mở `http://localhost:8001`, hoặc `BACKEND_URL=http://localhost:8001 npm run dev` rồi mở `http://localhost:5173`. Ô gõ chữ cho phép thử mà không cần micro. |

## Quy tắc khi chạy thử

- **Cổng 8000 là server của người dùng.** Không dừng hay khởi động lại server này. Thử nghiệm trên server riêng ở cổng 8001, **trỏ lịch sử sang file tạm và tắt lưu ghi âm**, để không ghi lẫn vào dữ liệu thật:

```
HISTORY_DB=<thư mục tạm>/hist.db SAVE_AUDIO_DIR= uvicorn app.main:app --port 8001
```

  Biến môi trường đặt sẵn được ưu tiên hơn `.env`. Để `HISTORY_DB=` trống nếu không cần lịch sử.

- Chỉ dừng đúng tiến trình đang giữ cổng 8001. **Không bao giờ tắt `python.exe` theo tên** vì có thể tắt cả tiến trình của người dùng:

```
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8001 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
```

- Server mất khoảng 10 đến 30 giây để nạp Whisper. Chờ `/api/units` trả lời rồi mới thử.
- `recordings/` (giọng nói) và `data/` (lịch sử luyện tập) là dữ liệu thật của người dùng. Không xóa, không ghi đè. File tạo ra khi thử thì tự dọn.
- Editor của người dùng tự định dạng file Python khi lưu (kiểu Black, 88 ký tự, sắp xếp lại import). Đọc lại file trước khi sửa nếu công cụ báo file đã thay đổi.

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
