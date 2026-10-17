# Xây dựng tập nhãn chuẩn cho bài toán đánh giá cặp CV–JD

> Bản nháp để đưa vào chương Phương pháp (mục gợi ý: 3.x). Số liệu tính đến ngày 17/10/2026. Các ô **[…]** cần nhóm điền hoặc xác nhận; phần số liệu vòng chính sẽ cập nhật sau khi hai người chấm nộp (hạn 20/10/2026).

## 1. Mục tiêu

Để đánh giá các phương pháp chấm CV tự động (bộ luật, M1–M4 và phương pháp đề xuất P), nhóm cần một tập nhãn do người chấm theo cùng bộ tiêu chí mà máy dùng. Tập nhãn phải đủ tin cậy để so sánh máy với người. Vì vậy quy trình được thiết kế để: (i) hai người chấm độc lập trên cùng một tập cặp; (ii) đo độ đồng thuận giữa hai người trước khi dùng nhãn; (iii) hợp nhất bất đồng bằng một quy trình phân xử có ghi vết.

## 2. Tập cặp CV–JD

Tập cặp gồm 24 CV và 12 JD, tạo thành 48 cặp (Bảng X.1).

- **CV** lấy từ tập GOLD40, chỉ giữ CV thuộc các hướng backend, fullstack, frontend và mobile. Mỗi CV trong GOLD40 đã có CVSchema gán nhãn tay, nên mọi phương pháp chấm đều chạy được trên hai loại đầu vào: CVSchema chuẩn và CVSchema do mô hình trích xuất.
- **Ghép cặp:** mỗi CV ghép với hai JD, một JD cùng hướng và một JD khác hướng, để mức phù hợp trải từ thấp đến cao. JD cùng hướng được chọn theo mức trùng kỹ năng cao nhất với CV.
- **JD:** mỗi JD được tách thành các yêu cầu nguyên tử, gồm yêu cầu bắt buộc (must) và yêu cầu ưu tiên (nice).
- **Chia tập theo CV:** tập phát triển (dev) có 8 CV, 16 cặp, dùng để chấm thử, hiệu chỉnh hướng dẫn và chọn cấu hình phương pháp. Tập kiểm tra (test) có 16 CV, 32 cặp, chỉ dùng một lần để báo cáo kết quả cuối. Việc chia tập được phân tầng theo hướng và ngôn ngữ CV. Hai cặp của cùng một CV luôn nằm trong cùng một tập.

**Bảng X.1. Tập cặp CV–JD**

| Tập | Số CV (EN/VI) | Số cặp | Cùng hướng / khác hướng | Số JD dùng |
|---|---|---|---|---|
| dev | 8 (5/3) | 16 | 10 / 6 | 9 |
| test | 16 (9/7) | 32 | 19 / 13 | 12 |
| Tổng | 24 | 48 | 29 / 19 | 12 |

## 3. Đơn vị và nội dung gán nhãn

Với mỗi cặp, người chấm gán bốn loại nhãn theo rubric v2 (`rubric_v2_draft1`):

1. **Trạng thái từng yêu cầu của JD:**
   - `met`: có bằng chứng sử dụng trong dự án, kinh nghiệm hoặc chứng chỉ;
   - `mentioned_only`: CV chỉ liệt kê ở mục kỹ năng hoặc giới thiệu;
   - `missing`: không có;
   - `unclear`: có nội dung liên quan nhưng không đủ để khẳng định.

   Với `met` và `mentioned_only`, người chấm chép nguyên văn đoạn trích và ghi mục chứa đoạn đó.
2. **Điểm 0–4 cho 8 tiêu chí** (Bảng X.2), kèm trạng thái của tiêu chí:
   - `scored`: chấm điểm bình thường;
   - `missing_in_cv`: CV không có nội dung cho tiêu chí, tính 0 điểm;
   - `not_applicable`: tiêu chí không áp dụng;
   - `unreadable`: không đọc được phần liên quan.

   Mỗi điểm từ 1 trở lên phải có trích dẫn và lý do.
3. **Điểm C8 (mức phù hợp với JD):** không chấm cảm tính mà suy ra từ trạng thái các yêu cầu.
   - Tính tỉ lệ (met + 0,5 × mentioned_only) / số yêu cầu bắt buộc, không tính các yêu cầu `unclear`.
   - Quy tỉ lệ thành mức 0–4 theo các ngưỡng 0,2 / 0,4 / 0,6 / 0,8.
   - Mức 4 cần đạt thêm ít nhất một yêu cầu ưu tiên.
4. **Mức phù hợp tổng thể 1–5** và tối đa ba gợi ý sửa CV.

Điểm tổng 0–100 của một cặp được tính bằng 100 · Σ wᵢsᵢ / (4 Σ wᵢ), trong đó sᵢ là điểm và wᵢ là trọng số của tiêu chí i, chỉ lấy các tiêu chí chấm được.

**Bảng X.2. Tiêu chí và trọng số của rubric v2**

| Mã | Tiêu chí | Trọng số |
|---|---|---|
| C1 | Cấu trúc và hình thức trình bày | 10 |
| C2 | Nội dung chuyên môn phù hợp lĩnh vực CNTT | 10 |
| C3 | Kỹ năng chuyên môn và kỹ năng bổ trợ | 15 |
| C4 | Chất lượng mô tả dự án | 15 |
| C5 | Kinh nghiệm làm việc hoặc thực tập | 10 |
| C6 | Chứng chỉ, thành tích và hoạt động liên quan | 5 |
| C7 | Khả năng đáp ứng ATS (máy đọc được) | 10 |
| C8 | Mức phù hợp với JD | 25 |

## 4. Công cụ và kiểm soát chất lượng

Mỗi người chấm nhận một gói riêng gồm: file Excel chấm điểm, PDF gốc của các CV và tài liệu hướng dẫn.

- **File Excel:**
  - Có danh sách chọn cho mọi trường, công thức kiểm tra từng dòng và sheet theo dõi tiến độ.
  - Cấu trúc sheet bị khóa, để người chấm không xóa hay đổi thứ tự dòng.
  - Ẩn mức phù hợp dự kiến của cặp (cùng hướng / khác hướng) để người chấm không bị định hướng.
- **Khi nhận lại:** một script đọc lại toàn bộ file, kiểm tra các lỗi Excel không chặn được (giá trị dán đè danh sách chọn, dòng bị xóa, rubric sai phiên bản) rồi xuất ra JSONL.
- **Tính độc lập:**
  - Hai người chấm làm riêng và không trao đổi nhãn.
  - Danh sách bất đồng chỉ đưa cho người phân xử.
  - Các cập nhật hướng dẫn chỉ nêu xu hướng chung, không nêu quyết định của từng người trên cặp cụ thể.
- **Bảo vệ dữ liệu:** gói chứa CV có thông tin cá nhân nên chỉ gửi qua kênh riêng của nhóm. File nhãn và danh sách bất đồng không đưa lên kho mã. Thông tin cá nhân được che trước khi gửi CV cho mô hình ngôn ngữ.

Hai người chấm A và B là **[mô tả: thành viên nhóm / sinh viên CNTT năm …]**. Người phân xử là **[tên, và ghi rõ có phải người thứ ba, không trùng A hay B]**.

## 5. Quy trình

Quy trình gồm bốn bước: chấm thử, hiệu chỉnh hướng dẫn, phân xử, chấm vòng chính **[có thể vẽ thành Hình X.1]**.

**Bước 1 — Vòng chấm thử (16 cặp dev).**
- A và B chấm độc lập theo hướng dẫn bản 1, mỗi cặp mất trung bình khoảng 11 phút.
- Độ đồng thuận ban đầu ở mức khá: kappa bậc hai gộp 8 tiêu chí 0,69 (KTC 95% [0,55; 0,83]).
- Phân tích cho thấy ba vấn đề:
  1. Hiệu ứng trần: một người cho mức 4 ở phần lớn CV tại C1, C2, C3 và C7, nên kappa ở các tiêu chí này gần 0.
  2. C7 được chấm bằng cảm nhận về bố cục thay vì kiểm tra khả năng máy đọc (kappa 0,30).
  3. Trạng thái yêu cầu JD lệch nhiều (kappa 0,41). Phần lớn do bỏ sót khi đọc, hoặc hiểu khác nhau với các yêu cầu là khái niệm (Responsive, OOP) thay vì tên công nghệ. Không người chấm nào dùng `unclear`.

**Bước 2 — Hiệu chỉnh hướng dẫn (bản 2).**
- Bổ sung nguyên tắc chấm từ dưới lên, và danh sách kiểm tra đánh số cho C1, C2, C3, C7.
  - C7 bắt buộc thử chép văn bản PDF sang Notepad để kiểm tra thứ tự đọc.
- Bổ sung quy tắc tìm kiếm (Ctrl+F) trước khi chọn `missing`.
- Người chấm A chấm lại 16 cặp sau khi đọc bản 2 mà không xem nhãn của B. Điều này đã được điều phối viên xác nhận.
- Kết quả: kappa gộp tăng lên 0,82 [0,75; 0,89]. Các tiêu chí tăng rõ: C3 từ 0,00 lên 0,76, C7 từ 0,30 lên 0,81 (Bảng X.3).
- Hai bên không cân xứng: A chấm theo bản 2, B theo bản 1, và bản 2 được viết sau khi đã thấy kết quả vòng thử. Vì vậy con số này chỉ cho thấy bước hiệu chỉnh có tác dụng. Nó **không** được dùng làm độ đồng thuận chính thức của rubric.

**Bước 3 — Phân xử và hợp nhất thành nhãn FINAL cho tập dev.** Người phân xử đọc PDF gốc và xử lý bất đồng trong ba vòng (Bảng X.4).
- **Vòng 1:** các bất đồng lớn, gồm điểm lệch từ 2 trở lên, `met` so với `missing`, và mức phù hợp lệch từ 2 trở lên.
- **Vòng 2:** các bất đồng về trạng thái yêu cầu còn lại. Loại này không lấy trung bình được.
- **Vòng 3:** rà lại tính nhất quán của các quyết định theo quy tắc trong hướng dẫn. Danh sách rà được lập bán tự động:
  - tìm từ khóa của yêu cầu trong lớp chữ của PDF và trong CVSchema chuẩn;
  - kiểm tra link GitHub gắn trong PDF;
  - so sánh nhãn của cùng một CV giữa hai cặp.

  Công cụ AI hỗ trợ lập danh sách và đề xuất quy tắc áp dụng cho từng dòng **[ghi theo quy định của khoa về việc dùng công cụ AI]**. Người phân xử quyết định từng dòng.

Các nhãn được hợp nhất theo luật cố định:
- hai người đồng ý thì giữ;
- có quyết định phân xử thì theo quyết định, vòng sau ghi đè vòng trước;
- điểm tiêu chí hoặc mức phù hợp lệch đúng 1 thì lấy trung bình (cho phép giá trị x,5);
- C8 tính lại từ trạng thái yêu cầu sau phân xử theo công thức ở mục 3.

Script hợp nhất dừng nếu còn ô chưa có quyết định. Nó cũng cảnh báo khi một tiêu chí không phụ thuộc JD (C1, C2, C3, C6, C7) có điểm khác nhau giữa hai cặp của cùng một CV. Các quy tắc mới được chốt trong lúc phân xử, chẳng hạn chỉ có công nghệ nền thì chọn `unclear`, được đưa vào hướng dẫn bản 3.

**Bước 4 — Vòng chính (32 cặp test).** A và B chấm độc lập theo hướng dẫn bản 3, hạn nộp 20/10/2026. Đây là lần đầu hai người dùng cùng một bản hướng dẫn, nên độ đồng thuận đo ở vòng này là số liệu chính thức. Bất đồng ở tập test được phân xử theo đúng quy trình của bước 3 **[cập nhật số liệu sau khi có]**.

## 6. Đo độ đồng thuận

- **Điểm tiêu chí:** kappa có trọng số bậc hai (QWK), tính cho từng tiêu chí và gộp 8 tiêu chí. Kèm theo tỉ lệ trùng khớp, tỉ lệ lệch không quá 1 và MAE.
- **Trạng thái tiêu chí và trạng thái yêu cầu:** kappa Cohen. Riêng yêu cầu còn tính thêm kappa trên nhãn hai lớp "có trong CV" (gồm `met` và `mentioned_only`) và "không có".
- **Mức phù hợp và điểm tổng:** hệ số Spearman.
- **Khoảng tin cậy 95%:** bootstrap 2000 lần, lấy mẫu lại theo CV, vì hai cặp của cùng một CV không độc lập với nhau.
- **Mức diễn giải kappa:** theo Landis và Koch (1977) **[kiểm tra trích dẫn]**.

**Bảng X.3. Độ đồng thuận giữa hai người chấm ở vòng chấm thử (16 cặp dev)**

| Chỉ số | A bản 1 – B | A bản 2 – B |
|---|---|---|
| QWK gộp 8 tiêu chí [KTC 95%] | 0,69 [0,55; 0,83] | 0,82 [0,75; 0,89] |
| QWK C1 / C2 / C3 | 0,00 / 0,00 / 0,00 | 0,25 / 0,33 / 0,76 |
| QWK C4 / C5 | 0,67 / 0,93 | 0,67 / 0,93 |
| QWK C7 / C8 | 0,30 / 0,58 | 0,81 / 0,47 |
| Kappa trạng thái tiêu chí | 0,90 | 0,90 |
| Kappa trạng thái yêu cầu (205 yêu cầu) | 0,41 [0,31; 0,50] | 0,40 [0,31; 0,47] |
| — yêu cầu là tên công nghệ (94) / khái niệm (111) | – | 0,46 / 0,33 |
| Spearman mức phù hợp | 0,54 [0,02; 0,86] | 0,60 [0,19; 0,86] |
| Spearman điểm tổng | 0,72 [0,30; 0,95] | 0,74 [0,28; 0,97] |
| Điểm tổng trung bình A / B | 69,1 / 59,1 | 54,9 / 59,3 |
| Số mục cần phân xử (vòng 1) | 61 | 46 |

C6 không tính được kappa vì cả hai người cho cùng một mức ở mọi cặp.

**Bảng X.4. Phân xử và nhãn FINAL của tập dev**

| Vòng | Số dòng | Nội dung |
|---|---|---|
| 1 | 46 | 36 yêu cầu `met` so với `missing`; 8 điểm lệch từ 2 trở lên; 2 mức phù hợp lệch 2 |
| 2 | 35 | 19 yêu cầu `met` so với `mentioned_only`; 16 yêu cầu `mentioned_only` so với `missing` |
| 3 | 20 | Rà tính nhất quán theo quy tắc: 18 quyết định vòng 1–2 và 2 nhãn mà hai người đồng ý nhưng trái quy tắc |

Kết quả hợp nhất:
- **Nguồn của từng ô:** 206 ô hai người đồng ý, 79 ô theo quyết định phân xử, 45 ô lấy trung bình, 16 ô C8 tính lại từ yêu cầu.
- **Trạng thái 205 yêu cầu:** `met` 62, `mentioned_only` 19, `missing` 114, `unclear` 10.
- **Điểm tổng trung bình:** A 54,9; B 59,3; FINAL 57,5.

## 7. Hạn chế

- **Tập dev nhỏ:** 8 CV, nên khoảng tin cậy rộng. Kết luận về độ đồng thuận lấy từ vòng chính.
- **Hướng dẫn được hiệu chỉnh trên chính tập dev:** cấu hình phương pháp cũng được chọn trên tập này, nên tập test được giữ riêng và chỉ dùng một lần.
- **Bộ luật cơ sở được viết sau khi đã thấy nhãn vòng thử,** nên kết quả của bộ luật trên tập dev có thể lạc quan.
- **Hướng dẫn cho người chấm có nhiều ví dụ hơn prompt của mô hình:** các quy tắc mới ở bản 3 không đưa vào prompt, để giữ cấu hình đã chạy trên tập dev. Đổi lại, bước kiểm tra yêu cầu khái niệm trong code của P thực hiện cùng nguyên tắc.
- **Độ đồng thuận về trạng thái yêu cầu** còn ở mức trung bình (0,40), thấp nhất ở các yêu cầu là khái niệm (0,33). Đây cũng là phần khó nhất với phương pháp tự động.
