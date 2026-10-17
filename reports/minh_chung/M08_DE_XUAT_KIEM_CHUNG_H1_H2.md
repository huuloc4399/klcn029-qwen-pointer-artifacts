# M08 · Đề xuất cách kiểm chứng H1 và H2

Bản đề xuất ngày 17/10/2026 để nhóm trao đổi và chốt với giảng viên hướng dẫn. Sau khi chốt, ghi quyết định vào mục 4 và vào `downstream/eval/DANG_KY_TRUOC.md` §7, **trước khi** xem kết quả tập test.

Giả thuyết gốc (`Ke_hoach_nghien_cuu_KLCN029.md`):

- **H1:** Chấm theo từng tiêu chí với đoạn CV làm bằng chứng làm giảm tỷ lệ nhận xét không có căn cứ so với prompt yêu cầu LLM cho một điểm tổng trực tiếp.
- **H2:** Bổ sung tri thức được tuyển chọn bằng RAG cải thiện chất lượng gợi ý chỉnh sửa CV so với cùng LLM không dùng RAG, nhưng không được phép biến nội dung truy xuất thành "thành tích" của ứng viên.
- **H3:** Đánh dấu "cần xác minh" khi trích xuất lỗi làm giảm sai lệch điểm giữa CV thiếu thông tin thật và CV đọc lỗi. Đã có thiết kế và công cụ (`perturb_h3`), không bàn ở đây.

## 1. H1

**Vấn đề với cách viết hiện tại:** hệ thống chưa có chiến lược "cho một điểm tổng trực tiếp". Mọi chiến lược đều chấm theo từng tiêu chí, nên H1 như đang viết chưa kiểm được.

**Phương án A (khuyến nghị): viết lại H1 cho khớp thiết kế đã chạy**

> H1': Chấm theo tiêu chí **có kiểm chứng trích dẫn bằng code** (P) làm giảm tỷ lệ điểm và nhận xét không có căn cứ trong CV, so với chấm theo tiêu chí mà LLM tự nêu bằng chứng không được kiểm (M1–M4).

- **Chỉ số tự động (toàn bộ tập test, không tốn thêm lượt gọi):** tỷ lệ điểm từ 1 trở lên mà đoạn bằng chứng LLM đưa ra **không tìm thấy nguyên văn trong CV**.
  - Cùng một hàm kiểm cho mọi chiến lược (`grounded_scoring.locate`).
  - Prompt của M1–M4 đã yêu cầu bằng chứng là "trích ngắn, nguyên văn từ CV", nên phép so sánh công bằng.
- **Hai so sánh:**
  1. P với M3: hiệu quả tổng thể.
  2. P với `p_no_verify` (P bỏ bước kiểm chứng): tách riêng tác dụng của bước kiểm chứng. Đây là so sánh sạch nhất vì hai bên chỉ khác đúng một thành phần.
- **Cái giá phải báo cáo kèm:** P đạt tỷ lệ có căn cứ cao một phần nhờ từ chối chấm. Vì vậy báo cáo luôn kèm tỷ lệ từ chối chấm và độ khớp với người (kappa), để không đổi chất lượng lấy việc chấm ít đi.
- **Kiểm tra bằng người (bổ sung, khoảng 1 giờ):**
  - Lấy ngẫu nhiên 40 nhận định (tiêu chí, điểm, bằng chứng, lý do) của P và 40 của M3 trên tập test, trộn lẫn, ẩn tên chiến lược.
  - Một người đánh dấu từng nhận định: "có căn cứ đúng", "có căn cứ nhưng sai ý", hoặc "không có căn cứ".
  - Mục đích: kiểm xem chỉ số tự động có phản ánh đúng đánh giá của người không.
- **Kết luận H1' được ủng hộ khi:** tỷ lệ không có căn cứ của P thấp hơn M3 và thấp hơn `p_no_verify`, với khoảng tin cậy 95% (bootstrap theo CV) của chênh lệch không chứa 0, **và** kappa của P không thấp hơn M3 quá 0,05.
- **Số liệu thăm dò trên dev** (đầu vào gold, chỉ để thấy chỉ số đo được, không dùng để kết luận):

| Chiến lược | Số điểm > 0 | Có bằng chứng tìm thấy trong CV |
|---|---|---|
| M1 | 77 | 68% |
| M2 | 76 | 59% |
| M3 | 77 | 69% |
| M4 | 77 | 65% |
| P | 71 | 100% (do thiết kế; 3,1% tiêu chí bị từ chối chấm) |

- **Cần làm thêm:** bằng chứng của M1–M4 có thể gộp nhiều đoạn trong một chuỗi. Trước khi chạy trên tập test, sẽ tách các đoạn theo dấu chấm phẩy và dấu nháy, rồi kiểm từng đoạn, để không tính oan là "không có căn cứ".

**Phương án B: giữ nguyên H1, thêm chiến lược M0 "điểm tổng trực tiếp"**

- M0 dùng prompt yêu cầu một điểm 0–100 và một đoạn nhận xét, không có rubric theo tiêu chí. Chi phí: 64 lượt gọi (32 cặp × 2 đầu vào), khoảng nửa ngày hạn mức.
- Đo bằng cách tách nhận xét của M0 và của P thành các khẳng định về CV, rồi người chấm đánh dấu khẳng định nào không có trong CV.
- Nhược điểm:
  - tốn công gán nhãn hơn nhiều;
  - M0 không có bằng chứng theo tiêu chí nên không dùng được chỉ số tự động;
  - phải thêm M0 vào cấu hình đã đăng ký trước. Làm được, nhưng phải ghi là thay đổi sau đăng ký.

## 2. H2

**So sánh sạch:** M3 với M1. Code xác nhận hai chiến lược dùng cùng prompt, cùng model; M3 chỉ thêm phần tri thức truy xuất (`rubric_scoring.score`). Cả hai đã nằm trong lần chạy tập test, nên **không tốn thêm lượt gọi**.

**Đơn vị đánh giá:** bộ gợi ý sửa CV (gợi ý của 6 tiêu chí C1–C6) của mỗi cặp, chỉ trên đầu vào gold để không lẫn lỗi trích xuất. Tổng cộng 32 cặp.

**Đánh giá bằng người, so sánh cặp mù:**

- Mỗi cặp hiện CV (PDF), JD và hai bộ gợi ý ghi là X và Y. Thứ tự M1/M3 được trộn ngẫu nhiên; người chấm không biết bên nào là RAG.
- Người chấm trả lời 3 câu:
  1. Bộ nào cụ thể, làm theo được hơn (X / Y / ngang nhau)?
  2. Bộ nào đúng với CV và rubric hơn (X / Y / ngang nhau)?
  3. Với **từng bộ**: có gợi ý nào bịa thông tin không, tức đề nghị ghi thêm kỹ năng, thành tích, số liệu, dự án mà CV không có (có / không)?
- Hai người chấm làm độc lập. Gợi ý: người chưa tham gia viết prompt và cơ sở tri thức; nếu dùng A và B thì làm sau vòng chính. Đo độ đồng thuận trên câu 1–2, sau đó phân xử như tập dev.
- Thời gian ước tính: 4–5 phút một cặp, khoảng 2,5 giờ mỗi người.

**Chỉ số tự động bổ sung (không tốn lượt gọi):**

- **Tỷ lệ gợi ý nêu kỹ năng mà CV không có:** dùng từ điển kỹ năng, so với kỹ năng trong CV.
- **Tỷ lệ gợi ý chứa con số không có trong CV và không nằm trong chỗ trống `[số liệu thật]`:** prompt đã cấm bịa số liệu.

**Kết luận H2 được ủng hộ khi:**
- M3 được chọn nhiều hơn M1 ở câu 1 hoặc câu 2 (kiểm định dấu trên các cặp không ngang nhau, mức 0,05);
- **và** tỷ lệ bịa thông tin của M3 không cao hơn M1 (câu 3 và hai chỉ số tự động).

Nếu M3 tốt hơn nhưng bịa nhiều hơn, H2 chỉ được ủng hộ một phần. Đây chính là vế "không được biến nội dung truy xuất thành thành tích" của giả thuyết.

**Phụ thuộc:** chất lượng gợi ý của M3 phụ thuộc cơ sở tri thức. Hiện 10/12 mục là quy ước nội bộ, nên cần Khải kiểm nguồn xong trước khi viết kết luận H2. Kết quả kiểm nguồn không đổi nội dung các mục đã dùng để chạy.

## 3. Lịch đề xuất

| Việc | Ai | Khi nào |
|---|---|---|
| Chốt phương án H1 (A hay B) và thiết kế H2 với giảng viên | Lộc, giảng viên hướng dẫn | Trước khi xem kết quả test |
| Ghi quyết định vào đăng ký trước | Claude | Ngay sau khi chốt |
| Viết script đo H1' và tạo phiếu so sánh cặp mù cho H2 | Claude | Trong lúc tập test chạy |
| Chấm H2 (2 người) và kiểm tra H1' bằng người (1 người) | Nhóm | Sau khi tập test chạy xong M1, M3, P |

## 4. Quyết định sau khi trao đổi với giảng viên

- H1: [phương án A / B / khác]
- H2: [đồng ý / chỉnh sửa]
- Người chấm H2: [tên]
- Ngày chốt: [ ]
