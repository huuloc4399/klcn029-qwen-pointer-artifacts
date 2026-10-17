# I01 · Lý do chọn model chấm điểm

Cập nhật 17/10/2026 (đã có xác nhận của nhóm về ngân sách). Mã I01 trong Sổ quyết định và minh chứng. Số liệu lấy từ hai lần chạy `dev_v1` và `dev_v2` (16–17/10/2026).

## Quyết định

Mọi chiến lược chấm dùng LLM (M1–M4 và P) gọi **cùng một model `qwen/qwen3.8-27b` qua Groq API**, với cấu hình:
- nhiệt độ 0, seed 42, `reasoning_effort = none`;
- đầu ra ép theo JSON Schema chế độ strict. Nếu dịch vụ từ chối schema thì chuyển sang `json_object`.

Cấu hình được ghi tự động trong `run_config.json` của mỗi lần chạy, và đã cố định trong `downstream/eval/DANG_KY_TRUOC.md` §2.

## Lý do và minh chứng

| # | Lý do | Minh chứng |
|---|---|---|
| 1 | Mọi chiến lược dùng cùng một model và tham số, nên chênh lệch giữa M1–M4 và P đến từ phương pháp, không từ model | `run_config.json` của `dev_v2`: một bộ điều kiện chung cho mọi chiến lược |
| 2 | Đầu ra phải đúng cấu trúc để code kiểm điểm và trích dẫn; Groq hỗ trợ JSON Schema strict | Tỉ lệ tuân thủ rubric 100% ở mọi chiến lược LLM trong báo cáo `dev_v2` |
| 3 | Chi phí: nhóm không có ngân sách cho API trả phí (nhóm xác nhận ngày 17/10/2026), nên dùng gói miễn phí của Groq | Xác nhận của nhóm; chi phí đo được ở bảng dưới |
| 4 | Cùng model đã dùng làm baseline trích xuất, nên hạ tầng gọi API, che dữ liệu cá nhân và xử lý lỗi đã được kiểm thử | `Ke_hoach_nghien_cuu_KLCN029.md` (baseline trích xuất: Qwen trên Groq, `qwen/qwen3.8-27b`, JSON Schema strict); `baseline_extraction/` |
| 5 | Model Qwen3-4B được huấn luyện cho trích xuất CVSchema, không được huấn luyện cho chấm theo rubric, nên khâu chấm dùng model lớn qua prompt | Kế hoạch nghiên cứu: thành phần huấn luyện là Qwen 4B cho Resume Parsing (SFT/QLoRA) |
| 6 | Nhiệt độ 0 và seed cố định để kết quả lặp lại được ở mức dịch vụ cho phép | `rubric_scoring.py` `groq_caller` |
| 7 | `reasoning_effort = none` để giảm token và thời gian | Là lý do thiết kế, **chưa đo** so sánh với chế độ có suy luận |

**Chi phí đo được** (chỉ tính các kết quả gọi thật, không tính kết quả dùng lại):

| Chiến lược | Số kết quả | Lượt gọi/cặp | Token vào/cặp | Token ra/cặp | Giây/cặp |
|---|---|---|---|---|---|
| M1 zero-shot | 32 | 1 | 2 851 | 517 | 27,8 |
| M2 few-shot | 32 | 1 | 3 144 | 495 | 23,2 |
| M3 RAG | 32 | 1 | 3 311 | 514 | 30,6 |
| M4 nhiều tác tử | 24 | 3 | 7 398 | 1 140 | 65,1 |
| P (`p_grounded`) | 19 | 1,37 | 4 149 | 2 274 | 39,6 |

## Ràng buộc, rủi ro và cách xử lý

- **Hạn mức gói miễn phí.** `dev_v1` phải chạy tiếp 8 lần, `dev_v2` 9 lần; có 17 lượt lỗi do vượt hạn mức hoặc dịch vụ quá tải. Các lượt lỗi không tạo kết quả sai, chỉ phải chạy lại. Cách xử lý:
  - bộ chạy ghi kết quả từng cặp và tiếp tục từ chỗ dừng;
  - chờ theo `retry-after` khi bị giới hạn theo phút, dừng hẳn khi hết hạn mức ngày (`--max-wait`).
- **Model ở trạng thái Preview** (đã kiểm trên trang Groq ngày 17/10/2026), nên có thể bị thay đổi hoặc ngừng. Mỗi kết quả đều ghi tên model và thời điểm gọi (`scored_at`): các lần chạy dev diễn ra ngày 16–17/10/2026. Bản ghi trạng thái theo ngày và cách ghi vào ngày chạy test: `I01_TRANG_THAI_MODEL_GROQ.md`.
- **Groq phục vụ bản lượng tử hóa** (TruePoint Numerics), không hoàn toàn giống trọng số gốc BF16. Báo cáo ghi "Qwen3.8-27B do Groq phục vụ".
- **Nhiệt độ 0 khác khuyến nghị 0,7 của Groq cho chế độ instruct.** Đề tài chọn 0 để kết quả lặp lại được khi đánh giá; chất lượng ở nhiệt độ 0,7 chưa được đo.
- **Nhiệt độ 0 không bảo đảm tất định trên dịch vụ.** Các lần chạy dev chỉ chạy 1 lần mỗi cặp (`repeats = 1`), nên độ dao động giữa các lần chạy chưa được đo. Nếu còn hạn mức: chạy lặp 3 lần trên một nhóm nhỏ cặp dev bằng `--repeats 3`; nếu không, ghi là hạn chế.
- **Dữ liệu cá nhân gửi ra dịch vụ ngoài.** Trước khi gửi:
  - email, số điện thoại và dòng tên ứng viên được che (`baseline_extraction/privacy.py`, `redact_text`);
  - bản demo web xin đồng ý của người dùng;
  - CV và nhãn không đưa lên git.
- **Chỉ một model.** Kết luận chỉ đúng cho model này; chưa so với model khác. Đây là hạn chế về khả năng khái quát.
- **CV tiếng Việt.** Khả năng xử lý hai ngôn ngữ phải được chứng minh bằng kết quả tách riêng EN và VI trên tập test (đăng ký trước §4), không suy ra từ việc model hỗ trợ nhiều ngôn ngữ.

## Việc còn lại

- Tài liệu: đã thêm `qwen38` (trích dẫn chính thức của Qwen3.8), model card và trang Groq vào `TAI_LIEU_THAM_KHAO.md` (17/10/2026); còn phải mở bài blog của Qwen để đối chiếu nội dung.
- Ghi trạng thái model trên trang Groq vào ngày chạy tập test.
