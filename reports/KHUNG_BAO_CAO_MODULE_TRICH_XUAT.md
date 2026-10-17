# Khung báo cáo mô-đun OCR và trích xuất CV

Trạng thái cập nhật 10/10/2026: đã đánh giá P0/P1 trên GOLD40 hậu kiểm; parser Pointer v1 giữ nguyên  
Phạm vi: mô-đun đầu vào của hệ thống đánh giá CV theo JD

> Mô-đun này kết thúc tại CVSchema 2.0 đã xác thực và evidence sidecar. So khớp CV-JD,
> chấm điểm, xếp hạng và sinh gợi ý được trình bày tại các phần của thành viên phụ trách.

## 1. Vai trò trong hệ thống tổng thể

### 1.1 Mục tiêu

Chuyển CV PDF tiếng Anh hoặc tiếng Việt thành CVSchema 2.0 có cấu trúc, truy vết được nguồn
và đủ ổn định để làm đầu vào cho mô-đun so khớp/chấm điểm.

### 1.2 Đầu vào và đầu ra

- Đầu vào: CV PDF hoặc text CV.
- Đầu ra chính: `cv.json` đúng CVSchema 2.0.
- Đầu ra kiểm toán: `evidence.json` và `extraction_manifest.json`.
- Ngoài phạm vi: match score, ranking, recommendation và quyết định tuyển dụng.

## 2. Cơ sở lựa chọn phương pháp

Mỗi tiểu mục phải trình bày theo thứ tự: vấn đề, phương án thay thế, nghiên cứu trước, ràng
buộc đề tài, lựa chọn, thực nghiệm kiểm chứng và giới hạn.

### 2.1 Text PDF, OCR và hợp nhất nội dung

**Phương án xem xét:** chỉ text PDF; OCR toàn trang; kết hợp text PDF và OCR.  
**Lựa chọn:** ưu tiên text PDF hợp lệ, dùng OCR cho trang/vùng cần thiết và định tuyến theo
ngôn ngữ.  
**Dẫn chứng:** bài báo 2510.09722, mục 3.1 và ablation Table 4; khi bỏ text fusion, Long Text
Accuracy giảm từ 0,858 xuống 0,743.  
**Bằng chứng đề tài cần điền:** CER, WER/Token F1, lỗi đọc cột và latency theo EN/VI.  
**Giới hạn:** kết quả bài báo trên Trung–Anh không tự động chuyển sang Việt–Anh.

### 2.2 Lựa chọn Qwen3-4B

**Phương án xem xét:** Qwen3-0.6B, 4B, 14B và API đóng.  
**Lựa chọn:** Qwen3-4B-Instruct-2507 làm model thống nhất cho baseline và fine-tuning.  
**Lý do:** đã có baseline khóa, năng lực zero-shot cao hơn 0.6B trong bài báo và vẫn có thể
QLoRA trên T4.  
**Vì sao chưa chọn 0.6B:** bài báo đạt kết quả cao sau full SFT với 59.500 instruction sample
và 8 A800; điều kiện đó khác dữ liệu/tài nguyên đề tài.  
**Vì sao chưa chọn 14B:** vượt ngân sách VRAM/latency của Colab Free.  
**Kiểm chứng:** so B0–B1–P0 trên cùng model revision và split.

### 2.3 Lựa chọn QLoRA

**Phương án xem xét:** prompt-only, full SFT, LoRA và QLoRA.  
**Lựa chọn:** QLoRA 4-bit NF4.  
**Lý do:** đề tài bắt buộc có huấn luyện; full SFT 4B không phù hợp T4; prompt-only chỉ làm
baseline.  
**Dẫn chứng cần trích:** Hu et al. (LoRA) và Dettmers et al. (QLoRA).  
**Bằng chứng đề tài:** peak VRAM, thời gian, train/eval loss và chất lượng trước/sau train.

### 2.4 Full JSON và index-based pointer

**Phương án xem xét:** sinh lại toàn bộ trường dài hoặc trả khoảng dòng.  
**Lựa chọn:** kế thừa index-based pointer từ bài báo cho summary, experience description và
project details.  
**Dẫn chứng:** bài báo, mục 3.2; biến thể bỏ post-processor có Long Text Accuracy 0,781 so
với 0,858 của hệ thống đầy đủ.  
**Lưu ý đóng góp:** pointer là phương pháp kế thừa, không phải sáng kiến của nhóm.  
**Kiểm chứng:** output token, span validity, reconstruction exact match và Long Text F1.

### 2.5 Một lượt và phân rã tác vụ

**Phương án xem xét:** nhiều prompt chuyên biệt chạy song song hoặc một JSON thống nhất.  
**Lựa chọn:** Hybrid Pointer một lượt.  
**Giả thuyết:** giảm số lần gọi và lặp input; giữ các trường của một entity trong cùng object.  
**Rủi ro:** prompt phức tạp có thể giảm accuracy; bài báo ưu tiên task decomposition.  
**Kết quả validation:** so với B1 Full JSON, P0 giữ 100% JSON/CVSchema hợp lệ, tăng document
exact từ 81,33% lên 85,33%, giảm output token trung bình 37,41% và giảm latency trung bình
37,00%. Field Micro F1 tăng nhẹ từ 0,995951 lên 0,996438. Vì vậy một lượt phù hợp với
giới hạn Colab và mục tiêu giảm chi phí, nhưng chưa chứng minh ưu thế trên CV thật EN/VI.

### 2.6 Vì sao không dùng RAG cho extraction

Các sự thật cần trích phải xuất hiện trong CV hiện tại. Truy hồi tri thức ngoài không cung cấp
bằng chứng cho tên công ty, thời gian hoặc mô tả của ứng viên. RAG có thể được xem xét ở mô-đun
chuẩn hóa taxonomy hoặc sinh gợi ý, không được dùng để bổ sung sự thật vào CVSchema.

## 3. Phương pháp mô-đun trích xuất

### 3.1 Baseline Full JSON

CV text -> prompt CVSchema 2.0 -> Qwen3-4B -> Parser v1 -> CVSchema 2.0.

### 3.2 P0 - Hybrid Pointer một lượt

1. Chuẩn hóa các dòng không rỗng.
2. Đánh số `[L0001]`, `[L0002]`, ...
3. Qwen sinh trường ngắn và ba loại span trong một JSON.
4. Pointer parser kiểm tra type, khóa, giới hạn và thứ tự span.
5. Dựng lại văn bản dài bằng phép nối dòng xác định.
6. Xác thực CVSchema 2.0 và chính sách kỹ năng.

### 3.3 P1 - Kiểm chứng và sửa lỗi chọn lọc

P1 chọn CV có lỗi cấu trúc/span được P0 báo qua `retry_targets`, rồi sinh lại toàn bộ JSON
Pointer với ràng buộc nhắm vào trường lỗi, tối đa một lần cho mỗi CV. Trên 75 validation,
75/75 output hợp lệ và không có `retry_targets`, nên cổng P1
không gọi thêm model và có cùng metric với P0. 11 mẫu không document-exact đều là sai khác
ngữ nghĩa ở trường ngắn, chủ yếu `projects.role`; parser không thể phát hiện các lỗi này nếu
không có gold. Không dùng luật ánh xạ synonym học từ validation vì dễ quá khớp và thay đổi
sự thật CV. Cổng retry được giữ cho lỗi OCR/thực tế và sẽ đo riêng trên 80 CV thật.

### 3.4 Hợp đồng bàn giao

- `cv.json`: CVSchema 2.0 hợp lệ.
- `evidence.json`: field path, span và text nguồn.
- `extraction_manifest.json`: OCR/model/parser/config hash và trạng thái.

## 4. Dữ liệu

| Split | Số mẫu | Quyền sử dụng |
|---|---:|---|
| Train | 850 | Cập nhật gradient |
| Validation | 75 | Chọn cấu hình và phân tích lỗi |
| Test | 75 | Đánh giá sau khi đóng băng |

### 4.1 Chuyển đổi Pointer

| Chỉ tiêu | Kết quả |
|---|---:|
| Tổng mẫu round-trip | 1.000/1.000 |
| Tổng trường dài | 6.175 |
| Exact contiguous | 5.906 |
| Span null | 269 |
| Alignment mơ hồ | 0 |
| Source trùng giữa split | 0 |

## 5. Thiết kế thực nghiệm

| Mã | Cấu hình | Vai trò |
|---|---|---|
| B0 | Qwen3-4B gốc, Full JSON | Baseline zero-shot |
| B1 | Qwen3-4B adapter v1, Full JSON | Baseline fine-tuned |
| P0 | Qwen3-4B adapter Pointer | Phương pháp kế thừa/điều chỉnh |
| P1 | P0 + validator + selective retry | Cải tiến cần kiểm chứng |

Các cấu hình phải dùng cùng model revision, split, greedy decoding, chính sách parser và cách
tính metric sau khi dựng về CVSchema 2.0.

### 5.1 Metric

- Strict/recoverable JSON rate.
- Pointer-schema và CVSchema-valid rate.
- Valid span, span exact match và reconstruction exact match.
- Field precision, recall, Micro/Macro F1.
- Long Text F1.
- Input/output token và tỷ lệ chạm giới hạn.
- Số model call, retry rate và latency p50/p95.
- Peak VRAM và thời gian train.

## 6. Kết quả đã có

### 6.1 Độ dài Pointer theo tokenizer Qwen

| Split | p50 | p95 | p99 | Max | Vượt 5.120 |
|---|---:|---:|---:|---:|---:|
| Train | 2.137 | 2.629 | 2.775 | 2.890 | 0 |
| Validation | 2.176 | 2.626 | 2.764 | 2.828 | 0 |

Theo ký tự, assistant output Pointer giảm 52,48%; indexed source tăng 15,33%. Cần bổ sung
tỷ lệ giảm token sau khi chạy cả B1 và P0.

### 6.2 Smoke continued QLoRA P0

| Chỉ tiêu | Kết quả |
|---|---:|
| Optimizer steps | 2 |
| Train loss | 0,031515 |
| Eval loss | 0,018196 |
| Eval token accuracy | 0,996441 |
| Train runtime | 285,75 giây |
| Peak reserved VRAM | 9,561 GB |

Smoke xác nhận pipeline có thể train trên T4; không được dùng hai bước smoke để kết luận chất
lượng P0.

### 6.3 Kết quả validation chính

| Metric | B0 | B1 | P0 | P1 |
|---|---:|---:|---:|---:|
| Recoverable JSON | 97,33% | 100,00% | 100,00% | 100,00% |
| CVSchema valid | 97,33% | 100,00% | 100,00% | 100,00% |
| Skill policy valid | 46,67% | 98,67% | 100,00% | 100,00% |
| Document exact | 0,00% | 81,33% | 85,33% | 85,33% |
| Micro F1 | 0,880626 | 0,995951 | 0,996438 | 0,996438 |
| Macro F1, field có support | 0,776169 | 0,987672 | 0,989769 | 0,989769 |
| Long Text F1 | 0,957126 | 1,000000 | 1,000000 | 1,000000 |
| Output token trung bình | 814,55 | 609,71 | 381,64 | 381,64 |
| Model call/CV | 1 | 1 | 1 | 1,00 |
| Latency trung bình/CV | 70,32 giây | 97,18 giây | 61,22 giây | 61,22 giây |

P1 bằng P0 trên validation vì validator không phát hiện lỗi cấu trúc hoặc span nào để kích
hoạt retry. Đây là kết quả âm cần báo cáo, không được trình bày P1 như một cải thiện accuracy.

### 6.4 Kết quả huấn luyện full P0

| Chỉ tiêu | Kết quả |
|---|---:|
| Epoch / optimizer step | 1 / 107 |
| Train loss | 0,016707 |
| Eval loss step 40 / 80 / 107 | 0,015829 / 0,015044 / 0,014881 |
| Eval token accuracy cuối | 0,999497 |
| Train runtime | 10.552,24 giây |
| Peak reserved VRAM | 9,562 GB |

### 6.5 Kết quả raw validation P0

| Chỉ tiêu | Kết quả |
|---|---:|
| Recoverable JSON / Pointer schema / span contract | 75/75 |
| CVSchema 2.0 và skill policy hợp lệ | 75/75 |
| Pointer document exact | 64/75 (85,33%) |
| CVSchema document exact | 64/75 (85,33%) |
| Span exact trên gold khác null | 440/440 (100,00%) |
| Field Micro F1 | 0,996438 |
| Macro F1 trên field có support | 0,989769 |
| Long-text Micro F1 | 1,000000 |
| Output token trung bình | 381,64 |
| Latency trung bình; p50; p95 | 61,22; 65,61; 83,88 giây |

Toàn bộ 75 output có block `<think>...</think>` hoàn chỉnh ở đầu, nên strict JSON là 0/75
nhưng recoverable JSON là 75/75 theo đúng Parser v1. Không mẫu nào chạm giới hạn token.
11 mẫu không exact gồm 9 mẫu sai `projects.role`, 2 mẫu sai hard skill và 1 mẫu sai tên
dự án; một mẫu có thể sai nhiều trường. Tất cả summary/experience/project span đều exact.

Parser `cvpointer_output_parser_v1` đã đóng băng sau validation với manifest SHA-256
`6fbba87b448cdd9f6ac1cec4771c639d3d3422939c36f4c9453a23d3140c5746`.

### 6.6 Kết quả test khóa

Gold test chỉ được mở ngoại tuyến sau khi parser Pointer v1 đã đóng băng. Không sửa parser,
schema, skill policy hoặc metric theo lỗi test.

| Metric | B0 | B1 | P0 Pointer |
|---|---:|---:|---:|
| Recoverable JSON | 97,33% | 100,00% | 100,00% |
| CVSchema valid | 97,33% | 100,00% | 98,67% |
| Skill policy valid | 53,33% | 100,00% | 98,67% |
| Document exact | 1,33% | 76,00% | **82,67%** |
| Micro F1 | 0,879847 | **0,995234** | 0,991860 |
| Macro F1, field có support | 0,785797 | **0,988491** | 0,986019 |
| Long-text Micro F1 | 0,929609 | **1,000000** | 0,995614 |
| Output token trung bình | 835,21 | 627,45 | **385,97** |
| Latency trung bình/CV | 72,22 giây | 92,82 giây | **58,13 giây** |

P0 giảm 38,49% output token và 37,37% latency so với B1. Document exact tăng 6,67 điểm
phần trăm, nhưng Micro F1 giảm 0,003374 vì một output thiếu hai khóa bắt buộc và bị loại toàn
bộ khỏi đầu ra bàn giao. Do đó không được kết luận P0 tốt hơn B1 trên mọi tiêu chí; lợi thế
được chứng minh của P0 là hiệu quả sinh, tỷ lệ document exact và khả năng truy vết span.

Chi tiết P0 test:

| Chỉ tiêu | Kết quả |
|---|---:|
| Recoverable JSON | 75/75 |
| Pointer schema / span contract / CVSchema valid | 74/75 |
| Pointer và CVSchema document exact | 62/75 (82,67%) |
| Raw non-null span exact | 458/458 (100,00%) |
| Field Micro F1 | 0,991860 |
| Macro F1 trên field có support | 0,986019 |
| Long-text Micro F1 sau validation gate | 0,995614 |
| EOS / chạm max token | 75/75 / 0/75 |

Mẫu `rpv_r00826` thiếu `activities` và `awards`. Parser v1 từ chối thay vì tự thêm giá trị;
đây là nguyên nhân 74/75 CVSchema valid và phần lớn độ giảm F1. Trong các output hợp lệ,
sai khác tiếp tục tập trung ở `projects.role`. Mặc dù raw span đạt 458/458, field metric chính
thức chỉ chấm CVSchema đã qua validation gate, nên mẫu bị từ chối vẫn tạo false negative.

Test tạo một `retry_targets` ở mẫu trên. Không chạy P1 trên test vì prompt retry chưa được
đóng băng trước khi mở test; thiết kế hoặc điều chỉnh retry theo lỗi này sẽ gây test leakage.
P1 phải được đánh giá trên tập CV thật có nhãn hoặc một held-out set mới.

### 6.7 Kết quả pipeline trích xuất trên 80 CV thật và selective retry

Pipeline được chạy trên 60 CV tiếng Anh và 20 CV tiếng Việt. 79 CV dùng text layer đã kiểm
tra; `EN047` dùng PaddleOCR tiếng Anh vì PDF chỉ chứa ảnh. Parser, adapter, model revision và
greedy decoding giữ nguyên. Tại thời điểm chạy 80 CV, tập chưa có gold label, nên phần này
chỉ báo tính hợp lệ cấu trúc và hiệu năng. Ngày 10/10/2026 đã có GOLD40 để đánh giá nội dung
trên một phần tập, báo riêng ở mục 6.8; chưa có gold của toàn bộ 80 CV.

| Chỉ tiêu | P0 toàn bộ | P0 EN | P0 VI | P1 hiệu dụng |
|---|---:|---:|---:|---:|
| Recoverable JSON | 77/80 (96,25%) | 59/60 (98,33%) | 18/20 (90,00%) | 80/80 (100,00%) |
| CVSchema hợp lệ | 71/80 (88,75%) | 56/60 (93,33%) | 15/20 (75,00%) | 78/80 (97,50%) |
| Cần review/retry | 9/80 | 4/60 | 5/20 | 2/80 |
| Output token trung bình P0 | 332,38 | 300,73 | 427,30 | — |
| Latency trung bình P0 | 51,74 giây | 47,12 giây | 65,57 giây | — |

P1 chỉ gọi lại model cho 9 mẫu P0 bị Parser v1 từ chối. Prompt retry được tạo từ loại lỗi và
`retry_targets`, không dùng gold và không đưa raw output trước vào prompt. P1 khôi phục 7/9
mẫu, tăng CVSchema hợp lệ từ 88,75% lên 97,50%. Mức tăng theo ngôn ngữ là 5 điểm phần trăm
cho EN và 20 điểm phần trăm cho VI. Chi phí so với P0 tăng 11,25% số lần gọi model, 12,93%
output token và 13,29% thời gian sinh.

Hai mẫu còn lại được gắn cờ review: `EN011` tiếp tục sinh span có một đầu `null`; `VI006`
sửa được kiểu dữ liệu `activities` nhưng bỏ khóa `soft_skills`. Pipeline dừng retry sau một
vòng để chi phí hữu hạn và tránh vòng lặp lỗi.

Kết quả này hỗ trợ giả thuyết rằng cổng kiểm chứng và retry chọn lọc cải thiện độ tin cậy cấu
trúc với chi phí thấp hơn chạy lại toàn bộ 80 CV. Nó chưa chứng minh nội dung trích xuất đúng
hơn; cần đánh giá riêng trên gold CV thật. Kết quả hậu kiểm trên GOLD40 nằm ở mục 6.8.

### 6.8 Kết quả nội dung trích xuất trên GOLD40 hậu kiểm

Ngày đánh giá: 10/10/2026. GOLD40 gồm 20 EN và 20 VI, đã được người dùng tổng hợp sau đối
soát Khải/Đắc; ba mẫu có trợ lý hỗ trợ hoàn tất từ PDF theo yêu cầu người dùng. Bản A/B trước
đối soát không còn được giữ, nên không tính IAA. P0/P1 đã chạy real80 trước khi gold được
khóa; đây là gold hậu kiểm, không phải tập test hoàn toàn chưa từng quan sát.

Evaluator kiểm tra hash ZIP, input, PDF, gold, sidecar và parser v1. Field metric dùng cùng
phép normalized exact set đã đóng băng. CV lỗi vẫn nằm trong mẫu số và được chấm dự đoán
rỗng. Không chặn kỹ năng mềm của CV thật bằng chính sách Communication-only của tập tổng
hợp. Kết quả Micro và từng trường khớp với hàm metric đóng băng cho cả hai model/all/EN/VI.

| Metric | P0 | P1 |
|---|---:|---:|
| CVSchema hợp lệ | 34/40 (85,00%) | 39/40 (97,50%) |
| Micro precision | 58,97% | 57,89% |
| Micro recall | 42,89% | 48,54% |
| Micro F1 toàn bộ | 49,66% | 52,81% |
| Micro F1 EN | 55,88% | 57,20% |
| Micro F1 VI | 42,46% | 48,05% |
| Macro F1 trên trường có support | 45,80% | 50,17% |
| Long Text F1 | 17,39% | 16,60% |
| Document exact | 0/40 | 0/40 |
| Số lần gọi model | 40 | 46 |
| Output token tổng | 14.510 | 16.985 |
| Tổng thời gian sinh model đã ghi | 2.254,67 giây | 2.642,90 giây |

P1 tăng Micro F1 3,14 điểm phần trăm và khôi phục cấu trúc ở 5/6 CV được retry trong GOLD40.
Khoảng bootstrap 95% của chênh lệch F1 là [0,79; 6,77] điểm phần trăm, tính ghép cặp theo CV,
giữ cân bằng EN/VI (2.000 lần, seed 42). Recall tăng 5,65 điểm phần trăm nhưng precision
giảm 1,07 điểm phần trăm; thời gian sinh tăng 17,22%. Trường dài và entity exact của dự án
vẫn thấp, nên không kết luận P1 cải thiện mọi mặt hoặc đã đủ chính xác để triển khai rộng.

Một số lỗi quan sát được: kỹ năng còn kèm tiêu đề nhóm (`Ngôn ngữ lập trình: C/C++` so với
`C/C++`), thiếu kỹ năng, span bỏ phần đầu summary, hoặc span dự án lấy thêm dòng công nghệ/
tiêu đề dự án khác. `VI006` sau retry vẫn thiếu khóa `skills.soft_skills`. Exact match cũng
phạt bullet, dấu câu và mức đầy đủ khác nhau giữa span và nhãn; điểm thấp không được quy
toàn bộ thành lỗi ngữ nghĩa hoặc OCR.

Giới hạn đối chứng: chưa có B0/B1 trên GOLD40; không so trực tiếp F1 ở đây với test tổng hợp
75 mẫu. Retry P1 có max_new_tokens=1.280, trong khi P0 là 768, nên chưa cô lập được tác động
validator khỏi tác động tăng ngân sách sinh. 39 CV dùng text PDF, chỉ EN047 dùng PaddleOCR
tiếng Anh; toàn bộ VI dùng text nhúng. Số liệu này chưa đánh giá OCR tiếng Việt. Thời gian
đo là chi phí sinh LLM cộng dồn từ artifact, không phải latency đầy đủ của web hoặc OCR.

Nguồn số liệu và lỗi chi tiết:
[`REPORT.md`](../training/evaluation/results/gold40_p0_vs_p1_v1/REPORT.md),
[`model_metrics.csv`](../training/evaluation/results/gold40_p0_vs_p1_v1/model_metrics.csv),
[`field_metrics.csv`](../training/evaluation/results/gold40_p0_vs_p1_v1/field_metrics.csv).

### 6.9 Hoàn thiện đối chứng B0/B1/P0/P1 trên GOLD40

Ngày đánh giá: 11/10/2026. B0/B1 sinh đúng cùng 40 văn bản GOLD40 đã dùng cho P0/P1;
hai ZIP đã kiểm tra CRC, hash từng file/bản ghi, ID, nguồn PDF/text, adapter, hợp đồng
notebook, phần mềm và các tổng token/thời gian. Nhãn và parser không đổi. B0/B1 đều
kết thúc EOS 40/40, không mẫu nào chạm giới hạn 1.280 token. P0/P1 được tái dựng và
khớp hoàn toàn bản đo ở mục 6.8. Output lỗi vẫn được chấm như dự đoán rỗng.

| Chỉ số | B0: Qwen gốc | B1: Full JSON đã train | P0: Pointer | P1: Pointer + retry |
|---|---:|---:|---:|---:|
| CVSchema hợp lệ | 40/40 | 35/40 | 34/40 | 39/40 |
| Micro precision | 64,25% | 60,65% | 58,97% | 57,89% |
| Micro recall | 66,84% | 40,10% | 42,89% | 48,54% |
| Micro F1 toàn bộ | 65,52% | 48,28% | 49,66% | 52,81% |
| Micro F1 EN | 72,23% | 52,16% | 55,88% | 57,20% |
| Micro F1 VI | 58,52% | 44,16% | 42,46% | 48,05% |
| Long Text F1 | 52,73% | 39,86% | 17,39% | 16,60% |
| Document exact | 0/40 | 0/40 | 0/40 | 0/40 |
| Input token tổng | 73.839 | 73.839 | 83.114 | 98.507 |
| Output token tổng | 32.839 | 23.773 | 14.510 | 16.985 |
| Số lần gọi model | 40 | 40 | 40 | 46 |
| Tổng thời gian sinh đã ghi (giây) | 3.097,70 | 3.550,81 | 2.254,67 | 2.642,90 |

**Kết quả không hỗ trợ tuyên bố mô hình đã huấn luyện hoặc P1 chính xác hơn Qwen gốc
trên CV thật.** B1 thấp hơn B0 17,24 điểm phần trăm Micro F1 (bootstrap CI 95%
[-22,58; -11,75]); P1 thấp hơn B0 12,72 điểm phần trăm (CI [-17,52; -7,74]). P1 vẫn
tăng so với P0 3,14 điểm phần trăm. P0−B1 là +1,38 điểm phần trăm nhưng CI
[-4,32; +6,79] đi qua 0, chưa có bằng chứng ổn định cho cải thiện này.

B1 có 5 lỗi: EN012 JSON không khôi phục được; EN035 thiếu `skills.soft_skills`;
VI006/VI008/VI010 sinh object thay vì string trong `activities`. Đây không phải lỗi
bị cắt vì hết token. Hard-skills F1 B1 chỉ 13,69% so với B0 58,33%; ví dụ EN003
gộp `Programming: C#, JavaScript, Python` thành một kỹ năng. Exact-set metric phạt
khác đơn vị nhãn; không quy toàn bộ FN thành thông tin bị mất. Trên 35 CV mà cả hai
đều hợp lệ, F1 B0/B1 là 65,91%/52,28%, nên 5 lỗi schema không giải thích hết mức giảm.
Phân tích 35 CV này có chọn mẫu theo validity và không thay chỉ số chính 40 CV.

P1 giảm output token 48,28% so với B0, nhưng tổng input + output tăng từ 106.678 lên
115.492 token (+8,27%) và tăng số call. Không kết luận giảm tổng chi phí. Thời gian
sinh lấy từ các phiên khác nhau, không phải latency đầu cuối hoặc đối chứng cùng phiên
GPU. B0/B1 dùng ngân sách 1.280 token, P0 768, retry P1 1.280; chưa cô lập tác động
kiến trúc, dữ liệu huấn luyện và validator.

Các kết quả này xác định hạn chế và hướng cải tiến cần kiểm chứng: đơn vị kỹ năng,
ranh giới span và thích ứng dữ liệu CV thật EN/VI. Dịch chuyển miền synthetic English
sang real CV là giả thuyết, chưa chứng minh nguyên nhân suy giảm. Giữ nguyên phiên
đo, không chỉnh gold/parser/metric theo output. Nếu huấn luyện tiếp, cần tập phát
triển riêng và tập xác nhận mới chưa dùng để chọn hướng; GOLD40 tiếp tục được gọi là
hậu kiểm. Các số liệu vẫn chỉ đánh giá extraction, không suy sang matching/chấm
điểm/sinh gợi ý của toàn đề tài.

Nguồn: [`REPORT.md`](../training/evaluation/results/gold40_b0_b1_p0_p1_v1/REPORT.md),
[`model_metrics.csv`](../training/evaluation/results/gold40_b0_b1_p0_p1_v1/model_metrics.csv),
[`field_metrics.csv`](../training/evaluation/results/gold40_b0_b1_p0_p1_v1/field_metrics.csv).

## 7. Phân tích và giới hạn

- Dataset model là synthetic English text; không đại diện trực tiếp cho OCR CV thật EN/VI.
- 80 CV thật phục vụ đánh giá đầu cuối cần báo riêng theo ngôn ngữ và loại PDF.
- Kết quả bài báo và đề tài không được so số trực tiếp vì khác dataset/schema/hạ tầng.
- Pointer đảm bảo sao chép đúng span đã chọn, không đảm bảo model chọn đúng span.
- Selective retry không được kích hoạt trên synthetic validation vì mọi output đều hợp lệ về
  cấu trúc và span. Trên 80 CV thật, P1 tăng schema validity; trên GOLD40 hậu kiểm, P1 tăng
  Micro F1 3,14 điểm phần trăm với chi phí sinh tăng. Precision và Long Text F1 giảm nhẹ.
  Hai tập và các mặt đánh giá này phải trình bày riêng.
- Chất lượng extraction không đại diện cho chất lượng so khớp, chấm điểm hoặc gợi ý.

## 8. Tài liệu tham khảo tối thiểu

1. *Layout-Aware Parsing Meets Efficient LLMs: A Unified, Scalable Framework for Resume
   Information Extraction and Evaluation*, arXiv:2510.09722.
2. Hu et al., *LoRA: Low-Rank Adaptation of Large Language Models*.
3. Dettmers et al., *QLoRA: Efficient Finetuning of Quantized LLMs*.
4. Tài liệu/model card Qwen3-4B-Instruct-2507.
5. Nghiên cứu/tài liệu chính thức của PaddleOCR và VietOCR dùng trong thực nghiệm.
