# Prompt LLM và NOTE

LLM: Qwen2.5-7B-Instruct qua LM Studio, `temperature` 0.35, `max_tokens` 160, có stream.

## Mã nguồn

| Phần | Vị trí (trong `backend/app/`) |
|---|---|
| System prompt | `SYSTEM_TEMPLATE`, `build_messages()` trong `interview/prompts.py` |
| Ví dụ mẫu | `FEW_SHOT` (3 cặp user/assistant) trong `interview/prompts.py` |
| Tin nhắn mỗi lượt | `build_user_message()` trong `interview/prompts.py` |
| Gọi LLM | `stream_reply()` trong `services/llm.py` |
| Xử lý stream | `run_turn()` trong `interview/turn.py`, cùng `split_sections()` / `ready_sentences()` trong `utils/parsing.py` |
| Chặn NOTE xấu | `safe_note()`, `EXAMPLE_WORDS` trong `interview/prompts.py` |

## Định dạng đầu ra (4 dòng)

```
RETRY: yes|no
SAY: <phản ứng ngắn, ngôi thứ hai, dưới 15 từ, không phải câu hỏi>
ASK: <một câu hỏi phụ, hoặc NEXT>
NOTE: <câu của ứng viên viết lại tự nhiên hơn, ngôi thứ nhất, dưới 25 từ>
```

- RETRY đứng đầu để không bị cắt mất khi chạm `max_tokens`.
- SAY được TTS từng câu ngay khi viết xong. Câu nào trong SAY kết thúc bằng `?` thì bị bỏ, vì câu hỏi do app quyết định.
- NOTE chỉ hiện chữ, không đọc (người học bấm "Nghe câu này" nếu muốn).
- Nếu output không có nhãn SAY, app báo "AI trả sai định dạng" và tự chuyển câu.

## Tin nhắn user mỗi lượt

```
Earlier in the interview:          (tối đa MAX_HISTORY cặp hỏi/đáp)
- Q: ... A: ...
Current question: ...
Target phrase: ...
Follow-up allowed: yes|no
Latest answer: ...                 (luôn để cuối)
```

## Các lỗi đã gặp và cách chặn

| Lỗi | Nguyên nhân | Cách chặn |
|---|---|---|
| AI nói câu trả lời thay ứng viên ("I'm responsible for...") | Prompt cũ gọi model là "coach", mẫu câu ở ngôi thứ nhất, luật "reuse the correct form" | Khóa vai INTERVIEWER, SAY ngôi thứ hai, mẫu câu chỉ nằm trong NOTE |
| Lời gợi ý mở đầu câu bị đọc như lời người phỏng vấn | Prompt cũ bảo SAY đưa "sentence starter" | Bỏ hẳn, gợi ý chỉ nằm trong NOTE |
| Câu hỏi lại chép từ ví dụ mẫu | Model tự diễn đạt lại câu hỏi | App dùng `simple` soạn sẵn, LLM viết `ASK: NEXT` khi RETRY |
| Phản ứng với câu trả lời cũ | Câu trả lời mới bị đặt giữa tin nhắn | `Latest answer` đặt cuối, cộng luật "respond ONLY to the latest answer" |
| NOTE chép chi tiết từ ví dụ ("logistics coordinator") | Few-shot bị rò | `safe_note()` thay bằng khung mẫu câu nếu NOTE có từ trong `EXAMPLE_WORDS` mà người học chưa nói, hoặc khi RETRY mà chưa biết gì về người học |
| NOTE bịa thêm chi tiết | Câu nhận dạng sai, vô nghĩa | Luật "ONLY facts the candidate said", dùng "..." khi thiếu. Vẫn còn xảy ra, cần sửa ở phía STT |

## Khi sửa prompt

- Ví dụ few-shot cố ý lấy từ nghề **logistics**, khác nghề của người dùng (Java developer). Đổi nghề trong ví dụ thì phải cập nhật `EXAMPLE_WORDS`.
- Với model 7B, thêm ví dụ hiệu quả hơn thêm luật.
- Bắt buộc kiểm chứng bằng `scripts/replay.py` trên server thử (cổng 8001), chạy ít nhất 3 lần, từ thư mục `backend/`:

```
python -m scripts.replay answers.txt --runs 3 --url ws://localhost:8001/ws
```

  Dò: AI có nói ở ngôi thứ nhất không, có lặp câu hỏi không, có đi hết câu hỏi không, NOTE có bịa không.
  Số câu hỏi phụ thay đổi giữa các lần chạy, nên kịch bản cố định có thể lệch nhịp ở cuối. Đó không phải lỗi.
- Đặt `LM_SEED` trong `.env` nếu muốn các lần chạy dễ so hơn.
