# Tổng hợp và rà soát toàn bộ dự án KLCN029

**Ngày rà soát:** 11/10/2026, múi giờ Việt Nam.  
**Thư mục dự án:** `D:\CNTT-KLCN029`.  
**Đề tài:** Nghiên cứu hệ thống hỗ trợ đánh giá và cải thiện CV sử dụng mô hình ngôn ngữ lớn.  
**Căn cứ:** cấu trúc thực tế trên ổ đĩa, mã nguồn, notebook, tài liệu, nhãn, artifact và lịch sử Git tại thời điểm rà soát.

Tài liệu này là bản tổng hợp hiện trạng. “Đã có mã”, “đã chạy”, “đã đo chất lượng” và “đã triển khai dịch vụ” được phân biệt theo bằng chứng. Các số liệu thực nghiệm được lấy từ báo cáo/artifact đã lưu; trong lần rà soát này chỉ chạy kiểm tra cục bộ, không huấn luyện lại hay gọi model/API. Nội dung khóa bí mật và thông tin định danh trong CV không được đưa vào bản tổng hợp.

## 1. Dự án đã làm đến đâu?

Dự án đã xây dựng được pipeline trích xuất CV có cấu trúc, hai giai đoạn huấn luyện Qwen bằng QLoRA, bộ đánh giá ngoại tuyến, công cụ gán nhãn, công cụ rà gold và demo đánh giá CV theo JD. Đã có checkpoint adapter, log huấn luyện, raw output và báo cáo so sánh trên dữ liệu tổng hợp lẫn CV thật.

Kết quả quan trọng nhất hiện tại: **mô hình fine-tune đạt F1 khoảng 99% trên dữ liệu tổng hợp tiếng Anh, nhưng chưa vượt Qwen gốc trên GOLD40 CV thật**. Qwen gốc đạt Field Micro F1 65,52%; adapter Full JSON đạt 48,28%; Hybrid Pointer P0/P1 đạt 49,66%/52,81%. Đây là kết quả của mô-đun trích xuất, chưa phải chất lượng toàn hệ thống đánh giá CV.

| Mảng công việc | Hiện trạng và bằng chứng |
|---|---|
| Phạm vi và thiết kế | Có kế hoạch nghiên cứu, quyết định phạm vi và hợp đồng bàn giao giữa mô-đun |
| Dữ liệu CV thật | Có 80 PDF: 60 EN, 20 VI; kiểm kê lịch sử ghi 110 trang và 77 nội dung độc nhất theo SHA-256 |
| Corpus văn bản | Có JSONL đầu vào, metadata, khối văn bản và split; corpus này không phải gold |
| Schema CV/JD | Có CVSchema 2.0, JDSchema và JSON Schema xuất từ Pydantic |
| Baseline API | Có pipeline và pilot Groq 2 CV theo schema v1; không có bằng chứng đã chạy Groq toàn bộ 80 CV |
| OCR | Đã pilot PaddleOCR EN/VI và VietOCR hybrid trên 5 trang VI; có báo cáo định lượng |
| Chuẩn bị dữ liệu train | Có hai bộ tổng hợp Full JSON/Hybrid Pointer, mỗi bộ 850 train, 75 validation, 75 test |
| Huấn luyện | Có adapter Full JSON stage 1 và adapter Hybrid Pointer stage 2 full; stage 2 hiện có tiếp tục trên dữ liệu tổng hợp Pointer |
| Parser/evaluator | Có parser nghiêm ngặt, pointer reconstruction, metric, snapshot parser đóng băng và manifest |
| Thực nghiệm dữ liệu tổng hợp | Có so sánh validation/test của Qwen gốc, adapter stage 1 và P0 |
| Thực nghiệm 80 CV thật | Có P0 toàn bộ 80 CV và P1 retry 9 CV lỗi; P1 dựng được 78/80 CVSchema |
| GOLD40 | Có 40 gold JSON và 40 sidecar trạng thái, 20 EN/20 VI; đã so sánh B0/B1/P0/P1 |
| Gán nhãn và rà gold | Có hai web app riêng, workbook, backup, audit và gói rà portable cho nhóm |
| Matching/chấm điểm/gợi ý | Có baseline xác định, module M1/M2/M3 và notebook prototype; chưa có benchmark gold của người đánh giá để kết luận chiến lược nào tốt hơn |
| Demo | Có Flask web MVP, notebook Colab tuyến tính và giao diện Colab; có ZIP chạy đầu cuối |
| Cloud | Có Docker, cấu hình Render, worker RunPod và smoke script; tài liệu ghi tạm dừng cloud từ 07/10 do ngân sách, chưa có bằng chứng smoke GPU/cloud thành công |
| Báo cáo | Có báo cáo tiến độ Word/PDF, khung viết mô-đun, phân tích bài báo và báo cáo lỗi/chẩn đoán GOLD40; chưa xác nhận báo cáo khóa luận cuối cùng và slide bảo vệ |

Nguồn ưu tiên cho hiện trạng mới nhất: [quyết định phạm vi](PROJECT_SCOPE_AND_DECISIONS.md), [bản đo GOLD40 bốn cấu hình](../training/evaluation/results/gold40_b0_b1_p0_p1_v1/REPORT.md), [chẩn đoán ngày 11/10](GOLD40_CHAN_DOAN_TONG_QUAT_HOA_VA_RASOAT_2026-10-11.md).

## 2. Kiến trúc và luồng dữ liệu

```text
CV PDF EN/VI
  │
  ├─ PDF có text ──────────────── PyMuPDF
  └─ Trang cần OCR ────────────── PaddleOCR EN / VietOCR hybrid VI
                                  │
                                  ▼
                          Text, trang và dòng nguồn
                                  │
             ┌────────────────────┴───────────────────────┐
             │                                            │
       Full JSON B0/B1                          Hybrid Pointer P0
             │                                            │
       Parser CVSchema                     Parser Pointer + kiểm tra span
             │                                  + dựng lại văn bản
             │                                            │
             │                               P1 retry CV bị từ chối
             └────────────────────┬───────────────────────┘
                                  ▼
                    CVSchema 2.0 + evidence + manifest
                                  │
JD text ──────────────────────────┤
                                  ▼
                 Matching / chấm điểm / gợi ý riêng
                                  │
                                  ▼
                         Kết quả web hoặc Colab
                                  │
                    Có opt-in nghiên cứu: lưu hồ sơ
                    Opt-out: xử lý tạm, xóa theo luồng
```

Đây là sơ đồ các nhánh đã có trong dự án, không có nghĩa mọi nhánh đã chạy cùng một phép đánh giá đầu cuối. Pilot OCR VI, benchmark extraction và benchmark matching phải được báo riêng.

- Mô-đun extraction bàn giao `cv.json`, `evidence.json`, `extraction_manifest.json` theo [hợp đồng](../training/EXTRACTION_MODULE_CONTRACT.md). Pointer và raw output là biểu diễn nội bộ.
- Evidence Pointer hiện chủ yếu phục vụ các trường dài như summary, mô tả kinh nghiệm và details dự án; chưa đủ để tuyên bố mọi trường đều có grounding.
- JDSchema đã có trong hợp đồng. Demo hiện nhận JD text; pipeline chuẩn hóa JD độc lập và benchmark JD chưa được xác nhận hoàn thiện.
- Các hướng fusion theo vùng, tái dựng layout và retry theo từng trường trong tài liệu nghiên cứu là hướng phát triển. P1 đã đo hiện chọn các CV lỗi và sinh lại JSON Pointer; chưa phải chỉ vá riêng trường lỗi.

**Quy ước tên trong bản tổng hợp:** extraction dùng B0 = Qwen gốc, B1 = adapter Full JSON, P0 = adapter Pointer, P1 = P0 + retry. `deterministic_b1` trong matching là baseline matching khác. Tài liệu phân tích bài báo cũ có bảng B0/B1 theo quy ước khác; cần ghi tên đầy đủ khi dùng lại bảng.

## 3. Công việc đã thực hiện theo từng thành phần

### 3.1. Phạm vi, kế hoạch và nghiên cứu nền

- Lập [kế hoạch nghiên cứu](../Ke_hoach_nghien_cuu_KLCN029.md): mục tiêu, câu hỏi nghiên cứu, rubric đề xuất, dữ liệu, thực nghiệm, phân công và lịch 12 tuần.
- Chốt phạm vi toàn hệ thống gồm extraction, JD, matching, chấm điểm, giải thích/gợi ý và tích hợp. Extraction là một mô-đun đầu vào.
- Đọc và phân tích bài báo `2510.09722v1`; lưu PDF, bản Markdown và [phân tích ứng dụng vào đề tài](phan_tich_bai_bao_2510_09722_va_ke_hoach_cai_tien.md).
- Xây dựng [khung báo cáo mô-đun](KHUNG_BAO_CAO_MODULE_TRICH_XUAT.md), phân biệt phần kế thừa Pointer với điều chỉnh và giả thuyết cải tiến của nhóm.
- Tạo báo cáo tiến độ bằng `reports/build_progress_report.py`; có DOCX tại root và `reports/`, cùng PDF/ảnh render để kiểm tra bố cục.

Kế hoạch và tài liệu phân tích ghi cả phương án dự kiến. Có đề xuất trong tài liệu không tự chứng minh phương án đó đã được triển khai hoặc nghiệm thu.

### 3.2. Dữ liệu đầu vào và cách chia tập

| Bộ dữ liệu | Nơi lưu | Vai trò / quy mô |
|---|---|---|
| PDF nguồn EN | `CV_EN_PDF/` | 60 PDF tiếng Anh |
| PDF nguồn VI | `CV_VN_PDF/` | 20 PDF tiếng Việt |
| Corpus v2 | `corpus_v2/` | 80 bản ghi đầu vào; 73 bản chính theo cờ deduplicate, split 16/15/42 |
| Manifest baseline | `baseline_extraction/data/` | Manifest, input audit, split baseline test 20 CV độc nhất: 15 EN/5 VI |
| Dữ liệu tổng hợp Full JSON | `training/data/resume_parsing_vision_cvschema_v2/` | 850/75/75 train/validation/test |
| Dữ liệu tổng hợp Pointer | `training/data/resume_parsing_vision_cvschema_v2_pointer_v1/` | 850/75/75, thêm đánh số dòng và target span |
| Real80 Pointer input | `experiments/baseline80/real_cv_pointer_inputs_v1/` | 80 đầu vào đã chuẩn bị và log routing |
| P1 retry input | `experiments/baseline80/real80_selective_retry_p1_v1/` | 9 CV P0 lỗi cấu trúc |
| GOLD40 input | `training/data/gold40_cvschema2_inputs_v1/` | 40 input cho đối chứng B0/B1 |
| GOLD40 đáp án | `annotation/gold_v2/` | 40 JSON CVSchema và 40 JSON trạng thái |

Các split này thuộc những giao thức khác nhau. Không trộn test baseline 20 CV, corpus test 42 CV, synthetic test 75 mẫu và GOLD40 40 CV trong cùng phép đánh giá.

Theo [audit corpus](../corpus_v2/AUDIT.md), có 3 cặp trùng byte và 4 cặp gần trùng theo quy tắc corpus. Vì vậy “77 nội dung độc nhất theo SHA-256” khác “73 bản chính” và không chứng minh số ứng viên độc lập.

Hai script `prepare_external_dataset.py` và `prepare_pointer_dataset.py` thực hiện ánh xạ nhãn, mask tên/email/điện thoại, tạo chat messages, manifest và hash. Pointer converter đã có báo cáo round-trip 1.000/1.000 mẫu; lần rà soát này xác nhận lại số dòng 850/75/75 của cả hai bộ.

### 3.3. Schema và baseline extraction

- `baseline_extraction/schema.py`: nguồn định nghĩa CVSchema 2.0 và JDSchema; gồm thông tin cá nhân được mask, summary, skills, experience, projects, education, certifications, activities, awards.
- `contracts/`: JSON Schema máy đọc được; `export_schemas.py` xuất từ hợp đồng Python.
- `prompts.py`: prompt dùng cho inference và chuẩn bị dữ liệu huấn luyện.
- `prepare_manifest.py`, `make_split.py`: kiểm kê PDF, metadata, hash và chia tập.
- `run.py`: đọc tài liệu/OCR, gọi nhà cung cấp LLM, parse và lưu kết quả vận hành.
- `privacy.py`: che các loại định danh theo quy tắc; không bảo đảm loại bỏ mọi dạng tái định danh trong văn bản tự do.
- `evaluate.py`: đánh giá trường CV theo schema; có test hợp đồng API/schema/redaction/evaluator.

Pilot Groq đã lưu **2 CV theo schema v1.0**: một kết quả `ok`, một kết quả cần review dẫn chứng. Hai JSON lịch sử tại `outputs/pilot/` không dùng trực tiếp như output v2.0. Tài liệu baseline cũ chưa được cập nhật toàn bộ theo GOLD40 mới.

### 3.4. OCR EN/VI

Đã thử PaddleOCR trên 5 trang VI và một CV scan EN; đã phát hiện rule “ít hơn 80 ký tự thì OCR” gây chọn nhầm các trang gần trắng. Rule ứng viên bổ sung mật độ pixel tối, chỉ chọn EN047 trên corpus hiện có.

| Phương án, pilot 5 trang VI | Token F1 | Recall token có dấu |
|---|---:|---:|
| PaddleOCR v5 Latin | 55,81% | 39,60% |
| VietOCR VGG Seq2Seq | 94,15% | 96,57% |
| VietOCR VGG Transformer | 96,38% | 99,01% |
| Seq2Seq + contact fallback | 94,66% | 96,57% |
| Transformer + contact fallback | 96,82% | 99,01% |

Pilot chọn PaddleOCR detector + VietOCR Seq2Seq + PaddleOCR fallback cho liên hệ đối với trang VI cần OCR. Transformer giữ làm đối chứng chất lượng. Nguồn: [PaddleOCR pilot](../experiments/ocr/paddleocr_pilot_v1/REPORT.md), [VietOCR hybrid pilot](../experiments/ocr/vietocr_hybrid_pilot_v1/REPORT.md).

Giới hạn: 5 trang VI được raster từ PDF có text sạch, chưa đại diện cho ảnh scan/máy ảnh thực tế. Thời gian recognizer tái dùng detector không thể so trực tiếp với thời gian toàn pipeline PaddleOCR. Trong batch Real80, 79 CV dùng PDF text và EN047 dùng OCR EN; GOLD40 cũng không đo OCR tiếng Việt.

### 3.5. Huấn luyện Qwen và notebook Colab

Mô hình dùng trong nhánh huấn luyện là `Qwen/Qwen3-4B-Instruct-2507`. Có notebook huấn luyện, script dựng notebook, validator, gói dữ liệu và SHA-256 để xác minh dữ liệu/adapter.

| Giai đoạn đã có artifact | Dữ liệu / phương pháp | Bằng chứng hoàn tất |
|---|---|---|
| Stage 1 Full JSON | 850 mẫu tổng hợp EN; QLoRA NF4, LoRA rank 16, alpha 32; 1 epoch | 107 optimizer steps; `final_adapter-full_1.zip`; run config, metrics, Trainer state và audit |
| Stage 2 Hybrid Pointer full | Continued QLoRA từ adapter stage 1 trên 850 mẫu tổng hợp Pointer; 1 epoch | 107 optimizer steps; adapter full, log loss và manifest; đã chạy validation/test P0 |
| Stage 2 smoke | Chạy thử ngắn để kiểm tra pipeline | Adapter smoke và artifact bổ sung; không thay thế kết quả full |

Theo audit, stage 1 có runtime Trainer khoảng 38 phút 12 giây, eval loss cuối 0,010912. Stage 2 full khoảng 2 giờ 55 phút 52 giây, eval loss cuối 0,014881. Loss/token accuracy teacher-forced không thay thế đánh giá sinh tự do.

**Điểm cần diễn giải đúng:** README training ban đầu đề xuất giai đoạn 2 thích nghi trên CV thật EN/VI. Artifact stage 2 hiện có là Hybrid Pointer trên dữ liệu tổng hợp EN; chưa tìm thấy bằng chứng một run SFT trên gold CV thật EN/VI.

Các nhóm notebook tại `training/colab/`:

- Huấn luyện: `Qwen3_CVSchema2_QLoRA_Colab.ipynb`, `Qwen3_CVSchema2_Hybrid_Pointer_Stage2_Colab.ipynb`.
- Validation/test Full JSON: notebook Qwen gốc, adapter và raw locked test.
- Validation/test Pointer: raw validation và locked test stage 2.
- CV thật: Real80 P0, Real80 selective retry P1, GOLD40 B0/B1.
- Demo: Single CV, Pointer EndToEnd CV–JD và Pointer Colab UI.

Notebook mới thường được lưu không có output cell; bằng chứng đã chạy nằm ở ZIP raw output, adapter và báo cáo audit. Xem [hướng dẫn Colab](../training/colab/README.md) và [hướng dẫn GOLD40 B0/B1](../training/colab/HUONG_DAN_CHAY_GOLD40_B0_B1.md).

### 3.6. Parser, metric và truy nguyên kết quả

- Parser CVSchema chỉ loại wrapper hoàn chỉnh đã quy định: leading think, leading tool-call closers, Markdown fence bao toàn output. Không tự bổ sung khóa hoặc sửa JSON bị cắt.
- Parser Pointer xác minh schema, kiểu/giới hạn dòng, dựng lại nội dung từ nguồn, kiểm tra CVSchema và trả lỗi theo field path/retry targets.
- Hai snapshot đóng băng được giữ tại `training/evaluation/frozen/`; có manifest/hash cùng schema và code evaluator.
- Metric field dùng exact set sau NFKC/casefold/chuẩn hóa khoảng trắng. Không tự dịch, ghép synonym hoặc bỏ dấu để nâng số liệu.
- Evaluator GOLD40 có phân tích all/EN/VI, field F1, entity exact, long text, lỗi và bootstrap theo CV.
- Kết quả giữ raw ZIP, sample results, CSV metric, summary JSON và snapshot mã để tái lập.

Phải báo riêng strict JSON, recoverable JSON, schema validity, skill policy và F1 nội dung. Chúng đo các tính chất khác nhau.

### 3.7. Gán nhãn và rà GOLD40

`annotation_app/` là Flask app hiển thị PDF và form CVSchema, lưu vào workbook theo vòng A/B/FINAL. Đã có CSRF, chế độ LAN có mã truy cập, khóa Excel, revision conflict, backup và xuất gold/sidecar.

GOLD40 đã chốt FINAL ngày 10/10: **40/40 mẫu, 20 EN/20 VI**. Ba mẫu được trợ lý hỗ trợ hoàn tất từ PDF theo yêu cầu trước đó, có changelog trong audit. Lần rà soát này kiểm tra lại 40 JSON đều đúng schema và hiện có đủ 40 sidecar.

Giới hạn nguồn gốc nhãn: bản A/B trước phân xử không còn được giữ, nên không tính được IAA lịch sử. Kiểm tra kỹ thuật 40/40 không chứng minh mọi nhãn đúng về nội dung. GOLD40 là hậu kiểm vì pipeline đã chạy Real80 trước khi nhãn hoàn tất.

`gold_review_app/` bổ sung lượt rà mới: snapshot gold/PDF/quy tắc, 19 trường cần đối chiếu, bằng chứng và đề nghị sửa, lịch sử theo người rà, xuất ZIP, kiểm tra hash và chống ghi đè. Có gói `dist/GOLD40_Review_Team_v1.zip` chứa 40 PDF và snapshot gold.

Bộ 10 CV ưu tiên là mẫu chẩn đoán lỗi; không dùng tỷ lệ lỗi của bộ này để suy rộng cho toàn GOLD40. Đề nghị trong công cụ không tự ghi đè gold và chưa có bằng chứng đã được phân xử thành phiên bản gold mới. Nguồn: [audit chốt FINAL](../annotation/audits/gold40_final_2026-10-10_complete/REPORT.md), [README công cụ rà](../gold_review_app/README.md).

### 3.8. Matching, web và demo đầu cuối

- `MatchCV_JD&Baseline.ipynb` là prototype matching: keyword, embedding, rubric LLM, few-shot, retrieval và các vai trò HR/tech lead/critic. Notebook có output lưu sẵn nhưng chưa đủ thành benchmark với điểm gold của chuyên gia.
- `cv_evaluation_web/`: Flask + Waitress + Jinja/HTML/CSS/JS, nhận PDF/JD, giới hạn file/trang, consent, kết quả, lưu opt-in và rút dữ liệu bằng mã.
- `services/evaluator.py`: baseline xác định, rubric ATS 20 + Impact 30 + JD/Semantic 35 + Tone 15. Rubric này khác rubric đề xuất trong kế hoạch nghiên cứu ban đầu.
- `services/llm_matching.py`: M1 zero-shot, M2 few-shot và M3 retrieval từ rubric nội bộ, gọi Groq khi cấu hình và đồng thuận phù hợp. Đã tích hợp lựa chọn trong notebook Colab; chưa xác nhận web Flask có lựa chọn M1/M2/M3 cho người dùng.
- M3 hiện truy xuất kho rubric nội bộ nhỏ bằng quy tắc token; không phải kho tri thức học thuật/vector RAG đã được đánh giá đầy đủ.
- `services/runpod_client.py`, `job_store.py`: tích hợp job bất đồng bộ, polling/webhook, lưu trạng thái.
- `training/evaluation/deployment_policy.py`: policy cho CV thật, tách quyết định cho demo khỏi parser benchmark đã đóng băng.
- Hai notebook demo Colab dùng extraction trước, matching sau; có consent/receipt và luồng lưu nghiên cứu/rút dữ liệu trên Drive.

Hiện có **7 ZIP** trong `training/endtoend_result/`; báo cáo `AUDIT_2026-10-07.md` chỉ phân tích **4 lần chạy**. Không coi 7 ZIP là 7 ca đã kiểm tra nội dung đầy đủ. Audit 4 ca ghi pipeline chạy hết, CVSchema hợp lệ 4/4, nhưng còn lỗi reading order hai cột, span thiếu/lẫn mục và điểm ATS 20/20 không phản ánh lỗi layout. Bốn ca trong audit đều `research_consent=false`, không được nhập vào dữ liệu nghiên cứu từ các lượt đó.

Chưa có bằng chứng benchmark có gold để đánh giá độ đúng matching, rubric hay chất lượng gợi ý. Nguồn: [rà notebook/kiến trúc](../cv_evaluation_web/ARCHITECTURE_AND_NOTEBOOK_REVIEW.md), [audit đầu cuối](../training/endtoend_result/AUDIT_2026-10-07.md).

### 3.9. Triển khai và tài liệu bàn giao

Có Docker cho web và worker Qwen, `render.yaml`, GitHub Actions build worker, prompt contract, script publish artifact và smoke Render/RunPod.

[Trạng thái triển khai](../deployment/BASELINE_DEPLOYMENT_STATUS.md) ghi đã kiểm thử local và lưu artifact private, nhưng cloud tạm dừng từ 07/10 vì ngân sách. Chưa có bằng chứng GPU RunPod nạp model và Render–RunPod vượt smoke đầu cuối. Không kiểm tra lại trạng thái tài khoản/dịch vụ bên ngoài trong lần rà soát này.

Phương án demo hiện tại là Colab có người vận hành, theo [kế hoạch Colab](../deployment/COLAB_ZERO_COST_PLAN.md); không được mô tả như dịch vụ GPU 24/7 đã triển khai.

## 4. Các kết quả định lượng đã lưu

### 4.1. Tổng hợp: validation/test tổng hợp và GOLD40 thật

| Extraction | Validation tổng hợp, F1 | Test tổng hợp, F1 | GOLD40 thật, F1 | GOLD40 schema valid |
|---|---:|---:|---:|---:|
| B0: Qwen gốc Full JSON | 88,06% | 87,98% | **65,52%** | **40/40** |
| B1: adapter stage 1 Full JSON | 99,60% | 99,52% | 48,28% | 35/40 |
| P0: Hybrid Pointer stage 2 | 99,64% | 99,19% | 49,66% | 34/40 |
| P1: P0 + retry | Chưa có bản đo riêng | Chưa có bản đo riêng | 52,81% | 39/40 |

Đây là Field Micro F1. Hai miền có cả khác dữ liệu và phạm vi nhãn nên không coi chênh lệch tổng hợp–thật là thí nghiệm chỉ thay miền đầu vào.

Nguồn: [synthetic test B0/B1](../training/evaluation/results/locked_test_base_vs_adapter_v1/comparison_report.md), [synthetic test P0](../training/evaluation/results/pointer_stage2_locked_test_p0_v1/test_report.md), [GOLD40 bốn cấu hình](../training/evaluation/results/gold40_b0_b1_p0_p1_v1/REPORT.md).

### 4.2. GOLD40 theo ngôn ngữ và văn bản dài

| Chỉ số | B0 | B1 | P0 | P1 |
|---|---:|---:|---:|---:|
| F1 EN | 72,23% | 52,16% | 55,88% | 57,20% |
| F1 VI | 58,52% | 44,16% | 42,46% | 48,05% |
| Long Text F1 | 52,73% | 39,86% | 17,39% | 16,60% |
| CV đúng toàn bộ theo document exact | 0/40 | 0/40 | 0/40 | 0/40 |
| Model calls | 40 | 40 | 40 | 46 |
| Output tokens tổng | 32.839 | 23.773 | 14.510 | 16.985 |

- B1 thấp hơn B0 17,24 điểm phần trăm F1; bootstrap ghép cặp CI 95% [-22,58; -11,75].
- P1 cao hơn P0 khoảng 3,14 điểm; CI [0,79; 6,77]. Số chênh lệch làm tròn từ dữ liệu đầy đủ có thể khác phép trừ các F1 hiển thị hai chữ số.
- P1 giảm output token 48,28% so với B0, nhưng tổng input + output tăng khoảng **8,26%** và số call tăng. Chưa chứng minh giảm tổng chi phí.
- P1 cải thiện F1 tổng và schema validity so với P0, nhưng Long Text F1 không tăng. Không diễn giải retry là sửa được mọi loại lỗi.
- Thời gian các cấu hình lấy từ những phiên khác nhau, chưa là đối chứng latency trên cùng hạ tầng.

### 4.3. Real80: khả năng dựng schema và retry

| Chỉ tiêu | P0 | P1 hiệu dụng |
|---|---:|---:|
| CVSchema hợp lệ | 71/80 (88,75%) | 78/80 (97,50%) |
| EN hợp lệ | 56/60 | 59/60 |
| VI hợp lệ | 15/20 | 19/20 |
| Model calls | 80 | 89 |
| Output tokens tổng | 26.590 | 30.027 |
| Tổng thời gian sinh đã ghi | 68,98 phút | 78,15 phút |

P1 khôi phục 7/9 CV lỗi. Artifact bàn giao gồm 35 `ready`, 43 `ready_policy_review` và 2 `manual_review` có `cvschema=null`. Policy review chủ yếu phản ánh allowlist soft skill tổng hợp chưa phù hợp CV thật; không đồng nhất với lỗi schema hay accuracy.

Nguồn: [Real80 P0](../training/evaluation/results/pointer_real80_p0_v1/real80_report.md), [Real80 P1](../training/evaluation/results/pointer_real80_selective_retry_p1_v1/selective_retry_report.md). Đây là chỉ số cấu trúc trên 80 CV; độ đúng nội dung chỉ đã được đo ở 40 CV có gold.

## 5. Sơ đồ cấu trúc thư mục lưu trữ thực tế

Cây dưới thể hiện các thư mục và artifact chính đang tồn tại. Các dòng mô tả nhóm file được ghi trong ngoặc; không liệt kê tên PDF ứng viên, backup từng lần, package cài đặt hoặc cache.

```text
D:\CNTT-KLCN029\
├── CV_EN_PDF/                         # 60 PDF nguồn EN
├── CV_VN_PDF/                         # 20 PDF nguồn VI
├── corpus_v2/                         # Corpus text + metadata, chưa phải gold
│   ├── all_80_inputs.jsonl
│   ├── corpus_deduplicated_inputs.jsonl
│   ├── dev_inputs.jsonl
│   ├── validation_inputs.jsonl
│   ├── test_inputs.jsonl
│   └── AUDIT.md
├── baseline_extraction/               # Schema và baseline đọc tài liệu/API
│   ├── schema.py, prompts.py, privacy.py, run.py
│   ├── prepare_manifest.py, make_split.py, evaluate.py
│   ├── contracts/                     # CV/JD JSON Schema
│   ├── data/                          # Manifest, audit, split và file cục bộ
│   ├── outputs/pilot/                 # Output pilot lịch sử v1
│   ├── tests/
│   └── README.md, SCHEMA_CONTRACT.md, BASELINE_REPORT.md
├── annotation/                        # Workbook và nhãn chuẩn
│   ├── CV_LABEL_TEMPLATE_v2.xlsx
│   ├── GOLD40_BATCH_v1.txt
│   ├── HUONG_DAN_GAN_NHAN_CV.md
│   ├── HUONG_DAN_DOI_CHIEU_GOLD40.md
│   ├── build_template.mjs, prepare_gold40_content_review.py
│   ├── gold_v2/                       # 40 gold + 40 status JSON
│   ├── backups/                       # Workbook trước các lần lưu
│   ├── examples/EN001_DEMO/            # Ví dụ gán nhãn
│   ├── audits/                        # Chốt FINAL, kiểm tra, hồ sơ rà
│   │   ├── gold40_final_2026-10-10/
│   │   ├── gold40_final_2026-10-10_ready/
│   │   ├── gold40_final_2026-10-10_finalize/
│   │   ├── gold40_final_2026-10-10_complete/
│   │   ├── gold40_final_2026-10-10_recheck/
│   │   └── gold40_content_review_2026-10-11/
│   └── .qa/                           # Ảnh/artefact kiểm tra giao diện
├── annotation_app/                    # Web gán nhãn vào workbook
│   ├── app.py, storage.py
│   ├── audit_gold40_final.py, finalize_gold40_reviewed.py
│   ├── complete_three_gold40.py
│   ├── static/, templates/, tests/
│   └── (launcher local/LAN và requirements)
├── gold_review_app/                   # Web rà gold độc lập theo người
│   ├── app.py, contract.py, prepare.py, test_app.py
│   ├── data/
│   │   ├── pdf/                       # 40 PDF trong gói rà riêng
│   │   ├── gold/                      # Snapshot gold + sidecar
│   │   ├── reviews/                   # Lượt rà của từng người
│   │   └── history/                   # Phiên bản lượt rà
│   ├── dist/GOLD40_Review_Team_v1.zip
│   ├── static/, templates/, .venv/
│   └── (launcher local/LAN và README)
├── experiments/                       # Pilot OCR và chuẩn bị batch CV thật
│   ├── ocr/
│   │   ├── paddleocr_pilot.py, analyze_paddleocr_pilot.py
│   │   ├── vietocr_hybrid_pilot.py, analyze_vietocr_hybrid_pilot.py
│   │   ├── paddleocr_pilot_v1/
│   │   ├── paddleocr_pilot_v3_rec_v1/
│   │   ├── vietocr_hybrid_pilot_v1/
│   │   ├── vietocr_configs/
│   │   └── .venv-vietocr/              # Môi trường OCR cục bộ
│   └── baseline80/
│       ├── prepare_real_cv_pointer_inputs.py
│       ├── prepare_real80_selective_retry.py
│       ├── real_cv_pointer_inputs_v1/
│       └── real80_selective_retry_p1_v1/
├── training/                          # Dữ liệu train, adapter, đánh giá và demo
│   ├── README.md, EXTRACTION_MODULE_CONTRACT.md
│   ├── prepare_external_dataset.py, verify_external_dataset.py
│   ├── prepare_pointer_dataset.py, verify_pointer_dataset.py
│   ├── data/
│   │   ├── resume_parsing_vision_cvschema_v2/
│   │   ├── resume_parsing_vision_cvschema_v2_pointer_v1/
│   │   └── gold40_cvschema2_inputs_v1/
│   ├── colab/
│   │   ├── (15 notebook train/eval/raw/demo)
│   │   ├── (script build/validate/package và ZIP/hash)
│   │   ├── artifacts/gold40_cvschema2_inputs_v1.zip
│   │   └── README.md, HUONG_DAN_CHAY_GOLD40_B0_B1.md
│   ├── audits/                        # Audit adapter, dataset, parser, loss
│   │   ├── gold40_generalization_2026-10-11_v1/
│   │   └── gold40_generalization_2026-10-11_v2/
│   ├── evaluation/
│   │   ├── parser.py, pointer_parser.py, metrics.py
│   │   ├── deployment_policy.py
│   │   ├── (script compare/evaluate/freeze)
│   │   ├── frozen/
│   │   │   ├── cvschema2_output_parser_v1/
│   │   │   └── cvpointer_output_parser_v1/
│   │   └── results/
│   │       ├── validation_base_vs_adapter_v1/
│   │       ├── locked_test_base_vs_adapter_v1/
│   │       ├── pointer_stage2_validation_p0_v1/
│   │       ├── pointer_stage2_locked_test_p0_v1/
│   │       ├── pointer_real80_p0_v1/
│   │       ├── pointer_real80_selective_retry_p1_v1/
│   │       ├── gold40_p0_vs_p1_v1/
│   │       └── gold40_b0_b1_p0_p1_v1/
│   ├── endtoend_result/               # 7 ZIP demo + audit 4 ca
│   ├── tests/
│   └── (ZIP adapter stage 1, stage 2 smoke/full và raw output)
├── cv_evaluation_web/                 # Web CV Insight
│   ├── app.py, storage.py, serve.py, wsgi.py
│   ├── services/
│   │   ├── pdf_extractor.py, evaluator.py, llm_matching.py
│   │   └── job_store.py, runpod_client.py
│   ├── data/
│   │   ├── submissions/, jobs/, tmp/, .qa/
│   │   └── (SQLite và trạng thái runtime)
│   ├── static/, templates/, tests/
│   └── Dockerfile, README.md, ARCHITECTURE_AND_NOTEBOOK_REVIEW.md
├── deployment/                        # Cấu hình/worker/hướng dẫn triển khai
│   ├── BASELINE_DEPLOYMENT_STATUS.md
│   ├── COLAB_ZERO_COST_PLAN.md
│   ├── DEPLOY_RENDER_RUNPOD.md
│   ├── smoke_render_e2e.py
│   └── runpod_qwen/
│       ├── handler.py, model_runtime.py, document_ingest.py
│       ├── prompting.py, prompt_contract.json, build_prompt_contract.py
│       ├── publish_artifacts.py, smoke_endpoint.py, test_handler.py
│       └── Dockerfile, requirements.txt, README.md
├── reports/                           # Tổng hợp, phân tích và báo cáo
│   ├── PROJECT_SCOPE_AND_DECISIONS.md
│   ├── KHUNG_BAO_CAO_MODULE_TRICH_XUAT.md
│   ├── phan_tich_bai_bao_2510_09722_va_ke_hoach_cai_tien.md
│   ├── GOLD40_PHAN_TICH_LOI_VA_BUOC_TIEP_2026-10-10.md
│   ├── GOLD40_CHAN_DOAN_TONG_QUAT_HOA_VA_RASOAT_2026-10-11.md
│   ├── TONG_HOP_DU_AN_KLCN029_2026-10-11.md  # Bản tổng hợp này
│   ├── build_progress_report.py
│   ├── assets/, rendered_progress_report/pages/
│   └── (DOCX báo cáo tiến độ và PDF render)
├── .github/workflows/runpod-worker.yml
├── .secrets/                         # Bí mật cục bộ, không đọc nội dung
├── .git/                             # Lịch sử và trạng thái Git
├── .docx_review/                      # Thư mục phụ trợ review tài liệu
├── tmp/                              # Tệp tạm, ảnh render và script rà soát
├── Ke_hoach_nghien_cuu_KLCN029.md
├── MatchCV_JD&Baseline.ipynb
├── 2510.09722v1.pdf, 2510.09722v1.md
├── CAMNANG_KLTN.pdf
├── (DOCX đề cương, phân tích CV/JD, báo cáo tiến độ)
├── parsing.png
├── (ZIP demo một CV lịch sử)
└── render.yaml, .env.example, .gitignore, .dockerignore, .gitattributes
```

Không có thư mục top-level RAG/vector database hoặc module JD độc lập đã được xác nhận hoàn thiện. Các thành phần retrieval/prototype nằm trong notebook và `services/llm_matching.py`.

## 6. Tìm sản phẩm và bằng chứng ở đâu?

| Cần tìm | Đường dẫn ưu tiên | Cách sử dụng |
|---|---|---|
| Phạm vi đang áp dụng | `reports/PROJECT_SCOPE_AND_DECISIONS.md` | Đối chiếu mô-đun và cách diễn giải kết quả |
| Hợp đồng CV/JD | `baseline_extraction/SCHEMA_CONTRACT.md`, `contracts/` | Tích hợp schema, không tự thêm khóa |
| Hợp đồng extraction | `training/EXTRACTION_MODULE_CONTRACT.md` | CVSchema, evidence và manifest bàn giao |
| PDF gốc | `CV_EN_PDF/`, `CV_VN_PDF/` | Đối chiếu nguồn, tránh nhân bản không cần thiết |
| Workbook/nhãn | `annotation/CV_LABEL_TEMPLATE_v2.xlsx`, `annotation/gold_v2/` | Nhãn FINAL và status thiếu/không rõ |
| Nguồn gốc gold | `annotation/audits/gold40_final_2026-10-10_complete/` | Manifest, hash và thay đổi ba mẫu |
| Hướng dẫn gán nhãn | `annotation/HUONG_DAN_GAN_NHAN_CV.md` | Thống nhất đơn vị kỹ năng, span và giá trị thiếu |
| Adapter Full JSON | `training/final_adapter-full_1.zip` | Checkpoint stage 1; audit cùng tên trong `training/audits/` |
| Adapter Pointer full | `training/qwen3_4b_cvschema2_pointer_stage2_full_v1_final_adapter.zip` | Checkpoint stage 2; không nhầm bản smoke |
| Parser benchmark | `training/evaluation/frozen/` | Snapshot giữ cố định để tái lập |
| Raw model output | Các ZIP trực tiếp trong `training/` | Dữ liệu inference gốc, tách khỏi số liệu đã tính |
| Bảng kết quả mới nhất | `training/evaluation/results/gold40_b0_b1_p0_p1_v1/` | `REPORT.md`, `summary.json`, CSV và manifest |
| CVSchema bàn giao Real80 | `training/evaluation/results/pointer_real80_selective_retry_p1_v1/cvschema2_effective.jsonl` | 78 schema và 2 manual review; kèm cờ policy |
| Chẩn đoán miền dữ liệu | `training/audits/gold40_generalization_2026-10-11_v2/` | Diagnostics, manifest và snapshot script |
| Demo hiện tại | `training/colab/Qwen3_Pointer_Colab_UI_Demo.ipynb` | Vận hành Colab; xem README trước khi chạy |
| Demo tuyến tính để debug | `training/colab/Qwen3_Pointer_EndToEnd_CV_JD_Demo_Colab.ipynb` | Quan sát từng công đoạn extraction/matching |
| Rà gold trong nhóm | `gold_review_app/dist/GOLD40_Review_Team_v1.zip` | Gói riêng có PDF; nhận lại ZIP lượt rà để phân xử |
| Web cục bộ | `cv_evaluation_web/Start_CV_Web.bat` | Chạy MVP, cấu hình mode theo README |
| Hồ sơ tự nguyện trên web | `cv_evaluation_web/data/submissions/` và SQLite | Dữ liệu runtime, không phải corpus đã gán nhãn |
| Kho nghiên cứu demo Drive | `MyDrive/KLCN029/pointer_e2e_demo/` theo tài liệu | Vị trí ngoài repo được thiết kế; chưa kiểm kê Drive trong lần rà này |

Các file workbook/gold, ảnh OCR, ZIP có CV, JSONL nguồn và SQLite có thể chứa nội dung cá nhân dù một số trường đã được mask. Chia sẻ mã và báo cáo cần chọn file cụ thể; không đóng gói toàn bộ thư mục dự án như một gói mã nguồn công khai.

## 7. Kết quả kiểm tra trực tiếp ngày 11/10/2026

### 7.1. Kiểm thử cục bộ

Đã chạy bằng Python hệ thống `C:\Python314\python.exe`, phiên bản 3.14.4. Các test dịch vụ dùng fake/mocked generation hoặc HTTP test client, không gọi GPU/cloud thật.

| Nhóm | Lệnh / cách chạy | Kết quả |
|---|---|---:|
| Training parser/dataset/metric/artifact | `python -m unittest discover -s training/tests -q` | 50/50 đạt |
| Baseline hợp đồng | `python -m unittest discover -s baseline_extraction/tests -q` | 5/5 đạt |
| Web CV | `python -m unittest discover -s cv_evaluation_web/tests -q` | 8/8 đạt |
| Web gán nhãn | `python -m unittest discover -s annotation_app/tests -q` | 8/8 đạt |
| Web rà gold | `python -m unittest test_app -q` trong `gold_review_app/` | 4/4 đạt |
| Worker không GPU | `python -m unittest discover -s deployment/runpod_qwen -p test_handler.py -q` | 2/2 đạt |
| Deployment policy | Gọi trực tiếp 7 hàm `test_*` không tham số có sẵn | 7/7 đạt |
| LLM matching contract | Gọi trực tiếp 6 hàm `test_*` không tham số có sẵn; API được mock | 6/6 đạt |
| **Tổng** | **77 unittest + 13 kiểm tra dạng hàm** | **90/90 đạt** |

Runtime Python đi kèm Codex thiếu pytest/PyMuPDF/Flask cho một số nhóm nên không chạy được trọn bộ. Python hệ thống có các phụ thuộc ứng dụng và đã chạy thành công các kiểm tra trên; không cài thêm thư viện. pytest chưa có, nên không ghi rằng đã chạy pytest thành công.

### 7.2. Kiểm tra tĩnh và artifact

- **142 file Python** của dự án/snapshot qua `ast.parse`, không lỗi cú pháp; loại môi trường cài đặt, cache, `.git`, `.secrets` và `tmp` khỏi phạm vi này.
- Có cảnh báo không chặn trên Python 3.14 về escape `\*` trong `experiments/ocr/analyze_vietocr_hybrid_pilot.py`; chưa sửa mã trong đợt tổng hợp.
- **18 notebook** đọc được JSON: 15 notebook Colab, 2 snapshot notebook trong kết quả GOLD40 và notebook matching tại root. Không chạy tất cả notebook từ runtime sạch.
- **26 ZIP** tại `training/`, `training/colab/`, `training/colab/artifacts/`, `training/endtoend_result/` qua kiểm tra CRC. CRC không thay thế kiểm tra provenance hoặc độ đúng nội dung.
- **40/40 gold JSON** qua CVSchema; có đủ 40 `.status.json`. Chưa đối chiếu bằng mắt lại toàn bộ PDF trong lần rà này.
- Hai dataset tổng hợp đều có đủ **850/75/75** dòng train/validation/test.

Script phụ trợ cho lần rà được lưu ở `tmp/project_review_inventory.py` và `tmp/project_review_checks.py`. Chúng phục vụ kiểm kê/kiểm tra, không sửa gold, checkpoint hoặc kết quả thực nghiệm.

### 7.3. Trạng thái lưu trữ và Git

Snapshot Git trước khi thêm bản tổng hợp này: **77 file tracked**, **2 file tracked đã sửa** (`.gitignore`, `training/colab/README.md`) và **22.294 file untracked**. Phần lớn untracked nằm trong `experiments/`, chủ yếu do môi trường OCR cục bộ; số file untracked không tương đương số sản phẩm nghiên cứu.

Các thư mục dữ liệu lớn như PDF nguồn, corpus, training data/results/audits, gold và backup được loại khỏi Git bằng các quy tắc hiện có. Nhiều mã nguồn, tài liệu và kết quả còn ở trạng thái cục bộ. `.venv-vietocr/` chưa được quy tắc `.venv/` hiện tại loại trừ đầy đủ.

Lịch sử commit gần nhất hiện thấy là ngày 07/10/2026, gồm web/Colab đầu cuối, consent/rút dữ liệu và chuẩn hóa soft skills. Có file trên máy chưa chứng minh file đó đã được commit/push. Lần rà soát không stage, commit, push hoặc sửa các thay đổi đang có của người dùng.

## 8. Những điểm còn thiếu hoặc cần chỉnh

| Ưu tiên | Phát hiện có bằng chứng | Hướng xử lý tiếp |
|---|---|---|
| Cao | Train và gold khác phạm vi nhãn kỹ năng; 543/544 CV train có công nghệ dự án không xuất hiện nguyên dạng trong hard skills target | Chốt quy tắc chung, tạo converter/dataset phiên bản mới, giữ phiên bản cũ để truy vết |
| Cao | Train 850 EN, không có ví dụ dương GitHub/GPA/activities/awards; soft skill target chỉ Communication | Bổ sung dữ liệu phát triển EN/VI và độ phủ trường, tránh tăng epoch ngay khi chưa xử lý lệch dữ liệu |
| Cao | B1 gộp kỹ năng thành chuỗi; hard-skills F1 13,69% so với B0 58,33% | Rà đơn vị nhãn/output bằng PDF và quy tắc; không thay metric v1 hoặc sửa gold theo model |
| Cao | Pointer long text kém trên GOLD40; dự án có thể lẫn/thiếu span | Ưu tiên ranh giới mục, thứ tự đọc và đối chiếu span với nguồn |
| Cao | Audit đầu cuối ghi lỗi hai cột và ATS tối đa khi text bị trộn | Sửa hoặc gắn review cho reading order/layout, kiểm chứng lại bằng ca lỗi trước khi trình diễn rộng |
| Cao | GOLD40 đã dùng hậu kiểm/chọn hướng; thiếu A/B gốc để tính IAA | Giữ đúng giới hạn; rà độc lập mới, phân xử có biên bản; dùng tập xác nhận mới cho cải tiến |
| Trung bình | Có mã matching M1/M2/M3 nhưng chưa có benchmark gold score/CV–JD | Chốt tập cặp, rubric và người chấm; đánh giá matching tách extraction |
| Trung bình | Có schema JD nhưng chưa xác nhận parser JD độc lập và kết quả đo | Chốt contract/pipeline JD và test yêu cầu bắt buộc/ưu tiên |
| Trung bình | Baseline README còn ghi chưa có gold/chưa thử VietOCR; training README mô tả stage 2 CV thật chưa khớp artifact | Cập nhật README theo báo cáo mới nhất và ghi rõ phần lịch sử/phương án dự kiến |
| Trung bình | Nhiều file chưa vào Git, môi trường OCR chưa ignore đầy đủ; một số audit/ảnh có thể chứa CV | Rà danh sách file, ignore môi trường/runtime, commit theo danh sách mã/tài liệu được phép |
| Trung bình | Báo cáo audit đầu cuối bao phủ 4 trong 7 ZIP hiện có | Rà ba gói còn lại nếu dùng làm bằng chứng, kiểm tra consent và lỗi trước khi nhập corpus |
| Theo nhu cầu | Cloud chưa xác nhận smoke GPU/đầu cuối, đang dừng vì ngân sách | Tiếp tục demo Colab; chỉ mở lại cloud khi có nguồn lực và chạy smoke thật |
| Bàn giao | Chưa xác nhận báo cáo khóa luận/slide hoàn chỉnh | Tổng hợp bảng kết quả hiện có, giới hạn, đóng góp và kịch bản demo thành gói bảo vệ |

Những khác biệt train–real là bằng chứng về dữ liệu và hành vi output. Chưa có thí nghiệm xác định nguyên nhân chính là overfitting, catastrophic forgetting hoặc OCR. Không dùng các giả thuyết này như kết luận nhân quả.

## 9. Mốc công việc có bằng chứng

| Mốc | Công việc/sản phẩm đã lưu |
|---|---|
| 22/09 | Kế hoạch nghiên cứu, kiểm kê 80 CV/corpus, baseline API pilot và báo cáo trạng thái |
| 23/09 | Quy tắc phân loại kỹ năng dữ liệu tổng hợp được ghi phiên bản đã duyệt |
| 27/09 | Audit adapter stage 1 và artifact validation Full JSON |
| 29/09 | PaddleOCR pilot, VietOCR hybrid pilot, quyết định OCR EN/VI và router |
| 02/10 | Chốt phạm vi dự án/mô-đun và hợp đồng extraction |
| 03/10, theo audit stage 2 | Adapter Pointer full, validation/test P0; báo cáo sau đó bổ sung Real80/P1 |
| 06/10 | Web MVP, worker/cấu hình Render–RunPod, rà notebook matching và kiểm thử local |
| 07/10 | Chuyển demo vận hành sang Colab; thêm UI, consent, rút dữ liệu, matching strategy và audit đầu cuối |
| 10/10 | Chốt GOLD40 FINAL, kiểm tra manifest/hash và đo P0/P1; phân tích lỗi |
| 11/10 | So sánh đầy đủ B0/B1/P0/P1, chẩn đoán dữ liệu/tổng quát hóa, công cụ rà gold và bản tổng hợp này |

Mốc trên dựa vào báo cáo và artifact hiện có. Ngày tên file/báo cáo không luôn là ngày chạy của mọi nội dung bổ sung; dùng run manifest/log khi cần lịch thực nghiệm chính xác.

## 10. Các việc tiếp theo để khép lại dự án

1. Giữ cố định GOLD40, parser v1 và bảng kết quả hiện tại. Hoàn tất lượt rà độc lập, phân xử trên PDF và tạo phiên bản nhãn mới nếu có sửa được chấp nhận.
2. Thống nhất phạm vi nhãn train–gold; xây tập phát triển EN/VI đủ trường, tách một tập xác nhận mới chưa dùng chọn hướng.
3. Kiểm chứng cải tiến extraction trên lỗi kỹ năng/span/layout, đối chứng với Qwen gốc. Chọn cấu hình bằng chất lượng và tổng chi phí, không chỉ output token.
4. Chốt pipeline JD, tập CV–JD và rubric; chạy benchmark matching/gợi ý có nhãn tham chiếu và bằng chứng nguồn.
5. Kiểm tra lại demo trên CV EN text, VI text, scan EN và hai cột; rà opt-in/opt-out/rút dữ liệu và thông tin định danh trong gói xuất.
6. Cập nhật README, quy tắc lưu trữ/Git và chỉ đưa mã/tài liệu được phép vào kho; giữ CV, nhãn, backup và artifact riêng tư có manifest.
7. Hoàn thiện báo cáo khóa luận, slide và kịch bản demo bằng kết quả đã đo. Nêu rõ kết quả extraction tốt trên tổng hợp nhưng giảm trên CV thật, giới hạn GOLD40 và phạm vi matching chưa được kiểm chứng.

**Trạng thái bàn giao hiện tại:** nền tảng kỹ thuật và bộ thực nghiệm extraction đã hình thành, có bằng chứng huấn luyện và demo chạy được; phần khép lại cần tập trung vào tổng quát hóa CV thật, nhãn/đánh giá độc lập, benchmark hạ nguồn và tài liệu bảo vệ.
