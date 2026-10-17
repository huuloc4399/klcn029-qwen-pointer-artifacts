# Báo cáo tiến độ thực hiện khóa luận

Đề tài: Nghiên cứu hệ thống hỗ trợ đánh giá và cải thiện cv sử dụng mô hình ngôn ngữ lớn  
Giảng viên hướng dẫn: ThS. Huỳnh Thị Cẩm Dung  
Sinh viên thực hiện: 2001230468-Nguyễn Hữu Lộc-14DHTH01; 2001230364-Dương Chí Khải-14DHTH01; 2001230169-Lê Tâm Đắc-14DHTH03  
Tp. hồ chí minh, tháng 10 năm 2026

## 1. Tóm tắt

Nhóm đã hoàn thành pipeline trích xuất CV sang CVSchema 2.0, hai giai đoạn huấn luyện QLoRA trên Qwen3-4B, bộ đánh giá có truy vết, bộ nhãn chuẩn GOLD40 (20 CV tiếng Anh, 20 CV tiếng Việt) và demo đánh giá CV theo JD trên Colab.

Kết quả chính: mô hình fine-tune đạt Field Micro F1 99,52% trên test tổng hợp, nhưng trên CV thật GOLD40 chỉ đạt 48,28%, thấp hơn Qwen gốc (65,52%). Nhóm đã phân tích và xác định nguyên nhân chính: dữ liệu train tổng hợp khác CV thật cả về hình thức văn bản, quy tắc gán nhãn lẫn độ phủ, nên mô hình học thuộc quy ước của bộ tổng hợp thay vì học cách đọc CV. Báo cáo này trình bày bằng chứng và kế hoạch khắc phục.

## 2. Công việc đã hoàn thành

Các hạng mục đã hoàn thành đến ngày 11/10/2026 được tổng hợp trong Bảng 1.

*Bảng 1: Các hạng mục đã hoàn thành*

| Hạng mục | Kết quả |
| --- | --- |
| Dữ liệu | 80 CV thật (60 EN, 20 VI); 1.000 CV tổng hợp chia 850/75/75; schema CV/JD |
| Nhãn chuẩn | GOLD40 chốt ngày 10/10 (40/40 hợp lệ schema); web app gán nhãn và web app rà nhãn độc lập |
| OCR | Pilot trên 5 trang tiếng Việt: VietOCR đạt Token F1 94–97%, PaddleOCR Latin 55,81%; đã chọn phương án lai cho tiếng Việt |
| Huấn luyện | Stage 1 Full JSON và stage 2 Hybrid Pointer (QLoRA, 1 epoch, Colab T4); đủ adapter, log, audit |
| Đánh giá | Parser và metric khóa trước test; đã đo trên validation/test tổng hợp, 80 CV thật và GOLD40 |
| Kiểm chứng/retry | P1 nâng tỷ lệ CV hợp lệ schema trên 80 CV thật từ 71/80 lên 78/80 |
| Hạ nguồn | Matching M1/M2/M3, chấm điểm và gợi ý có mã và demo; chưa có benchmark có nhãn |
| Demo | Web Flask chạy local; Colab chạy đầu cuối CV–JD; cloud tạm dừng do ngân sách |

## 3. Kết quả trích xuất

B0 là Qwen gốc; B1 là adapter stage 1 (Full JSON); P0 là adapter stage 2 (Pointer); P1 là P0 cộng kiểm chứng và retry. Bảng 2 so sánh Field Micro F1 của bốn cấu hình trên test tổng hợp và trên GOLD40.

*Bảng 2: Field Micro F1 trên test tổng hợp và GOLD40*

| Cấu hình | Test tổng hợp | GOLD40 thật |
| --- | --- | --- |
| B0 | 87,98% | 65,52% |
| B1 | 99,52% | 48,28% |
| P0 | 99,19% | 49,66% |
| P1 | Chưa đo | 52,81% |

Trên GOLD40, khoảng tin cậy 95% (bootstrap ghép cặp theo CV) của chênh lệch B1 so với B0 là −22,58 đến −11,75 điểm phần trăm; khoảng không chứa 0 nên mức giảm không phải dao động ngẫu nhiên giữa các CV trong nhóm này. P1 tốt hơn P0 (+3,14 điểm) nhưng vẫn thấp hơn B0. Tiếng Việt kém hơn tiếng Anh ở mọi cấu hình (B0: 72,23% EN, 58,52% VI). GOLD40 được dùng để phân tích lỗi nên từ nay không còn là tập test độc lập.

## 4. Nguyên nhân mô hình tốt trên dữ liệu tổng hợp nhưng kém trên CV thật

Eval loss giảm đều đến cuối cả hai run (stage 1: 0,0154 → 0,0112 → 0,0109), nên chưa thấy dấu hiệu train quá lâu. Nguyên nhân là test tổng hợp cùng nguồn sinh, cùng 3 template và cùng quy tắc nhãn với train: F1 99% đo mức tuân theo quy ước của bộ tổng hợp. Dấu hiệu: tỷ lệ CV đúng toàn bộ trên test tổng hợp tăng từ 1/75 (Qwen gốc) lên 57/75 sau fine-tune. Có ba nhóm lệch, đều có số đo.

### 4.1. Lệch hình thức văn bản đầu vào

Bảng 3 so sánh hình thức văn bản nguồn đưa vào mô hình giữa dữ liệu train tổng hợp và CV thật.

*Bảng 3: Hình thức văn bản nguồn của train tổng hợp và GOLD40*

| Đặc điểm văn bản nguồn | Train tổng hợp | GOLD40 thật |
| --- | --- | --- |
| Summary nằm trọn trên một dòng | 617/617 | 0/38 |
| CV có dòng gạch đầu dòng (•, -) | 0/850 | 27/40 |
| CV có một dòng chứa từ 3 kỹ năng trở lên | 24/850 | 31/40 |
| CV tiếng Việt | 0/850 | 20/40 |

Mô hình học các quy tắc tắt: mỗi dòng trong mục Skills là một kỹ năng, mỗi đoạn văn là một dòng. Khi gặp CV thật, các quy tắc này gây lỗi:

- B1 chép nguyên dòng "Programming: C#, JavaScript, Python" thành một kỹ năng; 78/176 mục kỹ năng của B1 chứa dấu ":" (B0: 37/513). F1 kỹ năng cứng của B1 chỉ 13,69%, của B0 là 58,33%.

- P0 trỏ khoảng dòng quá ngắn cho văn bản dài bị ngắt nhiều dòng, nên summary bị cắt giữa câu. Trong 102 văn bản dài P0 sinh ra (gold có 151): 22 khớp, 16 chỉ sai vì giữ ký hiệu gạch đầu dòng, 11 bị cắt cụt, 12 lấy lố sang phần khác, 11 chỉ là một đoạn nhỏ. Vì vậy Long Text F1 của P0 chỉ 17,39%.

- B1 chèn dòng chức danh vào đầu summary và bỏ sót cụm từ ở đoạn bị ngắt từng từ một dòng.

### 4.2. Lệch quy tắc gán nhãn

- Converter dữ liệu tổng hợp không đưa công nghệ của dự án vào hard skills (543/544 CV train có công nghệ dự án bị thiếu), trong khi hướng dẫn gán nhãn gold có đưa vào. Ngoại ngữ cũng không được đưa vào nhãn kỹ năng.

- Soft skills trong train chỉ có một giá trị duy nhất là "Communication".

### 4.3. Thiếu độ phủ dữ liệu train

- Không có CV tiếng Việt; không có ví dụ có giá trị cho GitHub (gold có 30), GPA (28), activities (6), awards (2).

- Chỉ 3 template; 1 epoch trên dữ liệu đồng nhất như vậy đủ để thói quen tổng hợp lấn át năng lực đọc CV sẵn có của Qwen gốc. B1 còn sinh activities dạng object ở 3 CV tiếng Việt, làm hỏng schema.

Giới hạn: phân tích này thực hiện hậu kiểm trên GOLD40; nhãn gold đang được rà lại. Các cải tiến dưới đây phải được xác nhận trên dữ liệu mới.

## 5. Kế hoạch khắc phục

Kế hoạch gồm tám bước, đi từ các thay đổi không cần GPU đến huấn luyện lại và xác nhận trên dữ liệu mới (Bảng 4).

*Bảng 4: Kế hoạch khắc phục*

| Bước | Nội dung | Cần GPU | Kiểm chứng |
| --- | --- | --- | --- |
| 1 | Hậu xử lý Pointer: bỏ ký hiệu gạch đầu dòng, nối dòng bị ngắt, dừng khoảng dòng tại tiêu đề mục | Không | Unit test, dev thật |
| 2 | Tách kỹ năng dạng "Nhóm: a, b, c"; hợp công nghệ dự án và ngoại ngữ vào hard skills theo quy tắc gold | Không | Unit test, dev thật |
| 3 | Chốt quy tắc nhãn chung cho train, gold và prompt; hoàn tất rà GOLD40 bằng PDF | Không | Biên bản phân xử, gold v2 |
| 4 | Lập tập dev thật: 37 CV tiếng Anh còn lại của Real80 (bỏ EN043 trùng EN024 trong GOLD40) cộng CV tiếng Việt mới thu thập, vì cả 20 CV tiếng Việt đã nằm trong GOLD40 | Không | Hai người gán, đo đồng thuận |
| 5 | So sánh B0 + hậu xử lý, B0 few-shot với CV thật, P1 + hậu xử lý trên tập dev | Chỉ suy luận | F1 dev thật, EN/VI |
| 6 | Dataset v2: render CV tổng hợp ra PDF nhiều bố cục rồi trích text như pipeline thật; thêm tiếng Việt, các trường còn thiếu và CV thật | Không | Thống kê như Bảng 3 |
| 7 | Huấn luyện lại; chọn checkpoint theo F1 trên dev thật, không theo loss tổng hợp | Có | So với baseline tốt nhất ở bước 5 |
| 8 | Xác nhận cấu hình cuối trên nhóm CV mới, khóa trước khi chạy | Có | Báo kết quả một lần |

Nguyên tắc: giữ nguyên metric v1 và kết quả đã đo; không sửa gold theo output mô hình; không đưa GOLD40 vào train. Nếu sau bước 7 fine-tune vẫn không vượt Qwen gốc, nhóm sẽ dùng Qwen gốc kèm hậu xử lý và kiểm chứng cho hệ thống, và trình bày phân tích dịch chuyển miền như một kết quả nghiên cứu.

## 6. Đề nghị ý kiến giảng viên

- Nhóm đề xuất dùng 37 CV tiếng Anh còn lại của Real80 làm tập phát triển, thu thập thêm CV tiếng Việt cho tập phát triển, và một nhóm CV mới làm tập kiểm tra cuối. Giảng viên có đồng ý và có gợi ý nguồn thu thập CV không?

- Nếu fine-tune không vượt Qwen gốc, kết luận "Qwen gốc + hậu xử lý + kiểm chứng" kèm phân tích nguyên nhân có đáp ứng yêu cầu của đề tài không?

- Phạm vi hard skills có nên gồm công nghệ dự án và ngoại ngữ như hướng dẫn gold hiện tại không?

## 7. Tài liệu kèm theo

- Báo cáo chi tiết cấu hình huấn luyện, số liệu và phụ lục từng trường: `reports/BAO_CAO_TONG_HOP_DU_LIEU_HUAN_LUYEN_VA_DANH_GIA_2026-10-11.docx`

- Chẩn đoán lệch nhãn và độ phủ dữ liệu: `reports/GOLD40_CHAN_DOAN_TONG_QUAT_HOA_VA_RASOAT_2026-10-11.md`

- Script và số đo lệch hình thức đầu vào ở mục 4.1: `training/audits/gold40_input_shift_2026-10-11_v1/`

- Kết quả GOLD40 đã khóa: `training/evaluation/results/gold40_b0_b1_p0_p1_v1/`
