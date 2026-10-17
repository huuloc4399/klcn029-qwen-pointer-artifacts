# Đăng ký trước: cấu hình, luật chọn tham số và chỉ số chính cho tập dev và tập test

Viết ngày 17/10/2026, trước khi tính bất kỳ chỉ số nào của phương pháp P. Commit chứa file này là mốc thời gian; mọi thay đổi sau đó phải thêm vào mục 7 kèm lý do, không sửa nội dung cũ.

## 1. Trạng thái dữ liệu lúc viết

- `downstream/results/dev_v2`: M1–M4 và bộ luật đã chạy xong trên đầu vào gold (M4 trên b0 xong 8/16 cặp). `p_grounded` có 19 kết quả hợp lệ và 7 lỗi do hạn mức; các biến thể P khác chưa chạy. **Chưa tính chỉ số nào của P.** Báo cáo `dev_v2` đã xem chỉ chứa M1–M4 và bộ luật.
- Nhãn dev: `downstream/data/labels_v1/FINAL_dev.jsonl` (SHA-256 bắt đầu `fb580164`), quy trình trong `GHI_CHU_PHIEN_BAN_PILOT.md`.
- Nhãn test: chưa có; hai người chấm nộp hạn 20/10/2026 theo hướng dẫn bản 3.

## 2. Cố định từ thiết kế, không chọn trên dev

Tập dev chỉ có 8 CV, nên khoảng tin cậy quá rộng để chọn giữa các biến thể. Vì vậy các lựa chọn sau được cố định trước và không đổi theo kết quả dev:

| Mục | Giá trị cố định |
|---|---|
| Phương pháp đề xuất | `p_grounded` với đủ thành phần: kiểm chứng trích dẫn và hỏi lại một lần, từ chối chấm khi thiếu căn cứ, cờ mất nội dung `LOW_TEXT_RATIO = 0,25`, kiểm tra yêu cầu khái niệm |
| Biến thể bỏ bớt một thành phần | `p_no_verify`, `p_no_abstain`, `p_no_concept_check`: chỉ báo cáo để đo đóng góp từng thành phần, không thay thế phương pháp chính |
| Phương pháp so sánh chính | `m3_rag` (cùng model, rubric, tri thức truy xuất) |
| Model và tham số | theo `run_config.json` của `dev_v2`: `qwen/qwen3.8-27b`, nhiệt độ 0, seed 42, truy xuất bm25 |
| Rubric và prompt | `rubric_v2_draft1`; code `rubric_scoring.py` giữ nguyên hash như `dev_v2` (quyết định 17/10: không chỉnh C2/C3, không đổi `REQUIREMENT_GUIDE`) |

## 3. Luật chọn `COVERAGE_MIN` (không dùng nhãn người)

- `COVERAGE_MIN` chỉ quyết định có **hiện điểm tổng** hay không; điểm từng tiêu chí và các chỉ số đồng thuận không phụ thuộc vào nó.
- Ứng viên: 0,50; 0,60; 0,70; 0,75; 0,80; 0,85; 0,90.
- Với mỗi ứng viên, tính tỉ lệ kết quả `p_grounded` trên dev (đầu vào gold và b0 gộp lại) có điểm tổng được hiện: độ bao phủ ≥ ngưỡng và C3, (C4 hoặc C5), C8 đều chấm được.
- **Chọn ngưỡng cao nhất có tỉ lệ hiện điểm tổng ≥ 80%.** Không ngưỡng nào đạt thì lấy 0,50 và báo cáo đó là một phát hiện.
- Chỉ áp luật khi có ít nhất 90% số kết quả dự kiến (16 cặp × 2 đầu vào).
- Lý do của 80%: đây là yêu cầu sử dụng của hệ thống (đa số CV phải nhận được điểm tổng), không phải chỉ số khớp với người, nên luật không thể bị chỉnh theo nhãn.
- Cách tính: `python -m downstream.eval.lock_config --run-id dev_v2`, ghi kết quả vào `downstream/results/dev_v2/coverage_rule.json`.

## 4. Chỉ số và so sánh trên tập test

Tập test chạy **một lần** với cấu hình ở mục 2–3, mọi chiến lược, đầu vào gold và b0, so với nhãn FINAL của tập test (phân xử theo đúng quy trình dev).

**So sánh chính (một so sánh duy nhất):** `p_grounded` với `m3_rag`, trên từng đầu vào:

1. Kappa bậc hai gộp 8 tiêu chí so với nhãn FINAL.
2. Spearman điểm tổng so với điểm tổng của người.

Chênh lệch kèm KTC 95% bootstrap theo CV (2000 lần, seed 42). Chỉ kết luận P khác M3 khi khoảng tin cậy không chứa 0. Mọi so sánh khác là thăm dò, báo cáo đầy đủ nhưng không dùng để kết luận.

**Chỉ số phụ:** kappa và MAE theo tiêu chí; kappa trạng thái yêu cầu (P so với bộ luật K; M1–M4 không xuất trạng thái yêu cầu), tách theo yêu cầu từ điển và khái niệm; tỉ lệ tuân thủ rubric; tỉ lệ trích dẫn hợp lệ; tỉ lệ từ chối chấm và tỉ lệ hiện điểm tổng; chi phí (số lần gọi, token, thời gian); tách riêng CV tiếng Anh và tiếng Việt.

## 5. Giả thuyết và cách kiểm chứng

| Giả thuyết | Cách kiểm chứng | Trạng thái |
|---|---|---|
| H1: chấm theo tiêu chí có bằng chứng giảm nhận xét không căn cứ | Tỉ lệ điểm > 0 có trích dẫn tìm thấy trong CV, so giữa P và M1–M4 | Cần chốt cách đo trích dẫn của M1–M4; kế hoạch gốc so với "prompt cho một điểm tổng trực tiếp", chiến lược này chưa có |
| H2: RAG cải thiện gợi ý sửa CV | Chưa có quy trình đánh giá gợi ý | **Chưa có thiết kế**, cần quyết định |
| H3: đánh dấu cần xác minh giảm sai lệch giữa CV thiếu thật và CV đọc lỗi | `perturb_h3`: 10 CV test × {gốc, đọc lỗi, thiếu thật} | Cơ chế đã kiểm (cờ bắt 9/10 ca đọc lỗi, 0/10 ca thiếu thật); chờ chạy LLM |

## 6. Điều không làm

- Không chỉnh prompt, rubric, danh sách từ hay ngưỡng sau khi xem kết quả test.
- Không loại cặp test nào khỏi phân tích, trừ cặp có trích xuất không hợp lệ, và việc loại này áp dụng như nhau cho mọi chiến lược.
- Không chạy lại tập test để chọn lần chạy tốt hơn.

## 7. Thay đổi sau đăng ký

(chưa có thay đổi nào với luật hay cấu hình)

## 8. Kết quả áp luật

- 17/10/2026, `python -m downstream.eval.lock_config --run-id dev_v2`: 32/32 kết quả `p_grounded`. Mọi ứng viên từ 0,50 đến 0,90 đều hiện điểm tổng cho 100% kết quả (gold và b0), nên luật chọn **`COVERAGE_MIN` = 0,90**. Kết quả lưu ở `downstream/results/dev_v2/coverage_rule.json`; giá trị đã ghi vào `grounded_scoring.py`.
- Nhận xét: trên dev, P gần như không từ chối chấm tiêu chí nào, nên ngưỡng này chưa được thử thách. Tác dụng của việc từ chối chấm cần được đánh giá bằng phép thử H3 và trên tập test.
- Biến thể bỏ bớt thành phần (`p_no_concept_check`, `p_no_verify`, `p_no_abstain`) không dùng để chọn cấu hình (§2), nên không bắt buộc chạy trên dev; chúng được chạy và báo cáo trên tập test.
