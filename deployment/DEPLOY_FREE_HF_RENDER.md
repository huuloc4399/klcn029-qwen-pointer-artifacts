# Triển khai thử nghiệm miễn phí: API trên Hugging Face Spaces, web trên Render

Ngày soạn: 12/10/2026. Phương án này thay cho Render + RunPod (cần ngân sách) và cho Colab có
người vận hành (không chạy như dịch vụ). Mọi thành phần dùng gói miễn phí.

## 1. Kiến trúc

```text
Trình duyệt
  │  upload PDF + JD
  ▼
Render (free) ── cv_evaluation_web: Flask, kiểm tra PDF, CSRF, rate limit, che PII,
  │               chấm điểm deterministic baseline v1, hiển thị kết quả
  │  POST /v1/jobs  (X-API-Key)      ▲  GET /v1/jobs/{id} mỗi 2,5–5 giây
  ▼                                  │
Hugging Face Space (CPU basic, free) ── deployment/hf_space_api: FastAPI
     PDF router + OCR (PaddleOCR EN, Paddle + VietOCR VI)      ← các hàm cell OCR của Colab
     Qwen3-4B + Pointer Stage 2, gộp LoRA, GGUF, llama.cpp     ← cell sinh Pointer của Colab
     Parser v1 đóng băng + acceptance v2 → CVSchema 2.0 + evidence
  ▲
  │ tải GGUF một lần mỗi lần khởi động (HF_TOKEN read)
Hugging Face model repo private ── gguf/qwen3-4b-pointer-stage2-q4_k_m.gguf (+ manifest)
  ▲
  │ xuất một lần
Colab CPU ── training/colab/Qwen3_Pointer_GGUF_Export_Colab.ipynb
```

| Thành phần | Nền tảng | Chi phí | Giới hạn chính (theo chính sách hiện tại, cần kiểm tra lại khi tạo tài khoản) |
|---|---|---|---|
| Web | Render web service, plan free | 0 | 512 MB RAM; ngủ sau 15 phút không có truy cập (lần mở đầu chờ khoảng 1 phút); không có ổ đĩa lâu dài |
| API | Hugging Face Space Docker, CPU basic | 0 | 2 vCPU, 16 GB RAM; ngủ sau 48 giờ không dùng; ổ đĩa tạm |
| Model | Hugging Face model repo private | 0 | GGUF Q4_K_M khoảng 2,5 GB |
| Chuyển đổi model | Google Colab runtime CPU | 0 | Chạy một lần, khoảng 1 giờ |

Vì sao không dùng GPU miễn phí: Colab/Kaggle không cho phép biến notebook thành dịch vụ web công
khai, và nhóm đã chốt không dùng tunnel (`deployment/COLAB_ZERO_COST_PLAN.md`). Space CPU chạy được
24/7 hợp lệ nhưng không có GPU, nên model được gộp LoRA và lượng tử hóa để llama.cpp chạy trên CPU.

**Đánh đổi cần ghi trong báo cáo:**

- Số đo benchmark (P0, GOLD40) là của Qwen NF4 + LoRA trên GPU. Bản triển khai dùng GGUF đã gộp và
  lượng tử hóa. Notebook xuất model chỉ upload khi GGUF qua cổng độ trung thực: CVSchema hợp lệ không
  ít hơn P0, và Field Micro F1 giảm không quá 1 điểm trên N CV validation tổng hợp.
- Mỗi CV mất vài phút trên 2 vCPU (thời gian thật lấy từ bước 6 của notebook) và API xử lý tuần tự
  từng CV. Phù hợp để thử nghiệm với nhóm nhỏ, không phải dịch vụ đông người dùng.
- Bản miễn phí không lưu CV cho nghiên cứu (`CV_WEB_RESEARCH_ENABLED=0`), vì Render free không có ổ
  đĩa lâu dài. Muốn thu thập dữ liệu tự nguyện thì tiếp tục dùng luồng Colab + Drive.
- Matching hiện dùng deterministic baseline v1 trên web. Các chế độ M1/M2/M3 qua Groq mới có trong
  notebook Colab, chưa đưa lên web.

## 2. Chuẩn bị (một lần)

Tạo ba khóa. Không dán khóa vào mã nguồn, chat hay tài liệu.

| Khóa | Tạo ở đâu | Quyền | Dùng ở |
|---|---|---|---|
| `HF_TOKEN` (write) | huggingface.co → Settings → Access Tokens | write vào repo artifact và Space | Colab Secret khi xuất GGUF; biến môi trường máy local khi đẩy Space |
| `SPACE_HF_TOKEN` (read) | như trên, fine-grained, chỉ đọc repo artifact | read | Secret `HF_TOKEN` của Space để tải GGUF |
| `API_KEY` | tự sinh: `python -c "import secrets; print(secrets.token_urlsafe(32))"` | — | Secret của Space và biến `EXTRACTION_API_KEY` trên Render |

Nếu Space để private, cần thêm một token read cho web (`EXTRACTION_HF_TOKEN`), có quyền đọc Space.

## 3. Bước 1: Xuất GGUF bằng Colab (khoảng 1 giờ, runtime CPU)

1. Trên máy, tạo lại bundle và notebook để hash trong notebook khớp với bundle:

   ```bash
   python deployment/hf_space_api/fidelity/build_fidelity_bundle.py
   ```

   ```bash
   python training/colab/build_gguf_export_notebook.py
   ```

2. Mở `training/colab/Qwen3_Pointer_GGUF_Export_Colab.ipynb` trên Colab, chọn runtime CPU, thêm Secret
   `HF_TOKEN` (write).
3. Chạy lần lượt cell 1–7. Ở cell 3, upload `training/colab/artifacts/gguf_fidelity_bundle_v1.zip`.
4. Ở cell 6, ghi lại `fidelity` (F1, số CV hợp lệ, số giây mỗi CV). Nếu không qua cổng, đổi `QUANT`
   sang `Q5_K_M` hoặc `Q6_K` rồi chạy lại từ cell 2; bước gộp LoRA không phải chạy lại.
5. Cell 7 upload GGUF cùng manifest rồi in bốn dòng `GGUF_REPO_ID`, `GGUF_FILENAME`, `GGUF_REVISION`,
   `GGUF_SHA256`. Lưu bốn dòng này lại cho bước 2.

## 4. Bước 2: Đẩy API lên Hugging Face Space

Trên máy (PowerShell), đặt biến môi trường rồi chạy script. Script build bundle, tạo Space private
(Docker), đặt variables/secrets và upload:

```powershell
$env:HF_TOKEN = "<HF token write>"
$env:SPACE_HF_TOKEN = "<HF token read cho Space>"
$env:API_KEY = "<API key đã sinh>"
$env:GGUF_REPO_ID = "<từ cell 7>"; $env:GGUF_FILENAME = "<từ cell 7>"
$env:GGUF_REVISION = "<từ cell 7>"; $env:GGUF_SHA256 = "<từ cell 7>"
python deployment/hf_space_api/build_space.py --push <hf-username>/klcn029-cv-api --configure
```

Space tự build Docker. Lần đầu mất khoảng 20–30 phút vì phải biên dịch llama.cpp và cài OCR. Khi tab
Logs báo `Model ready`, kiểm tra:

```powershell
$env:EXTRACTION_API_URL = "https://<hf-username>-klcn029-cv-api.hf.space"
$env:EXTRACTION_API_KEY = $env:API_KEY
$env:EXTRACTION_HF_TOKEN = $env:SPACE_HF_TOKEN   # chỉ khi Space private
python deployment/hf_space_api/smoke_api.py
```

Kết quả mong đợi: `smoke: passed`. Script chỉ gửi một CV tổng hợp, không gửi CV thật.

Nếu build lỗi ở bước OCR, có thể build tạm không có OCR bằng cách đổi `ARG WITH_OCR=1` thành `0` trong
`deployment/hf_space_api/Dockerfile`. Khi đó PDF dạng ảnh sẽ bị từ chối với thông báo rõ ràng.

## 5. Bước 3: Đưa web lên Render

1. Render cần đọc mã từ GitHub. Commit và push các tệp của phương án này lên branch sẽ deploy, gồm
   `render.yaml`, `cv_evaluation_web/`, `baseline_extraction/privacy.py` và `baseline_extraction/schema.py`.
   Không push CV, nhãn, dữ liệu hay model.
2. Trên Render: **New → Blueprint**, chọn repo, Render đọc `render.yaml` (plan free).
3. Điền ba biến được đánh dấu `sync: false`:
   - `EXTRACTION_API_URL` = `https://<hf-username>-klcn029-cv-api.hf.space`
   - `EXTRACTION_API_KEY` = API key đã sinh
   - `EXTRACTION_HF_TOKEN` = token read, chỉ cần khi Space private; nếu không thì để trống
4. Sau khi deploy, mở `https://<tên-service>.onrender.com/api/health`; kết quả phải có
   `"pipeline_mode": "hf_space"`.

## 6. Kiểm tra đầu cuối trước khi gửi link

1. Một CV tiếng Anh dạng text: trang xử lý chuyển sang kết quả; khối "Pipeline đã xác minh" hiện
   `GGUF, CPU`, số token và thời gian model.
2. Một CV tiếng Việt dạng text.
3. Một PDF ảnh tiếng Anh: chọn ngôn ngữ "Tiếng Anh". Nếu để "Tự động", web sẽ nhắc chọn ngôn ngữ.
4. Một PDF ảnh tiếng Việt: kết quả phải có cảnh báo chất lượng OCR.
5. Gửi CV khi Space đang ngủ: web báo "Máy chủ trích xuất đang khởi động…". Thử lại sau vài phút.
6. Trang chủ không còn ô "đóng góp nghiên cứu"; thư mục `/tmp/cv-web-data/submissions` trên Render
   không có tệp nào.

## 7. Vận hành

- **Ngủ:** Space ngủ sau 48 giờ không dùng; lần dùng đầu tiên phải chờ container khởi động và tải lại
  GGUF (khoảng 3–5 phút). Render ngủ sau 15 phút. Không cài cron để giữ dịch vụ luôn thức.
- **Tác vụ:** job chỉ nằm trong bộ nhớ của Space, hết hạn sau 1 giờ và mất khi Space khởi động lại. Khi đó
  web báo người dùng gửi lại CV. Hàng đợi tối đa 8 CV (`MAX_PENDING_JOBS`); vượt quá thì trả lỗi 429.
- **Cập nhật model:** xuất GGUF mới bằng notebook, đổi `GGUF_FILENAME`, `GGUF_REVISION`, `GGUF_SHA256`
  trong Settings của Space rồi Restart. Space từ chối khởi động nếu hash GGUF không khớp.
- **Cập nhật mã API:** chạy lại `build_space.py --push`. Khi khởi động, API kiểm tra hash của Parser v1
  đóng băng và mọi tệp trong `RUNTIME_MANIFEST.json`.
- **Rollback web:** chọn bản deploy trước trong Render. Muốn quay về RunPod thì dùng
  `deployment/render.runpod.yaml`.

## 8. Dữ liệu và bảo mật

- Với PDF có lớp chữ, web che tên và thông tin liên hệ trước khi gửi văn bản sang API. PDF dạng ảnh
  được gửi nguyên bản để OCR; API che PII trên văn bản OCR trước khi đưa vào model.
- API không ghi CV xuống đĩa và không log nội dung CV. Mọi route `/v1` đều yêu cầu `X-API-Key`.
- Nên để Space private. Nếu proxy của Hugging Face không chấp nhận token khi gọi từ máy chủ, có thể
  chuyển Space sang public: mã API không chứa bí mật, model vẫn nằm trong repo private, và API vẫn
  khóa bằng `X-API-Key`.
- Link thử nghiệm chỉ gửi cho nhóm hoặc người tham gia đã được thông báo. Trước khi mở công khai, cần
  giảng viên duyệt nội dung đồng thuận và danh sách nhà cung cấp hạ tầng (Render, Hugging Face).

## 9. Kiểm thử cục bộ

```bash
python -m unittest deployment/hf_space_api/tests/test_api.py -v
```

```bash
python -m unittest discover -s cv_evaluation_web/tests -v
```

Test API cần `fastapi`, `httpx`, `pydantic`, `PyMuPDF`. Test dùng runtime giả nên không cần llama.cpp
hay model.
