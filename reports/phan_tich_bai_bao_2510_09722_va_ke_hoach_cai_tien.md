# Phân tích bài báo 2510.09722 và kế hoạch cải tiến hệ thống trích xuất CV

> **Ranh giới phạm vi:** tài liệu này phân tích riêng mô-đun OCR và trích xuất CV. Trích xuất
> chỉ là đầu vào của hệ thống tổng thể, bên cạnh các mô-đun chuẩn hóa JD, so khớp CV-JD,
> chấm điểm và sinh gợi ý sửa do các phần khác của dự án phụ trách. Mọi tên “hệ thống” trong
> tài liệu này phải được hiểu là hệ thống con trích xuất, không phải toàn bộ đề tài.

> **Trạng thái quyết định:** đây là tài liệu phân tích phương án ngày 30/09, không phải cấu
> hình cuối. Khuyến nghị task decomposition/0.6B trong các mục dưới vẫn là phương án đối
> chứng. Quyết định hiện hành là tiếp tục Qwen3-4B Hybrid Pointer một lượt (`P0`), sau đó
> đánh giá kiểm chứng theo schema và selective retry (`P1`). Khi có xung đột, áp dụng
> `reports/PROJECT_SCOPE_AND_DECISIONS.md`.

Ngày lập: 2026-09-30  
Nguồn phân tích: *Layout-Aware Parsing Meets Efficient LLMs: A Unified, Scalable Framework for Resume Information Extraction and Evaluation*  
Phạm vi đối chiếu: pipeline OCR song ngữ, Qwen3-4B QLoRA, CVSchema 2.0, Parser v1 và các kết quả validation/test đã khóa của đề tài KLCN029.

## 1. Kết luận điều hành

Bài báo là một nền tảng tham chiếu rất phù hợp cho đề tài vì giải quyết đúng ba vấn đề của hệ thống trích xuất CV: bố cục tài liệu phức tạp, chi phí suy luận LLM và khó khăn khi đánh giá danh sách thực thể. Ba thành phần có giá trị kế thừa cao nhất là:

1. Hợp nhất text có sẵn trong PDF với OCR theo tọa độ thay vì chọn một nguồn cho toàn trang.
2. Tái tạo thứ tự đọc và gán chỉ mục cho từng dòng.
3. Chia bài toán thành các tác vụ nhỏ; dùng chỉ mục dòng làm con trỏ cho trường văn bản dài; kiểm tra kết quả với nguồn.

Pipeline hiện tại của nhóm đã có một baseline huấn luyện được kiểm soát tốt, nhưng mới chứng minh khả năng học ánh xạ `resume_text -> CVSchema 2.0` trên dữ liệu tổng hợp tiếng Anh cùng nguồn. Kết quả Micro F1 99,52% trên 75 mẫu test khóa chưa đo OCR, bố cục PDF, tiếng Việt, CV thật hoặc chuyển miền. Vì vậy, không nên trình bày 99,52% như độ chính xác đầu cuối của hệ thống trên CV thực tế.

Hướng nghiên cứu đề xuất là:

> **Trích xuất CV song ngữ có nhận biết bố cục và bằng chứng nguồn, sử dụng OCR thích ứng và Qwen được huấn luyện theo tác vụ phân rã.**

Hệ thống mới kế thừa kiến trúc của bài báo, đồng thời bổ sung ba cải tiến có thể kiểm chứng:

- Chọn và hợp nhất text/OCR theo vùng, ngôn ngữ và độ tin cậy cho CV Việt–Anh.
- Không gửi toàn bộ CV lặp lại cho mọi tác vụ; định tuyến các đoạn liên quan tới từng tác vụ để giảm input token.
- Mọi giá trị quan trọng có `evidence_line_ids`; bộ kiểm chứng chỉ yêu cầu mô hình chạy lại tác vụ hoặc trường không đủ bằng chứng.

Sự cải thiện phải được chứng minh bằng so sánh các biến thể trên cùng một bộ test CV thật đã khóa, không so trực tiếp số F1 của hai nghiên cứu dùng dataset và schema khác nhau.

## 2. Bài báo giải quyết vấn đề gì?

### 2.1 Ba khó khăn chính

Bài báo xác định ba khó khăn khi triển khai resume parsing:

- CV khác nhau mạnh về bố cục và nội dung; multi-column làm sai thứ tự đọc.
- LLM lớn có độ trễ và chi phí cao.
- Dữ liệu có nhãn hiếm; đánh giá danh sách như kinh nghiệm làm việc khó vì số lượng và thứ tự thực thể có thể khác nhau.

### 2.2 Kiến trúc ba giai đoạn

#### Giai đoạn A - Layout-aware parsing and regeneration

Tác giả lấy text và bounding box từ metadata PDF. Trang cũng được render thành ảnh; các vùng text đã biết được che đi và phần còn lại được OCR. Kết quả cuối là các primitive dạng `(text, x1, y1, x2, y2)`.

Một YOLOv10 được fine-tune trên khoảng 500 CV có nhãn bounding box cho các vùng bố cục lớn. Mục tiêu nhãn đơn giản là chia trang thành các vùng mà bên trong có thể đọc từ trên xuống dưới, trái sang phải. Sau đó hệ thống sắp xếp hai cấp:

- Sắp xếp giữa các vùng bố cục.
- Sắp xếp các text block bên trong từng vùng.

Mỗi dòng sau khi tuyến tính hóa được gán một chỉ mục tuần tự.

#### Giai đoạn B - Parallelized instruction-tuned LLM extractor

Thay vì một prompt sinh toàn bộ schema, tác giả chia thành các tác vụ như thông tin cơ bản, học vấn, kinh nghiệm và trong phần phụ lục có thêm dự án. Mỗi tác vụ dùng prompt chuyên biệt.

Với trường dài, LLM trả về khoảng chỉ mục dòng, ví dụ `[15, 25]`, thay vì sinh lại mô tả. Post-processor lấy nguyên văn các dòng tương ứng từ nguồn. Mục tiêu là giảm output token, tránh diễn giải lại và tăng khả năng truy vết.

Mô hình cuối là Qwen3-0.6B được full-parameter SFT trên 15.500 CV, tạo thành 59.500 instruction sample. Tác giả dùng AdamW, learning rate `5e-6`, cosine scheduler, batch mỗi thiết bị 2, gradient accumulation 2 và 8 GPU A800.

#### Giai đoạn C - Two-stage automatic evaluation

Danh sách thực thể dự đoán và gold được ghép cặp bằng Hungarian algorithm dựa trên độ giống của các trường khóa. Sau khi ghép cặp, từng loại trường dùng quy tắc khác nhau:

- Thời gian: chuẩn hóa năm/tháng.
- Named entity: substring hoặc chuẩn hóa để chấp nhận viết tắt/hậu tố.
- Văn bản dài: edit similarity.
- Trường khác: normalized exact match.

### 2.3 Dữ liệu và kết quả chính của bài báo

| Dataset | Quy mô | Train/Test | Ngôn ngữ | Đặc điểm |
|---|---:|---:|---|---|
| SynthResume | 2.994 | 2.500/494 | Trung | Mẫu tuyến tính và phi tuyến |
| RealResume | 13.100 | 13.000/100 | Trung–Anh | CV thật, font và bố cục phức tạp |

Kết quả tổng thể đáng chú ý:

| Phương pháp | SynthResume F1 | RealResume F1 | Thời gian RealResume |
|---|---:|---:|---:|
| Claude-4 chỉ OCR | 0,927 | 0,919 | 22,71 s |
| Claude-4 trong pipeline | 0,946 | 0,959 | 4,62 s |
| Qwen3-4B trong pipeline | 0,885 | 0,869 | 6,85 s |
| Qwen3-0.6B gốc trong pipeline | 0,645 | 0,641 | 1,54 s |
| Qwen3-0.6B-SFT trong pipeline | 0,917 | 0,964 | 1,54 s |

Fine-tune 0.6B đem lại mức tăng rất lớn trên RealResume. Tuy nhiên, trên SynthResume, Qwen3-0.6B-SFT F1 0,917 vẫn thấp hơn một số LLM zero-shot lớn; đóng góp nổi bật là tỷ lệ hiệu năng/độ trễ.

Ablation của bài báo cho thấy Long Text nhạy nhất:

| Biến thể | Overall Accuracy | Long Text Accuracy |
|---|---:|---:|
| Bỏ text fusion | 0,907 | 0,743 |
| Bỏ layout generator | 0,916 | 0,758 |
| Bỏ post-processor | 0,921 | 0,781 |
| Hệ thống đầy đủ | 0,932 | 0,858 |

Đây là bằng chứng trực tiếp để nhóm ưu tiên bố cục, span pointer và kiểm chứng nguồn thay vì chỉ tăng kích thước LLM.

## 3. Đánh giá phản biện bài báo

### 3.1 Điểm mạnh

- Bài toán được thiết kế theo hệ thống đầu cuối thay vì chỉ đánh giá LLM trên text sạch.
- Có baseline phi LLM, LLM naïve, nhiều LLM trong cùng pipeline và mô hình fine-tuned.
- Có ablation text fusion, layout regeneration và post-processing.
- Đo cả chất lượng và độ trễ.
- Cơ chế line pointer tạo đầu ra có thể truy vết và phù hợp với văn bản dài.
- Hungarian matching giải quyết hợp lý sự khác nhau về số lượng và thứ tự entity.

### 3.2 Hạn chế cần lưu ý khi kế thừa

1. **Split SynthResume có nguy cơ làm test dễ hơn.** Tác giả sắp dữ liệu theo độ dài, lấy 2.500 CV dài nhất làm train và 494 CV còn lại làm test. Đây không phải split ngẫu nhiên hoặc template-disjoint; test có xu hướng ngắn hơn. Bài báo cũng không công bố kiểm tra trùng template giữa train và test.

2. **RealResume test chỉ có 100 CV.** Dataset train rất lớn nhưng test nhỏ; bài báo không báo confidence interval hay kiểm định ý nghĩa thống kê.

3. **Chi tiết evaluator chưa đủ để tái lập hoàn toàn.** Ngưỡng ghép entity, cách tính trung bình similarity, ngưỡng substring và quy mô tập human verification không được mô tả đầy đủ.

4. **Accuracy trên các entity đã align có thể che lỗi bỏ sót.** Mẫu không align không nằm trong mẫu số Accuracy. Precision, Recall và F1 vẫn cần là chỉ số chính.

5. **Ablation chưa tách hết đóng góp.** Chưa có ablation riêng cho task decomposition, parallelism, pointer, SFT và source verification.

6. **Parallel prompt không tự động giảm chi phí.** Mỗi tác vụ nhận lại toàn bộ CV, nên input token và tổng compute có thể tăng. Độ trễ giảm khi có hạ tầng chạy song song; trên một GPU Colab, chạy đồng thời có thể không mang lại lợi ích.

7. **“100% content fidelity” chỉ đúng theo nghĩa sao chép span đã chọn.** Nếu mô hình chọn sai dòng, OCR sai hoặc reading order sai thì nội dung vẫn sai về mặt trích xuất.

8. **JSON extraction bằng `find("{")` và `rfind("}")` khá rộng.** Cách này có thể bỏ qua trailing text hoặc lỗi wrapper. Parser v1 nghiêm ngặt của nhóm dễ kiểm toán hơn.

9. **Một số mô tả thiếu nhất quán.** Phần chính nói ba tác vụ nhưng có chỗ gọi bốn category; phụ lục có project extraction. Phụ lục B ghi Qwen-6B trong khi phần còn lại ghi Qwen3-0.6B. Mức tăng 0,919 lên 0,959 được gọi là “40-point gain”, trong thực tế là 0,040 tuyệt đối, tức 4 điểm phần trăm.

Những điểm này không phủ nhận giá trị của bài báo. Chúng chỉ xác định các chỗ mà đề tài có thể thiết kế chặt hơn.

## 4. Đánh giá hệ thống hiện tại của nhóm

### 4.1 Những gì đã hoàn thành tốt

- Có CVSchema 2.0 thống nhất và chính sách kỹ năng đã được nhóm duyệt.
- Có Parser v1 đóng băng, hash nguồn và quy tắc recovery rõ ràng.
- Có Qwen3-4B-Instruct-2507 QLoRA được huấn luyện trên 850 mẫu, 1 epoch, rank 16; quá trình huấn luyện hoàn tất trên T4 khoảng 38 phút.
- Có baseline Qwen gốc và adapter trên cùng validation/test, cùng revision model, prompt, quantization và greedy decoding.
- Test khóa cho thấy adapter cải thiện so với Qwen gốc:

| Chỉ số, 75 test tổng hợp EN | Qwen gốc | Qwen + QLoRA |
|---|---:|---:|
| Recoverable JSON | 97,33% | 100,00% |
| Schema valid | 97,33% | 100,00% |
| Skill policy valid | 53,33% | 100,00% |
| Exact full JSON | 1,33% | 76,00% |
| Micro F1 | 87,98% | 99,52% |
| Macro F1 có support | 78,58% | 98,85% |
| Chạm max token | 2,67% | 0,00% |

- OCR tiếng Việt đã có pilot cho hướng lai Paddle detector + VietOCR Seq2Seq + Paddle contact fallback. Trên 5 trang thử, Token F1 đạt 94,66%, recall token có dấu 96,57% và định danh đúng tuyệt đối 13/15.

### 4.2 Các giới hạn khiến chưa thể kết luận hệ thống đầu cuối tốt

1. **Test model không chứa OCR.** Manifest ghi rõ ảnh không được tải; `resume_text` là input của model.
2. **Validation và test đều là 75 CV tổng hợp tiếng Anh.** Chưa có CV tiếng Việt và CV thật.
3. **Train/validation/test cùng một dataset và cùng cách sinh.** Kết quả gần trần có thể phản ánh cấu trúc nhãn ổn định và miền dữ liệu hẹp. Cần kiểm tra near-duplicate và template leakage.
4. **Bốn trường không có gold support:** GitHub, GPA, activities và awards. Hệ thống chưa được chứng minh ở các trường này.
5. **Một số trường vẫn khó:** `projects.role` F1 87,58% và `certifications` F1 95,74% trên test adapter.
6. **Strict JSON của adapter bằng 0%.** Tất cả output cần Parser v1 bỏ wrapper `<think>` hoặc `</tool_call>`. Recoverability đạt 100%, nhưng format chưa sạch ngay từ model.
7. **Đầu ra dài được model sinh lại.** Điều này tốn token, có nguy cơ paraphrase và không có bằng chứng dòng.
8. **OCR hiện chọn một đường cho trang.** Chưa hợp nhất text PDF và OCR theo vùng; chưa giữ bounding box xuyên suốt pipeline.
9. **Chưa có layout regenerator.** Multi-column có thể bị đảo section hoặc gắn sai mô tả với entity.
10. **Chưa có đo end-to-end trên 80 CV thật.** Vì vậy chưa biết tỷ lệ lỗi đến từ OCR, reading order, model hay parser.
11. **Chưa có benchmark độ trễ chuẩn.** Cần đo p50/p95 theo từng stage, input/output token và peak VRAM trên cùng T4.

### 4.3 Kết luận khoa học về baseline hiện tại

Có thể khẳng định:

> QLoRA giúp Qwen3-4B học rất tốt phép biến đổi từ text tổng hợp của Resume Parsing Vision sang CVSchema 2.0 và cải thiện rõ so với Qwen gốc trên cùng phân phối dữ liệu.

Chưa thể khẳng định:

> Pipeline OCR + Qwen đạt 99,52% trên CV thật tiếng Việt và tiếng Anh.

## 5. Khoảng cách giữa bài báo và hệ thống hiện tại

| Thành phần | Bài báo | Hệ thống hiện tại | Hành động |
|---|---|---|---|
| PDF + OCR | Fusion theo vùng và tọa độ | Chọn native text hoặc OCR theo trang | Xây region-level fusion |
| OCR đa ngôn ngữ | Trung–Anh | Paddle EN; hybrid VietOCR VI | Giữ ưu thế song ngữ, thêm confidence |
| Bố cục | YOLOv10 + sắp xếp hai cấp | Chưa có | Thêm rule baseline và detector tùy dữ liệu |
| Biểu diễn | Dòng có index | Text phẳng | Gán page/line id ổn định |
| Extraction | Prompt phân rã | Một prompt full schema | Tạo 4 task chuyên biệt |
| Long text | Trả span dòng | Sinh toàn văn | Pointer + deterministic copy |
| Grounding | Kiểm tra với nguồn | Schema/policy parser | Thêm evidence sidecar và verifier |
| Retry | Không nêu rõ | Chạy lại toàn CV thủ công | Retry đúng task/field lỗi |
| Model | 0.6B full SFT | 4B QLoRA | So 0.6B task-SFT/QLoRA với 4B baseline |
| Evaluator | Hungarian + field rules | Normalized exact set | Nâng cấp evaluator v2 |
| Test | Synthetic + real | Synthetic EN text | Tạo test thật EN/VI đã khóa |

## 6. Đề xuất cải tiến chính

### 6.1 Tên hướng nghiên cứu

**Adaptive bilingual layout-aware and evidence-grounded resume extraction with compact Qwen.**

Diễn đạt tiếng Việt:

**Trích xuất CV song ngữ thích ứng theo bố cục và bằng chứng nguồn bằng mô hình Qwen gọn nhẹ.**

### 6.2 Kiến trúc đề xuất

```text
PDF/DOCX
   |
   v
Primitive extractor
  - PDF text + bbox
  - OCR vùng ảnh
  - language/confidence metadata
   |
   v
Adaptive fusion + de-duplication
   |
   v
Layout ordering
  - rule-based baseline
  - fine-tuned lightweight detector for complex pages
   |
   v
Indexed lines [page:line] + section routing
   |
   +--> Basic/Summary/Skills task
   +--> Experience task
   +--> Project task
   +--> Education/Other task
            |
            v
Qwen task adapter outputs value + evidence_line_ids
            |
            v
Evidence verifier + targeted retry
            |
            v
CVSchema 2.0 + evidence sidecar + audit log
```

### 6.3 Cải tiến 1 - Fusion theo vùng, ngôn ngữ và độ tin cậy

Thay router cấp trang bằng primitive cấp vùng:

- Lấy từng span text PDF và bounding box.
- Che vùng text PDF rồi OCR vùng ảnh còn lại.
- Nếu text PDF có font lỗi, ký tự thay thế hoặc tỷ lệ ký tự lạ cao, OCR lại đúng vùng.
- Với tiếng Anh dùng PaddleOCR recognizer EN.
- Với tiếng Việt dùng Paddle detector + VietOCR; dòng email, URL và điện thoại dùng contact fallback.
- Ghép primitive trùng nhau bằng IoU bounding box và text similarity.
- Lưu `source_type`, `ocr_confidence`, `language` và bbox cho từng dòng.

Điểm mới so với bài báo là lựa chọn recognizer song ngữ và quyết định fusion dựa trên chất lượng từng vùng.

### 6.4 Cải tiến 2 - Section routing trước task decomposition

Bài báo gửi toàn bộ CV cho từng prompt. Nhóm nên xác định các section ứng viên từ heading và layout, sau đó gửi phần liên quan cho task tương ứng. Mỗi task vẫn nhận vài dòng lân cận để giữ ngữ cảnh.

Lợi ích cần kiểm chứng:

- Giảm input token bị lặp.
- Giảm việc lấy nhầm trường giữa Experience và Project.
- Có thể batch các task trên một GPU thay vì giả định hạ tầng song song.

### 6.5 Cải tiến 3 - Evidence pointer cho cả trường ngắn và dài

Đầu ra nội bộ của mỗi task nên có dạng:

```json
{
  "value": "Backend Developer",
  "evidence_line_ids": ["p1_l18"],
  "confidence": "high"
}
```

Với description/details, `value` được dựng lại hoàn toàn từ các dòng nguồn. Với named entity, verifier kiểm tra normalized value xuất hiện trong evidence. Confidence không dùng xác suất do model tự khai; nó được tính từ các tín hiệu kiểm chứng như span hợp lệ, source match, OCR confidence và schema validity.

CVSchema 2.0 vẫn là đầu ra cuối. Evidence được lưu trong sidecar để không phá hợp đồng schema hiện tại.

### 6.6 Cải tiến 4 - Targeted retry

Chỉ chạy lại khi có lỗi cụ thể:

- JSON hoặc schema lỗi: chạy lại task tương ứng với schema ngắn hơn.
- Evidence id ngoài phạm vi: yêu cầu chọn lại span.
- Named entity không xuất hiện trong nguồn: chạy lại trên section hẹp.
- OCR confidence thấp ở evidence: chạy recognizer thay thế cho đúng crop rồi trích xuất lại task.

Giới hạn tối đa một retry/task để giữ latency có thể dự đoán.

### 6.7 Lựa chọn mô hình huấn luyện

Khuyến nghị thực nghiệm:

- Giữ **Qwen3-4B QLoRA hiện tại** làm baseline B0.
- Huấn luyện **Qwen3-0.6B** theo task decomposition và pointer để tái lập ý tưởng cốt lõi của bài báo trong giới hạn Colab.
- Nếu 0.6B thiếu năng lực cho Việt–Anh, thêm Qwen cỡ trung gian như một thí nghiệm phụ; không thay baseline giữa chừng.

Không thể tái lập full-parameter SFT 8×A800 trên Colab Free. QLoRA hoặc LoRA cho 0.6B là phương án hợp lý; báo cáo phải ghi rõ đây là thay đổi về chế độ huấn luyện.

## 7. Xây dựng dữ liệu v2

### 7.1 Tập huấn luyện

Từ 850 mẫu train hiện tại:

1. Tuyến tính hóa source thành các dòng có index.
2. Chia mỗi CV thành tối đa bốn instruction sample.
3. Tự căn chỉnh description/details với dòng nguồn bằng exact normalization trước, fuzzy alignment sau.
4. Chỉ nhận nhãn pointer khi alignment vượt ngưỡng; các trường không chắc chắn cần review hoặc giữ ở dạng value-only.

850 CV có thể tạo khoảng 2.500–3.400 task sample mà không nhân bản thông tin giữa split.

### 7.2 Dữ liệu bổ sung

Tạo bộ synthetic song ngữ có layout:

- Dùng profile thuộc train hiện tại, không dùng validation/test.
- Render qua nhiều template một cột, hai cột, sidebar, icon, bảng và font khác nhau.
- Có phiên bản tiếng Việt và tiếng Anh.
- Sinh sẵn bounding box/layout/evidence từ template để giảm công dán nhãn.
- Chia theo **template family**, không chia ngẫu nhiên từng PDF, để test không dùng template đã thấy.

Mục tiêu khả thi ban đầu: 300–500 PDF synthetic, sau đó tăng nếu learning curve còn cải thiện.

### 7.3 Bộ 80 CV thật

Đề xuất phân bổ:

- **20 CV development:** 15 EN, 5 VI; chứa các CV đã dùng trong pilot OCR.
- **60 CV locked real test:** 45 EN, 15 VI; không dùng để chỉnh prompt, threshold hay train.

Cần stratify thêm theo:

- native PDF / scan / mixed;
- một cột / nhiều cột;
- một trang / nhiều trang;
- dễ / trung bình / khó theo chất lượng ảnh và font.

Nếu muốn dùng CV thật để train, phải thu thêm một tập khác. Không nên vừa dùng 80 CV để phát triển vừa gọi chúng là independent test.

### 7.4 Nhãn cần bổ sung

Mỗi CV thật cần:

- CVSchema 2.0 gold.
- Entity identity để phục vụ Hungarian matching.
- Evidence line hoặc bbox cho các trường được trích xuất.
- Layout type và document type.
- Cờ ngôn ngữ theo trang.
- Gold transcript cho một tập con OCR đủ lớn.

PII vẫn được mask trong artifact. Có thể đánh giá email/phone nội bộ bằng giá trị băm có salt hoặc chỉ bằng metric OCR định danh; không đưa giá trị thật vào dataset huấn luyện.

## 8. Baseline và ma trận thí nghiệm

### 8.1 Baseline bắt buộc

| ID | Biến thể |
|---|---|
| B0 | Pipeline hiện tại: router theo trang + text phẳng + Qwen3-4B QLoRA full schema + Parser v1 |
| B1 | Qwen3-4B gốc với cùng input/prompt B0 |
| B2 | Paper-inspired: fusion + layout order + task decomposition + pointer, chưa adaptive retry |
| P | B2 + OCR confidence routing + section routing + evidence verifier + targeted retry |

### 8.2 Ablation cho đề xuất P

| ID | Bỏ thành phần | Câu hỏi trả lời |
|---|---|---|
| A1 | Bỏ region fusion | Fusion có cải thiện CV mixed/native không? |
| A2 | Bỏ layout ordering | Multi-column giảm bao nhiêu? |
| A3 | Một prompt full schema | Task decomposition đóng góp bao nhiêu? |
| A4 | Sinh lại long text | Pointer giảm drift/token bao nhiêu? |
| A5 | Bỏ evidence verifier | Hallucination tăng bao nhiêu? |
| A6 | Bỏ targeted retry | Retry cải thiện F1 với chi phí latency bao nhiêu? |
| A7 | Gửi full CV cho mỗi task | Section routing giảm token bao nhiêu? |

Tất cả biến thể phải dùng cùng model checkpoint nếu ablation không nhằm đo huấn luyện. Cấu hình khác nhau phải được ghi vào manifest.

### 8.3 Hai chế độ đánh giá để định vị lỗi

1. **Oracle-text extraction:** dùng transcript và reading order gold. Đo riêng LLM + parser.
2. **End-to-end PDF:** dùng PDF gốc. Đo toàn pipeline OCR + layout + model + parser.

Khoảng cách giữa hai chế độ chính là tổn thất do document processing.

## 9. Metric đề xuất

### 9.1 OCR và bố cục

- CER, WER và token F1.
- Recall token có dấu tiếng Việt.
- Exact recall email/phone/URL trên tập đánh giá nội bộ.
- Reading-order pairwise accuracy hoặc Kendall correlation giữa chuỗi dòng gold/predicted.
- Layout segment mAP50 nếu fine-tune detector.

### 9.2 Trích xuất

- Schema validity và skill-policy validity.
- Micro/macro Precision, Recall, F1 theo field.
- Hungarian alignment cho Experience, Project và Education.
- Exact/normalized match cho trường ngắn.
- Span exact match, span IoU và normalized edit similarity cho long text.
- Hallucination rate: giá trị không có evidence hợp lệ.
- Evidence coverage: tỷ lệ field khác rỗng có evidence đúng.
- Exact full JSON chỉ là metric phụ vì quá nghiêm và phụ thuộc format.

### 9.3 Hiệu năng

- Input token, output token và tổng token/CV.
- p50, p95 latency theo stage và end-to-end.
- Peak GPU VRAM, peak RAM.
- Số task retry/CV.
- Throughput trên T4 với batch cố định.

### 9.4 Báo cáo độ tin cậy

- 95% bootstrap confidence interval theo CV.
- Paired bootstrap cho chênh lệch F1 giữa B0, B2 và P.
- Báo kết quả theo slice EN/VI, scan/native, single/multi-column.
- Không tuyên bố cải thiện nếu interval của delta còn bao gồm 0, trừ khi mục tiêu chính là giảm token/latency với chất lượng tương đương đã định nghĩa trước.

## 10. Tiêu chí thành công nên đăng ký trước

Trước khi mở locked real test, chốt các ngưỡng sau trên development set:

- Primary: Micro F1 end-to-end của P cao hơn B0.
- Long-text F1 hoặc span IoU tăng rõ trên multi-column.
- Hallucination rate giảm.
- Schema validity không thấp hơn B0 quá 1 điểm phần trăm.
- Output token giảm ít nhất 30% nhờ pointer; đây là giả thuyết cần đo, chưa phải kết quả.
- p95 latency không tăng quá mức đã thống nhất; báo riêng có và không có retry.
- Kết quả VI không bị che bởi số lượng mẫu EN lớn hơn; luôn báo macro theo ngôn ngữ.

Không đặt mục tiêu “vượt F1 0,964 của bài báo” vì hai dataset, schema và cách matching khác nhau.

## 11. Kế hoạch triển khai

### Giai đoạn 0 - Đóng băng baseline hiện tại (1–2 ngày)

- Giữ nguyên Parser v1 và artifact B0.
- Tạo manifest cho 80 CV, đánh dấu các mẫu đã dùng trong OCR pilot.
- Chốt protocol dev/test và cấm mở gold test trong quá trình phát triển.

### Giai đoạn 1 - Evaluator v2 và nhãn real dev (3–5 ngày)

- Viết Hungarian entity alignment.
- Viết matcher theo loại field và evidence metrics.
- Double-annotate ít nhất 10 CV; giải quyết bất đồng và cập nhật guideline.
- Tạo unit test cho order mismatch, quantity mismatch, duplicate entity và partial match.

### Giai đoạn 2 - Primitive fusion và reading order (5–7 ngày)

- Giữ bbox từ PyMuPDF/PaddleOCR.
- Region OCR, de-duplication và language-aware recognition.
- Rule-based column clustering làm baseline.
- Đo OCR/read-order trên dev trước khi kết nối LLM.

### Giai đoạn 3 - Tạo task/pointer dataset (3–5 ngày)

- Chuyển 850 train thành task-specific JSONL.
- Tạo evidence line label tự động và báo tỷ lệ alignment thành công.
- Review các trường có độ tin cậy thấp.
- Sinh một lô synthetic bilingual layout nhỏ.

### Giai đoạn 4 - Huấn luyện compact Qwen trên Colab (2–4 ngày)

- Smoke run trên 50–100 task sample.
- QLoRA 0.6B, checkpoint lên Drive và resume khi Colab ngắt.
- Full run; đánh giá dev; chỉ thay đổi cấu hình dựa trên dev.
- Nếu thiếu năng lực, chạy model cỡ trung gian như thí nghiệm đã đăng ký.

### Giai đoạn 5 - Evidence verifier và targeted retry (3–4 ngày)

- Kiểm tra span, source match, schema và OCR confidence.
- Retry tối đa một lần cho task lỗi.
- Ghi nguyên nhân retry vào audit log.

### Giai đoạn 6 - Ablation và locked test (3–5 ngày)

- Chốt code, prompt, parser/evaluator version và hash.
- Chạy B0, B2, P và ablation đã đăng ký trên 60 real test đúng một vòng.
- Tạo bootstrap CI, bảng slice và error taxonomy.

Tổng thời gian khả thi: khoảng 3–5 tuần tùy tiến độ dán nhãn.

## 12. Thứ tự ưu tiên nếu thời gian hạn chế

### Phạm vi tối thiểu đủ thành đề tài cải tiến

1. Dataset task-specific có line pointer.
2. Qwen3-0.6B QLoRA được huấn luyện.
3. Task decomposition + pointer + deterministic reconstruction.
4. Evaluator Hungarian + field-aware metrics.
5. Test trên CV thật EN/VI với B0 và phương pháp mới.

### Mở rộng nếu còn thời gian

1. Region-level text/OCR fusion.
2. Layout detector fine-tuned.
3. Section routing.
4. Confidence-guided targeted retry.

Không nên đưa RAG hoặc multi-agent vào phiên bản chính lúc này. Chúng làm tăng số biến và chi phí, trong khi vấn đề lớn nhất đã thấy là grounding, layout và domain shift. Few-shot có thể là một baseline prompt nhỏ; RAG chỉ nên dùng để lấy ví dụ cùng loại bố cục sau khi pipeline chính ổn định.

## 13. Cách trình bày đóng góp với giảng viên

Có thể phát biểu:

> Đề tài kế thừa framework layout-aware của Zhu và cộng sự, bao gồm hợp nhất nguồn text/OCR, tuyến tính hóa bố cục, task decomposition, index pointer và đánh giá entity bằng Hungarian matching. Trên cơ sở đó, đề tài đề xuất cơ chế trích xuất song ngữ Việt–Anh theo độ tin cậy ở mức vùng, định tuyến section để giảm input token, và evidence-grounded targeted retry để tăng khả năng truy vết. Hệ thống được huấn luyện bằng QLoRA trong giới hạn Colab và được đánh giá bằng ablation trên cùng một bộ CV thật đã khóa.

Không nên phát biểu:

- “Mô hình đạt 99,52% trên CV thực tế.”
- “Mô hình tốt hơn bài báo vì F1 của nhóm cao hơn.”
- “VietOCR đã tốt cho toàn bộ 20 CV tiếng Việt” khi pilot mới có 5 trang.

## 14. Quyết định đề xuất

1. Giữ pipeline hiện tại làm baseline B0; không huấn luyện lại hoặc thay parser v1.
2. Tạo protocol 20 real dev / 60 locked real test trước khi phát triển tiếp.
3. Xây evaluator v2 và evidence annotation trước model v2.
4. Triển khai task decomposition + line pointer trước; đây là cải tiến có bằng chứng mạnh nhất từ bài báo và khả thi nhất trên Colab.
5. Huấn luyện Qwen3-0.6B QLoRA task-specific; so chất lượng, token và latency với Qwen3-4B QLoRA hiện tại.
6. Sau đó thêm region fusion và adaptive retry; mỗi bước phải có ablation riêng.
