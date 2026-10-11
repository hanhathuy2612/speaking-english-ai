# Đo độ chính xác STT

Mục đích: chọn cấu hình STT dựa trên số đo giọng thật của người dùng, không đoán.
Nguyên tắc: so mọi cấu hình trên **cùng một bộ file ghi âm**, vì mỗi lần đọc lại là một lần đọc khác.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Trang đọc theo câu mẫu | `frontend/src/features/bench/BenchPage.tsx` (route `/bench`, mở từ liên kết cuối trang Tiến bộ, không nằm trên thanh điều hướng) |
| Danh sách câu | `backend/app/data/bench_sentences.json` (18 câu, theo nghề của người dùng và các mẫu câu) |
| API lưu file | `bench_list()`, `bench_save()` trong `backend/app/api/routes/bench.py`; lưu vào `recordings/bench/NN.webm` + `NN.ref.txt` |
| Chạy so sánh | `backend/scripts/stt_bench.py` |
| Tính WER | `word_errors()`, `wer()` trong `backend/app/utils/compare.py` |

## Cách dùng

1. Mở `http://localhost:8000/bench`, giữ nút hoặc phím Space để đọc từng câu. Đáp án được lưu sẵn.
2. Chạy từ thư mục `backend/` (thư mục mặc định là `recordings/bench`):

```
python -m scripts.stt_bench --config large-v3-turbo,cuda,float16,3 --config distil-large-v3,cuda,float16,3 --prompt "Hi, I'm Huy. Java developer, microservices, payment system." --show
```

Mỗi `--config` có dạng `model,device,compute,beam`. Ghi âm trong ứng dụng chính (`recordings/*.webm`) cũng dùng được, khi có thêm `<tên>.ref.txt` bên cạnh.

## Kết quả (2026-10-10, 18 câu, 187 từ)

| Cấu hình | WER | giây/câu |
|---|---|---|
| large-v3-turbo, cuda, float16, beam 3 | 7,0% | 0,36 |
| large-v3-turbo, cuda, float16, beam 1 | 7,5% | 0,37 |
| distil-large-v3, cuda, float16, beam 3 | 10,7% | 0,34 |
| small.en, cpu, int8, beam 1, có gợi ý | 9,6% | 2,5 |
| small.en, cpu, int8, beam 1, không gợi ý | 11,2% | 2,4 |
| large-v3-turbo, cpu, int8, beam 3 | 7,0% | 10,2 |

## Lưu ý khi đọc WER

- `word_errors()` chuẩn hóa số và viết tắt trước khi so ("10,000" = "ten thousand", "I've" = "I have"). Bảng kết quả bên dưới được đo **trước** khi có chuẩn hóa này, nên WER thật thấp hơn một chút; chạy lại để có số mới.
- Với turbo, phần lớn lỗi còn lại là phát âm thật của người dùng (xem [speech-recognition.md](speech-recognition.md)).
- Mẫu nhỏ: chênh 1% chỉ khoảng 2 từ.
- Chạy lại ngày 11/10/2026 (có chuẩn hóa): turbo cuda float16 beam 3 còn **5,2%**, 0,39 giây/câu. Các lỗi còn lại (customers → customer, thirty → 60%, cache → kit, unit tests → unise text) là nguồn của bộ câu luyện phát âm, xem [pronunciation-drills.md](pronunciation-drills.md).

## Hướng phát triển

Đã làm cho câu NOTE trong phòng tập, xem [shadowing.md](shadowing.md). Có thể dùng lại `compare()` để trang `/bench` cũng tô từ lệch ngay sau khi đọc.
