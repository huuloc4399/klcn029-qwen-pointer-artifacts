# P06 · Cách lập các danh sách từ dùng để xét yêu cầu JD

Cập nhật 17/10/2026. Mã P06 (và P05) trong Sổ quyết định và minh chứng. Bốn danh sách nằm trong `cv_evaluation_web/services/evaluator.py`. Chúng được dùng bởi:
- bộ luật K (trạng thái yêu cầu, trong `rule_rubric.py`);
- bước kiểm chứng yêu cầu của phương pháp P (`grounded_scoring.py`).

## Tóm tắt

| Danh sách | Kích thước | Dùng để | Nguồn | Ngày, commit |
|---|---|---|---|---|
| `SKILL_ALIASES` | 60 kỹ năng, 92 cách viết | Nhận ra tên công nghệ trong yêu cầu và trong CV | Bộ từ điển của bản web đầu tiên; bổ sung PHP, Express, NestJS, ASP.NET | 06/10 (`908b6f2`); bổ sung 16/10 (`a6074eb`) |
| `SKILL_IMPLIES` | 7 quy tắc | Bao hàm trực tiếp: dùng X nghĩa là dùng Y (Spring Boot → Java, React → JavaScript…) | Chép nguyên danh sách "bao hàm trực tiếp" của hướng dẫn người chấm | 16/10 (`a6074eb`) |
| `REQUIREMENT_STOPWORDS` | 83 từ | Bỏ các từ không phân biệt được yêu cầu này với yêu cầu khác khi khớp yêu cầu khái niệm | Từ chức năng (Anh, Việt) của bộ luật K cũ, cộng với từ CNTT chung chung | 16/10 (`18ebeb6`) |
| `CONCEPT_SYNONYMS` | 9 khóa | Cách gọi khác của cùng một yêu cầu (dịch Anh–Việt, viết tắt, kỹ thuật thuộc khái niệm) | Các quy tắc đồng nghĩa và ví dụ trong hướng dẫn người chấm | 16/10 (`18ebeb6`) |

## Nguyên tắc lập

1. **Lấy từ hướng dẫn người chấm, không lấy từ nhãn.** Người và máy dùng cùng một quy tắc, nên máy không bị chấm theo quy tắc mà nó không được biết.
   - `SKILL_IMPLIES` chép đúng danh sách bao hàm trực tiếp.
   - `CONCEPT_SYNONYMS` lấy từ ba quy tắc trong hướng dẫn:
     - kỹ năng mềm chỉ tính khi đúng tên hoặc đồng nghĩa (làm việc nhóm = teamwork, giải quyết vấn đề = problem-solving, giao tiếp = communication);
     - chứng chỉ ngoại ngữ (TOEIC, IELTS);
     - ví dụ của Responsive (responsive, mobile-first, media query, giao diện tương thích di động).
2. **Chỉ đưa vào cách gọi khác của chính yêu cầu, không đưa liên quan lỏng.** CSS không phải bằng chứng của Responsive; Java không phải bằng chứng của OOP. Đây là quy tắc "liên quan lỏng → `unclear`" của hướng dẫn.
3. **Từ chung chung bị loại khi khớp** vì làm kết quả sai theo cả hai chiều. Ví dụ giả được dùng để phát hiện lỗi, yêu cầu là "Responsive web design":
   - "Designed the database for a web application" khớp "web" và "design" nên bị chấm `met` sai;
   - "Built responsive layouts with Flexbox" chỉ khớp 1/3 từ nên bị chấm `missing` sai.

   Các từ thêm vào gồm: web, design, development, application, system, software, programming, technology, tools, concepts, practices, principles, production, platform, layer, cùng các âm tiết tiếng Việt không mang nghĩa riêng (phát, triển, công, nghệ, làm, việc, thiết, kế, hệ, thống…).
4. **Quy tắc khớp:**
   - chữ thường, bỏ dấu, đ → d;
   - chỉ xét từ từ 3 ký tự;
   - bỏ số phiên bản ở cuối từ (HTML5 → HTML, OAuth2 → OAuth; giữ nguyên S3, ES6);
   - từ dài hơn 4 ký tự khớp theo gốc từ (pattern ↔ patterns, debug ↔ debugging);
   - cách gọi khác khớp theo cụm từ.

## Phạm vi tác động

- Trong 166 yêu cầu của 12 JD, **88 yêu cầu (53%) nằm ngoài từ điển kỹ năng**. Trước 16/10, với các yêu cầu này code chỉ kiểm được trích dẫn có trong CV hay không.
- 87/88 yêu cầu có ít nhất một từ đặc trưng để kiểm. Riêng "UI/UX" không có, nên được bỏ qua kiểm tra và giữ cách xử lý cũ.
- 19 yêu cầu (10 cách diễn đạt khác nhau) có cách gọi khác trong `CONCEPT_SYNONYMS`: tiếng Anh, giao tiếp, giải quyết vấn đề, làm việc nhóm, OOP, Responsive.

## Kiểm soát việc chỉnh theo dữ liệu

- Các danh sách được viết từ văn bản hướng dẫn và ví dụ giả, **không dựa vào nhãn người**.
- Sau khi viết, đo một lần trên nhãn vòng thử: kappa trạng thái yêu cầu của bộ luật K hầu như không đổi (so với A: 0,48 → 0,48; so với B: 0,48 → 0,49, đầu vào gold). Không chỉnh thêm sau lần đo đó.
- Danh sách bị khóa cùng code: hash của `evaluator.py` được ghi trong `run_config.json`, và cấu hình được cố định trong đăng ký trước (commit `e9c95e6`).
- Test ghi lại hành vi mong muốn: `test_concept_requirements_need_their_own_words`, `test_keyword_concepts_ignore_generic_words`, các test của `SKILL_IMPLIES`.

## Hạn chế

- Kiểm tra chỉ ở mức từ ngữ, không hiểu nghĩa: một trích dẫn chứa từ của yêu cầu nhưng không chứng minh được yêu cầu vẫn được chấp nhận. Phần đánh giá nội dung vẫn do LLM làm.
- Danh sách cách gọi khác còn nhỏ. Cách diễn đạt đúng nhưng nằm ngoài danh sách sẽ bị chuyển thành `unclear`, ví dụ "CSS Grid cho nhiều kích thước màn hình" với yêu cầu Responsive.
- Hướng dẫn còn coi "class, kế thừa, design pattern" là bằng chứng của OOP, nhưng các từ này **chưa** có trong danh sách vì "class" quá mơ hồ khi khớp từ. Hậu quả: P có thể chuyển nhầm một số ca OOP đúng thành `unclear`.
- Khớp âm tiết tiếng Việt còn dễ dãi: một âm tiết trùng là đủ để giữ quyết định của LLM.
- Tác động thực của bước kiểm tra được đo bằng biến thể `p_no_concept_check` trên tập dev và tập test. Kết quả sẽ ghi vào đây khi có.
