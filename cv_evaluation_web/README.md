# CV Insight - Web đánh giá CV và thu thập dữ liệu tự nguyện

Web MVP chạy bằng Flask, PyMuPDF và SQLite. Giao diện lấy cảm hứng từ cách TopCV tổ chức trang upload: điều hướng gọn, màu xanh làm điểm nhấn, một luồng upload tập trung và kết quả dạng thẻ. Tên, logo, nội dung và mã nguồn đều là của đề tài KLCN029.

## Chức năng hiện có

- Tải một CV PDF tối đa 8 MB và 12 trang.
- Dán JD để đối chiếu.
- Chấm bốn nhóm điểm: khả năng đọc ATS 20, tác động thành tích 30, phù hợp JD 35 và văn phong 15.
- Hiển thị kỹ năng khớp, kỹ năng còn thiếu và góp ý có thể kiểm tra.
- Tách riêng đồng ý xử lý tạm thời và đồng ý đóng góp nghiên cứu.
- Không lưu CV khi người dùng không chọn đóng góp.
- Khi đóng góp, lưu PDF, JD, metadata và kết quả bằng ID ngẫu nhiên; cấp mã rút dữ liệu.
- Trang rút dữ liệu xóa hồ sơ nghiên cứu theo mã.
- Không yêu cầu tài khoản, email hoặc số điện thoại.
- Ở chế độ production, gửi job bất đồng bộ tới RunPod, kiểm tra CVSchema 2.0 bằng
  parser đóng băng rồi mới chấm điểm.
- CSRF, security headers và giới hạn 5 lượt/IP/giờ cho form upload công khai.

## Chạy trên Windows

Từ thư mục dự án:

```powershell
python -m pip install -r cv_evaluation_web/requirements.txt
python cv_evaluation_web/serve.py
```

Hoặc mở `cv_evaluation_web/Start_CV_Web.bat`, sau đó truy cập:

```text
http://127.0.0.1:8780
```

Biến môi trường:

| Biến | Mặc định | Mục đích |
|---|---|---|
| `CV_WEB_SECRET_KEY` | khóa ngẫu nhiên mỗi lần chạy | khóa phiên Flask |
| `CV_WEB_DATA_DIR` | `cv_evaluation_web/data` | nơi lưu dữ liệu opt-in |
| `CV_WEB_MAX_UPLOAD_MB` | `8` | giới hạn dung lượng PDF |
| `CV_WEB_MAX_PDF_PAGES` | `12` | giới hạn số trang |
| `CV_WEB_HOST` | `127.0.0.1` | địa chỉ lắng nghe |
| `CV_WEB_PORT` | `8780` | cổng web |
| `CV_PIPELINE_MODE` | `local_baseline` | `local_baseline` hoặc `runpod` |
| `RUNPOD_ENDPOINT_ID` | trống | endpoint Qwen trên RunPod |
| `RUNPOD_API_KEY` | trống | khóa server-side để gọi RunPod |
| `RUNPOD_WEBHOOK_SECRET` | trống | bí mật xác thực URL webhook |
| `CV_WEB_RATE_LIMIT_PER_HOUR` | `5` | số upload tối đa theo IP đã băm |

## Dữ liệu được lưu

Nếu người dùng **không** chọn đóng góp nghiên cứu, PDF nằm trong tệp tạm và bị xóa sau khi trả kết quả.

Nếu người dùng chọn đóng góp, mỗi hồ sơ có cấu trúc:

```text
data/submissions/<submission_id>/
  cv.pdf
  jd.txt
  submission.json
```

Chỉ mục và mã rút dữ liệu được quản lý trong `data/submissions.sqlite3`. Toàn bộ `data/` bị loại khỏi Git bằng `.gitignore`.

## Hai chế độ baseline

`local_baseline` chỉ dùng PyMuPDF và bộ chấm quy tắc, nhằm chạy giao diện không cần GPU.

`runpod` là luồng triển khai chính:

```text
PDF -> PDF text/OCR router -> Qwen3-4B + Pointer Stage 2 adapter
    -> Parser v1 -> CVSchema 2.0 -> matching baseline xác định -> giao diện kết quả
```

Model trích xuất và parser không sinh điểm tuyển dụng. `services/evaluator.py` nhận CVSchema
đã kiểm tra và thực hiện baseline matching có thể tái lập. Cách tách này giữ ranh giới mô đun
trích xuất với mô đun chấm điểm của dự án.

Hướng dẫn triển khai đầy đủ ở `deployment/DEPLOY_RENDER_RUNPOD.md`.

Lý do vẫn giữ chế độ local:

1. Web chạy được ngay cả khi Colab hoặc API hết hạn mức.
2. Không gửi CV ra dịch vụ ngoài trong giai đoạn thử nghiệm giao diện.
3. Có thể kiểm thử chính xác dữ liệu nào tạo ra từng điểm.
4. Đối chiếu kết quả web trước khi bật endpoint GPU.

## Chạy kiểm thử

```powershell
python -m unittest discover -s cv_evaluation_web/tests -v
```

## Trước khi công khai

- Giảng viên và đơn vị chủ trì duyệt phiếu thông tin người tham gia, thời hạn lưu, phạm vi sử dụng và danh sách người truy cập.
- Cấu hình HTTPS, backup mã hóa và nhật ký truy cập phù hợp.
- Chạy xử lý PDF/OCR trong worker cô lập.
- Chuyển SQLite sang PostgreSQL và thư mục cục bộ sang object storage riêng tư nếu chạy nhiều máy.
- Nhờ đơn vị chủ trì rà soát nghĩa vụ bảo vệ dữ liệu cá nhân trước khi thu thập công khai.
