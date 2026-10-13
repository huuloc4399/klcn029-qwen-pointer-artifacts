# Chạy API trích xuất trên laptop của nhóm, mở ra Internet bằng Cloudflare Tunnel

Ngày soạn: 12/10/2026. Phương án tạm trong lúc chờ máy Oracle Always Free
(`DEPLOY_FREE_ORACLE_RENDER.md`), hoặc dùng để demo. Không cần Docker. Web vẫn chạy trên Render;
chỉ đổi `EXTRACTION_API_URL`.

## 1. Kiến trúc

```text
Trình duyệt ── Render (free): cv_evaluation_web, không đổi
                 │  HTTPS, X-API-Key
                 ▼
Cloudflare quick tunnel  https://<ngẫu-nhiên>.trycloudflare.com   (không mở cổng nào trên router)
                 ▼
Laptop Windows (GTX 1650 4 GB, RAM 16 GB), mọi tệp nằm trên ổ ngoài <Root>
  cloudflared.exe ──► API FastAPI 127.0.0.1:7860 (cùng mã, kiểm tra hash khi khởi động)
                         └─► llama-server 127.0.0.1:8091 (llama.cpp b11312, CUDA 12.4) + GGUF Q4_K_M
```

Vì sao không dùng `llama-cpp-python` như trên Oracle: bản build sẵn cho Windows dừng ở 0.3.19 (CPU) và
0.3.4 (CUDA), còn tự biên dịch thì cần Visual Studio và CUDA Toolkit (nhiều GB, trong khi ổ C còn dưới
10 GB). Thay vào đó dùng `llama-server` chính thức của llama.cpp ở **đúng commit** đã xuất GGUF (bản
phát hành `b11312`). Prompt, decoding greedy và Parser v1 không đổi; API kiểm tra llama-server đã nạp
đúng tệp GGUF có hash đã khóa.

**Giới hạn cần ghi trong báo cáo:**

- API chỉ chạy khi laptop bật, cắm sạc, có mạng và cửa sổ PowerShell còn mở. Tắt máy là web báo không
  kết nối được máy chủ trích xuất.
- URL `trycloudflare.com` đổi mỗi lần khởi động lại, phải cập nhật lại trên Render. Cloudflare dành
  quick tunnel cho thử nghiệm, không cam kết thời gian hoạt động.
- Không cài OCR (thiếu dung lượng, và PaddleOCR trên Windows cần thêm nhiều GB): PDF có lớp chữ chạy bình
  thường; PDF dạng ảnh bị từ chối với thông báo rõ ràng.
- Chạy một phần model trên GPU, phần còn lại trên CPU. Kết quả số có thể lệch nhẹ so với lần đo trên Colab,
  nên bước 4 đo lại cổng độ trung thực trên chính laptop; báo cáo dùng số đo này.

## 2. Chuẩn bị

- Driver NVIDIA ≥ 551 (máy hiện có 576.80). Không cần cài CUDA Toolkit.
- Python 3.11 (`py -3.11 --version`; máy đã có 3.11.5).
- Ổ ngoài còn khoảng 4 GB trở lên (llama.cpp CUDA ~1 GB sau giải nén, GGUF 2,5 GB, venv ~0,3 GB). Ổ C
  gần như không dùng thêm. Ví dụ dưới đây dùng `E:\klcn029-home`; đổi theo ký tự ổ ngoài của bạn.
- Hai khóa, giống phương án Oracle: `HF_TOKEN` (fine-grained, chỉ đọc repo artifact) và `API_KEY` (chuỗi
  ngẫu nhiên, **không** phải token Hugging Face):

  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

## 3. Cài đặt (một lần, khoảng 15–30 phút tùy mạng)

Ở thư mục dự án:

```powershell
powershell -ExecutionPolicy Bypass -File deployment\home_api\setup_home.ps1 -Root E:\klcn029-home
```

Script tải llama.cpp b11312 bản CUDA 12.4 và cloudflared 2026.10.0 từ GitHub chính thức, kiểm tra
SHA-256, tạo Python 3.11 venv với các gói lõi của API, build API bundle vào `E:\klcn029-home\api` và tạo
`E:\klcn029-home\home.env`. Nếu CUDA lỗi, chạy lại với `-Backend vulkan` hoặc `-Backend cpu` (khi đó đặt
`N_GPU_LAYERS=0` cho bản CPU).

Mở `E:\klcn029-home\home.env` bằng Notepad, điền `API_KEY` và `HF_TOKEN`. Các biến `GGUF_*` đã điền sẵn.

## 4. Đo cổng độ trung thực trên laptop (khoảng 10–30 phút)

```powershell
powershell -ExecutionPolicy Bypass -File deployment\home_api\start_home.ps1 -Root E:\klcn029-home -Fidelity
```

Lần đầu script tải GGUF 2,5 GB vào ổ ngoài. Sau đó llama-server chạy 10 CV tổng hợp và so với P0. Yêu cầu
`"passed": true`. Lưu JSON cuối cùng cho báo cáo, rồi đặt `JOB_SECONDS_ESTIMATE` trong `home.env` bằng
`seconds_mean_after_first` để thời gian dự kiến trên web sát thực tế.

Script dừng ngay nếu cổng của llama-server (`LLAMA_PORT`, mặc định 8091) hoặc cổng API 7860 đang bị
chương trình khác giữ, và in PID của chương trình đó. Khi đó tắt chương trình kia hoặc đổi `LLAMA_PORT`
trong `home.env`.

Nếu llama-server không khởi động và log nhắc tới hết bộ nhớ (out of memory), giảm `N_GPU_LAYERS` (28 → 24
→ 20). Có thể thử tăng (32, 36) nếu `nvidia-smi` còn trống nhiều VRAM khi đang chạy.

## 5. Chạy dịch vụ

```powershell
powershell -ExecutionPolicy Bypass -File deployment\home_api\start_home.ps1 -Root E:\klcn029-home
```

Script in ra dòng `Public API URL: https://….trycloudflare.com`. Mở `<URL>/health`, chờ
`"model": "ready"`. Giữ cửa sổ mở; Ctrl+C dừng tất cả. Script giữ Windows không ngủ trong lúc chạy,
nhưng vẫn cần:

- cắm sạc;
- Control Panel → Power Options → Choose what closing the lid does → **Do nothing** (khi cắm sạc), nếu
  muốn gập màn hình;
- tạm dừng Windows Update tự khởi động lại trong thời gian demo.

Kiểm tra từ máy bất kỳ:

```powershell
$env:EXTRACTION_API_URL = "<URL>"
$env:EXTRACTION_API_KEY = "<API_KEY>"
python deployment/hf_space_api/smoke_api.py
```

## 6. Nối web trên Render

Trong Render → service → Environment:

- `EXTRACTION_API_URL` = URL vừa in ra
- `EXTRACTION_API_KEY` = `API_KEY`
- `EXTRACTION_HF_TOKEN` = để trống
- `CV_WEB_INFRA_NOTE` = `Render vận hành web; máy tính của nhóm (kết nối qua Cloudflare Tunnel) vận hành model trích xuất và lưu đánh giá mức độ hài lòng.`
- `CV_WEB_ADMIN_KEY` = khóa trang quản trị, chuỗi ngẫu nhiên ít nhất 16 ký tự, khác `API_KEY`
  (`python -c "import secrets; print(secrets.token_urlsafe(24))"`). Để trống thì trang quản trị bị tắt.

Lưu lại; Render deploy lại trong vài phút. Mỗi lần chạy lại `start_home.ps1` chỉ cần sửa
`EXTRACTION_API_URL`.

## 7. Vận hành và dữ liệu

- Nhật ký: `E:\klcn029-home\logs` (`llama-server`, `api`, `cloudflared`). API không log nội dung CV.
- **Trang quản trị:** `https://<tên-service>.onrender.com/admin`, đăng nhập bằng `CV_WEB_ADMIN_KEY`
  (phiên 8 giờ, tối đa 10 lần thử mỗi giờ mỗi IP). Trang đọc trực tiếp đánh giá từ API nên laptop phải
  đang chạy. Có: trạng thái máy chủ trích xuất (model, CV đang chờ, giây/CV), 5 chỉ số (số lượt, điểm TB
  và trung vị, tỷ lệ 4–5★ và 1–2★, số góp ý), biểu đồ phân bố số sao và số lượt 30 ngày (kèm bảng), bảng
  theo ngôn ngữ / tuyến xử lý / mức đánh giá / khoảng điểm CV, danh sách góp ý lọc theo số sao, và nút
  tải `.jsonl` để chạy `export_feedback.py`. Trang không có liên kết công khai và không cho công cụ tìm
  kiếm lập chỉ mục; chỉ đưa khóa cho thành viên nhóm và giảng viên.
- Đánh giá mức độ hài lòng: `E:\klcn029-home\data\feedback\feedback.jsonl`; tổng hợp nhanh qua
  `<URL>/v1/feedback/summary` với header `X-API-Key`. Xuất báo cáo Excel (tổng quan, phân bố sao kèm
  biểu đồ, theo ngôn ngữ / tuyến xử lý / mức đánh giá / khoảng điểm CV / ngày, và danh sách góp ý):

  ```powershell
  python deployment/tools/export_feedback.py E:\klcn029-home\data\feedback\feedback.jsonl
  ```

  Tệp `feedback_report_<ngày>.xlsx` được ghi cạnh tệp nguồn. Có thể truyền nhiều tệp (laptop và Oracle)
  để gộp; đánh giá trùng mã chỉ giữ một. Cần `openpyxl` (`python -m pip install openpyxl`). Không đưa
  tệp `.jsonl` hay `.xlsx` này lên kho mã nguồn (đã có trong `.gitignore`).
- Cập nhật mã API: chạy lại `setup_home.ps1` (bỏ qua các tệp đã tải, build lại `api\`).
- Rút ổ ngoài khi dịch vụ đang chạy sẽ làm API dừng; dừng bằng Ctrl+C trước.
- Khi máy Oracle sẵn sàng: chuyển `EXTRACTION_API_URL` sang tên miền của Oracle và xóa `CV_WEB_INFRA_NOTE`.
  Đánh giá đã lưu trên laptop không tự chuyển sang Oracle; giữ tệp `feedback.jsonl` để gộp khi phân tích.
