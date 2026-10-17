# Báo cáo dữ liệu huấn luyện và đánh giá mô đun trích xuất CV

Đề tài CNTT KLCN029 | Báo cáo cho giảng viên hướng dẫn | Cập nhật ngày 11 tháng 10 năm 2026

Nhóm đã hoàn tất hai giai đoạn QLoRA trên Qwen3 4B, đánh giá sinh tự do trên validation và test tổng hợp, chạy Pointer trên 80 CV thật và so sánh bốn cấu hình trên GOLD40. Fine-tuning cải thiện rõ trên test tổng hợp, nhưng chưa vượt Qwen gốc trên CV thật. Kiểm chứng và retry tăng tính hợp lệ đầu ra Pointer, đồng thời phát sinh thêm lần gọi model.

Phạm vi báo cáo là dữ liệu, OCR và trích xuất CVSchema 2.0. Các số dưới đây không đo chất lượng matching CV–JD, chấm điểm hoặc sinh gợi ý của các mô đun khác. Các bảng đều gắn với artifact đã lưu; các thí nghiệm mới sau rà gold chưa được thực hiện.

## 1 Dữ liệu và cách sử dụng

| Bộ dữ liệu | Số CV | Ngôn ngữ | Vai trò |
| --- | --- | --- | --- |
| Train tổng hợp | 850 | 850 EN | Cập nhật gradient cả stage 1 và stage 2 |
| Validation tổng hợp | 75 | 75 EN | Theo dõi loss và phân tích lỗi |
| Test tổng hợp | 75 | 75 EN | Đánh giá sau khóa parser |
| CV thật | 80 / 110 trang | 60 EN và 20 VI | Đo cấu trúc và hiệu năng P0/P1 |
| GOLD40 thuộc real80 | 40 / 60 trang | 20 EN và 20 VI | Đánh giá nội dung hậu kiểm B0/B1/P0/P1 |

Dataset tổng hợp là sukhrobnurali/resume-parsing-vision, revision 3c254be39d45f69c6e20bfb325b4e6ccb3b5e393, giấy phép CC-BY-4.0 theo manifest nguồn. Bộ đã được chuyển thành CVSchema 2.0 và Hybrid Pointer v1. Hai stage dùng lại cùng 850 CV train, không phải 1.700 CV khác nhau. Chỉ split train dùng cập nhật gradient.

Dữ liệu tổng hợp không có source/target trùng hoàn toàn giữa train, validation và test theo audit đã đo. Ba template train gồm sidebar 271, two_column 267 và classic 312. Không có trùng nguyên văn không bảo đảm độc lập về mẫu sinh hoặc cấu trúc gần trùng.

Input đóng băng real80 có 77 canonical ID trên 80 bản ghi. GOLD40 có 40 canonical ID cho 40 bản ghi theo mapping đó. Bộ corpus ở giai đoạn chuẩn bị khác có quy tắc deduplicate khác; không dùng số lượng của một phiên bản thay cho số mẫu của benchmark đã khóa.

GOLD40 đã được tổng hợp từ hai thành viên và phân xử; nhãn A/B trước phân xử không còn lưu nên không thể đo IAA lịch sử. Ba mẫu VI003, VI005, VI017 từng được trợ lý hỗ trợ hoàn tất theo yêu cầu. Chất lượng nội dung đang được rà lại bằng PDF; chưa có gold v2 được chấp nhận.

## 2 Phương pháp và cấu hình đã chạy

| Mã | Model và biểu diễn | Vai trò |
| --- | --- | --- |
| B0 | Qwen3 4B gốc, Full JSON | Baseline zero-shot |
| B1 | Adapter stage 1, Full JSON | Fine-tuning trên nhãn tổng hợp |
| P0 | Adapter stage 2, Hybrid Pointer | Sinh trường ngắn và khoảng dòng cho trường dài |
| P1 | P0 và validator với một retry tối đa | Chọn CV lỗi và sinh lại toàn JSON Pointer |

Model chung là Qwen/Qwen3-4B-Instruct-2507, revision 1b4199c4f36b0cef378bfb12390c18780c18af4c. Stage 2 tiếp tục adapter stage 1 trên nhãn Pointer; full stage 2 không dùng adapter smoke làm điểm xuất phát. B0 và B1 dùng cùng prompt Full JSON trong từng benchmark; Pointer thêm đánh số dòng và hợp đồng span.

Nhóm chọn QLoRA để thực hiện yêu cầu có huấn luyện trong giới hạn Colab T4; kết quả VRAM bên dưới kiểm chứng khả năng chạy cấu hình này. Full fine-tuning cần cập nhật toàn bộ base, còn prompt-only là baseline B0 và không đáp ứng riêng yêu cầu huấn luyện. Các siêu tham số là cấu hình đã chốt của run, chưa có tìm kiếm siêu tham số để chứng minh tối ưu.

Hybrid Pointer dùng khoảng dòng cho summary, experience.description và projects.details nhằm bảo toàn nguyên văn và giảm phần văn bản model phải sinh. Lựa chọn một lượt giữ các trường của cùng entity trong một object và giảm lặp input so với nhiều prompt chuyên biệt; đề tài chưa có đối chứng nhiều prompt để kết luận phương án một lượt tốt hơn. P1 bổ sung kiểm chứng/retry cho lỗi cấu trúc và span có thể phát hiện mà không cần gold; chưa sửa được mọi lỗi ngữ nghĩa.

| Thông số | Stage 1 Full JSON | Stage 2 Pointer full |
| --- | --- | --- |
| Train / validation | 850 / 75 | 850 / 75 |
| Epoch / optimizer steps | 1 / 107 | 1 / 107 |
| Batch mỗi thiết bị / accumulation | 1 / 8 | 1 / 8 |
| Batch hiệu dụng | 8 | 8 |
| Learning rate | 0.0002 | 5e-05 |
| Optimizer / scheduler | paged_adamw_8bit / cosine | paged_adamw_8bit / cosine |
| Warmup ghi trong contract | warmup_steps = 0.03 | warmup_steps = 0.03 |
| Weight decay / max grad norm | 0.01 / 0.3 | 0.01 / 0.3 |
| LoRA rank / alpha / dropout | 16 / 32 / 0.05 | 16 / 32 / 0.05 |
| LoRA target modules | all-linear | all-linear |
| Lượng tử hóa base | 4-bit NF4, double quantization | 4-bit NF4, double quantization |
| Precision / attention | FP16 / SDPA | FP16 / SDPA |
| Maximum sequence length | 5.120 token | 5.120 token |
| Loss / masking | chunked_nll / completion-only | chunked_nll / completion-only |
| Packing / seed | False / 42 | False / 42 |
| Lưu checkpoint / eval | Mỗi 20 / 40 bước | Mỗi 20 / 40 bước |

Cấu hình warmup được chép nguyên khóa và giá trị trong contract để tái lập; không tự đổi thành số bước nguyên hoặc phần trăm khác. Gradient checkpointing được bật. Checkpoint có optimizer state để resume; local giữ 2 checkpoint, Drive giữ 3 theo contract. Tham số adapter trainable được nâng FP32 trong luồng FP16 đã sửa lỗi AMP.

Adapter lưu 504 tensor FP32 với 33,030,144 tham số LoRA, tương đương khoảng 33,03 triệu. Base được lượng tử hóa và giữ cố định; đây là QLoRA, không phải full fine-tuning tất cả tham số base.

Các run huấn luyện dùng Colab T4 theo hồ sơ notebook/audit. Môi trường B0/B1 GOLD40 được ghi trực tiếp là Tesla T4, Python 3.13.15, PyTorch 2.11.0+cu130 và CUDA 13.0. Đây là môi trường benchmark GOLD40, không thay thế log môi trường của mọi run trước.

| Thư viện trong contract train | Phiên bản |
| --- | --- |
| transformers | 5.17.0 |
| trl | 1.13.0 |
| peft | 0.21.0 |
| accelerate | 1.15.0 |
| bitsandbytes | 0.50.2 |
| datasets | 5.0.1 |
| huggingface_hub | 1.32.0 |
| tokenizers | 0.23.2 |

## 3 Kết quả huấn luyện đã đo

| Run | Train/val | Steps | Train loss | Eval loss | Token accuracy |
| --- | --- | --- | --- | --- | --- |
| Stage 1 full | 850/75 | 107 | 0,002952 | 0,010912 | 99,9482% |
| Stage 2 smoke | 16/8 | 2 | 0,031515 | 0,018196 | 99,6441% |
| Stage 2 full | 850/75 | 107 | 0,016707 | 0,014881 | 99,9497% |

| Run | Trainer giây | Trainer phút | Eval cuối giây | Allocated GiB | Reserved GiB |
| --- | --- | --- | --- | --- | --- |
| Stage 1 full | 2.292,47 | 38,21 | 235,73 | 8,184 | 12,447 |
| Stage 2 smoke | 285,75 | 4,76 | 34,85 | 8,671 | 9,561 |
| Stage 2 full | 10.552,24 | 175,87 | 269,84 | 8,703 | 9,562 |

VRAM dùng GiB vì mã đo chia byte cho 1024³, dù khóa JSON có hậu tố _gb. Reserved và allocated là hai đại lượng khác nhau, không cộng lại. Trainer runtime và runtime phiên hoàn tất đã ghi không bao gồm toàn bộ cài đặt, tải model, thời gian chờ hoặc mất kết nối; stage 1 có resume nên 38,21 phút không được coi là tổng thời gian từ đầu đến cuối hoặc dùng để kết luận train nhanh hơn stage 2.

Smoke dùng 16 mẫu train và 8 mẫu validation dài nhất, chỉ 2 optimizer steps. Nó kiểm tra khả năng chạy, lưu trọng số và parse output; không đại diện chất lượng mô hình full. Mẫu quick smoke có hai span chọn nhầm dòng tên dự án thay vì mô tả.

### 3 1 Loss validation theo các mốc đã lưu

| Run | Step | Epoch | Eval loss | Eval token accuracy |
| --- | --- | --- | --- | --- |
| Stage 1 | 40 | 0,376 | 0,015352 | 99,5554% |
| Stage 1 | 80 | 0,753 | 0,011234 | 99,9367% |
| Stage 1 | 107 | 1,000 | 0,010912 | 99,9482% |
| Stage 2 full | 40 | 0,376 | 0,015829 | 99,9407% |
| Stage 2 full | 80 | 0,753 | 0,015044 | 99,9432% |
| Stage 2 full | 107 | 1,000 | 0,014881 | 99,9497% |

Loss validation giảm ở ba mốc của cả hai stage. Token accuracy là đánh giá dự đoán token khi có prefix mục tiêu, không tương đương chất lượng sinh tự do. Train loss tổng của run có resume và eval loss toàn tập khác phạm vi tích lũy; không dùng riêng tỷ số hai loss để khẳng định overfitting.

### 3 2 Chuẩn bị nhãn Pointer và độ dài

| Chỉ tiêu chuyển đổi | Kết quả |
| --- | --- |
| CV round-trip đúng CVSchema | 1000/1000 |
| Slot trường dài | 6175 |
| Span contiguous / null | 5906 / 269 |
| Alignment mơ hồ | 0 |
| Giảm ký tự assistant target | 52,48% |
| Tăng ký tự source do đánh số dòng | 15,33% |

| Split | p50 | p95 | p99 | Max | Vượt 5.120 |
| --- | --- | --- | --- | --- | --- |
| train | 2137 | 2629 | 2775 | 2890 | 0 |
| validation | 2176 | 2626 | 2764 | 2828 | 0 |

Độ dài trên tính bằng tokenizer Qwen cho hội thoại Pointer. Giảm ký tự không phải giảm token; lợi ích token khi inference được đo riêng bên dưới. Round-trip hoàn hảo chỉ xác nhận chuyển đổi nhãn nguồn đúng, không xác nhận nhãn nguồn đầy đủ theo quy tắc gold thật.

## 4 Quy tắc đánh giá và ý nghĩa chỉ số

- Strict JSON: raw output parse trực tiếp. Recoverable JSON: chỉ bỏ wrapper đã cho phép trong parser đóng băng; không sửa JSON thiếu hoặc bị cắt.

- CVSchema-valid: đủ khóa và đúng kiểu. Nó chưa xác nhận dữ kiện đúng PDF. Chính sách Communication-only của bộ tổng hợp được báo riêng; không dùng để loại CV thật schema-valid khỏi tính F1.

- Field Micro F1: tập giá trị theo 19 trường, chuẩn hóa Unicode NFKC, casefold và khoảng trắng. Không tự dịch, gộp synonym hoặc bỏ dấu câu. Tên, email và điện thoại đã mask không thuộc 19 trường đo.

- Precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = 2TP/(2TP+FP+FN). Output schema-invalid được tính như dự đoán rỗng; không bỏ CV đó khỏi mẫu.

- Macro F1 chỉ trên field có gold support. Trường không có ví dụ dương có thể không có F1 áp dụng; không được xem nhãn luôn rỗng là bằng chứng trích xuất tốt.

- Document exact: toàn cấu trúc nội dung khớp theo cách chuẩn hóa của evaluator tương ứng. F1 52,81% không có nghĩa 52,81% số CV hoàn toàn đúng.

- Span contract kiểm tra kiểu và giới hạn dòng. Span exact so với gold đo chọn dòng đúng. Dựng đúng văn bản của một span được chọn không có nghĩa span đó bao phủ thông tin đúng.

Parser Full JSON v1 và Pointer v1 đã khóa trước test tổng hợp. Một số quy tắc wrapper được phát triển trên validation, vì vậy validation là tập phát triển; GOLD40 được đánh giá hậu kiểm và đã dùng để nghiên cứu lỗi. Tập xác nhận cho cải tiến tiếp theo phải có dữ liệu mới.

## 5 Kết quả validation tổng hợp

| Chỉ tiêu | B0 Full JSON | B1 Full JSON | P0 Pointer |
| --- | --- | --- | --- |
| Strict JSON | 73/75 (97,33%) | 0/75 (0,00%) | 0/75 (0,00%) |
| Recoverable JSON | 73/75 (97,33%) | 75/75 (100,00%) | 75/75 (100,00%) |
| CVSchema-valid | 73/75 (97,33%) | 75/75 (100,00%) | 75/75 (100,00%) |
| Policy tổng hợp hợp lệ | 35/75 (46,67%) | 74/75 (98,67%) | 75/75 (100,00%) |
| Document exact | 0/75 (0,00%) | 61/75 (81,33%) | 64/75 (85,33%) |
| Field Precision | 88,73% | 99,64% | 99,68% |
| Field Recall | 87,41% | 99,55% | 99,61% |
| Field Micro F1 | 88,06% | 99,60% | 99,64% |
| Macro F1 field có support | 77,62% | 98,77% | 98,98% |
| Long Text Micro F1 | 95,71% | 100,00% | 100,00% |
| Chạm giới hạn token | 2 | 0 | 0 |

| Model | Output token tổng | Token/CV | Giây/CV | p50 giây | p95 giây |
| --- | --- | --- | --- | --- | --- |
| B0 | 61091 | 814,55 | 70,32 | 69,62 | 110,92 |
| B1 | 45728 | 609,71 | 97,18 | 99,05 | 149,17 |
| P0 | 28623 | 381,64 | 61,22 | 65,61 | 83,88 |

Pointer span exact cho slot gold khác null: 440/440. Chỉ số này đọc theo phạm vi span của evaluator, tách khỏi schema gate và Document exact.

Kết quả B1 ban đầu ngày 27/09 dùng checker cũ: recoverable 71/75, document exact 57/75, Micro F1 97,25%. Bốn wrapper </tool_call> được checker cũ từ chối. Bảng chính dùng parser v1 đã thống nhất, đạt recoverable 75/75 và F1 99,60%. Hai con số thể hiện thay đổi parser trên cùng validation, không phải hai lần train hoặc cải thiện model mới.

Trên validation Pointer, validator không có retry_targets nên cổng P1 không gọi thêm model và cho kết quả hiệu dụng bằng P0. Không có một run P1 độc lập để chứng minh cải thiện trên tập này. So với B1, P0 tăng Document exact từ 61/75 lên 64/75.

## 6 Kết quả test tổng hợp đã khóa

| Chỉ tiêu | B0 Full JSON | B1 Full JSON | P0 Pointer |
| --- | --- | --- | --- |
| Strict JSON | 73/75 (97,33%) | 0/75 (0,00%) | 0/75 (0,00%) |
| Recoverable JSON | 73/75 (97,33%) | 75/75 (100,00%) | 75/75 (100,00%) |
| CVSchema-valid | 73/75 (97,33%) | 75/75 (100,00%) | 74/75 (98,67%) |
| Policy tổng hợp hợp lệ | 40/75 (53,33%) | 75/75 (100,00%) | 74/75 (98,67%) |
| Document exact | 1/75 (1,33%) | 57/75 (76,00%) | 62/75 (82,67%) |
| Field Precision | 88,39% | 99,55% | 99,68% |
| Field Recall | 87,58% | 99,49% | 98,70% |
| Field Micro F1 | 87,98% | 99,52% | 99,19% |
| Macro F1 field có support | 78,58% | 98,85% | 98,60% |
| Long Text Micro F1 | 92,96% | 100,00% | 99,56% |
| Chạm giới hạn token | 2 | 0 | 0 |

| Model | Output token tổng | Token/CV | Giây/CV | p50 giây | p95 giây |
| --- | --- | --- | --- | --- | --- |
| B0 | 62641 | 835,21 | 72,22 | 69,19 | 115,25 |
| B1 | 47059 | 627,45 | 92,82 | 94,18 | 139,56 |
| P0 | 28948 | 385,97 | 58,13 | 55,67 | 80,92 |

Pointer span exact cho slot gold khác null: 458/458. Chỉ số này đọc theo phạm vi span của evaluator, tách khỏi schema gate và Document exact.

Trên test tổng hợp, B1 tăng Micro F1 từ 87,98% lên 99,52% so với B0. P0 đạt 99,19%, thấp hơn B1 0,34 điểm phần trăm; Document exact tăng từ 57/75 lên 62/75. Mẫu rpv_r00826 thiếu activities và awards nên Pointer parser từ chối toàn output. Chưa chạy P1 riêng trên test này.

B0/B1 dùng giới hạn 1.280 token; P0 test dùng 768 token theo config đã lưu. P0 không chạm giới hạn và tối đa đã sinh 569 token; B0 có 2 mẫu chạm giới hạn. Chênh lệch ngân sách là một giới hạn đối chứng cần công bố, không gọi mọi điều kiện decoding hoàn toàn giống nhau.

P0 test giảm 38,49% output token trung bình so với B1. Latency trung bình đã ghi giảm khoảng 37,37%; các run ở phiên khác nhau nên đây là mô tả số đo, chưa là thử nghiệm kiểm soát để xác nhận tốc độ do kiến trúc.

## 7 Kết quả trên 80 CV thật

| Chỉ tiêu | P0 | P1 hiệu dụng |
| --- | --- | --- |
| CVSchema-valid | 71/80 (88,75%) | 78/80 (97,50%) |
| Model calls | 80 | 89 |
| Output token tổng | 26590 | 30027 |
| Thời gian sinh phút | 68,98 | 78,15 |
| CV còn bị từ chối | 9/80 | 2/80 |

Nguồn đầu vào: 79 CV dùng text PDF, chỉ EN047 dùng PaddleOCR tiếng Anh. Tất cả 20 VI dùng embedded text. P1 retry 9 CV, khôi phục 7/9, còn EN011 và VI006 cần review. P0 valid EN 56/60, VI 15/20; P1 valid EN 59/60, VI 19/20.

P1 tăng 8,75 điểm phần trăm schema validity, phát sinh thêm 11,25% model calls, 12,93% output token và 13,29% runtime sinh. Cả 9 retry kết thúc EOS, không chạm 1.280 token. Bộ 80 chưa có nhãn nội dung cho toàn bộ nên không báo F1/accuracy nội dung trên đủ 80; GOLD40 là nhóm có gold bên dưới.

## 8 Kết quả GOLD40 thật

| Chỉ tiêu | B0 | B1 | P0 | P1 |
| --- | --- | --- | --- | --- |
| CVSchema-valid | 40/40 (100,00%) | 35/40 (87,50%) | 34/40 (85,00%) | 39/40 (97,50%) |
| Precision | 64,25% | 60,65% | 58,97% | 57,89% |
| Recall | 66,84% | 40,10% | 42,89% | 48,54% |
| Micro F1 | 65,52% | 48,28% | 49,66% | 52,81% |
| Micro F1 EN | 72,23% | 52,16% | 55,88% | 57,20% |
| Micro F1 VI | 58,52% | 44,16% | 42,46% | 48,05% |
| Macro F1 supported | 60,28% | 48,40% | 45,80% | 50,17% |
| Long Text F1 | 52,73% | 39,86% | 17,39% | 16,60% |
| Short Field F1 | 66,93% | 49,32% | 53,05% | 56,54% |
| Document exact | 0/40 | 0/40 | 0/40 | 0/40 |
| TP / FP / FN | 1030/573/511 | 618/401/923 | 661/460/880 | 748/544/793 |

B0 có Field Micro F1 cao nhất trên GOLD40. P1 khôi phục 5 output bị từ chối P0 và tăng recall; precision giảm. P1 chưa cải thiện mọi tiêu chí: Long Text F1 giảm từ 17,39% xuống 16,60%, Document exact vẫn 0. B0 không đứng đầu tất cả tiêu chí entity; bảng entity riêng trong phụ lục tránh suy rộng kết luận từ Micro F1.

| Cấu hình | F1 điểm | CI 95 phần trăm |
| --- | --- | --- |
| B0 | 65,52% | 61,03% đến 69,51% |
| B1 | 48,28% | 42,27% đến 53,76% |
| P0 | 49,66% | 42,68% đến 55,48% |
| P1 | 52,81% | 47,52% đến 57,51% |

Khoảng trên dùng bootstrap 5.000 lần, seed 42, phân tầng 20 EN/20 VI và lấy lại toàn CV. Không xem từng field là mẫu độc lập. Khoảng giữ cố định nhãn và nhóm quan sát; chưa bao gồm sai số nhãn hoặc thiên lệch chọn mẫu.

| So sánh ghép cặp | Delta F1 điểm phần trăm | CI 95 điểm phần trăm |
| --- | --- | --- |
| B1 so với B0 | -17,24 | -22,58 đến -11,75 |
| P0 so với B1 | 1,38 | -4,32 đến 6,79 |
| P1 so với P0 | 3,14 | 0,79 đến 6,77 |
| P1 so với B0 | -12,72 | -17,52 đến -7,74 |

Bootstrap ghép cặp này dùng 2.000 lần, seed 42, cũng phân tầng theo ngôn ngữ. P1 tốt hơn P0 trên nhóm quan sát, nhưng P1 vẫn thấp hơn B0. P0 so với B1 có khoảng chứa 0; chưa có bằng chứng rõ về cải thiện F1. Đây là kết quả hậu kiểm, không suy rộng trực tiếp sang quần thể ứng viên.

### 8 1 Chi phí suy luận trên cùng GOLD40

| Model | Calls | Input token | Output token | Tổng token | Phút sinh |
| --- | --- | --- | --- | --- | --- |
| B0 | 40 | 73839 | 32839 | 106678 | 51,63 |
| B1 | 40 | 73839 | 23773 | 97612 | 59,18 |
| P0 | 40 | 83114 | 14510 | 97624 | 37,58 |
| P1 | 46 | 98507 | 16985 | 115492 | 44,05 |

| Model | Giây/CV | p50 giây | p95 giây | EOS calls | Hit max calls |
| --- | --- | --- | --- | --- | --- |
| B0 | 77,44 | 69,94 | 125,58 | 40 | 0 |
| B1 | 88,77 | 81,82 | 140,02 | 40 | 0 |
| P0 | 56,37 | 50,70 | 96,29 | 38 | 2 |
| P1 | 66,07 | 50,70 | 155,43 | 44 | 2 |

Tất cả cấu hình GOLD40 dùng greedy và giới hạn 1.280 token. P1 gồm 40 lượt đầu và 6 retry thuộc GOLD40; tổng runtime và token bao gồm các lượt không thành công. P1 giảm 48,28% output token so với B0, nhưng tổng input+output tăng 8,27%; không kết luận tổng chi phí giảm từ riêng số output. Model seconds mean của P1 là thời gian đầu+retry chia 40 CV, không phải trung bình thời gian một call. Chưa quy đổi thành USD vì chạy Colab và chưa có giá hạ tầng đo được.

## 9 Kết quả OCR pilot đã đo

Pilot dùng 5 trang VI001, VI006, VI013, VI018, VI020, raster 200 DPI từ PDF có text. Một CV EN047 chỉ có ảnh được kiểm tra riêng. Các trang VI này không phải bộ scan máy ảnh/máy quét mới; text embedded dùng làm tham chiếu nên phép đo OCR vẫn cần công bố giới hạn tham chiếu.

| OCR recognizer | Token F1 | Recall dấu | Recall kỹ thuật | Định danh exact | Giây/trang |
| --- | --- | --- | --- | --- | --- |
| paddleocr_v5_latin | 55,81% | 39,60% | 95,95% | 13/15 | 34,84 |
| vgg_seq2seq | 94,15% | 96,57% | 93,58% | 7/15 | 7,97 |
| vgg_transformer | 96,38% | 99,01% | 91,75% | 6/15 | 38,21 |
| hybrid_seq2seq_contact_fallback | 94,66% | 96,57% | 93,58% | 13/15 | 7,97 |
| hybrid_transformer_contact_fallback | 96,82% | 99,01% | 91,75% | 13/15 | 38,21 |

PaddleOCR v5 đo detector+recognizer; VietOCR và hybrid chỉ đo recognizer với polygon detector tái sử dụng. Không so trực tiếp runtime end-to-end giữa các hàng. VietOCR không được fine-tune trong đề tài này; đây là đánh giá pretrained recognizer. Các định danh có 15 giá trị tham chiếu, không phải 15 CV.

| OCR recognizer | CER có thứ tự | WER có thứ tự |
| --- | --- | --- |
| paddleocr_v5_latin | 9,15% | 44,56% |
| vgg_seq2seq | 2,33% | 7,35% |
| vgg_transformer | 1,55% | 5,53% |
| hybrid_seq2seq_contact_fallback | 2,15% | 6,79% |
| hybrid_transformer_contact_fallback | 1,43% | 4,95% |

Đối chứng PaddleOCR v3 Latin đạt Token F1 32,62%, recall token có dấu 7,68%, CER 15,67%, WER 69,78%, 24,15 giây/trang. V5 Latin đạt CER 9,15%, WER 44,56% và confidence macro 96,08%; confidence cao không bảo đảm dấu tiếng Việt đúng. Dictionary audit ghi thiếu 45/74 ký tự VI kiểm tra ở v5 Latin và 53/74 ở v3 Latin.

Nhánh pilot được chọn cho scan VI là Paddle detector + VietOCR Seq2Seq + Paddle contact fallback. Scan EN dùng PaddleOCR English có cờ review; EN047 chưa có ground truth OCR đầy đủ để báo CER/F1 EN tương đương bảng VI. Benchmark trích xuất real80/GOLD40 không đánh giá nhánh OCR VI vì các PDF VI đều đi tuyến native text.

## 10 Phân tích lỗi và giới hạn của dữ liệu

| Độ phủ nhãn | Train 850 | GOLD40 |
| --- | --- | --- |
| CV tiếng Việt | 0 | 20 |
| GitHub có giá trị | 0 | 30 |
| GPA có giá trị | 0 | 28 |
| Activities có giá trị | 0 | 6 |
| Awards có giá trị | 0 | 2 |
| Soft skill target | Chỉ Communication | Nhiều kỹ năng tường minh |

Lệch phạm vi nhãn đã xác nhận: converter tổng hợp chỉ đưa source.skills sang hard/soft skills; công nghệ dự án giữ ở projects.technologies, Languages không chuyển vào skills. Gold yêu cầu kỹ năng tường minh toàn CV. 543/544 CV train có công nghệ dự án thiếu ít nhất một giá trị nguyên dạng trong hard_skills target, và 850/850 nguồn có Languages. Cần thống nhất phạm vi nhãn trước run mới.

B1 hard-skills F1 13,69%, B0 58,33%. Heuristic tìm 304 cặp ứng viên trên 26 CV có kỹ năng gold bị chấm thiếu nhưng nằm trong chuỗi kỹ năng B1 dài hơn. Đây là ca nghi ngờ gộp, có thể có ứng viên giả như C/C#/C++; không cộng lại thành TP. Nếu loại riêng hard_skills khỏi phép tổng hợp chẩn đoán, B0 F1 69,28%, B1 62,48%. Điểm chính vẫn giữ đủ 19 trường.

B1 schema-invalid gồm EN012 lỗi JSON, EN035 thiếu skills.soft_skills và VI006/VI008/VI010 activities sai kiểu. Trên 35 CV cả B0/B1 đều hợp lệ, B0 F1 65,91%, B1 52,28%; lỗi parse không giải thích hết khoảng cách. Phân tích có điều kiện này có thiên lệch chọn mẫu và không thay metric toàn 40.

GOLD40 nhỏ làm ước lượng và độ phủ hạn chế, không trực tiếp gây overfitting. Các loss validation giảm và test tổng hợp cao chưa cho thấy train quá lâu theo bằng chứng đã lưu; vẫn có khả năng chuyên biệt vào miền/quy tắc tổng hợp. Nhãn gold có thể có lỗi nội dung, nhưng chưa có kết quả rà đủ bộ để lượng hóa ảnh hưởng. Schema validation không thay thế đối chiếu PDF.

## 11 Kết luận để trình bày với giảng viên

Nhóm đã thực hiện huấn luyện QLoRA hai giai đoạn trên Qwen3 4B và có checkpoint, adapter, log và phép đánh giá có truy vết. Stage 1 cải thiện Field Micro F1 trên test tổng hợp từ 87,98% lên 99,52%. Stage 2 Pointer giảm lượng output sinh và tăng Document exact trên test tổng hợp, nhưng Micro F1 giảm nhẹ xuống 99,19%.

Trên GOLD40 thật, Qwen gốc đạt 65,52% F1, cao hơn adapter Full JSON 48,28%, Pointer một lượt 49,66% và Pointer retry 52,81%. P1 cải thiện tính hợp lệ và recall so với P0, nhưng chưa vượt Qwen gốc về chất lượng nội dung. Do đó chưa có căn cứ tuyên bố fine-tuning hoặc Pointer cải thiện F1 CV thật so với baseline gốc.

Ưu tiên tiếp theo là rà gold và nguồn PDF, thống nhất phạm vi nhãn train–gold–prompt, bổ sung ví dụ VI/các trường thiếu và đánh giá cấu hình mới trên dữ liệu phát triển riêng. Sau khi chốt cải tiến, cần CV mới để xác nhận. Nếu sửa gold, chấm lại cùng raw output và báo cả gold v1/v2 với lý do sửa; không đưa GOLD40 vào train rồi báo chính nó là test.

Phần kiến trúc Pointer kế thừa nghiên cứu trước. Các điều chỉnh của nhóm gồm Hybrid Pointer một lượt, hợp đồng xác thực và retry chọn CV lỗi trong giới hạn tài nguyên. Hiệu quả của từng điều chỉnh phải gắn với phép đo cụ thể; không dùng kết quả bài báo khác như kết quả của đề tài.

## 12 Các số liệu còn cần bổ sung

- Kết quả rà nhãn nội dung đầy đủ và mức đồng thuận mới của hai người rà; không thể truy dựng IAA lịch sử.

- Gold cho 40 CV thật còn lại hoặc nhóm CV mới để đo nội dung; real80 hiện chủ yếu có structural benchmark.

- OCR trên scan VI thực tế, OCR EN có ground truth và kiểm tra reading order độc lập.

- So checkpoint sớm/cuối trên dev thật mới nếu muốn kiểm chứng over-training; phép đo hiện chưa xác định nguyên nhân nhân quả.

- Latency và peak VRAM inference trong cùng phiên/hạ tầng, gồm OCR, tải model, cold start và xử lý PDF nếu muốn kết luận end-to-end.

- Benchmark riêng cho matching, chấm điểm và gợi ý do các thành viên phụ trách.

## Phụ lục A F1 từng trường trên validation tổng hợp

| Trường | Gold support | B0 F1 | B1 F1 | P0 F1 |
| --- | --- | --- | --- | --- |
| personal_info.github_url | 0 | Không áp dụng | Không áp dụng | Không áp dụng |
| summary | 54 | 96,30% | 100,00% | 100,00% |
| skills.hard_skills | 759 | 94,36% | 99,80% | 99,80% |
| skills.soft_skills | 33 | 46,38% | 98,51% | 100,00% |
| experience.company | 295 | 98,10% | 100,00% | 100,00% |
| experience.job_title | 289 | 97,71% | 100,00% | 100,00% |
| experience.duration | 295 | 98,10% | 100,00% | 100,00% |
| experience.description | 295 | 98,10% | 100,00% | 100,00% |
| projects.name | 91 | 95,45% | 98,90% | 98,90% |
| projects.role | 61 | 14,49% | 84,30% | 85,95% |
| projects.technologies | 310 | 97,35% | 100,00% | 100,00% |
| projects.details | 91 | 87,50% | 100,00% | 100,00% |
| education.university | 153 | 14,62% | 100,00% | 100,00% |
| education.degree | 153 | 98,34% | 100,00% | 100,00% |
| education.gpa | 0 | Không áp dụng | Không áp dụng | Không áp dụng |
| education.year_graduated | 153 | 98,00% | 100,00% | 100,00% |
| certifications | 57 | 29,46% | 100,00% | 100,00% |
| activities | 0 | 0,00% | Không áp dụng | Không áp dụng |
| awards | 0 | Không áp dụng | Không áp dụng | Không áp dụng |

## Phụ lục B F1 từng trường trên test tổng hợp

| Trường | Gold support | B0 F1 | B1 F1 | P0 F1 |
| --- | --- | --- | --- | --- |
| personal_info.github_url | 0 | Không áp dụng | Không áp dụng | Không áp dụng |
| summary | 60 | 97,48% | 100,00% | 99,16% |
| skills.hard_skills | 737 | 92,40% | 99,59% | 99,18% |
| skills.soft_skills | 35 | 48,53% | 100,00% | 98,55% |
| experience.company | 286 | 97,86% | 100,00% | 99,65% |
| experience.job_title | 275 | 97,96% | 99,82% | 99,45% |
| experience.duration | 286 | 97,86% | 100,00% | 99,65% |
| experience.description | 286 | 97,86% | 100,00% | 99,65% |
| projects.name | 112 | 97,25% | 100,00% | 99,55% |
| projects.role | 76 | 28,90% | 87,58% | 88,74% |
| projects.technologies | 386 | 97,48% | 100,00% | 99,74% |
| projects.details | 112 | 77,78% | 100,00% | 99,55% |
| education.university | 150 | 18,31% | 100,00% | 99,00% |
| education.degree | 150 | 98,31% | 100,00% | 99,67% |
| education.gpa | 0 | Không áp dụng | Không áp dụng | Không áp dụng |
| education.year_graduated | 150 | 98,31% | 100,00% | 99,67% |
| certifications | 47 | 32,43% | 95,74% | 97,83% |
| activities | 0 | 0,00% | Không áp dụng | Không áp dụng |
| awards | 0 | Không áp dụng | Không áp dụng | Không áp dụng |

## Phụ lục C F1 từng trường và entity trên GOLD40

| Trường | Support | B0 F1 | B1 F1 | P0 F1 | P1 F1 |
| --- | --- | --- | --- | --- | --- |
| personal_info.github_url | 30 | 50,00% | 38,30% | 38,30% | 44,90% |
| summary | 38 | 89,47% | 60,32% | 30,19% | 30,19% |
| skills.hard_skills | 569 | 58,33% | 13,69% | 37,78% | 38,25% |
| skills.soft_skills | 103 | 70,14% | 68,09% | 65,14% | 72,34% |
| experience.company | 10 | 75,00% | 61,54% | 57,14% | 57,14% |
| experience.job_title | 12 | 38,46% | 28,57% | 27,27% | 29,63% |
| experience.duration | 12 | 69,23% | 76,92% | 52,17% | 66,67% |
| experience.description | 12 | 38,46% | 20,00% | 47,62% | 43,48% |
| projects.name | 109 | 83,87% | 71,79% | 74,87% | 79,21% |
| projects.role | 47 | 68,85% | 58,33% | 50,88% | 53,54% |
| projects.technologies | 355 | 76,02% | 70,57% | 63,28% | 67,60% |
| projects.details | 101 | 41,15% | 36,17% | 10,06% | 9,52% |
| education.university | 40 | 90,00% | 81,58% | 81,08% | 88,61% |
| education.degree | 40 | 45,00% | 48,00% | 43,24% | 48,10% |
| education.gpa | 28 | 96,30% | 94,34% | 90,20% | 96,30% |
| education.year_graduated | 13 | 37,50% | 38,10% | 34,29% | 42,11% |
| certifications | 9 | 66,67% | 53,33% | 66,67% | 66,67% |
| activities | 11 | 10,81% | 0,00% | 0,00% | 19,05% |
| awards | 2 | 40,00% | 0,00% | 0,00% | 0,00% |

| Entity exact F1 | B0 | B1 | P0 | P1 |
| --- | --- | --- | --- | --- |
| experience | 14,81% | 12,90% | 16,67% | 12,90% |
| projects | 9,22% | 15,31% | 3,21% | 2,97% |
| education | 20,00% | 28,95% | 21,62% | 25,32% |

Field set F1 tổng hợp các giá trị theo trường, còn entity exact yêu cầu thuộc cùng object và khớp đủ thuộc tính; hai phép đo trả lời khác nhau. Toàn bộ TP/FP/FN, precision/recall/F1 từng trường, breakdown EN/VI và log train nằm trong tệp số liệu JSON kèm báo cáo.

## Phụ lục D Nguồn số liệu và tài liệu nghiên cứu

- training/final_adapter-full_1.zip

- training/qwen3_4b_cvschema2_pointer_stage2_full_v1_final_adapter.zip

- training/evaluation/results/validation_base_vs_adapter_v1/comparison_summary.json

- training/evaluation/results/locked_test_base_vs_adapter_v1/comparison_summary.json

- training/evaluation/results/pointer_stage2_validation_p0_v1/evaluation_summary.json

- training/evaluation/results/pointer_stage2_locked_test_p0_v1/evaluation_summary.json

- training/evaluation/results/pointer_real80_selective_retry_p1_v1/evaluation_summary.json

- training/evaluation/results/gold40_b0_b1_p0_p1_v1/summary.json

- training/audits/gold40_generalization_2026-10-11_v2/diagnostics.json

- experiments/ocr/vietocr_hybrid_pilot_v1/comparison_summary.json

Tệp số liệu kèm báo cáo lưu hash đầy đủ của nguồn, contract train, log đã ghi và metric gốc. Kiểm tra lại CRC và 10/10 manifest member của mỗi adapter stage 1/smoke/full; kiểm tra manifest kết quả GOLD40, dataset và hash gold. Báo cáo không thay raw output, adapter, parser, nhãn hoặc kết quả cũ.

Hu và cộng sự, LoRA, 2021: https://arxiv.org/abs/2106.09685. LoRA giữ cố định trọng số base và học các ma trận thích nghi hạng thấp; đây là căn cứ chọn adapter thay vì cập nhật toàn base.

Dettmers và cộng sự, QLoRA, 2023: https://arxiv.org/abs/2305.14314. QLoRA kết hợp base lượng tử hóa 4-bit với LoRA, NF4 và double quantization để giảm yêu cầu bộ nhớ. VRAM đo trong đề tài xác nhận cấu hình hiện tại chạy được, không chứng minh chất lượng CV thật.

Layout-Aware Parsing Meets Efficient LLMs, 2025: https://arxiv.org/abs/2510.09722. Pointer là hướng kế thừa từ bài báo đã đọc; khác dữ liệu và giao thức đánh giá nên không so trực tiếp F1 của nhóm với số báo cáo trong bài.
