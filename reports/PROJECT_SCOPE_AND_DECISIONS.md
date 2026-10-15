# Phạm vi dự án và các quyết định đã chốt

Phiên bản: `project_scope_decisions_v1`  
Ngày chốt: 2026-10-02  
Trạng thái: áp dụng cho báo cáo, mã nguồn và phân công tiếp theo

## 1. Phạm vi toàn dự án

Đề tài là một hệ thống hỗ trợ đánh giá CV theo JD. Trích xuất CV chỉ là một mô-đun đầu
vào, không đại diện cho toàn bộ dự án.

```text
CV PDF -> OCR/xử lý tài liệu -> trích xuất CVSchema 2.0 --+
                                                        +-> so khớp CV-JD
JD ----> trích xuất/chuẩn hóa JDSchema -----------------+         |
                                                                  v
                                                              chấm điểm
                                                                  |
                                                                  v
                                                     giải thích và gợi ý sửa CV
```

Các mô-đun cấp dự án:

1. OCR và trích xuất CV có cấu trúc.
2. Trích xuất hoặc chuẩn hóa JD.
3. So khớp CV với JD.
4. Chấm điểm và xếp hạng.
5. Sinh giải thích, câu trả lời và gợi ý sửa CV.
6. Tích hợp và đánh giá đầu cuối.

Tài liệu này khóa phạm vi của mô-đun 1. Thiết kế thuật toán và nội dung báo cáo phải chừa
không gian cho các mô-đun do thành viên khác phụ trách.

## 2. Ranh giới mô-đun trích xuất

Mô-đun trích xuất phụ trách:

- nhận PDF hoặc text CV;
- lấy text gốc hoặc OCR theo tuyến đã chọn;
- bảo toàn thứ tự đọc và đánh số dòng;
- trích xuất JSON có cấu trúc;
- kiểm tra pointer, JSON và CVSchema 2.0;
- trả CVSchema 2.0 cùng evidence/provenance sidecar.

Mô-đun trích xuất không phụ trách:

- quyết định ứng viên phù hợp;
- đặt trọng số tiêu chí tuyển dụng;
- so khớp CV với JD;
- tính điểm hoặc xếp hạng;
- kết luận tuyển dụng;
- sinh nhận xét và gợi ý sửa CV.

`CVSchema 2.0` là hợp đồng dữ liệu bàn giao. Nhóm hạ nguồn không phải đọc raw LLM output,
pointer nội bộ, checkpoint hoặc log OCR để sử dụng các trường CV.

## 3. Nguyên tắc viết báo cáo

Mọi quyết định kỹ thuật phải trình bày theo chuỗi:

> Vấn đề -> phương án thay thế -> bằng chứng nghiên cứu trước -> ràng buộc đề tài -> lựa
> chọn -> thực nghiệm kiểm chứng -> giới hạn.

Mỗi lựa chọn phải trả lời được:

1. Vì sao cần thành phần này?
2. Có những phương án nào khác?
3. Vì sao chọn phương án hiện tại trong bối cảnh đề tài?
4. Vì sao chưa chọn các phương án còn lại?
5. Nguồn nghiên cứu hoặc tài liệu kỹ thuật nào hỗ trợ quyết định?
6. Thực nghiệm nào của đề tài xác nhận hoặc bác bỏ giả thuyết?

Không dùng kết quả của nghiên cứu trước như kết quả trên dữ liệu của nhóm. Không dùng các
từ “tốt nhất”, “phù hợp nhất” hoặc “cải thiện” khi chưa có đối chứng trên cùng dữ liệu.

## 4. Phần kế thừa và phần của đề tài

### 4.1 Kế thừa từ bài báo 2510.09722

- hợp nhất text PDF và OCR;
- tái tạo thứ tự đọc và đánh số dòng;
- task decomposition/parallel prompting;
- index-based pointer cho trường văn bản dài;
- lấy lại nguyên văn từ dòng nguồn;
- hậu xử lý và đánh giá thực thể dạng danh sách.

Pointer không được tuyên bố là sáng kiến của nhóm. Giai đoạn dữ liệu và huấn luyện Pointer
hiện tại là tái hiện và điều chỉnh phương pháp đã công bố cho CVSchema 2.0.

### 4.2 Điều chỉnh của mô-đun trích xuất

- schema chung CVSchema 2.0;
- OCR phục vụ CV tiếng Anh và tiếng Việt;
- Qwen3-4B continued QLoRA trong giới hạn Colab T4;
- trường ngắn sinh trực tiếp, trường dài dùng pointer trong cùng một JSON;
- parser nghiêm ngặt, evidence sidecar và provenance có hash.

### 4.3 Giả thuyết cải tiến riêng cần kiểm chứng

Hướng đang được kiểm chứng là trích xuất Hybrid Pointer một lượt, có kiểm tra theo schema
và sửa lỗi chọn lọc theo trường. Phần này chỉ được gọi là cải tiến sau khi đối chứng chứng
minh lợi ích về chất lượng hoặc hiệu quả.

Các cấu hình dự kiến:

- `B0`: Qwen3-4B gốc sinh CVSchema 2.0 đầy đủ;
- `B1`: adapter giai đoạn 1 sinh CVSchema 2.0 đầy đủ;
- `P0`: adapter Hybrid Pointer một lượt;
- `P1`: P0 + kiểm chứng pointer/schema + sửa lỗi chọn lọc.

Các chỉ số bắt buộc gồm field F1, JSON/schema validity, span validity, reconstruction exact
match, input/output token, số lần gọi model, latency và tỷ lệ cần retry.

## 5. Lý do lựa chọn cấp mô-đun

| Quyết định | Phương án khác | Lý do hiện tại | Bằng chứng cần dùng |
|---|---|---|---|
| Text PDF + OCR có định tuyến | chỉ PDF text; OCR toàn trang | giảm OCR không cần thiết nhưng vẫn xử lý PDF ảnh/font lỗi | ablation text fusion của bài báo + pilot OCR của nhóm |
| Qwen3-4B | 0.6B; 14B; API đóng | đã có baseline; đủ năng lực; QLoRA được trên T4 | bảng model của bài báo + số liệu runtime nhóm |
| QLoRA | full SFT; prompt-only | đề tài bắt buộc train, tài nguyên T4 không đủ full SFT 4B | LoRA, QLoRA và giới hạn VRAM đo thực tế |
| JSON | YAML; Markdown; text tự do | hợp đồng máy đọc được và đã có schema/parser | thí nghiệm format của bài báo + JSON-valid rate nhóm |
| Pointer cho trường dài | sinh lại toàn văn | giảm output và content drift | mục 3.2 + ablation bài báo; token/accuracy nhóm |
| Một lượt thống nhất | nhiều task song song | giả thuyết giảm lặp input/call và giữ quan hệ cùng entity | phải làm ablation; chưa được coi là kết luận |
| Parser xác định | sửa JSON tự do | truy vết được, không bịa phần output bị cắt | parser contract và error analysis của nhóm |
| Không dùng RAG trong extraction | truy hồi tài liệu ngoài | sự thật cần trích phải nằm trong CV | phạm vi grounded extraction; RAG chỉ có thể dùng downstream |

Lý do “không chọn” chỉ đúng trong ràng buộc của đề tài; không được diễn đạt rằng phương án
khác luôn kém hơn.

## 6. Phân bổ báo cáo

Phần trích xuất là một tiểu mục trong phương pháp tổng thể:

- kiến trúc tổng thể và hợp đồng giữa mô-đun;
- OCR và trích xuất CV;
- chuẩn hóa JD;
- so khớp CV-JD;
- chấm điểm;
- sinh giải thích/gợi ý;
- tích hợp đầu cuối.

Metric phải báo riêng theo mô-đun. Kết quả extraction tốt không được suy rộng thành chất
lượng chấm điểm, so khớp hoặc gợi ý.

## 7. Trạng thái mô-đun trích xuất

Tiến độ cập nhật 11/10/2026; các quyết định phạm vi ở trên vẫn áp dụng.

- Baseline Qwen gốc/B1 và P0 đã được đánh giá trên test tổng hợp 75 mẫu.
- Parser CVSchema v1 và Pointer v1 đã đóng băng, không sửa theo GOLD40.
- Hybrid Pointer đã huấn luyện full và chạy P0/P1 trên 80 CV thật.
- GOLD40 (20 EN/20 VI) đã chốt FINAL, có manifest/hash và provenance. Nhãn A/B trước đối
  soát không còn được giữ; ba mẫu có trợ lý hỗ trợ hoàn tất từ PDF theo yêu cầu người dùng.
- Đã đánh giá P0/P1 trên GOLD40 hậu kiểm: Micro F1 49,66%/52,81%, CVSchema valid 34/40 và
  39/40. Không gọi đây là held-out hoàn toàn hoặc suy rộng sang matching/chấm điểm/gợi ý.
- Đã nhận và đánh giá B0/B1 trên cùng input GOLD40: B0 Micro F1 65,52%, CVSchema valid
  40/40; B1 F1 48,28%, valid 35/40. Hai ZIP đủ 40 ID, khớp hash/cấu hình và không có
  output chạm giới hạn token. P0/P1 được tái dựng và khớp bản đo trước.
- **Kết luận hiện tại:** B0 đứng đầu Field Micro F1 và schema validity trên GOLD40.
  P1 cải thiện so với B1/P0 nhưng chưa vượt B0; không tuyên bố huấn luyện hoặc Pointer
  đã cải thiện độ chính xác trích xuất trên CV thật so với Qwen gốc.
- P1 giảm output token 48,28% so với B0, nhưng tổng input + output tăng 8,27% và số call
  là 46 so với 40. Không suy giảm output thành giảm tổng chi phí. Runtime thuộc các
  phiên khác nhau; chưa là đối chứng latency trên cùng phiên/hạ tầng.
- B1 gộp nhóm/câu kỹ năng thành một phần tử và có 5 output lỗi cấu trúc. Chưa xác định
  nguyên nhân huấn luyện bằng thực nghiệm; dịch chuyển miền synthetic→real là giả thuyết.
  Không tăng epoch ngay hoặc sửa parser/metric/gold để nâng số liệu.
- Bản đo đầy đủ: `training/evaluation/results/gold40_b0_b1_p0_p1_v1/REPORT.md`.
  Bước tiếp theo: rà nguồn/nhãn và đơn vị kỹ năng/ranh giới span trên mẫu đại diện;
  mọi thử nghiệm cải tiến cần phiên bản mới, tập phát triển riêng và tập xác nhận mới
  chưa dùng chọn hướng. Giữ GOLD40 là hậu kiểm và giữ phạm vi extraction riêng.
- Đã tạo `gold_review_app` và gói portable riêng cho thành viên: 40 PDF + snapshot gold,
  checklist 19 trường, bằng chứng, đề nghị JSON, lịch sử và ZIP kết quả theo người rà.
  Không ghi đè gold; chưa có quyết định nhãn mới từ người rà. Bộ 10 ưu tiên để rà độc lập
  không là mẫu khách quan để ước lượng tỷ lệ lỗi toàn GOLD40.
- Kiểm tra converter/dataset xác nhận lệch phạm vi nhãn: hard skills tổng hợp không hợp
  công nghệ dự án/ngoại ngữ như hướng dẫn gold; 543/544 CV train có công nghệ dự án thiếu
  ít nhất một giá trị nguyên dạng trong hard skills. Train 850 EN, không có ví dụ dương
  GitHub/GPA/activities/awards, soft skill target chỉ Communication. Đây là bằng chứng
  về dataset hiện có; chưa chứng minh tác động nhân quả lên điểm từng trường.
- Stage 1 và stage 2 validation loss cùng miền đều giảm ở ba mốc đã lưu; test tổng hợp
  F1 vẫn khoảng 99%. Chưa kết luận overfitting theo số bước; khả năng quá chuyên biệt
  với miền/quy tắc tổng hợp vẫn cần thí nghiệm. Tập test nhỏ không trực tiếp gây overfit.
  Báo cáo mới: `reports/GOLD40_CHAN_DOAN_TONG_QUAT_HOA_VA_RASOAT_2026-10-11.md`.

## 8. Quyết định ngày 14/10/2026: thu gọn mô-đun trích xuất và chốt tập JD

Bối cảnh: còn khoảng 3,5 tuần đến hạn nộp 08/11/2026. Phần đánh giá đầu cuối (tập JD, cặp CV–JD,
nhãn người chấm, chấm rubric, so sánh chiến lược) chưa có số liệu. Kế hoạch theo module:
`reports/HUONG_DAN_HOAN_THIEN_THEO_MODULE_KLCN029_2026-10-13.docx`.

### 8.1 Đánh giá trích xuất trên CV thật

- **Bắt buộc và đã có.** Đề cương yêu cầu đo "độ chính xác của thông tin được trích xuất". Số liệu
  dùng cho báo cáo là kết quả đã khóa trên GOLD40 (B0/B1/P0/P1, bootstrap theo CV, tách EN/VI) và
  Real80 (schema hợp lệ, retry). GOLD40 được trình bày là tập **hậu kiểm**, vì đã dùng để phân tích lỗi.
- **Không làm thêm:**
  - tập xác nhận 10 CV mới do hai người gán nhãn;
  - huấn luyện lại với dataset v2. Ghi vào hướng phát triển, kèm phân tích nguyên nhân trong
    `reports/PHAN_TICH_NGUYEN_NHAN_FINE_TUNE_KEM_TREN_CV_THAT_2026-10-13.md`.
- **Hoàn tất:** thí nghiệm `format_shift_v1` (B0 đã chạy; còn B1 và P0) để có bằng chứng nhân quả
  cho giả thuyết shortcut định dạng.
- **Chỉ làm nếu còn thời gian:** hậu xử lý output trích xuất; hỗ trợ DOCX. Nếu làm hậu xử lý, phải đo
  lại trên GOLD40 và ghi rõ là kết quả hậu kiểm.
- **Đánh giá đầu cuối không cần tập trích xuất riêng:** 24 CV dùng lập cặp CV–JD lấy từ GOLD40. Mỗi
  chiến lược chấm chạy trên CVSchema gold (đo riêng bước chấm) và trên output trích xuất B0 (đo toàn hệ
  thống). Phương pháp chính chạy thêm trên output P1, cấu hình của demo (xem 8.2, ý 2). Chênh lệch giữa
  các lượt là ảnh hưởng của lỗi trích xuất.

### 8.2 Cấu hình trích xuất cho hệ thống: còn phải quyết định

Theo số liệu GOLD40, B0 (Qwen gốc, Full JSON) có Field Micro F1 cao nhất (65,52%) và schema hợp lệ
40/40. Bản triển khai hiện tại (`deployment/home_api`) lại chạy GGUF của Pointer stage 2
(`qwen3-4b-pointer-stage2-q4_k_m.gguf`). Hai hướng:

1. Chuyển bản triển khai sang Qwen gốc với prompt Full JSON. Cần GGUF của model gốc và đo lại
   fidelity như đã làm với Pointer.
2. Giữ Pointer cho demo, và nêu rõ trong báo cáo rằng đây không phải cấu hình có độ chính xác cao nhất
   (lý do: output ngắn hơn và đã có quy trình triển khai đã kiểm chứng).

**Quyết định tạm thời (14/10/2026):** giữ Pointer stage 2 trên bản triển khai cho tới khi có đủ kết
quả `format_shift_v1` (B0, B1, P0), rồi mới chọn giữa hai hướng trên. Hạn chọn: **20/10/2026**, để còn
thời gian tạo GGUF cho model gốc và đo fidelity nếu phải chuyển, trước khi chạy đánh giá đầu cuối.

Tiêu chí đề xuất khi đọc kết quả `format_shift_v1`:

- P0 giảm F1 rõ khi đổi định dạng (khoảng tin cậy của DiD so với B0 nằm hẳn dưới 0 ở `headings`
  hoặc `grouped_skills`): khoảng cách với B0 trên GOLD40 là do Pointer dựa vào định dạng của dữ liệu
  tổng hợp và sẽ lặp lại trên CV thật khác. Nên **chuyển sang Qwen gốc**.
- P0 ổn định như B0: khoảng cách trên GOLD40 nghiêng về lệch phạm vi nhãn (kỹ năng, công nghệ dự án).
  Có thể **giữ Pointer** cho demo, kèm ghi chú độ chính xác trong báo cáo.

Dù chọn hướng nào, số liệu GOLD40 vẫn cho thấy B0 hơn P1 khoảng 13 điểm F1; báo cáo phải nêu điều này.

**Kết quả theo tiêu chí (15/10/2026).** Kết quả `format_shift_v1` nằm ở
`training/evaluation/results/format_shift_v1/REPORT.md` và mục 5.3 của báo cáo phân tích nguyên nhân.

- DiD của P0 so với B0: `headings` −2,03 [−9,26; +2,12]; `grouped_skills` −3,59 [−10,55; +0,68]. Cả hai khoảng
  tin cậy đều chứa 0, nên **theo tiêu chí đã đặt trước thì giữ Pointer cho demo**, kèm ghi chú độ chính xác.
- Điều tiêu chí không đo, nhưng cần nêu: P0 yếu thật khi văn bản dài bị ngắt nhiều dòng, như khi trích từ PDF.
  Ở biến thể `wrapped_text`, summary còn 62,50% và chi tiết dự án còn 51,85%; còn B0 không giảm trên các CV
  có output hợp lệ. Trên GOLD40, không summary nào nằm trọn một dòng (0/38), nên điểm yếu này xảy ra trên CV
  thật.

**Đề xuất, chờ nhóm chốt trước 20/10:**

1. Demo giữ Pointer (P1) như hiện tại. Không tốn thêm công tạo GGUF và đo fidelity.
2. **Đã chốt (15/10/2026).** Đánh giá đầu cuối ở mục 8.1 chạy phương pháp chính trên **ba loại đầu vào**
   cho cùng các cặp CV–JD:

   | Đầu vào của bước chấm | Đo được gì |
   |---|---|
   | CVSchema gold | Chất lượng riêng của bước chấm điểm |
   | Output B0 trên GOLD40 | Toàn hệ thống với cấu hình trích xuất chính xác nhất đã đo |
   | Output P1 trên GOLD40 | Toàn hệ thống với cấu hình đang chạy trên demo |

   - Chênh lệch giữa B0 và P1 cho biết khoảng cách khoảng 13 điểm F1 trích xuất có làm điểm phù hợp
     CV–JD sai đi bao nhiêu.
   - Không cần chạy lại model trích xuất: output của cả hai trên 40 CV GOLD40 đã được lưu và khóa.
   - Các chiến lược so sánh khác (module G) chạy trên CVSchema gold và output B0. Lượt P1 chỉ bắt buộc với
     phương pháp chính.
3. Báo cáo nêu rõ cấu hình nào dùng cho demo, cấu hình nào dùng cho đánh giá, và lý do.

Đánh giá đầu cuối ở mục 8.1 dùng output trích xuất theo ý 2 ở trên.

### 8.3 Tập JD và phạm vi lập cặp

- Phạm vi chỉ gồm vị trí **Backend và Frontend**, cấp intern, fresher, junior. CV hướng data/AI, QA,
  BA không dùng để lập cặp; ghi là giới hạn trong báo cáo.
- Tỉ lệ **8 JD Backend / 4 JD Frontend**, theo phân bố 73 CV thật (theo `canonical_id`):
  35 backend, 7 fullstack, 7 mobile, 4 frontend, 8 data/AI, 7 QA, 5 BA/khác. Nhãn hướng là ước
  lượng bằng heuristic: vai trò ghi trong CV, nếu không có thì đếm từ khóa công nghệ
  (`downstream/data/cv_track_profile.py`).
- Không nhận JD senior/lead hoặc yêu cầu từ 3 năm kinh nghiệm. Quy tắc tách yêu cầu JD và lưu trữ:
  `downstream/data/jd_v1/README.md`.
- Rubric chấm cặp CV–JD là bản nháp `rubric_v2_draft1` (`downstream/rubric/rubric_v2.json`), chỉ khóa
  sau vòng chấm thử khoảng 10 cặp.
