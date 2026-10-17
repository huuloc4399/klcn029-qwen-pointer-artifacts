# Tóm tắt tiến độ KLCN029 cho buổi họp với giảng viên hướng dẫn

Ngày họp dự kiến: 18/10/2026. Số liệu tính đến tối 17/10/2026. Hạn nộp khóa luận: 08/11/2026 (còn 3 tuần).

Tài liệu gồm: các việc cần thầy/cô chốt (mục 1), tiến độ từng phần kèm minh chứng (mục 2–6), rủi ro (mục 7), kế hoạch (mục 8), các câu hội đồng có thể hỏi (mục 9). Mọi số liệu đều trỏ tới file hoặc commit trong kho mã của nhóm (phụ lục).

## 1. Các việc cần thầy/cô chốt hôm nay

| # | Câu hỏi | Nhóm đề xuất | Vì sao cần chốt bây giờ |
|---|---|---|---|
| 1 | Kiểm chứng giả thuyết **H1** theo phương án A (viết lại H1 cho khớp thiết kế, đo tự động, không tốn thêm chi phí) hay phương án B (giữ nguyên H1, thêm chiến lược "điểm tổng trực tiếp")? | **A** | Phải chốt **trước khi xem kết quả tập test**, để không ai nói nhóm chọn cách đo theo kết quả |
| 2 | Thiết kế đánh giá **H2** (RAG có làm gợi ý sửa CV tốt hơn mà không bịa thông tin?): hai người so sánh cặp mù giữa M3 (có RAG) và M1 (không RAG) trên 32 cặp test | Đồng ý thiết kế; chọn 2 người chấm | H2 hiện **chưa có cách đánh giá**; cần khoảng 2,5 giờ mỗi người chấm |
| 3 | Có đưa phần so sánh với hệ thống tương tự (TechJobs.vn) vào chương 2 không? | Có, ở mức một đoạn và một bảng ngắn, không làm thành thí nghiệm | Đắc đang viết chương 2 |
| 4 | Cấu trúc báo cáo và phân công chương 3–5 | Xem mục 8 | Còn 3 tuần |
| 5 | Cách khai báo việc dùng công cụ AI (Claude) trong quá trình làm đề tài, theo quy định của khoa | Khai báo trong phần phương pháp và lời cam đoan | Ảnh hưởng cách viết mục gán nhãn và mục phát triển |
| 6 | Quy mô đánh giá: tập test 16 CV, 32 cặp CV–JD. Thầy/cô thấy có đủ cho kết luận không, hay cần ghi rõ là nghiên cứu quy mô nhỏ? | Giữ quy mô, báo cáo khoảng tin cậy, nêu rõ giới hạn | Không còn thời gian gán nhãn thêm |

Chi tiết phương án cho câu 1 và 2: `reports/minh_chung/M08_DE_XUAT_KIEM_CHUNG_H1_H2.docx` (gửi kèm).

## 2. Tổng quan đề tài và đóng góp chính

Hệ thống đánh giá CV ngành CNTT gồm hai mô-đun:

1. **Trích xuất CV** từ PDF thành dữ liệu có cấu trúc (CVSchema 2.0). Gồm OCR cho trang ảnh và mô hình Qwen3-4B; phần huấn luyện dùng QLoRA.
2. **Chấm CV theo rubric 8 tiêu chí và so khớp với JD**, có gợi ý sửa CV. So sánh 6 cách chấm:
   - bộ luật không dùng LLM;
   - M1 zero-shot; M2 few-shot; M3 có RAG; M4 nhiều tác tử;
   - **phương pháp đề xuất P**.

**Phương pháp P** dùng cùng model và tri thức truy xuất như M3, nhưng thêm 4 cơ chế do code thực hiện:

- **kiểm chứng trích dẫn:** mỗi điểm phải kèm đoạn trích có thật trong CV; không tìm thấy thì hỏi lại model một lần;
- **từ chối chấm** khi không đủ căn cứ (hiển thị "cần xác minh") thay vì đoán;
- **cờ mất nội dung:** khi văn bản trích xuất ít bất thường so với PDF, không coi "thiếu" là CV thật sự thiếu;
- **kiểm tra yêu cầu khái niệm của JD** (Responsive, OOP…).

Điểm phù hợp với JD (C8) được **tính từ từng yêu cầu đã kiểm chứng**, không để model tự cho điểm.

## 3. Mô-đun trích xuất: đã xong, có kết quả cần báo cáo trung thực

Kết quả trên 40 CV thật có nhãn tay (GOLD40, 20 tiếng Anh và 20 tiếng Việt), ngày 11/10:

| Cấu hình | CVSchema hợp lệ | Micro F1 |
|---|---|---|
| B0: Qwen3-4B gốc | 40/40 | **65,52%** |
| B1: Qwen3-4B fine-tune (adapter, stage 1) | 35/40 | 48,28% |
| P0: Pointer stage 2 | 34/40 | 49,66% |
| P1: P0 + chạy lại khi lỗi (cấu hình của demo) | 39/40 | 52,81% |

- **Bản fine-tune kém bản gốc:** B1 − B0 = −17,24 điểm F1, khoảng tin cậy 95% [−22,58; −11,75] (bootstrap theo CV). Nguyên nhân chính đo được là lỗi đơn vị kỹ năng: B1 gộp nhiều kỹ năng thành một mục. F1 của trường kỹ năng là 13,69% so với 58,33% của B0.
- Nhóm đã phân tích nguyên nhân (`reports/PHAN_TICH_NGUYEN_NHAN_FINE_TUNE_KEM_TREN_CV_THAT_2026-10-13.md`). Thí nghiệm phản thực `format_shift_v1` (15/10) không xác nhận giả thuyết "phụ thuộc định dạng" ở tiêu đề và cách nhóm kỹ năng. Nó cho thấy Pointer yếu khi văn bản dài bị ngắt dòng như khi trích từ PDF.
- **Quyết định 14–15/10** (`reports/PROJECT_SCOPE_AND_DECISIONS.md` §8):
  - không huấn luyện lại (ghi vào hướng phát triển);
  - demo giữ P1;
  - đánh giá đầu cuối chạy trên ba đầu vào (CVSchema chuẩn, B0, P1) để đo lỗi trích xuất ảnh hưởng tới điểm chấm bao nhiêu.
- **Xin ý kiến thầy/cô:** cách trình bày việc "fine-tune kém bản gốc" trong báo cáo. Nhóm đề xuất trình bày như một kết quả âm có phân tích nguyên nhân, không che giấu.

## 4. Tập nhãn chuẩn cho bước chấm điểm

**Dữ liệu.** 24 CV (từ GOLD40) ghép với 12 JD Backend/Frontend cấp thực tập đến junior, tạo 48 cặp. Mỗi CV ghép một JD cùng hướng và một JD khác hướng, để mức phù hợp trải từ thấp đến cao. Chia theo CV:
- **dev:** 8 CV, 16 cặp, dùng để thử nghiệm và khóa cấu hình;
- **test:** 16 CV, 32 cặp, chỉ chạy một lần.

**Quy trình.** Hai người chấm độc lập (A, B), theo hướng dẫn và rubric, gồm điểm 0–4 cho 8 tiêu chí, trạng thái từng yêu cầu JD và mức phù hợp 1–5:

| Bước | Kết quả | Minh chứng |
|---|---|---|
| Vòng thử (16 cặp dev) | Độ đồng thuận ban đầu: **kappa gộp 0,69** [0,55; 0,83]. Vấn đề: người chấm cho điểm 4 gần như mọi CV ở C1, C2, C3, C7; trạng thái yêu cầu JD lệch nhiều (kappa 0,41); không ai dùng `unclear` | `iaa_pilot_v1_2026-10-16/IAA_REPORT.md` |
| Hiệu chỉnh hướng dẫn (bản 2) | Thêm danh sách kiểm tra từng mức. A chấm lại **mà không xem nhãn của B**: kappa gộp **0,82** [0,75; 0,89] | `GHI_CHU_PHIEN_BAN_PILOT.md`; commit `8a7543f` |
| Phân xử 3 vòng | 46 + 35 + 20 dòng. Hợp nhất theo luật cố định: hai người đồng ý thì giữ; lệch 1 điểm lấy trung bình; C8 tính lại từ yêu cầu → nhãn FINAL dev | `downstream/eval/adjudicate.py`; commit `a38ca5f`, `94933e6` |
| Hướng dẫn bản 3 | Quy tắc cho yêu cầu khái niệm và khi nào chọn `unclear` | commit `2eef01c` |
| Vòng chính (32 cặp test) | Hai người đang chấm, **hạn 20/10**. Đây là độ đồng thuận chính thức, vì lần đầu hai người dùng cùng một bản hướng dẫn | `labels_v1/packages/PACKAGES_LOG.jsonl` |

**Lưu ý trung thực:** con số 0,82 không phải độ đồng thuận độc lập, vì A dùng hướng dẫn mới còn B dùng hướng dẫn cũ, và hướng dẫn được viết sau khi xem kết quả vòng thử. Nó chỉ cho thấy việc hiệu chỉnh có tác dụng. Bản mô tả đầy đủ cho chương phương pháp: `reports/MO_TA_QUY_TRINH_GAN_NHAN_CV_JD.docx`.

## 5. Kết quả trên tập dev (8 CV, chỉ để khóa cấu hình)

Đo so với nhãn FINAL dev; khoảng tin cậy 95% bằng bootstrap theo CV.

| Đầu vào | Chiến lược | Kappa gộp 8 tiêu chí | Spearman điểm tổng | Kappa trạng thái yêu cầu |
|---|---|---|---|---|
| CVSchema chuẩn | Bộ luật | 0,76 | 0,84 | 0,52 |
| | M3 (RAG) | 0,72 | 0,80 | – |
| | **P** | **0,79** | 0,84 | 0,42 |
| Trích xuất B0 | Bộ luật | 0,65 | 0,78 | 0,51 |
| | M3 | 0,71 | 0,75 | – |
| | **P** | **0,76** | 0,79 | 0,41 |

- **Chênh lệch kappa P − M3:** [+0,02; +0,10] trên CVSchema chuẩn; [−0,01; +0,12] trên B0. Dev chỉ có 8 CV, nên **chưa kết luận**; kết luận lấy từ tập test.
- **Phát hiện ban đầu:**
  1. **Lỗi trích xuất làm giảm chất lượng chấm.** Tương quan điểm tổng của LLM giảm từ 0,80–0,85 (CVSchema chuẩn) xuống 0,62–0,75 (B0). Đây là vấn đề P được thiết kế để xử lý.
  2. **Bằng chứng của LLM không được kiểm thì hay sai.** Chỉ **59–69%** điểm của M1–M4 có đoạn bằng chứng tìm thấy nguyên văn trong CV; P đạt 100% nhờ kiểm chứng (dữ liệu cho H1).
  3. **LLM chấm thấp hơn người ở C2 và C3.** Nhóm không chỉnh, để giữ cấu hình đã khóa; báo cáo như một phát hiện.
  4. **Xác định trạng thái yêu cầu JD là phần khó nhất** với cả người lẫn máy. Yêu cầu khái niệm có kappa giữa hai người chỉ 0,33. Ở phần này P (0,42) còn kém bộ luật từ khóa (0,52).
- **Phân tích độ nhạy rubric** (`reports/PHAN_TICH_DO_NHAY_RUBRIC_DEV.md`):
  - C8 tương quan với mức phù hợp của người 0,88, đây là căn cứ cho trọng số 25%;
  - với 2000 bộ trọng số ngẫu nhiên, thứ hạng CV gần như không đổi (trung vị 0,98);
  - đổi ngưỡng C8 chỉ làm 2–6/16 cặp đổi điểm.

## 6. Cách nhóm giữ tính khách quan

| Cơ chế | Làm gì | Minh chứng |
|---|---|---|
| Đăng ký trước | Cố định cấu hình, luật chọn tham số, so sánh chính (P với M3) và tiêu chí kết luận **trước khi có kết quả** | `downstream/eval/DANG_KY_TRUOC.md`, commit `e9c95e6` lúc 13:48 ngày 17/10 |
| Luật chọn ngưỡng không dùng nhãn | Ngưỡng hiện điểm tổng của P chọn theo tỉ lệ hiện điểm, không theo độ khớp với người; kết quả 0,90 | `lock_config.py`; `DANG_KY_TRUOC.md` §8 |
| Tập test chạy một lần | Không chỉnh prompt, rubric hay ngưỡng sau khi xem kết quả; mọi thay đổi ghi kèm lý do | `DANG_KY_TRUOC.md` §6–7 |
| Ghi vết mọi thay đổi | Hash code của từng lần chạy; nhật ký; sự cố code lệch sáng 17/10 được phát hiện, sửa và ghi lại công khai | `run_config.json`; `reports/NHAT_KY_TIEN_DO.md` |
| Sổ quyết định | 40 quyết định, mỗi quyết định có lý do, minh chứng và mức chắc chắn; còn 4 quyết định ở mức Yếu | Trang "Sổ quyết định và minh chứng KLCN029"; `reports/minh_chung/` |
| Tài liệu tham khảo | Chỉ trích tài liệu đã đối chiếu; đã kiểm thư mục 9 bài trên arXiv; cảnh báo một bài đăng ở tạp chí không cùng chuyên ngành | `reports/TAI_LIEU_THAM_KHAO.md` |

## 7. Rủi ro và cách xử lý

| Rủi ro | Mức | Cách xử lý |
|---|---|---|
| Hạn mức gói miễn phí của Groq (khoảng 170 lượt gọi/ngày); nhóm không có ngân sách API trả phí | Cao | Chạy theo thứ tự ưu tiên (P và M3 trước); các biến thể của P dùng lại câu trả lời nên không tốn lượt gọi; dự kiến 5–6 ngày cho tập test |
| Model chấm (`qwen/qwen3.8-27b` trên Groq) đang ở trạng thái Preview, có thể bị ngừng | Trung bình | Ghi trạng thái model mỗi ngày chạy (`model_snapshot`); nêu trong hạn chế |
| Nhãn vòng chính trễ hạn 20/10 | Trung bình | Chạy model trước, không phụ thuộc nhãn; phân xử ngay khi nhận |
| Cơ sở tri thức của RAG: 10/12 mục là quy ước nội bộ chưa có nguồn | Trung bình | Khải đang kiểm nguồn theo bảng hướng dẫn; không sửa nội dung trước khi chạy xong tập test |
| Tập đánh giá nhỏ (16 CV test) | Trung bình | Báo cáo khoảng tin cậy; không khẳng định quá dữ liệu |

## 8. Kế hoạch đến 08/11

| Thời gian | Việc | Người |
|---|---|---|
| 18/10 | Họp, chốt mục 1; ghi quyết định H1/H2 vào đăng ký trước | Lộc, giảng viên, Claude |
| 17–23/10 | Chạy tập test: P và M3 (trên CVSchema chuẩn, B0, P1), H3, rồi M1, M2, M4 | Lộc chạy máy |
| 20–22/10 | Nhận nhãn vòng chính, đo độ đồng thuận chính thức, phân xử, nhãn FINAL test | Lộc, Claude |
| 21–25/10 | Đánh giá H2 (so sánh cặp mù) và kiểm tra H1 bằng người | 2 người chấm, 1 người kiểm |
| 24–28/10 | Phân tích kết quả test, H1–H3, tách tiếng Anh/tiếng Việt, phân tích lỗi | Claude, Lộc |
| 18–25/10 | Chương 1–2 | Đắc, Khải |
| 26/10–02/11 | Chương 3 (phương pháp), chương 4 (kết quả), chương 5 (kết luận) | [phân công] |
| 03–07/11 | Rà soát, gom báo cáo cuối, chuẩn bị bảo vệ | Cả nhóm |

## 9. Câu hội đồng có thể hỏi và cách trả lời

**"Đề tài đo độ khớp với người chấm, vậy khi người dùng thật tải CV lên thì ai chấm?"**
- Không ai chấm cả: hệ thống chấm tự động. Người chấm chỉ dùng để **kiểm định hệ thống trước khi đưa vào dùng**, trên tập CV có nhãn (giống như kiểm định một bài test trên mẫu có đáp án trước khi dùng đại trà).
- Kết quả trên tập test cho biết điểm của hệ thống khớp với người chấm đến đâu, với loại CV tương tự: CV CNTT, thực tập đến junior, tiếng Anh và tiếng Việt.
- Với từng CV của người dùng thật, hệ thống không đo được độ khớp, nên bù bằng ba cơ chế:
  1. mỗi điểm kèm đoạn trích **có thật trong CV**, người dùng tự kiểm được;
  2. tiêu chí thiếu căn cứ hiện "cần xác minh" thay vì đoán;
  3. người dùng chấm mức hài lòng 1–5 sao, nhóm theo dõi trong trang quản trị.
- Kết luận chỉ áp dụng trong phạm vi đã kiểm định. CV ngành khác hoặc cấp quản lý nằm ngoài phạm vi.

**"Vì sao C8 chiếm 25%?"** Trên dev, C8 là tiêu chí gắn chặt nhất với đánh giá mức phù hợp của người (0,88). Thứ hạng CV gần như không đổi khi thay trọng số (`PHAN_TICH_DO_NHAY_RUBRIC_DEV.md`).

**"Có chỉnh cấu hình cho đẹp số không?"** Cấu hình và luật chọn tham số được đăng ký trước, có commit kèm thời điểm; tập test chạy một lần; mọi thay đổi được ghi kèm lý do (mục 6).

**"Vì sao chọn Qwen3.8-27B trên Groq?"**
- Gói miễn phí, vì nhóm không có ngân sách API.
- Hỗ trợ JSON Schema strict, nhờ đó tỉ lệ tuân thủ rubric đạt 100%.
- Mọi chiến lược dùng cùng một model, nên chênh lệch đến từ phương pháp.
- Đã ghi rõ: model đang ở trạng thái Preview, và Groq phục vụ bản lượng tử hóa (`reports/minh_chung/I01_*`).

**"Fine-tune kém bản gốc thì phần huấn luyện có ý nghĩa gì?"** Đây là kết quả âm được đo nghiêm túc: có khoảng tin cậy, phân tích nguyên nhân và thí nghiệm phản thực. Nó chỉ ra rủi ro khi huấn luyện trên dữ liệu tổng hợp rồi áp dụng cho CV thật. Hướng khắc phục (dữ liệu v2) ghi vào phần phát triển.

## Phụ lục: minh chứng

| Nội dung | Vị trí |
|---|---|
| Nhật ký tiến độ (theo thứ tự, có commit) | `reports/NHAT_KY_TIEN_DO.md` |
| Đăng ký trước | `downstream/eval/DANG_KY_TRUOC.md` |
| Minh chứng theo từng quyết định | `reports/minh_chung/README.md` |
| Quy trình gán nhãn | `reports/MO_TA_QUY_TRINH_GAN_NHAN_CV_JD.docx` |
| Đề xuất H1/H2 | `reports/minh_chung/M08_DE_XUAT_KIEM_CHUNG_H1_H2.docx` |
| Phân tích độ nhạy rubric | `reports/PHAN_TICH_DO_NHAY_RUBRIC_DEV.md` |
| Kết quả trích xuất GOLD40 | `training/evaluation/results/gold40_b0_b1_p0_p1_v1/REPORT.md` |
| Phân tích nguyên nhân fine-tune kém | `reports/PHAN_TICH_NGUYEN_NHAN_FINE_TUNE_KEM_TREN_CV_THAT_2026-10-13.md` |
| So sánh với TechJobs.vn | `reports/minh_chung/SO_SANH_TECHJOBS.md` |
| Tài liệu tham khảo | `reports/TAI_LIEU_THAM_KHAO.md`, `reports/tai_lieu_tham_khao.bib` |
| Kho mã | nhánh `deploy/free-tier` |
