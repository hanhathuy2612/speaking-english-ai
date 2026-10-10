# Phòng tập phỏng vấn: demo chạy local

Demo nhỏ cho luồng cốt lõi: **chuẩn bị mẫu câu, nói, nhận cách nói tự nhiên hơn, nói lại**.
Dùng đúng stack của bạn: LM Studio (Qwen2.5-7B), faster-whisper, edge-tts.

## Chạy

1. Bật LM Studio, nạp `qwen2.5-7b-instruct`, bật Local Server (cổng 1234).
2. Cài thư viện và chạy:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn server:app --port 8000
```

3. Mở http://localhost:8000, cho phép micro, **giữ nút để nói**, thả ra để gửi.
   Có ô gõ chữ để thử LLM + TTS khi chưa muốn dùng micro.

Kiểm tra logic thuần: `python test_parsing.py`.

## Luồng phỏng vấn

- **App điều khiển câu hỏi**, không phải LLM. Mỗi bài trong `units.json` có danh sách `questions`
  (câu hỏi `ask`, mẫu câu tương ứng `phrases`, bản dễ hơn `simple` để hỏi lại).
- Mỗi lượt LLM trả về 4 dòng: `RETRY`, `SAY` (phản ứng ngắn, ngôi thứ hai), `ASK` (câu hỏi phụ hoặc `NEXT`), `NOTE`.
- App quyết định câu tiếp theo:
  - RETRY: hỏi lại bằng câu `simple` soạn sẵn (tối đa 2 lần rồi chuyển câu).
  - Câu hỏi phụ: tối đa `INTERVIEW_FOLLOWUPS` câu cho mỗi câu chính.
  - Còn lại: chuyển sang câu chính tiếp theo, hết câu thì nói lời kết và hiện tổng kết.
- Câu hỏi chính, lời chào, lời kết được TTS sẵn và lưu cache.
- NOTE: nếu model chép từ ví dụ mẫu, hoặc RETRY khi chưa biết gì về bạn, app hiện khung mẫu câu thay thế.
- Nút **"Máy nghe sai, nói lại"**: bỏ lượt vừa rồi (cả lời AI) và trả về đúng câu hỏi trước đó.
- Nếu Whisper nghe không chắc (`avg_logprob` dưới `STT_MIN_LOGPROB` hoặc `no_speech` cao), app không gửi cho AI
  mà nhờ bạn nói lại. Số "Độ tin cậy nhận dạng" ở cột trái giúp bạn chỉnh ngưỡng.

## Cấu hình (`.env`, server tự nạp khi khởi động)

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `LM_URL` / `LM_MODEL` | `http://localhost:1234/v1` / `qwen2.5-7b-instruct` | |
| `LM_TEMPERATURE` | `0.35` | |
| `LM_SEED` | trống | đặt số cố định khi so prompt |
| `MAX_HISTORY` | `3` | số cặp hỏi/đáp trước đó gửi cho LLM |
| `INTERVIEW_FOLLOWUPS` | `1` | `0` để chỉ hỏi các câu chính |
| `STT_MODEL` | `small.en` | thử `distil-large-v3`, `large-v3-turbo` |
| `STT_DEVICE` / `STT_COMPUTE` | `cpu` / `int8` | GPU: `cuda` / `float16` |
| `STT_BEAM` | `1` | `.env` đang đặt 3 (ưu tiên độ chính xác) |
| `STT_VOCAB` | trống | tên riêng, từ nghề nghiệp; ghép với `vocab` của bài làm `initial_prompt` |
| `STT_MIN_LOGPROB` / `STT_MAX_NO_SPEECH` | `-1.0` / `0.6` | ngưỡng "máy nghe chưa rõ" |
| `SAVE_AUDIO_DIR` | trống | vd `recordings`: giữ file ghi âm để chạy `stt_bench.py` |
| `TTS_VOICE` / `TTS_RATE` | `en-US-JennyNeural` / `-10%` | |

Cột trái hiện cấu hình STT đang chạy thật, để biết `.env` đã có tác dụng chưa.

## Chạy Whisper trên GPU (Windows)

ctranslate2 cần cuBLAS 12 và cuDNN 9. Cài vào venv (khoảng 1 GB):

```
pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
```

Server tự thêm thư mục DLL này vào PATH (`cuda_dlls.py`). Sau đó đặt trong `.env`:
`STT_DEVICE=cuda`, `STT_COMPUTE=float16`, `STT_MODEL=distil-large-v3` (hoặc `large-v3-turbo`).
Nếu GPU vẫn lỗi, server tự về CPU int8 và ghi "(GPU lỗi)" ở cột trái.
Qwen 7B (khoảng 5 GB) và Whisper (khoảng 1,5 GB) cùng chạy được trên 3060 12 GB.

## So cấu hình STT: `stt_bench.py`

1. Đặt `SAVE_AUDIO_DIR=recordings`, tập bình thường và nói 15 đến 20 câu.
2. Với mỗi `recordings/<thời gian>.hyp.txt`, tạo `<thời gian>.ref.txt` ghi đúng câu bạn đã nói.
3. Chạy cùng bộ file qua nhiều cấu hình:

```
python stt_bench.py recordings --config small.en,cpu,int8,1 --config distil-large-v3,cuda,float16,3 --config large-v3-turbo,cuda,float16,3 --prompt "Hi, I'm Huy. Java developer, microservices, payment system."
```

Kết quả: WER (tỉ lệ từ sai) và số giây mỗi câu. Thêm `--show` để xem từng câu.

## So prompt: `replay.py`

Phát lại các câu trả lời (gõ chữ, bỏ qua STT) qua server đang chạy:

```
python replay.py answers.txt --runs 3
```

`answers.txt`: mỗi dòng một câu trả lời. Đặt `LM_SEED` để các lần chạy dễ so hơn.
Dò: AI có nói ở ngôi thứ nhất như ứng viên không, có hỏi lại câu cũ không, có đi hết câu hỏi không.
Lưu ý: số câu hỏi phụ thay đổi theo từng lần, nên kịch bản cố định có thể lệch nhịp ở cuối.

## Chỉ số nói

- `khi nói ... từ/phút`: bỏ các lần ngắt dài (trên 0,7 giây). `tính cả ngắt`: tính trên toàn bộ thời gian.
- Câu dưới 10 từ không tính tốc độ (quá nhiễu).
- "Máy nghe chưa chắc" bỏ qua từ chức năng (a, the, with...), vì Whisper luôn chấm chúng thấp.

## Chưa có (cố ý)

Đăng nhập, cơ sở dữ liệu, roadmap mở khóa, lặp ngắt quãng.
Phần này bạn đã có trong dự án chính, khi hài lòng với luồng nói thì ghép sang.

## Điểm thay thế

- Đổi STT: sửa hàm `transcribe` trong `server.py`.
- Đổi TTS (ví dụ Kokoro): sửa hàm `tts_bytes`. Trình phát đang nhận MP3, nên nếu TTS mới
  trả WAV/PCM thì cần đổi `type` của Blob trong `index.html`.
