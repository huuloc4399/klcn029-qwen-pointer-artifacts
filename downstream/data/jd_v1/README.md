# Tập JD v1

Mục tiêu: 12 JD gồm **8 Backend và 4 Frontend**, cấp độ intern, fresher hoặc junior, khoảng một nửa
tiếng Việt. Tỉ lệ 8/4 theo phân bố CV thật: 35/73 CV nghiêng backend, chỉ 4 frontend và 7 fullstack
(`python -m downstream.data.cv_track_profile`). Phạm vi chỉ gồm Backend và Frontend; CV data/AI, QA, BA
không dùng để lập cặp. Với JD Frontend, ưu tiên JD có React kèm một ít Node.js hoặc API để khớp CV fullstack.

## Tiêu chí chọn JD

CV trong tập chấm là CV sinh viên và người mới đi làm. Một JD chỉ có ích khi CV này có lúc đáp ứng,
có lúc không, để điểm phù hợp có độ phân tán.

- **Đúng mảng:** Backend là phát triển server, web API và CSDL (Java, .NET, Node.js, PHP, Python,
  Go…); Frontend là giao diện web (React, Vue, Angular, HTML/CSS). Không nhận JD lập trình hệ thống,
  desktop, nhúng/IoT, bảo mật endpoint, mobile hoặc data/AI, kể cả khi tiêu đề ghi "Software Developer"
  và có nhắc Golang hay C++.
- **Nhận:** thực tập, fresher, junior; yêu cầu tối đa 1–2 năm kinh nghiệm. Trên TopCV lọc
  "Kinh nghiệm: Không yêu cầu / Dưới 1 năm / 1 năm" và "Cấp bậc: Thực tập sinh / Nhân viên".
- **Không nhận:** senior, lead, trưởng nhóm; yêu cầu từ 3 năm kinh nghiệm. Với CV sinh viên, gần như
  mọi yêu cầu đều sẽ là `missing`, nên JD không phân biệt được CV tốt với CV yếu.
- Mục yêu cầu nên có khoảng 5–15 ý sau khi tách. JD quá dài làm người chấm mất nhiều thời gian
  cho mỗi cặp.
- Tránh hai JD gần như trùng nhau (cùng công ty, cùng vị trí). Lệnh `check` báo lỗi khi hai JD có cùng link tin (bỏ qua phần `?…` của link) hoặc bản gốc giống nhau từ 85% trở lên.
- Tránh JD chuyên sâu một mảng hẹp (ví dụ backend cho AI: RAG, vector DB, MLOps, streaming LLM).
  CV sinh viên hầu như không đáp ứng, và JD thường có trên 25 yêu cầu sau khi tách.
- Yêu cầu về giới tính, tuổi, ngoại hình, quê quán **không bao giờ** đưa vào JD gold, vì rubric không
  chấm các yếu tố này. Nên ưu tiên JD không có yêu cầu kiểu này. Nếu vẫn dùng, ghi ở cột `notes` rằng
  đã bỏ chúng.

## Lưu ở đâu

| Nội dung | Vị trí | Đưa lên Git |
|---|---|---|
| JD đã viết lại bằng lời của nhóm | `downstream/data/jd_v1/JD001.txt`, `JD002.txt`, … | Có |
| Thông tin nguồn của từng JD | `downstream/data/jd_v1/jd_manifest.csv` | Có |
| Bản gốc chép từ trang tuyển dụng (để đối chiếu) | `downstream/data/jd_v1/raw/JD001.txt` | Không (đã gitignore) |
| Yêu cầu đã tách (JD gold) | `downstream/data/jd_gold_v1/JD001.json` | Có |

## Thêm một JD

1. Đặt mã tiếp theo theo thứ tự: `JD001`, `JD002`, … Mã không được đổi sau khi đã dùng.
2. Lưu bản gốc vào `raw/JD00x.txt`, xóa thông tin liên hệ của người tuyển dụng.
3. Viết lại vào `JD00x.txt` (UTF-8) theo khung dưới đây. Giữ nguyên ý của từng yêu cầu, nhưng không
   chép nguyên văn và bỏ tên công ty nếu không cần.

   ```text
   Vị trí: Backend Developer Intern
   Cấp độ: intern
   Mô tả công việc:
   - Xây dựng và kiểm thử REST API
   - ...
   Yêu cầu bắt buộc:
   - Java, Spring Boot
   - ...
   Ưu tiên:
   - Docker
   - ...
   Quyền lợi:
   - (không bắt buộc)
   ```

   JD tiếng Anh viết lại bằng tiếng Anh với các nhãn `Position:`, `Level:`, `Responsibilities:`,
   `Required:`, `Preferred:` (xem `JD001.txt`).

4. Thêm một dòng vào `jd_manifest.csv`. Mở được bằng Excel, nhưng phải lưu lại dạng **CSV UTF-8**.

   | Cột | Giá trị |
   |---|---|
   | `jd_id` | `JD001` |
   | `role` | `backend` hoặc `frontend` |
   | `level` | `intern`, `fresher` hoặc `junior` |
   | `language` | `vi` hoặc `en` |
   | `job_title` | Tên vị trí |
   | `source_name` | ITviec, TopCV, LinkedIn, trang tuyển dụng công ty, … |
   | `source_url` | Link tin gốc |
   | `access_date` | Ngày truy cập, dạng `2026-10-14` |
   | `rewritten` | `yes` |
   | `collected_by` | Người thu |
   | `notes` | Tùy chọn |
   | `sha256` | Để trống; script tự điền |

5. Chạy kiểm tra:

   ```bash
   python -m downstream.data.jd_catalog check
   ```

## Tách yêu cầu (JD gold)

Khi đủ JD, tạo các tệp gold rỗng rồi điền tay:

```bash
python -m downstream.data.jd_catalog init-gold
```

- Mỗi phần tử `must_have` hoặc `nice_to_have` là **một yêu cầu nguyên tử**: "Java/Spring Boot" tách
  thành "Java" và "Spring Boot". "Có kinh nghiệm 1 năm" ghi vào `min_experience_years`, không đưa vào danh sách.
- Hai người tách độc lập rồi thống nhất một bản. Người chấm cặp CV–JD sẽ đánh giá đúng danh sách
  yêu cầu này, nên phải chốt gold trước khi tạo file Excel chấm.
- Chạy lại `check` sau khi điền: lệnh báo tệp sai `JDSchema`, JD chưa có `must_have` và yêu cầu bị lặp.

### Quy tắc tách yêu cầu

Mỗi yêu cầu là một thứ người chấm có thể trả lời "CV có hay không" bằng một đoạn trích.

| Quy tắc | Câu trong JD | Ghi vào gold |
|---|---|---|
| 1. Liệt kê bằng "và", dấu phẩy: **tách** | OOP, SOLID principles, and design patterns | `OOP`, `SOLID principles`, `Design patterns` |
| 2. Lựa chọn thay thế ("hoặc", "/", "or", "like", "such as", "e.g.", ví dụ trong ngoặc): **giữ một yêu cầu**, ghi các lựa chọn trong ngoặc | Entity Framework, Dapper, or other ORM frameworks | `ORM (Entity Framework, Dapper or other)` |
| 3. "/" nối hai thứ đều phải có thì vẫn **tách**. Riêng cặp quen thuộc `HTML/CSS` luôn giữ thành một yêu cầu | Java/Spring Boot; HTML/CSS/JS | `Java`, `Spring Boot`; `HTML/CSS`, `JavaScript` |
| 4. Số năm kinh nghiệm **không** đưa vào danh sách | 1+ years … with C# and .NET | `min_experience_years: 1.0`; kỹ năng tách riêng: `C#`, `.NET (Framework or Core)` |
| 5. Kỹ năng mềm có trong mục bắt buộc thì **giữ**, tách từng kỹ năng | problem-solving skills and ability to work in a team | `Problem-solving`, `Teamwork` |
| 6. Mục "Mô tả công việc" **không** sinh yêu cầu, chỉ đưa vào `responsibilities` | Design and implement … microservices | Không thêm `Microservices` vào yêu cầu |
| 7. Giữ ngôn ngữ của JD, dùng tên công nghệ chuẩn, bỏ từ chỉ mức độ ("solid", "strong", "familiarity") | Solid knowledge of SQL Server | `SQL Server` |
| 8. Bằng cấp ghi vào `education`; để trống nếu JD không nêu | | `education: ""` |
| 9. "Điểm cộng nếu có **một trong** các mảng A, B, C" với các mảng **khác nhau**: **tách**, vì mỗi mảng là một điểm cộng riêng. Quy tắc 2 chỉ dùng khi các lựa chọn thay thế nhau cho cùng một nhu cầu (EF hoặc Dapper đều là ORM) | một trong các mảng: LLM prompting, Vector DB, Docker, Linux/Apache | `LLM prompting`, `Vector database`, `Docker`, `Linux`, `Apache` |
| 10. Thẻ kỹ năng của trang tuyển dụng (TopCV "Kỹ năng cần có / nên có") chỉ dùng để **đối chiếu**. Câu trong phần yêu cầu là chính; chỉ thêm từ thẻ khi thẻ nêu thứ hoàn toàn mới: thẻ "cần có" vào `must_have`, thẻ "nên có" vào `nice_to_have`, vẫn áp dụng quy tắc 2 và 11 khi tách. Thẻ **mâu thuẫn** với mô tả (khác loại bắt buộc/ưu tiên, hoặc tách khác) thì **bỏ thẻ**, theo câu (ví dụ: JD004 lấy RESTful API, kiến trúc phần mềm, kiểm thử, CSDL từ thẻ; JD011 bỏ thẻ "nên có: Git" vì mô tả ghi Git là bắt buộc) | Câu: "RESTful API / Web services"; thẻ: "RESTful API, Web Services" | `RESTful API hoặc Web services` (một yêu cầu, theo câu) |

| 11. Các ý con sau "bao gồm / including" hoặc trong ngoặc là **chi tiết của cùng một mảng**: **không tách** | relational databases and SQL, including transactions, indexes, constraints | `Relational databases and SQL (PostgreSQL or similar)` |
| 12. Hai ý ở hai gạch đầu dòng khác nhau nhưng cùng một nội dung: **gộp** thành một yêu cầu | "relational databases and SQL" và "PostgreSQL or a similar relational database"; "debugging" và "troubleshoot issues across application and database layers" | Một yêu cầu cho mỗi cặp |
| 13. Phẩm chất, thái độ (trách nhiệm, chịu khó, cẩn thận, bình tĩnh, chịu áp lực…) **không đưa vào**, ở bất kỳ mục nào, vì CV không chứng minh được. Kỹ năng mềm thể hiện được qua CV (tư duy logic, làm việc nhóm, giao tiếp, tự học) nằm trong mục **bắt buộc** thì giữ theo quy tắc 5. Ở mục phẩm chất riêng ("Desired soft skills"), chỉ giữ ý là phương pháp hoặc kỹ năng cụ thể chưa có ở chỗ khác | Awareness of DevOps and Agile principles | `Agile` (DevOps đã có trong `CI/CD or GitOps`) |
| 14. Số năm kinh nghiệm chỉ **ưu tiên**, không bắt buộc: `min_experience_years: null`, ghi lại ở cột `notes` | 1+ years … is preferred; fresh graduates encouraged | `min_experience_years: null`, `fresher` |
| 15. Điều kiện làm việc (toàn thời gian, số tháng thực tập, địa điểm, ngày bắt đầu, lương) **không đưa vào**, vì CV không chứng minh được; ghi ở cột `notes` nếu bỏ | Có thể thực tập fulltime trong thời gian 3 tháng | Không thêm |
| 16. Câu có "là lợi thế" ở cuối mà không rõ áp dụng cho ý nào thì dùng thẻ kỹ năng của trang để phân định | Biết sử dụng Git, hiểu mô hình microservices là lợi thế (thẻ: Git "cần có", Microservices "nên có") | `Git` bắt buộc, `Microservices` ưu tiên |

Sau khi tách, nếu JD có hơn 15 yêu cầu thì ghi số lượng vào `notes` để khi lập cặp CV–JD có thể
dùng JD đó ít lần hơn (ví dụ JD003: 25 yêu cầu).

`seniority_level` dùng cùng giá trị với cột `level` trong manifest:

- Yêu cầu từ 1 năm kinh nghiệm trở lên: `junior`.
- Dưới 1 năm, hoặc JD ghi "fresher": `fresher`.
- Tuyển thực tập: `intern`.
- JD không nêu số năm kinh nghiệm nhưng yêu cầu đã tốt nghiệp: `fresher`, kèm lý do ở cột `notes` (ví dụ JD002).

### Ví dụ đầy đủ: JD001

`raw/JD001.txt` (bản gốc) → `JD001.txt` (viết lại) → `../jd_gold_v1/JD001.json` (gold).

| Câu gốc ([Required]) | must_have |
|---|---|
| 1+ years of experience in back-end development with C# and .NET (Framework/Core) | `C#`, `.NET (Framework or Core)` + `min_experience_years: 1.0` |
| Solid knowledge of SQL Server, database design, and optimization | `SQL Server`, `Database design`, `Database optimization` |
| Experience with RESTful API development and integration | `RESTful API development and integration` |
| Understanding of OOP, SOLID principles, and design patterns | `OOP`, `SOLID principles`, `Design patterns` |
| Familiarity with Agile/Scrum development methodologies | `Agile/Scrum` (Scrum là một cách làm Agile: quy tắc 2) |
| Strong problem-solving skills and ability to work in a team | `Problem-solving`, `Teamwork` |

| Câu gốc ([Preferred]) | nice_to_have |
|---|---|
| Experience with Entity Framework, Dapper, or other ORM frameworks | `ORM (Entity Framework, Dapper or other)` |
| Knowledge of cloud services (Azure, AWS, GCP) | `Cloud services (Azure, AWS or GCP)` |
| Familiarity with CI/CD pipelines and DevOps practices | `CI/CD pipelines`, `DevOps practices` |
| Experience in containerization technologies like Docker, Kubernetes | `Containerization (e.g. Docker, Kubernetes)` |

Kết quả: 12 yêu cầu bắt buộc, 5 yêu cầu ưu tiên, `seniority_level: junior`.

Khi hai người tách khác nhau, ghi trường hợp vào bảng quy tắc trên để các JD sau làm giống nhau.

### Lưu ý khi sửa manifest bằng Excel

- **Đóng tệp trong Excel trước khi chạy `check`**: khi tệp đang mở, Excel khóa nó và script không ghi được cột `sha256`.
- Lưu bằng Save As → **CSV UTF-8 (Comma delimited)**. Nếu Excel đổi ngày thành `14/10/2026` hoặc dùng
  dấu `;` làm phân cách, `check` vẫn đọc được và tự chuẩn hóa lại thành `2026-10-14` và dấu phẩy.
