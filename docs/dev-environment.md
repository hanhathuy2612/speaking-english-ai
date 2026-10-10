# Môi trường phát triển và kiểm thử

Windows 11, Python 3.11, venv tại `.venv`. GPU RTX 3060 12 GB. LM Studio chạy ở cổng 1234.

## Kiểm thử

| Việc | Lệnh |
|---|---|
| Test logic thuần (không cần model) | `python -m pytest` |
| Kiểm chứng prompt | `python -m scripts.replay answers.txt --runs 3 --url ws://localhost:8001/ws` |
| Đo STT | `python -m scripts.stt_bench --config ...` (xem [stt-benchmark.md](features/stt-benchmark.md)) |
| Thử giao diện | Mở `http://localhost:8001` trên trình duyệt. Ô gõ chữ cho phép thử mà không cần micro. |

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

## Lỗi thường gặp

- **In tiếng Việt lỗi `UnicodeEncodeError: 'charmap'`** khi chuyển output ra file: đặt `PYTHONIOENCODING=utf-8`. `app/main.py` đã tự `reconfigure` stdout, nhưng các script khác thì chưa.
- **Python 3.11** không cho dùng lại cùng loại dấu nháy bên trong f-string lồng nhau.
- **CRLF:** một số file có thể dùng xuống dòng CRLF, nên thay chuỗi nhiều dòng bằng script dễ không khớp. Dùng công cụ Edit.
- **`cublas64_12.dll` not found:** thiếu gói CUDA trong venv (xem [speech-recognition.md](features/speech-recognition.md)), hoặc quên gọi `add_cuda_dlls()` (`core/cuda.py`) trước khi import faster_whisper.
