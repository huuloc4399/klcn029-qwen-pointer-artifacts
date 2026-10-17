# Phân tích lỗi trích xuất GOLD40 và bước tiếp theo

Nguồn: kết quả offline tại `training/evaluation/results/gold40_p0_vs_p1_v1/`. Gold giữ nguyên
trong toàn bộ quá trình đo. Mô-đun đánh giá ở đây kết thúc tại CVSchema 2.0.

## Kết luận có thể viết trong báo cáo

Trên GOLD40 hậu kiểm gồm 20 CV tiếng Anh và 20 CV tiếng Việt, cấu hình kiểm chứng và retry
P1 nâng tỷ lệ output CVSchema hợp lệ từ 85,00% lên 97,50%, đồng thời tăng normalized exact
Field Micro F1 từ 49,66% lên 52,81%. Cải thiện chủ yếu đi cùng việc khôi phục 5 output bị
từ chối ở P0. Recall tăng từ 42,89% lên 48,54%, precision giảm từ 58,97% xuống 57,89%.
Chi phí gọi model tăng từ 40 lên 46 lần, thời gian sinh đã ghi tăng 17,22%. P1 chưa cải
thiện mọi tiêu chí: Long Text F1 giảm từ 17,39% xuống 16,60% và Document exact vẫn 0/40.

Kết quả này hỗ trợ lợi ích về độ hợp lệ cấu trúc và mức khớp trường tổng hợp của cấu hình
P1 trên tập đã đo. Nó chưa chứng minh lợi ích trên tập độc lập, ưu thế hơn B0/B1 trên CV
thật, hoặc chất lượng so khớp/chấm điểm/sinh gợi ý của hệ thống tổng thể.

## Những nhóm lỗi cụ thể

| Nhóm | Dẫn chứng trong kết quả P1 | Diễn giải |
|---|---|---|
| Output thiếu khóa | VI006: thiếu `skills.soft_skills`, parser từ chối | Một mẫu vẫn không bàn giao được sau retry. Không thêm khóa tự động để tăng điểm. |
| Kỹ năng chưa tách thành đơn vị | VI017 sinh `ngôn ngữ lập trình: c/c++`, `cơ sở dữ liệu: sqlite`, `kiến thức: oop` | Thông tin có thể gần đúng nhưng khác đơn vị nhãn; cần dạy model bỏ tiêu đề nhóm và trả mỗi kỹ năng riêng. Không sửa metric sau khi thấy lỗi. |
| Thiếu kỹ năng trong gold | `skills.hard_skills`: 394 FN, 171 FP, F1 38,25% | Đếm strict theo trường; không đồng nghĩa 394 sự thật bị mất hoàn toàn vì một phần có thể nằm trong mục công nghệ hoặc chuỗi gộp. |
| Span summary mất đoạn đầu | EN001: output bắt đầu `analytical thinking...`, gold bắt đầu `Seeking a Business Analyst internship opportunity...` | Span hợp lệ về chỉ số vẫn có thể chọn sai ranh giới nội dung. |
| Span dự án chứa nội dung không thuộc details | EN001 lấy thêm dòng `Technologies`; VI017 lấy thêm tiêu đề dự án tiếp theo | Pointer chỉ bảo đảm dựng nguyên văn của span đã chọn, không xác nhận span là đúng trường. |
| Sai khác cách thể hiện | EN001 details có dấu bullet; VI017 gold có dấu chấm và mô tả ngắn hơn span | Exact match phạt khác dấu câu hoặc mức đầy đủ. Cần đọc PDF để phân biệt lỗi model và quy tắc nhãn; không tự sửa gold theo prediction. |
| CV ảnh/OCR | EN047: hard skills có chuỗi `backend_and_apis: ...`, summary bị thiếu | Cần kiểm tra lại nguồn text và thứ tự đọc của CV ảnh trước khi quy nguyên nhân cho model. Chỉ có một CV OCR trong GOLD40. |

Các trường P1 có nhiều FN nhất: hard skills (394), project technologies (113), project
details (92), soft skills (35), summary (30), project name (29). Có thể ưu tiên rà mẫu
đại diện ở những trường này thay vì tăng epoch ngay.

## Việc làm tiếp theo theo thứ tự

1. **Hoàn thiện đối chứng B0/B1 trên đúng GOLD40.** Dùng cùng text nguồn/hash PDF và greedy
   decoding, giữ parser/metric đã khóa. B0 là Qwen gốc, B1 là adapter Full JSON giai đoạn 1.
   Chưa có artifact của hai cấu hình trên GOLD40; kết quả synthetic test không thay thế được.
2. **Giữ bản đo P0/P1 v1 làm mốc.** Không sửa các file gold/model output hoặc metric để tăng
   điểm hiện tại. Nếu phát hiện lỗi nhãn qua PDF, lập bản gold mới và chấm lại mọi cấu hình.
3. **Rà nguồn text và nguyên tắc gán nhãn trên một nhóm mẫu.** Ưu tiên EN047 (ảnh), EN001
   (summary/details), VI017 (tiêu đề kỹ năng/ràng giới span). Kiểm tra cả nguồn và gold;
   không xem prediction như căn cứ để điền sự thật CV. Các cảnh báo nhãn cũ về năm tốt
   nghiệp vẫn cần được đối chiếu với quyết định nguồn khi diễn giải field F1 học vấn.
4. **Thử cải thiện có phiên bản sau khi đối chứng đủ.** Hướng ít tốn chi phí là ràng buộc
   danh sách kỹ năng ở đơn vị riêng và hướng dẫn ranh giới span bằng dữ liệu có bằng chứng.
   Việc dùng GOLD40 để chọn prompt/model làm nó thành tập phát triển hậu kiểm; cần tập
   mới chưa dùng để xác nhận khả năng tổng quát. Không đổi parser v1 ngầm.
5. **Cô lập ngân sách token nếu muốn khẳng định tác động của validator.** P0 hiện giới hạn
   768 token, retry P1 là 1.280. Đối chứng cùng ngân sách hoặc retry không nhắm lỗi cần
   thực nghiệm riêng; chưa coi lợi ích hiện tại là hiệu ứng thuần của validator.

Không cần huấn luyện thêm để hoàn thành bước 1. Các bước thay đổi model/prompt nằm sau khi
đã có đối chứng và sau quyết định của nhóm về giới hạn thời gian. Phần matching, chấm điểm
và gợi ý vẫn được đánh giá riêng bởi thành viên phụ trách.

## Chạy lại đánh giá offline

```powershell
python -m training.evaluation.evaluate_gold40
```

Đầu vào mặc định là ZIP raw P0/P1 real80, input Pointer đã đóng băng và manifest GOLD40 hoàn
tất. Lệnh không gọi model, không gửi CV lên mạng và không sửa nhãn. Output có metric theo
ngôn ngữ/trường/CV, bootstrap ghép cặp, chi phí sinh và hash để tái lập.
