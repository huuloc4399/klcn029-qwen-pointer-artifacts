# Vì sao model fine-tune kém hơn Qwen gốc trên CV thật?

Ngày: 13/10/2026. Phạm vi: mô đun **trích xuất CV** (CVSchema 2.0). Bổ sung cho
`GOLD40_PHAN_TICH_LOI_VA_BUOC_TIEP_2026-10-10.md` và `GOLD40_CHAN_DOAN_TONG_QUAT_HOA_VA_RASOAT_2026-10-11.md`;
không lặp lại toàn bộ hai báo cáo đó. Mọi số mới tính offline từ output đã đóng băng, không gọi model,
không sửa nhãn, parser hay metric.

## 1. Kết luận

Fine-tune trên 850 CV tổng hợp dạy model **các quy ước bề mặt của bộ sinh dữ liệu** (tiêu đề mục cố định,
mỗi kỹ năng một dòng, mỗi văn bản dài một dòng) thay vì cách đọc CV nói chung. Trên dữ liệu cùng bộ sinh,
các quy ước này đủ để đạt F1 ≈ 99%. CV thật không tuân theo chúng, nên model fine-tune bỏ sót hoặc gộp sai ở
đúng những chỗ đó, trong khi Qwen gốc (không học các quy ước này) vẫn đọc được.

Bằng chứng trên GOLD40 là **tương quan có cơ chế rõ** (mục 3). Thí nghiệm phản thực `format_shift_v1`
(mục 5, chạy xong 15/10/2026) **xác nhận một phần** giả thuyết này:

- Có tác động nhân quả, nhưng **nhỏ**. B1 mất điểm khi kỹ năng bị gộp dòng; mức mất này lớn hơn B0 một cách
  có ý nghĩa (DiD −6,50 điểm, CI 95% [−14,00; −1,64]). P0 mất điểm ở summary và chi tiết dự án khi văn bản dài
  bị ngắt dòng.
- Đổi tiêu đề mục chỉ làm giảm nhẹ summary; không có ý nghĩa thống kê.
- Trong mọi biến thể, B1 và P0 vẫn đạt 94–99%, cao hơn B0 (83–90%). Định dạng bề mặt như đã mô phỏng **không
  giải thích được** khoảng cách khoảng 17 điểm giữa B1 và B0 trên GOLD40.

Vì vậy phần lớn khoảng cách nhiều khả năng đến từ các nguyên nhân còn lại trong bảng mục 4: lệch phạm vi nhãn,
dữ liệu train không phủ CV thật (tiếng Việt, hồ sơ sinh viên, các trường vắng) và độ nhiễu của CV thật. Chưa
có bằng chứng cho overfitting theo số bước train (loss validation vẫn giảm đến cuối run, xem báo cáo ngày 11/10).

## 2. Bối cảnh số liệu

| Cấu hình | Validation tổng hợp: Field Micro F1 | GOLD40 (40 CV thật): Field Micro F1 | CVSchema hợp lệ GOLD40 |
|---|---:|---:|---:|
| B0: Qwen gốc, Full JSON | 88,06% | **65,52%** | 40/40 |
| B1: adapter stage 1, Full JSON | 99,60% | 48,28% | 35/40 |
| P0: adapter Pointer stage 2 | 99,64% | 49,66% | 34/40 |
| P1: P0 + kiểm chứng/retry | — | 52,81% | 39/40 |

Nguồn: `training/evaluation/results/gold40_b0_b1_p0_p1_v1/`. Bootstrap ghép cặp B1 − B0: −17,24 điểm,
CI 95% [−22,58; −11,75].

## 3. Bằng chứng mới: model học quy ước của dữ liệu tổng hợp

Tính bằng `training/audits/gold40_format_shortcuts_2026-10-13_v1/analyze_format_shortcuts.py`
(kết quả: `format_shortcuts.json` cùng thư mục; chỉ có số đếm tổng hợp, không chứa nội dung CV).

### 3.1. Tiêu đề mục cố định

Cả 850 CV train dùng đúng một bộ tiêu đề tiếng Anh: `Summary`, `Skills`, `Experience`, `Education`,
`Projects`, `Languages`, `Certificates`, `Preferences`, `Hobbies`, `Looking for`. Trong 159 lần xuất hiện
tiêu đề mục ở GOLD40 (các tiêu đề có ở ≥ 2 CV), chỉ **58 (36%)** thuộc bộ từ này. Phần còn lại là `Học vấn`
(19), `Kỹ năng` (14), `Dự án` (11), `Technical skills` (8), `Objective` (6), `Career objective` (6),
`Soft skills` (6)...

### 3.2. Summary chỉ được nhận ra dưới tiêu đề "Summary"

617/617 CV train có summary đều đặt nó dưới tiêu đề `Summary`. Ở GOLD40, chỉ 2/38 CV có summary dùng tiêu đề
này; các CV còn lại dùng `Mục tiêu nghề nghiệp` (10), `Objective` (5), `Career objective` (5), `Giới thiệu`...

| Model | Có summary khi tiêu đề là "Summary" | Có summary khi tiêu đề khác |
|---|---:|---:|
| B0 – Qwen gốc | 2/2 | **35/36** |
| B1 – adapter stage 1 | 1/2 | 23/36 |
| P0 – Pointer | 2/2 | **13/36** |
| P1 – Pointer + retry | 2/2 | 13/36 |

Model fine-tune **bỏ trống** summary (không phải chép sai), giải thích phần lớn mức giảm F1 trường summary
từ 89,47% (B0) xuống 30,19% (P0/P1). Tiêu đề được xác định bằng heuristic (dòng ngắn gần nhất phía trên
summary); một vài CV không có tiêu đề rõ ràng.

### 3.3. "Mỗi dòng là một kỹ năng"

Trong train, kỹ năng gần như luôn nằm mỗi dòng một mục: 29/850 CV có một dòng chứa từ 3 kỹ năng được gán nhãn
trở lên (báo cáo `gold40_input_shift_v1` đếm 24/850 với định nghĩa hơi khác), và 0/8.253 nhãn kỹ năng có dạng
`Nhóm: ...`. Ở GOLD40, **31/40 CV** có dòng gộp kiểu `Programming: C#, JavaScript, Python`.

| Model | Số mục hard_skills trả về | Mục chứa ≥ 3 dấu phẩy (chuỗi gộp) | Mục là nguyên một dòng nguồn |
|---|---:|---:|---:|
| B0 | 513 | 28 (5%) | 75 (15%) |
| B1 | 176 | 59 (**34%**) | 64 (**36%**) |
| P0 | 316 | 41 (13%) | 70 (22%) |
| P1 | 347 | 46 (13%) | 86 (25%) |

B1 trả về ít hơn gần 3 lần số mục và chép nguyên dòng gộp thành một mục. `skills.hard_skills` có 569/1.541
giá trị gold nên kéo mạnh tổng F1: F1 trường này 58,33% (B0) → 13,69% (B1). Bỏ riêng trường này, khoảng
cách B0 − B1 thu hẹp từ 17,24 xuống 6,80 điểm (báo cáo ngày 11/10).

### 3.4. Văn bản dài một dòng và không có gạch đầu dòng

Theo `training/audits/gold40_input_shift_2026-10-11_v1/input_shift.json`: 617/617 summary train là đúng
một dòng nguồn, 0/38 ở GOLD40; train không có dòng gạch đầu dòng nào, GOLD40 có ở 27/40 CV. Với Pointer,
`summary_span`, `description_span`, `details_span` trong train luôn là khoảng một dòng, trong khi CV thật cần
khoảng nhiều dòng. Long Text F1: B0 52,73%, P0 17,39%.

## 4. Tổng hợp nguyên nhân

| Nguyên nhân | Mức bằng chứng | Nguồn |
|---|---|---|
| Học quy ước bề mặt của bộ sinh (tiêu đề cố định, mỗi dòng một kỹ năng, văn bản dài một dòng) thay cho đọc hiểu | **Có nhân quả nhưng tác động nhỏ** (mục 5.3): kỹ năng gộp (B1, DiD có ý nghĩa) và văn bản ngắt dòng (P0, trường dài); tiêu đề mục không có ý nghĩa. Không đủ giải thích khoảng cách trên GOLD40 | Mục 3, 5.3 |
| Dữ liệu train không phủ CV thật: 0 CV tiếng Việt, 0 nhãn GPA/GitHub, soft skill chỉ "Communication", hồ sơ người đi làm thay vì sinh viên | Mạnh | Báo cáo 11/10, mục 3.2 |
| Quy tắc nhãn lệch: converter không đưa công nghệ dự án và ngoại ngữ vào `hard_skills`, hướng dẫn gold có | Mạnh | Báo cáo 11/10, mục 3.1 |
| Lỗi cấu trúc output (5 CV invalid ở B1) | Có, giải thích một phần: trên 35 CV hợp lệ cả hai, B0 65,91% vs B1 52,28% | Báo cáo 11/10, mục 3.4 |
| Overfitting theo số bước train | Chưa có bằng chứng (eval loss vẫn giảm) | Báo cáo 11/10, mục 3.6 |
| OCR | Gần như không liên quan: 39/40 CV dùng lớp chữ có sẵn | Báo cáo 11/10, mục 3.5 |

Hệ quả thực tế: **train thêm trên cùng dữ liệu không giải quyết được**; cần đổi dữ liệu.

## 5. Thí nghiệm kiểm chứng nhân quả: `format_shift_v1`

### 5.1. Thiết kế

- 20 CV tổng hợp của tập validation (7 sidebar, 7 classic, 6 two_column; seed 42), mỗi CV 5 biến thể với
  **cùng nhãn**:
  - `original`: giữ nguyên (đối chứng).
  - `headings`: đổi tiêu đề mục sang từ đồng nghĩa của CV thật; một nửa số CV dùng tiêu đề tiếng Việt, một số viết hoa.
  - `grouped_skills`: kỹ năng gộp thành dòng `Nhóm: a, b, c`, soft skill thành dòng `Soft skills: ...`.
  - `wrapped_text`: summary, mô tả kinh nghiệm, chi tiết dự án ngắt thành nhiều dòng 60–85 ký tự (như trích PDF).
  - `combined`: cả ba thay đổi.
- Tổng thay đổi: 122 tiêu đề, 215 dòng kỹ năng, 129 đoạn văn dài. Khi tạo dữ liệu, script tự kiểm tra mọi giá trị
  nhãn tìm thấy trong bản gốc vẫn tìm thấy trong từng biến thể (ngắt dòng chỉ tại khoảng trắng), nên mọi thay
  đổi F1 giữa các biến thể của cùng CV **chỉ do định dạng đầu vào**.
- Chạy B0, B1, P0 với đúng cấu hình đã khóa: Qwen3-4B-Instruct-2507 revision cố định, NF4, greedy, Full JSON
  1.280 token, Pointer 768 token, cùng prompt và chat template.
- Chỉ số chính: Δ F1 so với `original` trên cùng CV, và **difference-in-differences** = (Δ của model fine-tune)
  − (Δ của B0) trên cùng CV và biến thể, kèm CI 95% bootstrap theo CV. DiD âm với CI không chứa 0 nghĩa là
  fine-tune làm model nhạy với định dạng hơn model gốc.

### 5.2. Dự đoán nếu giả thuyết đúng

- B0 giảm ít ở mọi biến thể.
- B1/P0 giảm rõ ở `headings` (summary bị bỏ trống) và `grouped_skills` (kỹ năng gộp), P0 giảm thêm ở
  `wrapped_text` nếu Pointer chỉ chọn một dòng; `combined` giảm nhiều nhất.
- Nếu B1/P0 **không** giảm hơn B0, giả thuyết bị bác bỏ và nguyên nhân chính nằm ở các mục khác của bảng 4
  (phạm vi nhãn, độ phủ nội dung).

### 5.3. Kết quả

Chạy xong ngày 14/10/2026 trên Colab T4.

- Cả ba lượt chạy đủ 100/100 mẫu và khớp SHA-256 đầu vào `17743e94…`. Adapter khớp `670e5725…` (B1) và
  `8d68628e…` (P0).
- Chỉ B0 có output chạm giới hạn token: 4/100.
- Chấm bằng parser và metric đã khóa:

```bash
python -m training.evaluation.evaluate_format_shift --base format_shift_v1_base_raw_greedy.zip --adapter-stage1 format_shift_v1_adapter_stage1_raw_greedy.zip --pointer-stage2 format_shift_v1_pointer_stage2_raw_greedy.zip
```

Kết quả đầy đủ: `training/evaluation/results/format_shift_v1/REPORT.md`.

**Field Micro F1 (%) theo biến thể** (Δ so với `original` trên cùng CV; ★ là CI 95% bootstrap theo CV không chứa 0)

| Model | original | headings | grouped_skills | wrapped_text | combined |
|---|---:|---:|---:|---:|---:|
| B0 | 86,65 | 88,51 (+1,86) | 90,07 (+3,42) | 83,37 (−3,28) | 86,80 (+0,15) |
| B1 | 99,61 | 99,38 (−0,23) | 96,53 (−3,08 ★) | 99,38 (−0,23) | 94,65 (−4,95 ★) |
| P0 | 99,61 | 99,44 (−0,17) | 99,44 (−0,17) | 96,34 (−3,27 ★) | 96,43 (−3,17 ★) |

**Trường bị ảnh hưởng**

| Model | Biến thể | Trường giảm |
|---|---|---|
| B1 | `grouped_skills` | `hard_skills` 99,76 → 85,79; `soft_skills` 100 → 90 |
| B1 | `combined` | `hard_skills` → 78,21 |
| B1, P0 | `headings` | summary → 93,33 (B1) và 89,66 (P0) |
| P0 | `wrapped_text` | summary → 62,50; chi tiết dự án → 51,85; mô tả kinh nghiệm → 89,53 |

**Difference-in-differences so với B0** (điểm %, CI 95%)

| Model | headings | grouped_skills | wrapped_text | combined |
|---|---|---|---|---|
| B1 | −2,09 [−9,29; +2,16] | **−6,50 [−14,00; −1,64]** | +3,05 [−1,72; +12,17] | −5,10 [−15,89; +6,45] |
| P0 | −2,03 [−9,26; +2,12] | −3,59 [−10,55; +0,68] | +0,01 [−5,24; +9,32] | −3,32 [−14,28; +7,38] |

**Đối chiếu với dự đoán ở 5.2**

| Dự đoán | Kết quả |
|---|---|
| B0 giảm ít | Đúng: B0 không giảm có ý nghĩa ở biến thể nào; tăng nhẹ ở `headings` và `grouped_skills` |
| B1/P0 giảm ở `headings` | **Không xác nhận**: summary giảm 6–10 điểm nhưng F1 chung và DiD không có ý nghĩa |
| B1 giảm ở `grouped_skills` | **Xác nhận**: Δ và DiD đều có ý nghĩa; `hard_skills` giảm gần 14 điểm |
| P0 giảm ở `grouped_skills` | Không: Pointer stage 2 giữ được `hard_skills` 99,44 |
| P0 giảm ở `wrapped_text` | **Xác nhận**: summary còn 62,50, chi tiết dự án còn 51,85; Δ chung có ý nghĩa với 20/20 output hợp lệ. DiD chung gần 0 chỉ vì B0 cũng giảm, nhưng mức giảm của B0 đến từ một output bị cắt do chạm giới hạn token: trên 18 CV B0 hợp lệ ở cả hai bản, B0 không giảm (89,36 → 89,99) |
| `combined` giảm nhiều nhất | Đúng với B1 (−4,95), gần đúng với P0 (−3,17 so với −3,27) |

**Cách hiểu**

- **Có quan hệ nhân quả.** Cách trình bày kỹ năng và cách ngắt dòng văn bản dài làm model fine-tune sai theo
  đúng cơ chế đã thấy trên GOLD40 (gộp kỹ năng; span Pointer bị cắt ở văn bản nhiều dòng).
- **Tác động nhỏ.** Mức giảm tối đa khoảng 5 điểm, và model fine-tune vẫn cao hơn B0 trên dữ liệu tổng hợp đã
  biến đổi. Ba biến đổi bề mặt này không tái tạo được khoảng cách khoảng 17 điểm trên GOLD40. Nguyên nhân chính
  nhiều khả năng là các mục còn lại của bảng 4: phạm vi nhãn, độ phủ dữ liệu (tiếng Việt, hồ sơ sinh viên,
  GitHub/GPA/activities/awards) và độ nhiễu của CV thật (bố cục hai cột, nội dung đa dạng).
- **Giới hạn của kết luận "nhỏ".** Thí nghiệm chỉ mô phỏng ba khác biệt trên một bộ sinh, với 20 CV; khoảng tin
  cậy của DiD còn rộng. Một biến đổi chưa mô phỏng (ví dụ trộn thứ tự đọc hai cột) vẫn có thể có tác động lớn.
- **Hệ quả cho hướng cải thiện ở mục 6.** Tăng cường định dạng (mục 6.1, ý đầu) vẫn cần, nhưng không đủ. Sửa
  phạm vi nhãn và thêm CV thật hoặc gần thật quan trọng hơn.

### 5.4. Cách chạy

1. Tạo dữ liệu (tái lập, cho cùng SHA-256): `python -m training.evaluation.format_shift`.
2. Mở `training/colab/Qwen3_Format_Shift_Counterfactual_Colab.ipynb` trên Colab (T4), chạy 3 lần với
   `MODEL_VARIANT` = `base`, `adapter_stage1`, `pointer_stage2`. Thời gian ước tính ~2 giờ, ~2,7 giờ, ~1,7 giờ
   (theo thời gian/CV của các lần đo validation trước). Notebook lưu từng mẫu vào Drive và tự chạy tiếp
   khi bị ngắt; thứ tự là từng CV đủ 5 biến thể nên dừng giữa chừng vẫn chấm được phần đã xong.
3. Chấm điểm offline bằng lệnh ở 5.3. Kiểm thử của phần tạo dữ liệu và chấm điểm:
   `python -m unittest training/tests/test_format_shift.py`.

## 6. Hướng cải thiện

1. **Dataset v2 có chủ đích**, giữ dataset v1 để truy vết:
   - tăng cường đúng các quy ước ở mục 3: tiêu đề đồng nghĩa và tiếng Việt, dòng kỹ năng gộp có nhãn tách
     từng mục, văn bản dài nhiều dòng với span nhiều dòng cho Pointer, gạch đầu dòng;
   - thêm nội dung còn thiếu: CV tiếng Việt, hồ sơ sinh viên/thực tập, ví dụ dương cho GPA, GitHub,
     activities, awards, nhiều soft skill;
   - sửa converter cho khớp hướng dẫn gold (công nghệ dự án, ngoại ngữ).
2. **Thêm một ít CV thật đã gán nhãn vào train** (ứng viên: 40 CV còn lại của real80, ghi rõ mức đã tiếp xúc).
   Với bài toán này, vài chục CV thật đa dạng thường có giá trị hơn nhiều CV tổng hợp cùng khuôn.
3. **Chọn checkpoint theo dev gồm CV thật**, không theo loss tổng hợp; cân nhắc ít bước hơn hoặc trộn dữ liệu chỉ
   dẫn tổng quát để giữ năng lực gốc.
4. **Kiểm tra lại bằng `format_shift_v1`** sau mỗi lần train: model mới phải có DiD gần 0.
5. **Phương án dự phòng cho triển khai và báo cáo:** Qwen gốc với prompt tốt hơn kết hợp Pointer/validator, vì B0
   đang tốt nhất về nội dung còn Pointer/retry tốt về độ hợp lệ cấu trúc và số token sinh.

## 7. Giới hạn

- GOLD40 là tập hậu kiểm, đã dùng để chẩn đoán; cải tiến sau này cần xác nhận trên nhóm CV thật mới.
- Các số ở mục 3 là tương quan trên 40 CV; nhận diện tiêu đề và dòng gộp dùng heuristic.
- `format_shift_v1` dùng một bộ sinh tổng hợp và mô phỏng một số khác biệt bề mặt; không thay thế đánh giá trên CV thật.
- Kết luận chỉ thuộc mô đun trích xuất; không đánh giá matching, chấm điểm hay sinh gợi ý.

## 8. Tái lập

| Mục | Lệnh |
|---|---|
| Số đo mục 3 | `python training/audits/gold40_format_shortcuts_2026-10-13_v1/analyze_format_shortcuts.py` |
| Dữ liệu `format_shift_v1` | `python -m training.evaluation.format_shift` |
| Notebook Colab | `python training/colab/build_format_shift_notebook.py` |
| Chấm điểm | `python -m training.evaluation.evaluate_format_shift --base ... --adapter-stage1 ... --pointer-stage2 ...` |
| Kiểm thử | `python -m unittest training/tests/test_format_shift.py` |
