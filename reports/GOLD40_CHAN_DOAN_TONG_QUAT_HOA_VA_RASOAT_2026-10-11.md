# Rà GOLD40 và chẩn đoán khả năng áp dụng mô hình lên CV thật

Ngày: 11/10/2026. Phạm vi: mô đun **trích xuất CV**; không đánh giá matching CV–JD, chấm điểm hoặc chất lượng gợi ý sửa của các mô đun khác.

## 1. Kết luận hiện tại

**Đánh giá trên CV thật phù hợp và cần thiết cho mục tiêu ứng dụng. Kết quả hiện tại cho thấy mô hình sau fine-tune chưa chuyển tốt từ bộ tổng hợp sang CV thật. Chưa có đủ bằng chứng kết luận nguyên nhân chính là overfitting hoặc gold sai.** Có bằng chứng trực tiếp về lệch phạm vi nhãn, thiếu độ phủ dữ liệu train, kỹ năng bị gộp và lỗi cấu trúc output.

40 CV là tập đánh giá nhỏ, làm kết quả kém chắc chắn và hạn chế đại diện. Kích thước **tập test** không trực tiếp gây overfitting; overfitting liên quan đến cách học, dữ liệu train và lựa chọn cấu hình. Nếu dùng kết quả test nhiều lần để sửa prompt/model thì có thể thích nghi vào tập test, cần công bố việc đó và dùng một tập mới để xác nhận. Tài liệu [scikit-learn về validation/learning curves](https://scikit-learn.org/stable/modules/learning_curve.html) giải thích dấu hiệu train tốt nhưng validation kém và việc cần test riêng sau lựa chọn cấu hình.

Không điều chỉnh gold để khớp model. Mỗi sửa nhãn phải có PDF, quy tắc và biên bản phân xử làm căn cứ. Các đề nghị trong giao diện chưa phải nhãn được chấp nhận.

## 2. Bằng chứng định lượng

Đã đọc lại output B0/B1/P0/P1 đã đóng băng, kiểm tra manifest của kết quả, hash gold và dữ liệu train/validation/test. Không gọi model, không thay parser/metric hoặc gold. Chi tiết có trong `training/audits/gold40_generalization_2026-10-11_v2/diagnostics.json`, script kèm theo và manifest.

### 2.1. Khác biệt giữa dữ liệu tổng hợp và dữ liệu thật

| Cấu hình | Validation tổng hợp: Field Micro F1 | Test tổng hợp: Field Micro F1 | GOLD40 thật: Field Micro F1 | Schema hợp lệ trên GOLD40 |
|---|---:|---:|---:|---:|
| B0: Qwen gốc, Full JSON | 88,06% | 87,98% | **65,52%** | 40/40 |
| B1: stage 1 fine-tune, Full JSON | 99,60% | 99,52% | **48,28%** | 35/40 |
| P0: stage 2 Hybrid Pointer | 99,64% | 99,19% | **49,66%** | 34/40 |
| P1: P0 + kiểm chứng/retry | Chưa chạy P1 trên tập này | Chưa chạy P1 trên tập này | **52,81%** | 39/40 |

Các con số trong một cột dùng cùng bộ nhãn/định nghĩa metric của bộ tương ứng. Hai bộ có khác phạm vi nhãn nên chênh lệch tổng hợp–thật không phải thí nghiệm chỉ thay miền đầu vào. Nó phản ánh đồng thời khác dữ liệu, bố cục, ngôn ngữ và quy tắc gán nhãn. Không kết luận causal từ bảng này.

P1 cải thiện so với P0 trên nhóm hiện có, nhưng chưa vượt B0. Khoảng bootstrap ghép cặp B1−B0: −17,24 điểm phần trăm, CI 95% [−22,58; −11,75]. P1−P0: +3,14 điểm, CI [0,79; 6,77]. P0−B1: +1,38 điểm, CI [−4,32; 6,79], chưa có bằng chứng rõ về cải thiện F1. Những khoảng này giữ cố định nhãn và lấy mẫu lại trong nhóm CV đã có; không bao gồm sai số nhãn hoặc thiên lệch chọn CV.

### 2.2. 40 CV làm ước lượng bất định đến mức nào?

Bootstrap 5.000 lần, seed 42, lấy lại **toàn CV**, phân tầng 20 EN/20 VI:

| Cấu hình | F1 điểm | Khoảng percentile 95% |
|---|---:|---:|
| B0 | 65,52% | 61,03–69,51% |
| B1 | 48,28% | 42,27–53,76% |
| P0 | 49,66% | 42,68–55,48% |
| P1 | 52,81% | 47,52–57,51% |

Không coi 1.541 giá trị gold là 1.541 mẫu độc lập: nhiều giá trị cùng thuộc một CV. Khoảng ghép cặp có ý nghĩa hơn so với nhìn hai khoảng riêng để so sánh model. Tăng số CV giúp tăng độ phủ và độ chính xác của ước lượng; không tự làm model tốt hơn nếu chỉ tăng tập test. GOLD40 cân bằng ngôn ngữ nhưng bộ 80 gốc là 60 EN/20 VI, vì vậy tổng F1 GOLD40 không đại diện trực tiếp cho tỷ lệ sử dụng thật. Cần luôn báo cáo riêng EN/VI.

## 3. Nguyên nhân và mức độ bằng chứng

### 3.1. Lệch quy tắc giữa nhãn train và nhãn gold — bằng chứng mạnh

Đọc `training/prepare_external_dataset.py`, hàm `convert_ground_truth`: `hard_skills` lấy từ danh sách `source.skills`; `projects.used_technologies` được đưa sang `projects.technologies` nhưng không hợp vào hard skills. Không đưa Languages vào nhãn kỹ năng. Hướng dẫn gold hiện tại yêu cầu lấy kỹ năng tường minh ở các vùng phù hợp trong CV, gồm công nghệ dự án và ngoại ngữ có mức độ.

- Train có 544 CV có công nghệ dự án; **543/544** có ít nhất một công nghệ dự án không xuất hiện nguyên giá trị trong `hard_skills` target.
- Cả **850/850** nguồn train có tiêu đề Languages, nhưng converter không chuyển danh sách ngoại ngữ vào nhãn kỹ năng.
- Ví dụ `rpv_r00001`: Azure, Docker Swarm, Python có trong `projects.technologies` nhưng không ở `hard_skills` target.

Đây là chênh lệch định nghĩa/phạm vi, không chỉ đổi tên các khóa JSON. Có thể model học đúng cách chuyển nhãn bộ tổng hợp rồi bị chấm thiếu theo quy tắc gold. Con số 543 dùng so khớp nguyên giá trị sau chuẩn hóa; synonym hoặc biểu diễn khác có thể làm số này cao hơn chênh lệch ngữ nghĩa thực tế. Converter là bằng chứng chắc chắn về phạm vi chuyển đổi. Khi sửa cần tạo phiên bản dataset mới, giữ dataset cũ để truy vết.

### 3.2. Thiếu độ phủ train — bằng chứng mạnh

| Đặc điểm | Train (850) | GOLD40 |
|---|---:|---:|
| CV tiếng Việt | 0 | 20 |
| Nhãn GitHub có giá trị | 0 | 30 |
| Nhãn GPA có giá trị | 0 | 28 |
| Nhãn activities có giá trị | 0 | 6 |
| Nhãn awards có giá trị | 0 | 2 |
| Soft skills target | Chỉ Communication, có ở 459 CV | Nhiều kỹ năng theo nguồn |

Train có ba template sidebar/two_column/classic (271/267/312); tất cả là CV tổng hợp EN. Kiểm tra không thấy nguồn hoặc target trùng **hoàn toàn** giữa các split. Điều này không loại trừ gần trùng, dùng chung kiểu sinh/vốn từ hoặc phụ thuộc template.

Khả năng tiếng Việt của model gốc không bảo đảm adapter học EN sẽ giữ nguyên chất lượng trích xuất VI. Nhãn GPA/GitHub luôn rỗng cũng không chứng minh model sẽ không đọc được chúng: B1 vẫn có một số kết quả đúng nhờ kiến thức gốc. Tuy nhiên các trường đó chưa có ví dụ dương để học và validation tổng hợp chưa kiểm chứng năng lực trên chúng.

### 3.3. Gộp kỹ năng và exact match — bằng chứng trực tiếp, cần rà từng ca

B1 hard-skills F1 chỉ **13,69%**; B0 đạt **58,33%**. B1 có 518 FN của trường này. Ví dụ EN003: một phần output là `Programming: C#, JavaScript, Python`, trong khi gold dùng các mục kỹ năng riêng.

Script tìm thấy **304 cặp ứng viên trên 26 CV**: giá trị kỹ năng gold bị chấm thiếu xuất hiện bên trong một chuỗi kỹ năng B1 dài hơn theo regex ranh giới từ. Đây là danh sách phục vụ kiểm tra lỗi gộp, **không phải 304 kỹ năng đã xác nhận đúng**: C/C#/C++ hoặc cụm từ chứa nhau có thể tạo ứng viên giả. Không cộng điểm bằng substring và không thay metric chính.

Chẩn đoán bỏ riêng `skills.hard_skills` ra khỏi tổng: B0 F1 69,28%, B1 62,48%. Khoảng cách thu hẹp từ 17,24 xuống 6,80 điểm. Phép này định vị phần đóng góp của trường kỹ năng, không phải benchmark thay thế hoặc chứng minh phần còn lại tốt. CV invalid vẫn bị chấm lỗi.

Exact match của văn bản dài giữ dấu câu, dấu tiếng Việt và ranh giới nội dung. Thay dấu câu, dịch, bỏ kết quả dự án hoặc gộp nhiều vùng có thể làm cả chuỗi sai dù chứa nhiều thông tin đúng. Phải rà PDF để phân biệt lỗi trích xuất thực sự, nhãn sai và khác biểu diễn. Không được gọi F1 52,81% là “52,81% CV đúng”; đó là F1 trên tập giá trị theo trường, document exact hiện đều 0/40.

### 3.4. Lỗi cấu trúc output — bằng chứng trực tiếp

B1 có 5 CV invalid: EN012 lỗi JSON không phục hồi được; EN035 thiếu `skills.soft_skills`; VI006/VI008/VI010 xuất `activities` thành danh sách object thay vì danh sách string. Chúng đều kết thúc EOS; không có dấu hiệu chạm giới hạn token trong các kết quả B0/B1 này.

Trên 35 CV mà cả B0/B1 đều schema-valid: B0 F1 65,91%, B1 52,28%. Độ kém của B1 vẫn còn; lỗi JSON không giải thích toàn bộ. Đây là phân tích có điều kiện, không thay điểm chính trên đủ 40 CV. Schema hợp lệ cũng không đồng nghĩa nội dung đúng.

Các cảnh báo chính sách soft skills lịch sử được báo riêng, không chặn CV thật schema-valid khỏi đánh giá. Không tiếp tục áp quy tắc Communication-only cho nhãn CV thật.

### 3.5. OCR và gold — chưa được loại trừ hoàn toàn

Đầu vào cố định có 39 CV lấy embedded text, EN047 dùng PaddleOCR EN. Cả 20 CV VI dùng embedded text. Vì vậy không có căn cứ quy lỗi thấp của cả tập VI cho PaddleOCR tiếng Việt. Embedded text vẫn có thể sai thứ tự cột hoặc thiếu vùng; cần đối chiếu PDF với nguồn đã đưa vào model để phân tách lỗi lấy văn bản và lỗi model.

Gold đã hợp lệ schema và hoàn tất gate không chứng minh đúng nội dung toàn bộ. Các năm tốt nghiệp dự kiến, phân loại công việc/môn học, tách kỹ năng và phạm vi `projects.details` là điểm phải rà. Chưa có quyết định mới từ người rà, nên chưa báo tỷ lệ lỗi gold. Giữ lịch sử ba mẫu từng được trợ lý hỗ trợ và việc không giữ nhãn A/B trước phân xử; không suy dựng IAA lịch sử.

### 3.6. Có overfitting không?

Stage 1 eval loss qua các lần đã lưu: step 40 **0,01535** → 80 **0,01123** → 107 **0,01091**. Stage 2: **0,01583** → **0,01504** → **0,01488**. Validation/test tổng hợp đều F1 khoảng 99%; chưa thấy dấu hiệu loss validation cùng miền tăng về cuối run.

Train loss tổng 0,00295 của stage 1 không dùng một mình để kết luận: run có resume, loss tổng và loss cửa sổ/eval có thể khác phạm vi tích lũy. Token accuracy khoảng 99,95% cũng là metric token trong đánh giá với ngữ cảnh mục tiêu đã có, không tương đương F1 free generation trên CV mới; [tài liệu TRL SFT Trainer](https://huggingface.co/docs/trl/sft_trainer) mô tả loss trên token không mask và token accuracy.

**Chưa chứng minh overfitting theo số bước train; vẫn có khả năng quá chuyên biệt với cấu trúc/quy tắc tổng hợp hoặc giảm năng lực ngoài miền sau fine-tune.** Nghiên cứu [TAIA, Jiang và cộng sự](https://arxiv.org/abs/2405.20192) xem xét việc fine-tuning có thể làm giảm hiệu năng khi dữ liệu học và tác vụ đích lệch nhau. Đây là căn cứ cho giả thuyết và thiết kế kiểm chứng, không phải chứng minh Qwen của đề tài bị cùng cơ chế và không phải lý do triển khai TAIA ngay.

## 4. Giao diện và quy trình rà nhãn

Tool `gold_review_app` dùng Flask/Python, xem ảnh trang PDF, văn bản trang để sao chép, đọc gold, checklist 19 trường, vấn đề có trang/trích dẫn/lý do, bản JSON đề nghị tùy chọn, lưu nháp/lịch sử và xuất ZIP theo người rà. Hash gold/PDF/quy tắc được kiểm tra khi khởi động; không có nút ghi đè gold. Không đưa output model lên UI. Người rà tự khai tên và mức tiếp xúc với output; đây không phải danh tính được xác thực hoặc bảo đảm rà mù.

1. Khải và Đắc rà độc lập cùng 10 CV ưu tiên ★; người tổng hợp xem PDF để phân xử sau khi nhận cả hai lượt.
2. Giữ các đề nghị chưa rõ thành unresolved cho đến khi chốt quy tắc. Không mặc định ép thành nhãn rỗng. Đề nghị không đọc được cần vùng/trang và lý do.
3. Sau rà ưu tiên, rà 30 CV còn lại theo phân công. Nếu muốn đo đồng thuận mới trên cả bộ, phải có hai lượt độc lập cùng bộ; chia mỗi người một nửa không tạo được IAA toàn bộ.
4. Lập gold v2 và changelog riêng sau xét đề nghị. Chấm lại **cùng output cố định** trên gold v1/v2 để đo ảnh hưởng nhãn, không chạy lại model ở bước này. Báo cả hai kết quả và lý do sửa.

Bộ 10 gồm ca chẩn đoán và ngẫu nhiên có seed; không suy rộng tỷ lệ lỗi của bộ này thành tỷ lệ chất lượng GOLD40.

## 5. Bước cải thiện phù hợp tiến độ

| Ưu tiên | Việc cần làm | Lý do / kiểm chứng | Có cần GPU? |
|---|---|---|---|
| 1 | Rà gold + nguồn văn bản từ PDF | Tách lỗi nhãn và lỗi input trước khi train lại | Không |
| 2 | Thống nhất đơn vị/phạm vi nhãn, prompt và converter | Khắc phục lệch kỹ năng dự án, ngoại ngữ, tách mục, năm dự kiến | Không |
| 3 | Chuẩn bị dataset v2: thêm ví dụ dương trường trống, đa dạng kỹ năng, VI và cách viết CV thực tế | Không chỉ tăng số mẫu tổng hợp theo mẫu cũ; kiểm tra nguồn và chứng cứ cho từng nhãn | Không ở khâu chuẩn bị |
| 4 | Sửa prompt tách kỹ năng, định dạng activities và ranh giới spans trên bộ dev mới | Thử chi phí thấp, tách thay đổi prompt khỏi thay đổi adapter | Có, chỉ inference |
| 5 | Train run ngắn với dữ liệu đã thống nhất; so checkpoint sớm/cuối trên dev thật độc lập | Nếu checkpoint cuối kém hơn sớm trên cùng dev mới mới có thêm bằng chứng cho over-training | Có |
| 6 | Xác nhận bằng nhóm CV thật mới, khóa trước sửa model/prompt | GOLD40 đã được nghiên cứu để đề xuất cải thiện nên không tiếp tục gọi là test hoàn toàn chưa thấy | Có, sau khi chốt |

Không dùng GOLD40 để train rồi báo lại chính nó là test. 40 CV còn lại của real80 đã có output được phân tích ở mức pipeline; nếu dùng chúng làm dev, phải ghi mức đã tiếp xúc. Nhóm mới nên thu thập sau khi chốt cấu hình; có thể dùng 10–20 CV làm **đợt xác nhận ban đầu**, báo hạn chế, không khẳng định kích thước này đủ để đại diện thị trường. Chưa có dữ liệu để tính cỡ mẫu đủ cho một biên sai số mục tiêu.

Không chạy 10-fold training ngay khi thiếu thời gian/Colab. Không giảm metric hoặc loại các CV khó để nâng điểm. Có thể bổ sung metric nội dung/văn bản dài sau khi định nghĩa và công bố rõ, song song exact match; phải giữ kết quả cũ và kiểm tra cụ thể với người rà.

## 6. Đoạn có thể dùng trong báo cáo

> Đề tài đánh giá mô đun trích xuất trên dữ liệu tổng hợp và một nhóm 40 CV thật cân bằng tiếng Anh/tiếng Việt. Fine-tuning đạt Field Micro F1 99,52% trên test tổng hợp nhưng 48,28% trên GOLD40, thấp hơn mô hình gốc 65,52%. Phân tích cho thấy khác biệt phạm vi nhãn kỹ năng, thiếu ví dụ dương ở một số trường, cách gộp kỹ năng và lỗi schema. Hybrid Pointer kết hợp kiểm chứng và retry cải thiện tỷ lệ schema-valid từ 85,00% lên 97,50% và F1 từ 49,66% lên 52,81% so với một lần sinh Pointer, nhưng chưa vượt mô hình gốc về F1. Kết quả này cho thấy tính hợp lệ cấu trúc và chất lượng nội dung cần được đánh giá riêng. GOLD40 được sử dụng cho phân tích hậu kiểm; việc cải tiến tiếp theo cần thống nhất quy tắc nhãn, rà nguồn PDF và xác nhận trên CV mới. Các kết quả này chỉ phản ánh mô đun trích xuất, không đại diện chất lượng chấm điểm, matching hay sinh gợi ý của toàn hệ thống.

## 7. Kiểm thử và giới hạn tool

Đã kiểm thử lưu/đọc nháp, lịch sử, tách người rà, xung đột phiên bản, điều kiện nộp, schema đề nghị, khóa trùng JSON, số trang, chặn đường dẫn, CSRF, truy cập LAN có mã và render PDF thành PNG. Kiểm tra cú pháp JavaScript thành công. Thư viện và server đã chạy trên Python 3.14 của máy hiện tại.

Runtime công cụ kiểm thử trình duyệt trong phiên này lỗi `failed to write kernel assets`; chưa xác nhận bố cục bằng ảnh chụp trình duyệt hoặc thao tác click tự động. CSS dùng nền sáng/chữ tối và layout co theo chiều rộng. Người dùng mở localhost để kiểm tra hiển thị thực tế trước khi gửi rộng. Đây là giới hạn kiểm thử giao diện, không phải hạn chế của phép đánh giá model.
