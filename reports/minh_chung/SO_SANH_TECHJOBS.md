# So sánh với công cụ "Kiểm tra" CV của TechJobs.vn

Ngày xem: 17/10/2026, trên tài khoản của Lộc, với CV của chính Lộc. Claude đọc trang kết quả và chỉ mở rộng hai danh sách để xem, không sửa CV hay cài đặt. Đây là trang sản phẩm, không phải công bố khoa học (khóa `techjobs2026` trong `../TAI_LIEU_THAM_KHAO.md`). Tài liệu này chỉ ghi cách chấm, không ghi nội dung CV.

## 1. TechJobs chấm thế nào (suy ra từ kết quả)

**Điểm cơ bản = điểm checklist, không phụ thuộc JD.**
- Có 16 tiêu chí chia 4 nhóm. Điểm tối đa của từng nhóm: Nền tảng 17, Chất lượng bullet 18, Kỹ năng và giới thiệu 8, Ngôn ngữ và trình bày 10; tổng 53.
- Mỗi tiêu chí không đạt bị trừ điểm trong nhóm của nó. Điểm 0–100 = tổng điểm 4 nhóm / 53.
- Kiểm bằng phép tính: các nhóm đạt 14,5 + 8,9 + 5,5 + 7 = 35,9 điểm, 35,9 / 53 = 67,7 ≈ **68**. Tổng điểm trừ của 10 việc là 17,0 = 53 − 35,9 (lệch 0,1 do làm tròn). Mỗi nhóm cũng khớp, ví dụ Nền tảng: 17 − 2 (CV 2 trang) − 0,5 (chưa ghi GPA) = 14,5.
- Mức trừ theo tỉ lệ số mục vi phạm: 17/17 bullet chưa có số liệu bị trừ 8 điểm (cả nhóm); 9/17 bullet chưa mở đầu bằng động từ bị trừ 0,6; 5 bullet quá ngắn hoặc quá dài bị trừ 0,1.
- Mức độ: "Quan trọng", "Nên sửa", "Gợi ý nhỏ". Có thêm "Gợi ý thêm, không ảnh hưởng điểm" (dùng AI trong công việc, link GitHub).
- Có hai hồ sơ chấm: "Tổng quát" và "Big Tech (chặt hơn)".
- Ghi chú: "không phải điểm ATS và không dự đoán khả năng được gọi phỏng vấn"; "100 điểm không phải mục tiêu, từ 'Tốt' là đủ để gửi".

**Các tiêu chí thấy được** (10 không đạt, 2 điểm mạnh, 2 gợi ý không tính điểm): bullet có số liệu; số trang (người mới 1 trang); kỹ năng xuất hiện trong kinh nghiệm hoặc dự án (13/20 chưa có); dấu chấm cuối bullet đồng nhất; viết hoa đầu bullet đồng nhất; bullet mở đầu bằng động từ hành động; có GPA; kỹ năng chia nhóm; không quá 5 bullet mỗi vị trí; độ dài bullet (dưới khoảng 60 ký tự là quá chung); mỗi vị trí nêu công nghệ (đạt); không dùng cụm sáo rỗng (đạt).

**Các phần khác** (theo trang chủ):
- "Chấm sâu bằng AI" đánh giá bullet có kết quả không, dự án có chiều sâu không. Phần này tách riêng, chỉ cho tài khoản đăng nhập, vì tốn lượt gọi model.
- Khớp CV–JD là công cụ riêng, theo 6 chỉ số: kỹ năng, chức vụ, cấp bậc, ngoại ngữ, học vấn, độ mới của JD.
- Khi AI viết lại CV, gợi ý thêm số liệu hoặc kỹ năng không có trong CV gốc bị chặn.

**Giao diện kết quả:**
- Điểm lớn kèm nhãn mức, ghi chú diễn giải, danh sách điểm mạnh, 4 thanh điểm nhóm.
- "Việc nên làm (N)" sắp theo số điểm bị trừ. Mỗi việc có mức độ, số đếm cụ thể, lời khuyên, "Gặp ở" (vị trí trong CV), nút "Đi tới chỗ cần sửa", nút "Không áp dụng cho tôi" và "−X điểm".
- Chỉ hiện 3 việc đầu, có nút "Xem tất cả".

## 2. Đối chiếu với đồ án

| Khía cạnh | TechJobs | Đồ án |
|---|---|---|
| Điểm tổng | Chất lượng CV, không phụ thuộc JD | Gộp chất lượng CV (C1–C7) với phù hợp JD (C8, 25%) |
| Cách chấm | 16 kiểm tra cơ học, đếm được, trừ điểm cộng dồn | 8 tiêu chí 0–4 theo mô tả mức; bộ luật hoặc LLM; P kiểm trích dẫn |
| Chiều sâu nội dung | Để cho "Chấm sâu bằng AI" (tốn phí) | LLM chấm trực tiếp (M1–M4, P) |
| Kiểm chứng với người | Không công bố | Hai người chấm, phân xử, kappa so với nhãn FINAL |
| Thiếu thông tin hoặc đọc lỗi | Không thấy cơ chế riêng | P từ chối chấm, hiện "cần xác minh" và độ bao phủ |
| Khớp JD | 6 chỉ số, có cấp bậc, ngoại ngữ, học vấn | Tỉ lệ yêu cầu bắt buộc đáp ứng, có trích dẫn từng yêu cầu |
| Chống bịa | Chặn gợi ý thêm số liệu hoặc kỹ năng không có | Prompt cấm; đo tỉ lệ bịa cho H2 |

**Tiêu chí của TechJobs ánh xạ sang rubric:**

| Kiểm tra của TechJobs | Rubric của đồ án | Ghi chú |
|---|---|---|
| Bullet có số liệu | C4, C5 mức 4 (kết quả đo được); cơ sở tri thức `kb_impact_bullet` | Cùng ý; họ đếm tỉ lệ bullet, đồ án xét 1–2 dự án liên quan nhất |
| Số trang | C1 (1–2 trang) | **Khác:** họ trừ điểm CV 2 trang với người mới; rubric chấp nhận 1–2 trang. Cần nguồn để chốt (việc của Khải, R03) |
| Kỹ năng xuất hiện trong kinh nghiệm hay dự án | C3 (kỹ năng có minh chứng) | Cùng ý; họ tính trên mọi kỹ năng, hướng dẫn chấm của đồ án xét tối đa 5 kỹ năng chính |
| Dấu chấm, viết hoa đồng nhất | C1 danh sách kiểm tra (2) "định dạng nhất quán" | Họ kiểm bằng máy, chính xác hơn đồ án ở phần này |
| Động từ hành động | Cơ sở tri thức `kb_action_verbs` | Không có trong mô tả mức của rubric |
| Kỹ năng chia nhóm | C3 mức 4 | Cùng ý |
| Có GPA | Không có tiêu chí học vấn | Khác phạm vi |
| Số bullet mỗi vị trí, độ dài bullet | Không có | Chi tiết trình bày |
| Không dùng cụm sáo rỗng | Không có | |
| Link GitHub hoặc portfolio | C4 mức 4 (repo, demo kiểm chứng được) | Họ để là gợi ý không tính điểm |
| (không có) | C7 khả năng ATS | Họ nói rõ không chấm ATS |

**Nhận xét:**
- Phần chấm cơ bản của TechJobs rất giống bộ luật (`baseline_rules`) của đồ án: kiểm cơ học, nhanh, miễn phí. Trên dev, bộ luật của đồ án đạt kappa 0,76, ngang các phương pháp LLM. Điều này ủng hộ việc tách "checklist miễn phí" khỏi "chấm sâu bằng AI".
- Điểm riêng của đồ án: đo độ khớp với người chấm, kiểm chứng trích dẫn và từ chối chấm khi trích xuất có thể đã mất nội dung.
- Một lần chấm trên một CV cho điểm gần nhau (68 so với đồ án, theo quan sát của Lộc) chỉ là ca đơn lẻ, không dùng làm minh chứng. So sánh có hệ thống chỉ làm trên CV của thành viên nhóm tự nguyện, sau khi đọc điều khoản của TechJobs; không tải CV trong tập dữ liệu lên dịch vụ ngoài.

## 3. Áp dụng vào đồ án

**Giao diện kết quả của bản demo.** Chỉ đổi cách trình bày (`result.html`, `app.py`, CSS), không đổi code chấm nên không ảnh hưởng tập test. Tham khảo cách bố trí, không sao chép giao diện hay nhận diện thương hiệu của TechJobs.

1. Đầu trang:
   - điểm lớn, nhãn mức, một câu "từ mức Khá là đủ để gửi";
   - ghi chú: "điểm tham khảo theo rubric của đề tài, không phải điểm ATS của nhà tuyển dụng, không dự đoán khả năng được gọi phỏng vấn".
2. Tách hai điểm cùng tính từ kết quả hiện có:
   - **Chất lượng CV** (C1–C7, trung bình có trọng số);
   - **Phù hợp với JD** (C8 và bảng yêu cầu).
3. Thanh điểm 8 tiêu chí dạng "điểm đạt / trọng số", ví dụ "C4 Dự án 11,25/15".
4. "Việc nên làm (N)":
   - mỗi tiêu chí chưa đạt mức 4 là một việc, kèm **"+X điểm nếu đạt mức tối đa"** = trọng số × (4 − điểm) / 4 / tổng trọng số × 100;
   - mức độ theo X: Quan trọng từ 5 điểm, Nên sửa 1–5, Gợi ý nhỏ dưới 1;
   - kèm gợi ý và bằng chứng của tiêu chí, nút "Đi tới chỗ cần sửa" (tới mục CV tương ứng), nút "Không áp dụng cho tôi" (đánh dấu `not_applicable`, tính lại điểm và độ bao phủ ngay trên trang);
   - chỉ hiện 3 việc đầu.
5. "Cần xác minh": các tiêu chí P từ chối chấm. TechJobs không có phần này, nên đây là điểm khác biệt của đồ án.
6. "Gợi ý thêm, không ảnh hưởng điểm": các yêu cầu bắt buộc của JD còn thiếu, và yêu cầu `unclear`.
7. Số đếm cụ thể chỉ để hiển thị, không cộng vào điểm: số bullet có số liệu, số kỹ năng có minh chứng / tổng kỹ năng, số bullet mở đầu bằng động từ. Đếm từ CVSchema đã trích xuất.

**Cho báo cáo:**
- Chương 2: TechJobs là hệ thống tương tự trong nước (mục 1–2 ở trên).
- Phần thảo luận: so sánh triết lý thiết kế (checklist kèm AI tách riêng, so với rubric có kiểm chứng với người).
- Hướng phát triển: thêm cấp bậc, ngoại ngữ, học vấn vào phần khớp JD; thêm kiểm tra cơ học về định dạng bullet vào C1.

**Không làm:** đổi rubric hay prompt theo TechJobs trước khi chạy xong tập test (cấu hình đã khóa). Chênh lệch "1 trang hay 2 trang" ghi lại để chốt khi có nguồn (R03).
