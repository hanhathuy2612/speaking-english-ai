# Prompt LLM và NOTE

LLM: Qwen2.5-7B-Instruct qua LM Studio, `temperature` 0.35, `max_tokens` 160, có stream.

## Mã nguồn

| Phần | Vị trí (trong `backend/app/`) |
|---|---|
| System prompt | `SYSTEM_TEMPLATE` (`You play {role}.`), `DEFAULT_ROLE`, `build_messages()` trong `interview/prompts.py`. Vai theo bài: [conversation-mode.md](conversation-mode.md) |
| Ví dụ mẫu | `FEW_SHOT` (5 cặp user/assistant) trong `interview/prompts.py` |
| Tin nhắn mỗi lượt | `build_user_message()` trong `interview/prompts.py` |
| Gọi LLM | `stream_reply()` trong `services/llm.py` |
| Xử lý stream | `run_turn()` trong `interview/turn.py`, cùng `split_sections()` / `ready_sentences()` trong `utils/parsing.py` |
| Cắt lý do bịa trong NOTE | `trim_invented()` trong `interview/steps.py`, xem [answer-steps.md](answer-steps.md) |
| Chặn NOTE xấu | `safe_note()`, `EXAMPLE_WORDS` trong `interview/prompts.py`; `invented_facts()` trong `utils/compare.py`; `has_cjk()` trong `utils/parsing.py` |

## Định dạng đầu ra (4 dòng)

```
RETRY: yes|no
SAY: <phản ứng ngắn, ngôi thứ hai, dưới 15 từ, không phải câu hỏi>
ASK: <một câu hỏi phụ, hoặc NEXT>
NOTE: <câu của ứng viên viết lại tự nhiên hơn, ngôi thứ nhất, dưới 25 từ>
```

- RETRY đứng đầu để không bị cắt mất khi chạm `max_tokens`.
- SAY được TTS từng câu ngay khi viết xong. Câu nào trong SAY kết thúc bằng `?` thì bị bỏ, vì câu hỏi do app quyết định. Câu có chữ Hán/Nhật/Hàn (`has_cjk`) cũng bị bỏ, không bao giờ đọc.
- NOTE chỉ hiện chữ, không đọc (người học bấm "Nghe câu này" nếu muốn).
- NOTE người học thấy = câu LLM viết, sau `safe_note()` và `trim_invented()` (xem mục dưới).
- Output không có nhãn nào: app báo "AI trả sai định dạng" và tự chuyển câu. Chỉ thiếu SAY (khoảng 1/30 lượt): app im lặng chuyển câu, chỉ ghi log `LLM output had no SAY`.

## Tin nhắn user mỗi lượt

```
Earlier in the interview:          (tối đa MAX_HISTORY cặp hỏi/đáp)
- Q: ... A: ...
Current question: ...
Target phrase: ...                 ("none (follow-up question)" khi đang ở câu hỏi phụ)
Follow-up allowed: yes|no
Latest answer: ...                 (luôn để cuối)
```

## NOTE ngắn, các ý để nói dài hơn hiện riêng

NOTE vẫn là một câu ngắn đã sửa. Lý do người học chưa nói mà model tự thêm vào NOTE bị `trim_invented()` cắt; các ý nên thêm (lý do, ví dụ, mặt trái...) hiện riêng dưới NOTE, viết sẵn cho từng câu hỏi. Xem [answer-steps.md](answer-steps.md).

## Mẫu câu theo ý kiến (`phrases[].when`)

Câu "Do you agree?" từng chỉ có mẫu phản đối, model nhét mẫu đó vào nên NOTE đảo ý kiến người học. Đưa cả hai mẫu cho model tự chọn thì nó chọn sai phía (5/5 lần sau khi thêm ví dụ few-shot). Nay mẫu câu có `when` (ví dụ "I see your point, but I think ..." với `don't agree`, `disagree`...) chỉ được gửi làm Target phrase khi câu trả lời có một trong các cụm đó; nếu không thì chỉ gửi các mẫu không có `when` (`target_phrases()` trong `prompts.py`).

## Các lỗi đã gặp và cách chặn

| Lỗi | Nguyên nhân | Cách chặn |
|---|---|---|
| AI nói câu trả lời thay ứng viên ("I'm responsible for...") | Prompt cũ gọi model là "coach", mẫu câu ở ngôi thứ nhất, luật "reuse the correct form" | Khóa vai INTERVIEWER, SAY ngôi thứ hai, mẫu câu chỉ nằm trong NOTE |
| Lời gợi ý mở đầu câu bị đọc như lời người phỏng vấn | Prompt cũ bảo SAY đưa "sentence starter" | Bỏ hẳn, gợi ý chỉ nằm trong NOTE |
| Câu hỏi lại chép từ ví dụ mẫu | Model tự diễn đạt lại câu hỏi | App dùng `simple` soạn sẵn, LLM viết `ASK: NEXT` khi RETRY |
| Phản ứng với câu trả lời cũ | Câu trả lời mới bị đặt giữa tin nhắn | `Latest answer` đặt cuối, cộng luật "respond ONLY to the latest answer" |
| NOTE chép chi tiết từ ví dụ ("logistics coordinator") | Few-shot bị rò | `safe_note()` thay bằng khung mẫu câu nếu NOTE có từ trong `EXAMPLE_WORDS` mà người học chưa nói, hoặc khi RETRY mà chưa biết gì về người học |
| Câu hỏi phụ trùng câu chính sắp tới ("How did you ensure this wouldn't happen again?" ngay trước câu chính hỏi đúng điều đó) | Bài STAR có sẵn câu chính cho từng bước, model không biết câu nào còn ở sau | Bài STAR đặt `"followups": 0` trong `units.json`. **Đã thử và bỏ:** gửi danh sách "Later questions" kèm luật cấm hỏi trùng; model 7B lại chép nguyên câu trong danh sách làm câu hỏi phụ (cả 6/6 lần chạy) |
| NOTE bịa thêm chi tiết | Câu nhận dạng sai, vô nghĩa | Luật "ONLY facts the candidate said", dùng "..." khi thiếu. Vẫn còn xảy ra, cần sửa ở phía STT |
| NOTE đổi chi tiết của người học ("if the design come tomorrow" → "comes in on Friday", 2/2 lần ở `standup`) | Model "sửa" cả nội dung | `safe_note()` dùng `invented_facts()`: NOTE có số, thứ, tháng, today/tomorrow/yesterday mà người học chưa nói (và không có trong mẫu câu) thì thay bằng khung mẫu câu. So sau khi chuẩn hóa như shadowing ("2-0" = "two zero"); bỏ qua "one" và "may" |
| NOTE chuyển sang tiếng Trung giữa câu (2/3 lần ở `microservices`) | Qwen thỉnh thoảng lẫn ngôn ngữ | NOTE có chữ CJK thì thay bằng khung mẫu câu; câu SAY có chữ CJK thì không đọc |
| NOTE ở ngôi thứ hai ("You enjoy solving…") | Model nói về người học thay vì viết câu cho người học nói | NOTE bắt đầu bằng "You" thì thay bằng khung mẫu câu |
| NOTE đảo ý kiến của người học (đồng ý "social media wastes too much time" → "I see your point, but… social media can be useful", 3/3 lần ở `opinions`) và bịa thêm lý do | Câu hỏi "Do you agree?" chỉ có mẫu câu phản đối, model cố dùng mẫu câu nên đổi luôn ý kiến | Câu hỏi kiểu đồng ý/phản đối có mẫu câu cho cả hai phía, app chọn theo câu trả lời (`phrases[].when`, mục trên). Prompt có thêm luật "NOTE keeps the candidate's opinion" và ví dụ few-shot "night shift" (giữ ý kiến, không thêm lý do). Replay sau khi sửa: đồng ý 3/3, phản đối 2/2 đúng phía. Lý do bịa thêm bị `trim_invented()` cắt ([answer-steps.md](answer-steps.md)) |
| NOTE bỏ sót lỗi dùng từ ("improve my production" giữ nguyên, trong khi SAY dùng đúng "productivity") và đổi từ đồng nghĩa chỉ để chèn mẫu câu ("I think" → "In my opinion") | Model ưu tiên chèn Target phrase hơn sửa lỗi | Luật "NOTE first fixes every grammar mistake and every wrong word choice... do not swap in synonyms" và ví dụ few-shot "scanning app" (production → productivity). Replay với prompt cuối: sửa đúng 3/4 lần, chưa ổn định hẳn với model 7B |
| NOTE ở lượt trả lời câu hỏi phụ viết lại câu trả lời **trước đó** | App vẫn gửi mẫu câu của câu chính, model cố nhét mẫu câu đó vào | Ở câu hỏi phụ gửi `Target phrase: none (follow-up question)` |

## Khi sửa prompt

- Ví dụ few-shot cố ý lấy từ nghề **logistics** (cả ví dụ "night shift", "scanning app in the warehouse"), khác nghề của người dùng (Java developer). Đổi nghề trong ví dụ thì phải cập nhật `EXAMPLE_WORDS`.
- Với model 7B, thêm ví dụ hiệu quả hơn thêm luật.
- Bắt buộc kiểm chứng bằng `scripts/replay.py` trên server thử (cổng 8001), chạy ít nhất 3 lần, từ thư mục `backend/`:

```
python -m scripts.replay answers.txt --runs 3 --url ws://localhost:8001/ws
```

  Dò: AI có nói ở ngôi thứ nhất không, có lặp câu hỏi không, có đi hết câu hỏi không, NOTE có bịa không.
  Số câu hỏi phụ thay đổi giữa các lần chạy, nên kịch bản cố định có thể lệch nhịp ở cuối. Đó không phải lỗi.
- Đặt `LM_SEED` trong `.env` nếu muốn các lần chạy dễ so hơn.
