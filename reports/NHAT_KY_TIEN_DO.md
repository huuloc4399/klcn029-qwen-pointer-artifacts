# Nhật ký tiến độ KLCN029

**Đọc file này đầu tiên khi bắt đầu phiên mới hoặc sau khi compact.** Cập nhật sau khi xong mỗi phần: thêm một dòng vào mục 4, sửa mục 2, 5, 6, 7. Ghi đủ ngày, file và commit, để không phải nhớ lại từ cuộc trò chuyện.

Cập nhật lần cuối: 17/10/2026, 15:30.

## 1. Mục tiêu và hạn

- Khóa luận KLCN029: hệ thống đánh giá CV ngành CNTT theo rubric, có so khớp với JD và gợi ý sửa CV. Có 2 mô-đun chính:
  - trích xuất CV (OCR, Qwen3-4B huấn luyện QLoRA, đầu ra CVSchema 2.0);
  - chấm điểm (bộ luật, M1–M4, phương pháp đề xuất P).
- Hạn nộp: **08/11/2026**. Kế hoạch tuần 11 (26/10–01/11): chạy tập test một lần, ablation, phân tích lỗi.
- Nhóm:
  - Lộc: điều phối, phân xử nhãn;
  - Khải: người chấm A, kiểm nguồn cơ sở tri thức;
  - Đắc: viết báo cáo, đang viết chương 1–2;
  - người chấm B **[ghi tên]**.

## 2. Trạng thái hiện tại (17/10)

- Tập dev đã khóa cấu hình. P đủ 32/32 kết quả; `COVERAGE_MIN` = 0,90 theo luật đăng ký trước.
- **Lộc bắt đầu chạy tập test** (`test_v1`): bộ luật, P, M3 trước; sau đó H3; rồi M1, M2, các biến thể bỏ bớt thành phần, M4.
- Vòng chấm chính (32 cặp test, hướng dẫn bản 3): hai người chấm đang làm, **hạn 20/10**.
- Chờ chốt với giảng viên hướng dẫn cách kiểm chứng H1 và H2 (`minh_chung/M08_DE_XUAT_KIEM_CHUNG_H1_H2.md`).
- Khải đang kiểm nguồn cơ sở tri thức (trang "Kiểm nguồn cơ sở tri thức KLCN029").
- **Vấn đề đang mở:** code trong thư mục làm việc khác HEAD. Xem mục 7.

## 3. Quy ước bắt buộc

- Trả lời bằng tiếng Việt.
- Không in token, nội dung `.env` hay nội dung CV thật (chỉ in số liệu tổng hợp). Nhãn, CV, JD thô không đưa lên git.
- Không dừng dịch vụ của người dùng. Không sửa gold, parser hay hàm tính chỉ số để làm đẹp kết quả.
- Giữ tính độc lập giữa hai người chấm: không cho người này xem nhãn của người kia; danh sách bất đồng chỉ đưa cho người phân xử.
- Che thông tin cá nhân và xin đồng ý trước khi gửi CV cho Groq.
- Tập test chạy **một lần** với cấu hình đã khóa (`downstream/eval/DANG_KY_TRUOC.md`). Mọi thay đổi sau đăng ký ghi vào §7 của file đó, kèm lý do.
- Mọi quyết định cần minh chứng: ghi vào Sổ quyết định và `reports/minh_chung/`. Tài liệu dùng đến ghi vào `reports/TAI_LIEU_THAM_KHAO.md` và `.bib`; chỉ trích tài liệu đã đối chiếu.
- Khi chỉ sửa hướng dẫn người chấm, chỉ gửi file docx, không đóng gói lại zip.
- Không sửa `rubric_scoring.py` (prompt, mô tả mức) trước khi chạy xong tập test.

## 4. Nhật ký theo thứ tự

### Trước 14/10: mô-đun trích xuất và bản web

| Ngày | Việc | Ở đâu |
|---|---|---|
| 06–07/10 | Triển khai baseline (Render, RunPod); bản demo Colab đầu cuối có thu CV thật kèm đồng ý | lịch sử git, `cv_evaluation_web/` |
| 10–11/10 | GOLD40: chốt nhãn trích xuất 40 CV; đo B0/B1/P0/P1; báo cáo tổng hợp dữ liệu và tiến độ cho giảng viên | `reports/GOLD40_*.md`, `reports/BAO_CAO_*_2026-10-11.*`, `training/evaluation/` |
| 12–13/10 | Triển khai miễn phí (HF Space, Oracle, laptop qua Cloudflare); trang quản trị và đánh giá sao | lịch sử git |
| 13/10 | Phân tích nguyên nhân bản fine-tune kém trên CV thật | `reports/PHAN_TICH_NGUYEN_NHAN_FINE_TUNE_KEM_TREN_CV_THAT_2026-10-13.md` |

### 14–15/10: chuẩn bị chấm CV–JD

| Ngày | Việc | Ở đâu |
|---|---|---|
| 14/10 | Mô-đun A: rubric v2 (8 tiêu chí, trọng số 10/10/15/15/10/5/10/25), bộ 12 JD, 48 cặp CV–JD (dev 16, test 32), file Excel chấm và gói cho người chấm | `downstream/rubric/rubric_v2.json`, `downstream/data/`, commit `cb1d572`, `e0ae9eb` |
| 15/10 | Thí nghiệm format_shift; chấm theo rubric v2 bằng M1–M4 và bộ luật trên web; RAG truy xuất 1 mục theo JD và 2 mục theo CV | commit `326f56d`, `8be30b0`, `8850509`, `058c3b3` |

### 16/10

| Việc | Ở đâu |
|---|---|
| Script độ đồng thuận giữa hai người chấm (bootstrap theo CV, danh sách phân xử) | `downstream/eval/iaa.py`, `74400bb` |
| Bộ chạy chiến lược với điều kiện cố định, chạy tiếp được khi bị dừng | `downstream/eval/run_strategies.py`, `eca6c69` |
| Phương pháp P: kiểm chứng trích dẫn, từ chối chấm, độ bao phủ; bộ luật K cho trạng thái yêu cầu | `grounded_scoring.py`, `a358c01` |
| Phép thử H3 (đọc lỗi và thiếu thật trên 10 CV test) | `downstream/eval/perturb_h3.py`, `cef8db3` |
| Đưa P vào web làm chiến lược mặc định | `8ab4d82` |
| Rà báo cáo của Đắc (37 nhận xét); tài liệu chốt đóng góp chính (trang Docs) | `Báo cáo khóa luận KLCN-029_NHAN_XET.docx` |
| Vòng thử: 16 cặp dev, A và B chấm; độ đồng thuận bản đầu: kappa gộp 0,69 | `downstream/data/labels_v1/iaa_pilot_v1_2026-10-16/` |
| Hướng dẫn chấm bản 2: danh sách kiểm tra C1/C2/C3/C7, quy tắc Ctrl+F | `package_rater.py`, `8a7543f` |
| Rà GOLD40 của Khải: lưu nguyên trạng, **không** tạo gold v2 | `annotation/audits/gold40_content_review_2026-10-11/returned/` |
| Phần A: kiểm tra yêu cầu khái niệm trong P và K; biến thể `p_no_concept_check`; tách độ đồng thuận yêu cầu thành loại từ điển và loại khái niệm; dùng lại kết quả qua `--reuse-from` | `18ebeb6` |

### 17/10

| Giờ | Việc | Ở đâu |
|---|---|---|
| sáng | A chấm lại theo bản 2 (không xem nhãn B): kappa gộp 0,82. Lấy A bản 3 làm bản chính | `labels_v1/GHI_CHU_PHIEN_BAN_PILOT.md` |
| 06:49–06:57 | **Phiên khác** commit `1c45168` (gom quy tắc yêu cầu vào `requirement_rules.py`) và `233b615` (biến thể P dùng lại câu trả lời của `p_grounded`); đến 06:59 bị hoàn tác trong thư mục làm việc, chưa commit. Xem mục 7 | git |
| 09:41–10:30 | Phân xử 3 vòng (46 + 35 + 20 dòng); ghép nhãn FINAL; C8 tính từ trạng thái yêu cầu | `downstream/eval/adjudicate.py`, `labels_v1/FINAL_dev.jsonl`, `a38ca5f`, `94933e6` |
| 10:38 | Hướng dẫn bản 3 (yêu cầu khái niệm, khi nào chọn `unclear`); gói vòng chính 32 cặp, hạn 20/10 | `2eef01c`, `labels_v1/packages/main_rater_*.zip` |
| trưa | Bản nháp mô tả quy trình gán nhãn cho chương phương pháp | `reports/MO_TA_QUY_TRINH_GAN_NHAN_CV_JD.md/.docx` |
| 13:48 | **Đăng ký trước** cấu hình, luật chọn `COVERAGE_MIN`, so sánh chính P với M3 | `downstream/eval/DANG_KY_TRUOC.md`, `lock_config.py`, `e9c95e6` |
| 13:56 | Sổ quyết định và minh chứng (40 quyết định, trang Docs); phân tích độ nhạy trọng số và luật C8 | `sensitivity.py`, `reports/PHAN_TICH_DO_NHAY_RUBRIC_DEV.md`, `34feafd` |
| 14:00–14:30 | Thư mục minh chứng: lý do chọn model (I01), trạng thái model trên Groq, cách lập danh sách từ (P06); script `model_snapshot`; danh mục tài liệu | `reports/minh_chung/`, `a632c2a`, `5feeba6` |
| 14:51 | Áp luật đăng ký trước: `COVERAGE_MIN` = 0,90. Dev đủ cho việc khóa cấu hình; không chạy biến thể P và 8 cặp M4/b0 còn lại trên dev | `8b9eb87`, `DANG_KY_TRUOC.md` §8 |
| 15:04 | Đề xuất kiểm chứng H1/H2; kiểm thư mục 9 tài liệu trên arXiv; cảnh báo bài Baral (tạp chí dược); trang hướng dẫn Khải kiểm nguồn | `minh_chung/M08_*`, `TAI_LIEU_THAM_KHAO.md`, `931719c`, `f173692` |

## 5. Kết quả chính đến nay (dev, chỉ tham khảo)

- Độ đồng thuận hai người chấm, vòng thử:
  - kappa gộp 0,69 (bản đầu), 0,82 (sau khi A đọc hướng dẫn bản 2);
  - kappa trạng thái yêu cầu 0,40;
  - không ai dùng `unclear`.
- Nhãn FINAL dev: 16 cặp. Trạng thái 205 yêu cầu: met 62, mentioned_only 19, missing 114, unclear 10.
- `dev_v2` so với FINAL (8 CV):
  - đầu vào gold: kappa gộp P 0,79, M3 0,72, chênh lệch [+0,02; +0,10];
  - đầu vào b0: P 0,76, M3 0,71, chênh lệch [−0,01; +0,12];
  - trạng thái yêu cầu: P 0,42, bộ luật K 0,52;
  - LLM chấm thấp hơn người ở C2 và C3 (không chỉnh; báo cáo như một phát hiện).
- H1 thăm dò: M1–M4 chỉ 59–69% điểm có bằng chứng tìm thấy trong CV; P 100%.
- Độ nhạy: C8 tương quan với mức phù hợp của người 0,88; thứ hạng CV gần như không đổi khi thay trọng số (trung vị 0,98).
- Chi phí: gói miễn phí Groq cho khoảng 170 lượt gọi (0,57 triệu token) mỗi ngày.

## 6. Còn thiếu

**Đang chạy hoặc chờ người khác**
- [ ] Tập test `test_v1` (Lộc chạy theo thứ tự ưu tiên; chạy `model_snapshot` mỗi ngày chạy)
- [ ] Phép thử H3 có LLM: `python -m downstream.eval.perturb_h3 run --run-id h3_v1`, rồi `report`
- [ ] Nhãn vòng chính của A và B (hạn 20/10) → kiểm lỗi, đo độ đồng thuận chính thức, phân xử, `FINAL_test.jsonl`
- [ ] Chốt H1 và H2 với giảng viên → ghi vào `DANG_KY_TRUOC.md` §7 **trước khi xem kết quả test**
- [ ] Khải kiểm nguồn 19 dòng → cập nhật `kb_v1.jsonl` (chỉ phần nguồn), danh mục tài liệu, R03
- [ ] Đắc viết chương 1–2

**Claude làm khi có đầu vào**
- [ ] Giải quyết vấn đề ở mục 7 (cần Lộc quyết định)
- [ ] Script đo H1 (tách nhiều đoạn bằng chứng của M1–M4) và phiếu so sánh cặp mù cho H2, sau khi chốt
- [ ] Báo cáo tập test: so sánh chính, các biến thể, tách EN/VI, chạy lại phân tích độ nhạy trên nhãn test
- [ ] P07: số lần hỏi lại và số điểm được cứu của P
- [ ] R07: ghi hạn chế của luật C7 (kappa 0,31 so với người)
- [ ] Đo độ lặp (`--repeats 3` trên 4 cặp dev) nếu còn hạn mức
- [ ] Tạo `RUBRIC_CHANGELOG`
- [ ] Gom `reports/minh_chung/` và các báo cáo thành báo cáo cuối

**Nhóm làm**
- [ ] Đối chiếu nội dung các tài liệu thống kê (Cohen, Landis–Koch, Efron, BM25) và các bài "Đã kiểm thư mục" khi trích
- [ ] Thay bài Baral bằng 2–3 bài có phản biện
- [ ] Khai báo việc dùng công cụ AI theo quy định của khoa
- [ ] Ghi tên người chấm B và xác nhận người phân xử có khác A và B không (cho mục mô tả gán nhãn)

## 7. Vấn đề đang mở

**Code trong thư mục làm việc khác HEAD (phát hiện 17/10, 15:20).**
- **Chuyện gì đã xảy ra:**
  - Lúc 06:49–06:57, một phiên khác commit `1c45168` và `233b615`.
  - Lúc 06:59, ba file được đưa về bản cũ trong thư mục làm việc mà không commit: `evaluator.py`, `rubric_scoring.py`, `test_run_strategies.py`; file `requirement_rules.py` bị xóa.
  - Các commit sau đó của phiên này đã đưa bản cũ của `run_strategies.py`, `package_rater.py` và vài file test vào HEAD.
- **Hệ quả:**
  - Code thực sự chạy `dev_v2` (và sẽ chạy `test_v1`) là bản trong thư mục làm việc. Hash trong `run_config.json` khớp đúng bản này, nên kết quả không bị ảnh hưởng.
  - Nhưng HEAD đang lẫn hai phiên bản: một bản checkout mới từ git sẽ không tái tạo được đúng cấu hình đã chạy.
- **Đề xuất:** commit trạng thái hiện tại thành một lần hoàn tác rõ ràng của `1c45168` và `233b615` (giữ đúng cấu hình đã đăng ký). Ghi vào `DANG_KY_TRUOC.md` §7. Các ý hay của `1c45168` (quy tắc dùng chung, ghi chú bắt buộc cho người chấm) để lại sau khi chạy xong tập test. **Chờ Lộc đồng ý.**

## 8. File và trang quan trọng

| Nội dung | Vị trí |
|---|---|
| Đăng ký trước, cấu hình khóa | `downstream/eval/DANG_KY_TRUOC.md` |
| Minh chứng theo mã quyết định | `reports/minh_chung/README.md` |
| Danh mục tài liệu | `reports/TAI_LIEU_THAM_KHAO.md`, `reports/tai_lieu_tham_khao.bib` |
| Phạm vi và quyết định của dự án | `reports/PROJECT_SCOPE_AND_DECISIONS.md`, `Ke_hoach_nghien_cuu_KLCN029.md` |
| Nhãn và phân xử (không có trên git) | `downstream/data/labels_v1/` (`GHI_CHU_PHIEN_BAN_PILOT.md`, `FINAL_dev.jsonl`) |
| Kết quả chạy (không có trên git) | `downstream/results/<run_id>/` (`report.json`, `REPORT.md`, `run_config.json`) |
| Sổ quyết định và minh chứng (trang Docs) | https://claude.ai/code/artifact/63101642-7714-4031-a3a7-1cfe3a306c2e |
| Kiểm nguồn cơ sở tri thức (trang Docs, cho Khải) | https://claude.ai/code/artifact/053d874c-3dc5-420b-8300-057948814631 |
| Chốt đóng góp chính (trang Docs, 16/10) | **[dán link]** |
