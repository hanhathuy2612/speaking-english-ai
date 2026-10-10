# Môi trường phát triển và kiểm thử

Windows 11, Python 3.11, venv tại `.venv`. GPU RTX 3060 12 GB. LM Studio chạy ở cổng 1234.

## Kiểm thử

| Việc | Lệnh |
|---|---|
| Test logic thuần (không cần model) | `python test_parsing.py` |
| Kiểm chứng prompt | `python replay.py answers.txt --runs 3 --url ws://localhost:8001/ws` |
| Đo STT | `python stt_bench.py recordings/bench --config ...` (xem [stt-benchmark.md](features/stt-benchmark.md)) |
| Thử giao diện | Mở `http://localhost:8001` trên trình duyệt. Ô gõ chữ cho phép thử mà không cần micro. |

## Quy tắc khi chạy thử

- **Cổng 8000 là server của người dùng.** Không dừng hay khởi động lại server này. Thử nghiệm trên server riêng ở cổng 8001:

```
uvicorn server:app --port 8001
```

- Chỉ dừng đúng tiến trình đang giữ cổng 8001. **Không bao giờ tắt `python.exe` theo tên** vì có thể tắt cả tiến trình của người dùng:

```
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8001 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
```

- Server mất khoảng 10 đến 30 giây để nạp Whisper. Chờ `/api/units` trả lời rồi mới thử.
- `recordings/` chứa giọng nói thật của người dùng. Không xóa, không ghi đè. File tạo ra khi thử thì tự dọn.

## Lỗi thường gặp

- **In tiếng Việt lỗi `UnicodeEncodeError: 'charmap'`** khi chuyển output ra file: đặt `PYTHONIOENCODING=utf-8`. `server.py` đã tự `reconfigure` stdout, nhưng các script khác thì chưa.
- **Python 3.11** không cho dùng lại cùng loại dấu nháy bên trong f-string lồng nhau.
- **CRLF:** một số file có thể dùng xuống dòng CRLF, nên thay chuỗi nhiều dòng bằng script dễ không khớp. Dùng công cụ Edit.
- **`cublas64_12.dll` not found:** thiếu gói CUDA trong venv (xem [speech-recognition.md](features/speech-recognition.md)), hoặc quên gọi `cuda_dlls.add()` trước khi import faster_whisper.
