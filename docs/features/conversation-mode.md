# Chế độ trò chuyện: AI đóng vai khác người phỏng vấn

Mục đích: luyện nói ngoài phỏng vấn (nói chuyện phiếm, standup, họp, code review…). Vẫn dùng đúng luồng của phòng tập: **app giữ danh sách câu hỏi**, LLM chỉ phản ứng, hỏi tối đa một câu phụ và viết NOTE (xem [interview-flow.md](interview-flow.md)). Chỉ khác vai của AI.

## Mã nguồn

| Phần | Vị trí |
|---|---|
| Vai AI trong prompt | `DEFAULT_ROLE`, `SYSTEM_TEMPLATE` (`You play {role}.`), `build_messages()` trong `backend/app/interview/prompts.py` |
| Nhãn hiện trên tin nhắn AI | `partner` trong tin `started` (`start_session()`, `backend/app/interview/turn.py`), `Chat.tsx` |
| Nội dung | `units.json`: chủ đề `daily` và `workplace` |
| Test | `test_interview_prompt_is_unchanged_by_the_role_field`, `test_conversation_units_name_the_partner` trong `backend/tests/test_units.py` |

## Trường trong `units.json`

| Trường | Ví dụ | Mặc định |
|---|---|---|
| `role` (tiếng Anh, vào prompt) | `"a TEAM LEAD running the daily stand-up meeting"` | `"the INTERVIEWER in a job interview"` |
| `partner` (tiếng Việt, hiện trên giao diện) | `"Trưởng nhóm"` | `"Người phỏng vấn"` |

- Bài phỏng vấn không có `role`, nên system prompt **giống từng chữ** bản đã kiểm chứng bằng replay (có test).
- `scenario` của bài trò chuyện mở đầu bằng "This is not an interview." để model không quay về giọng phỏng vấn.
- Các luật cũ vẫn giữ: AI nói ở ngôi thứ hai, không kể về bản thân, câu mẫu ngôi thứ nhất chỉ nằm trong NOTE.

## Nội dung (12 bài)

| Chủ đề | Bài | Vai AI |
|---|---|---|
| Giao tiếp hằng ngày | `weekend`, `hometown`, `hobbies`, `daily-routine`, `a-trip`, `opinions` | Đồng nghiệp, trò chuyện lúc uống cà phê |
| Tiếng Anh ở công ty | `standup` | Trưởng nhóm |
| | `explain-a-bug` | Đồng nghiệp senior |
| | `code-review` | Người review pull request |
| | `meeting-disagree` | Quản lý sản phẩm (người học nêu rủi ro, đề xuất phương án) |
| | `feature-demo` | Quản lý xem demo cuối sprint |
| | `clarifying` | Khách hàng đưa yêu cầu mơ hồ (người học đặt câu hỏi) |

**Bài người học đặt câu hỏi** (`clarifying`): lời của khách hàng trong `questions[].ask` phải **chứa sẵn thông tin** (báo cáo nào, chậm bao lâu, hạn chót). Bản đầu chỉ có câu chung chung, nên khi người học hỏi "Could you give me an example…", AI chỉ đáp "That helps" mà không đưa thông tin gì.

## Kiểm chứng (replay, 11/10/2026)

`weekend`, `opinions`, `standup`, `meeting-disagree`, `clarifying` (sau khi sửa), mỗi bài 2 lần: AI đúng vai, phản hồi ngắn, NOTE sửa đúng lỗi thì (go → went, win → won), đi hết các câu. Các lỗi tìm thấy khi chạy đã được chặn ở `safe_note()` (xem [llm-prompt.md](llm-prompt.md)): NOTE đổi chi tiết ("tomorrow" → "on Friday"), NOTE lẫn tiếng Trung.
