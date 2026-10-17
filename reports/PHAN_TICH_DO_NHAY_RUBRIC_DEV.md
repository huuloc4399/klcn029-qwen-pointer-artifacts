# Phân tích độ nhạy rubric · FINAL_dev.jsonl

16 cặp, 8 CV; khoảng tin cậy 95% bootstrap theo CV. Chỉ báo cáo, không dùng để chỉnh rubric.

## 1. Từng tiêu chí so với mức phù hợp của người

| Tiêu chí | Trọng số | Spearman với mức phù hợp | KTC 95% |
|---|---|---|---|
| C1_structure | 10 | 0,27 | [-0,21; 0,54] |
| C2_it_content | 10 | 0,23 | [-0,28; 0,63] |
| C3_skills | 15 | 0,25 | [-0,33; 0,63] |
| C4_projects | 15 | 0,55 | [0,19; 0,87] |
| C5_experience | 10 | 0,43 | [0,01; 0,66] |
| C6_certs_activities | 5 | – | [–; –] |
| C7_ats | 10 | 0,04 | [-0,37; 0,51] |
| C8_jd_fit | 25 | 0,88 | [0,80; 0,96] |

## 2. Độ nhạy của trọng số

2000 bộ trọng số ngẫu nhiên quanh trọng số rubric (Dirichlet, độ tập trung 50) và vài bộ thay thế.

| Bộ trọng số | Spearman với tổng theo rubric | Spearman tổng với mức phù hợp |
|---|---|---|
| rubric | 1,00 | 0,76 |
| equal | 0,98 | 0,69 |
| c8_doubled | 0,99 | 0,78 |
| no_c8 | 0,91 | 0,52 |
| ngẫu nhiên (5% / trung vị / 95%) | 0,95 / 0,98 / 1,00 | 0,67 / 0,74 / 0,80 |

Thứ tự chiến lược theo Spearman điểm tổng với người (trọng số rubric): m1_zero_shot > baseline_rules > p_grounded > m2_few_shot > m4_multi_agent > m3_rag. Giữ nguyên thứ tự ở 1% bộ trọng số ngẫu nhiên; giữ chiến lược đứng đầu ở 43%.

| Chiến lược | rubric | equal | c8_doubled | no_c8 |
|---|---|---|---|---|
| m1_zero_shot | 0,85 | 0,86 | 0,86 | 0,75 |
| baseline_rules | 0,84 | 0,73 | 0,78 | 0,71 |
| p_grounded | 0,84 | 0,73 | 0,94 | 0,52 |
| m2_few_shot | 0,81 | 0,82 | 0,79 | 0,77 |
| m4_multi_agent | 0,81 | 0,77 | 0,80 | 0,71 |
| m3_rag | 0,80 | 0,80 | 0,76 | 0,70 |

## 3. Độ nhạy của luật C8

| Biến thể | Số cặp đổi C8 | Đổi trung bình (mức) | Spearman C8 với mức phù hợp |
|---|---|---|---|
| rubric | 0 | 0,00 | 0,88 |
| edges_minus_0.05 | 4 | 0,25 | 0,81 |
| edges_plus_0.05 | 6 | 0,38 | 0,84 |
| mentioned_only_0.25 | 4 | 0,25 | 0,85 |
| mentioned_only_0.75 | 2 | 0,12 | 0,84 |
| mentioned_only_1.0 | 5 | 0,31 | 0,83 |
| mentioned_only_0 | 5 | 0,31 | 0,83 |

## Diễn giải (17/10/2026)

- Chạy bằng `python -m downstream.eval.sensitivity --labels downstream/data/labels_v1/FINAL_dev.jsonl --run-id dev_v2`; code và test ở `downstream/eval/sensitivity.py`. Mọi số liệu tính trên nhãn người (FINAL dev), chỉ để báo cáo, không dùng để chỉnh rubric.
- **Trọng số C8 = 25 có minh chứng dữ liệu:** C8 là tiêu chí gắn chặt nhất với mức phù hợp do người đánh giá (Spearman 0,88 [0,80; 0,96]). Bỏ C8 làm tương quan điểm tổng với mức phù hợp giảm từ 0,76 xuống 0,52.
- **Thứ hạng CV hầu như không phụ thuộc con số trọng số cụ thể:** với 2000 bộ trọng số ngẫu nhiên quanh rubric, Spearman giữa điểm tổng mới và điểm tổng theo rubric có trung vị 0,98 (5%: 0,95); trọng số bằng nhau cho 0,98. Câu hỏi "vì sao 15 mà không phải 10" ít ảnh hưởng tới kết luận.
- **C1, C2, C3, C7 tương quan yếu với mức phù hợp.** Điều này đúng thiết kế: các tiêu chí này đo chất lượng CV, không đo độ khớp với JD (C7 là khả năng máy đọc). Vì vậy tương quan với mức phù hợp chỉ là minh chứng cho trọng số của C8, chưa phải cho các tiêu chí khác.
- **Thứ tự các chiến lược không ổn định khi đổi trọng số** (giữ nguyên ở 1% bộ trọng số, giữ chiến lược đứng đầu ở 43%), vì Spearman của chúng chỉ chênh nhau 0,80–0,85. Điều này khớp với việc mọi khoảng tin cậy của chênh lệch đều chứa 0 trên dev. Kết luận so sánh phải dựa vào tập test và khoảng tin cậy, không dựa vào thứ hạng.
- **Thăm dò (không dùng để chọn cấu hình):** P phụ thuộc vào C8 nhiều hơn các chiến lược khác. Tương quan tổng của P là 0,94 khi nhân đôi C8 và 0,52 khi bỏ C8, vì C8 của P được tính từ các yêu cầu đã kiểm chứng.
- **Luật C8 hiện tại không nhạy với cách chọn ngưỡng:** dời ngưỡng ±0,05 hoặc đổi hệ số `mentioned_only` (0; 0,25; 0,75; 1) làm 2–6/16 cặp đổi C8, trung bình 0,1–0,4 mức. Spearman với mức phù hợp nằm trong 0,81–0,85, so với 0,88 của luật hiện tại. Luật hiện tại đã cố định từ trước; số liệu chỉ cho thấy nó không kém các phương án gần.
- **Giới hạn:** chỉ 8 CV; chạy lại trên tập test khi có nhãn FINAL test.
