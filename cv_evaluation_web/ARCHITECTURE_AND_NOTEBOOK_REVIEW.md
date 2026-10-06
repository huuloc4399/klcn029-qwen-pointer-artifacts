# Rà soát notebook matching và kiến trúc web đánh giá CV

**Ngày:** 06/10/2026
**Notebook:** `MatchCV_JD&Baseline.ipynb`
**Web MVP:** `cv_evaluation_web`

## 1. Công nghệ được đề cử

### Phương án đang triển khai cho MVP

| Thành phần | Công nghệ | Lý do |
|---|---|---|
| Web server | Flask + Waitress | Python, nhẹ, tương thích trực tiếp PyMuPDF/schema/parser hiện có, hoàn thành nhanh |
| Giao diện | Jinja, HTML, CSS, JavaScript thuần | Không cần build Node, dễ triển khai Colab/VPS, giao diện responsive |
| PDF native text | PyMuPDF | Nhanh, lấy được text block và tín hiệu bố cục |
| Baseline score | Python quy tắc xác định | Chạy được khi không có GPU/API, kết quả có thể tái lập |
| Metadata | SQLite | Phù hợp pilot nhỏ, giao dịch rõ ràng, không cần dịch vụ ngoài |
| CV opt-in | Thư mục riêng theo UUID | Không dùng tên file thật, dễ đóng gói dataset và xóa theo mã |

### Khi triển khai công khai hoặc tải lớn

- Giữ Python service cho OCR, Qwen và matching.
- Chuyển API sang FastAPI nếu cần client mobile hoặc frontend tách rời.
- PostgreSQL cho consent/submission; S3/MinIO private bucket cho PDF.
- Redis + Celery/RQ cho OCR và inference bất đồng bộ.
- Nginx/Caddy + HTTPS; worker OCR/inference chạy trong container cô lập.
- Có thể chuyển frontend sang Next.js sau khi luồng nghiệp vụ ổn định. Chưa nên làm ngay vì làm tăng hai codebase trong khi pipeline model vẫn thay đổi.

## 2. Kiến trúc đề xuất

```text
Browser
  -> Upload PDF + JD + language + consent
  -> Validation: PDF magic, size, pages
  -> Native text extraction
       -> text đủ: Qwen pointer extraction
       -> text thưa: OCR router EN/VI -> Qwen pointer extraction
  -> Frozen parser v1 -> CVSchema 2.0
  -> JD parser -> JDSchema
  -> Matching strategy selected for experiment
  -> Result contract -> Web result page
  -> if research opt-in: private PDF/JD/metadata storage
  -> else: delete temporary PDF
```

MVP hiện đã hoàn chỉnh nhánh upload, native extraction, baseline score, consent, lưu opt-in, kết quả và rút dữ liệu. Điểm kết nối Qwen/OCR được giữ ở tầng `services`.

## 3. Kết quả rà soát notebook

### Các phần có thể tái sử dụng

- Rubric tổng 100: ATS 20, Impact 30, Semantic 35, Tone 15.
- CVSchema và JDSchema là đầu vào thống nhất cho matching.
- B1 keyword, B2 embedding, M1 zero-shot, M2 few-shot, M3 RAG và M4 multi-agent tạo được khung ablation.
- Hợp đồng kết quả gồm điểm thành phần, kỹ năng thiếu, kỹ năng chưa minh chứng, điểm mạnh và đề xuất sửa.

### Các vấn đề cần sửa trước khi dùng trong web

1. **ATS được LLM chấm từ JSON.** JSON không còn font, bảng, cột, icon và thứ tự đọc, nên không đủ bằng chứng để chấm bố cục. Web MVP lấy tín hiệu trực tiếp từ PDF.
2. **`actual_exp_years = len(cv["experience"])`.** Số vị trí không phải số năm kinh nghiệm. Cần parser thời gian riêng hoặc chỉ báo `unknown`.
3. **Thêm `target_role` ngoài CVSchema 2.0.** Nếu cần trường này cho matching, đặt nó trong metadata suy ra, không sửa ngầm hợp đồng CVSchema.
4. **Prompt cho phép suy target role.** Điều này mâu thuẫn quy tắc trích xuất chỉ lấy thông tin có bằng chứng. Nên tách `stated_target_role` và `inferred_target_role`.
5. **Thứ tự Cell B có lỗi trạng thái.** `real_jd` được dùng trong nhánh fallback trước khi dòng chọn `JD_LIBRARY["BACKEND_JAVA"]`; chạy notebook từ trạng thái sạch có thể lỗi hoặc dùng biến cũ.
6. **Tên mô hình trong log không khớp code.** Một số nhãn in `Llama 3.3 70B` trong khi request gọi Qwen. Báo cáo benchmark cần lấy tên model từ config duy nhất.
7. **B1 normalization quá mạnh.** Xóa khoảng trắng/dấu gạch có thể tạo collision và không xử lý alias có kiểm soát. Web dùng từ điển alias có biên từ.
8. **B2 ghép toàn CV/JD thành một vector.** Điểm dễ bị phần dài chi phối. Nên tính theo field và ghi rõ aggregation.
9. **M1/M2/M3/M4 chưa có gold score của chuyên gia.** Chênh lệch điểm giữa các chiến lược chưa chứng minh chiến lược nào đúng hơn.
10. **RAG source chưa đủ provenance.** Một số nội dung KB là diễn giải do nhóm viết nhưng prompt trình bày như quy tắc nguyên văn của nghiên cứu. Cần lưu URL/DOI, trang, đoạn trích và trạng thái kiểm chứng.
11. **Multi-agent có ba lần gọi cùng model.** Đây là self-consistency theo vai trò, chưa phải ba chuyên gia độc lập; báo cáo cần mô tả đúng và đo chi phí/latency.
12. **Không có bảo vệ dữ liệu cho CV thật trong notebook.** Khi gọi API ngoài cần consent, mask PII, retention policy và log provider/model/version.

## 4. Quyết định cho web MVP

- Không đưa M4 vào request web đồng bộ vì ba lần gọi LLM dễ timeout và tốn hạn mức.
- Không hiển thị “dẫn chứng học thuật” do LLM tự tạo.
- Trả kết quả baseline trong một request để kiểm tra luồng người dùng và thu thập CV tự nguyện trước.
- Khi Qwen service sẵn sàng, thêm lựa chọn chiến lược ở backend và giữ nguyên giao diện kết quả.
- Lưu riêng `method`, model/version, parser version và consent version cho từng submission.

## 5. Nguyên tắc thiết kế giao diện

Tham khảo bố cục TopCV tại `https://www.topcv.vn/` và `https://www.topcv.vn/upload-cv`:

- thanh điều hướng nền trắng;
- màu xanh làm CTA;
- headline lớn và khối upload trung tâm;
- lợi ích/các bước trình bày dạng thẻ;
- kết quả có tổng điểm và các phần hành động tiếp theo.

Web dùng tên và nhận diện `CV Insight · KLCN029 Research`, không dùng logo, ảnh, văn bản hoặc thành phần độc quyền của TopCV.

## 6. Dữ liệu và đồng thuận

Hai checkbox tách biệt:

1. Đồng ý xử lý tạm thời để đánh giá - bắt buộc.
2. Tự nguyện đóng góp nghiên cứu - tùy chọn, mặc định bỏ chọn.

Nếu opt-in, hệ thống cấp mã rút dữ liệu. Nếu không opt-in, PDF tạm bị xóa ngay sau khi render kết quả. Trước khi public, cần giảng viên/đơn vị chủ trì duyệt chính sách và rà soát theo Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 cùng Nghị định 356/2025/NĐ-CP.

## 7. Thứ tự phát triển tiếp theo

1. Pilot nội bộ 5-10 người với baseline hiện tại.
2. Sửa nội dung đồng thuận theo góp ý giảng viên.
3. Kết nối OCR router và Qwen pointer adapter qua worker.
4. Khóa hợp đồng kết quả matching và bổ sung các chiến lược M1-M4.
5. Tạo tập đánh giá matching có chuyên gia chấm, sau đó mới so sánh chiến lược.
6. Đưa lên máy chủ HTTPS và mở đợt thu thập chính thức.
