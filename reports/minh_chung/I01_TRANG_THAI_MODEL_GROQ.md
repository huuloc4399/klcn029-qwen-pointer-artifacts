# I01 · Trạng thái model trên Groq theo ngày chạy

Mục đích: model chấm điểm đang ở trạng thái Preview, nên có thể bị đổi hoặc ngừng. Mỗi lần chạy chính thức cần lưu lại Groq mô tả model thế nào **vào đúng ngày chạy**, để báo cáo nói được chính xác kết quả đến từ model nào, phục vụ ở cấu hình nào.

## Bản ghi

| Ngày truy cập | Lần chạy | Trạng thái | Thông số Groq công bố | Nguồn | Người ghi |
|---|---|---|---|---|---|
| 17/10/2026 | dev_v1, dev_v2 (gọi API ngày 16–17/10) | **Preview** ("chỉ để đánh giá, có thể ngừng với thông báo ngắn") | ID `qwen/qwen3.8-27b`; tên "Qwen/Qwen3.8-27B" của Alibaba Cloud; context 131 072 token; đầu ra tối đa 16 384 token; hỗ trợ JSON Schema Mode và Reasoning; lượng tử hóa TruePoint Numerics của Groq; giới hạn gói Developer 250K TPM, 1K RPM. Không có trong danh sách ngừng hỗ trợ; được Groq chỉ định thay thế `qwen/qwen3.6-27b` (ngừng ngày 14/09/2026) | [Trang danh sách model](https://console.groq.com/docs/models), [trang model](https://console.groq.com/docs/model/qwen/qwen3.8-27b), [trang ngừng hỗ trợ](https://console.groq.com/docs/deprecations) | Claude (đọc trang qua trình duyệt) |
| [ngày chạy test] | test_v1 | | | | |

## Ba điều trang Groq cho biết cần ghi vào báo cáo

1. **Preview, không phải Production.** Kết quả gắn với ngày chạy. Nếu model bị ngừng, việc chạy lại sẽ cho kết quả khác; báo cáo cần nêu điều này ở phần hạn chế.
2. **Groq phục vụ bản lượng tử hóa** (TruePoint Numerics: giảm độ chính xác số ở một số phần). Model chạy trên Groq vì vậy không hoàn toàn giống bộ trọng số gốc BF16 trên Hugging Face. Báo cáo ghi "Qwen3.8-27B do Groq phục vụ", không ghi chung chung là "Qwen3.8-27B".
3. **Khác khuyến nghị của nhà cung cấp.** Groq khuyến nghị dùng chế độ instruct (`reasoning_effort = "none"`) với nhiệt độ 0,7. Đề tài dùng nhiệt độ 0 để kết quả lặp lại được khi đánh giá. Đây là lựa chọn có chủ ý: ghi lý do này, và nêu rằng chất lượng ở nhiệt độ 0,7 chưa được đo.

## Cách ghi vào ngày chạy tập test

1. **Chụp qua API (bằng chứng máy đọc được).** Chạy ngay trước khi chạy tập test (và mỗi ngày nếu lần chạy kéo dài nhiều ngày vì hạn mức):
   ```bash
   python -m downstream.eval.model_snapshot --run-id test_v1 --model qwen/qwen3.8-27b
   ```
   Lệnh lưu câu trả lời của Groq kèm thời điểm vào `downstream/results/test_v1/model_snapshot.json`; khóa API không bị ghi vào file. Nếu lệnh báo lỗi 404 thì model đã bị gỡ: dừng lại và báo nhóm trước khi chạy tiếp.
2. **Lưu trang web (bằng chứng người đọc được).**
   - Mở `https://console.groq.com/docs/model/qwen/qwen3.8-27b`, nhấn Ctrl+P, chọn "Save as PDF", lưu thành `reports/minh_chung/groq_qwen3.8-27b_<YYYY-MM-DD>.pdf`.
   - Làm tương tự với `https://console.groq.com/docs/models`. Đây là trang cho biết model nằm ở nhóm Production, Preview hay Deprecated.
   - Mở thêm trang ngừng hỗ trợ `https://console.groq.com/docs/deprecations` và tìm "qwen3.8". Nếu có lịch ngừng, ghi ngày ngừng vào bảng trên.
3. **Điền một dòng vào bảng Bản ghi:** ngày, run-id, trạng thái, các thông số đọc được, tên hai file PDF, người ghi.
4. **Đối chiếu với run_config.json.** Tên model trong `downstream/results/test_v1/run_config.json` phải đúng `qwen/qwen3.8-27b`. Thời điểm gọi API của từng cặp nằm ở trường `scored_at` trong `predictions.jsonl`.
