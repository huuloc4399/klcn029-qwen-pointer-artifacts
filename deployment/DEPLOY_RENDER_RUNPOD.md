# Triển khai baseline đầu cuối trên Render + RunPod Serverless

Phiên bản: `render_runpod_baseline_v1`
Model: `Qwen/Qwen3-4B-Instruct-2507` revision `1b4199c4f36b0cef378bfb12390c18780c18af4c`
Adapter: Pointer Stage 2 full v1, SHA-256 trọng số `8d68628e...a65f81`
Parser: `cvpointer_output_parser_v1`

## 1. Luồng được triển khai

```text
PDF + JD + consent
  -> Render kiểm tra PDF, lấy text và che PII nhận diện được
  -> RunPod /run (bất đồng bộ)
  -> PDF text hoặc PaddleOCR dự phòng
  -> Qwen3-4B 4-bit + QLoRA Pointer Stage 2
  -> Parser v1 -> CVSchema 2.0 + evidence
  -> matching baseline xác định
  -> Render trả điểm và góp ý
  -> lưu CV chỉ khi opt-in; cấp mã xóa
```

RunPod trả webhook khi hoàn tất. Trình duyệt cũng kiểm tra `/status`, vì vậy một webhook bị
lỡ không làm mất kết quả. Tệp opt-out được xóa khi hoàn tất/thất bại; tác vụ bỏ dở bị dọn
sau 3 giờ. Trang kết quả tạm hết hạn sau 24 giờ.

## 2. Tài khoản và bí mật cần có

1. GitHub để chứa **mã nguồn đã lọc dữ liệu** và build image GHCR.
2. Hugging Face để giữ adapter trong model repo private.
3. RunPod có phương thức thanh toán và API key.
4. Render có phương thức thanh toán, vì persistent disk không thuộc cấu hình web miễn phí.

Không commit `HF_TOKEN`, `RUNPOD_API_KEY`, PDF, ZIP adapter, `.env`, SQLite hoặc thư mục
`data`. `.gitignore` và `.dockerignore` ở gốc đã chặn các artifact này.

Nếu cần để công cụ trong workspace đọc token, tạo thư mục `.secrets/` (đã bị Git bỏ qua)
và lưu mỗi khóa trong một tệp một dòng. Không dán khóa vào chat. Ví dụ nạp khóa HF mà
không in giá trị:

```powershell
$env:HF_TOKEN = (Get-Content .secrets/hf_write.token -Raw).Trim()
```

## 3. Xuất bản adapter vào Hugging Face private repo

Tạo một model repository private, ví dụ:

```text
<hf-user>/klcn029-qwen-pointer-artifacts
```

Tạo token có quyền ghi, lưu vào biến môi trường, không dán vào chat hoặc mã nguồn:

```powershell
$env:HF_TOKEN = "..."
python -m pip install "huggingface_hub==1.32.0"
python deployment/runpod_qwen/publish_artifacts.py `
  --repo-id "<hf-user>/klcn029-qwen-pointer-artifacts"
```

Script kiểm tra CRC, SHA-256 ZIP và `adapter_model.safetensors` trước khi upload. Repo phải
có thư mục `final_adapter/` chứa adapter, tokenizer, run config và file manifest.

Sau khi upload xong, tạo một token **read-only** khác để gắn vào RunPod dưới tên `HF_TOKEN`.

## 4. Đưa mã nguồn lên GitHub private repo

Chỉ chạy sau khi kiểm tra `git status` không có CV hoặc khóa:

```powershell
git init
git add .gitignore .dockerignore .env.example render.yaml .github cv_evaluation_web deployment `
  baseline_extraction/__init__.py baseline_extraction/privacy.py baseline_extraction/schema.py `
  training/__init__.py training/evaluation/__init__.py `
  training/evaluation/frozen/cvpointer_output_parser_v1
git status
```

Không dùng `git add -A` trong lần commit đầu. Kiểm tra danh sách rồi mới commit và push.
Workflow `.github/workflows/runpod-worker.yml` build image:

```text
ghcr.io/<github-user>/klcn029-qwen-pointer:<commit-sha>
```

Nếu package GHCR private, cấp RunPod registry credential chỉ có quyền đọc package.

## 5. Tạo RunPod Serverless endpoint

1. Chọn **New Serverless Endpoint** và custom worker image ở bước 4.
2. GPU: lớp 16 GB trở lên; đặt `max workers = 1` cho pilot.
3. Flex workers: `0 -> 1`; active workers `0` để scale-to-zero.
4. Container disk: ít nhất 20 GB.
5. Gắn network volume tại `/runpod-volume` để cache Qwen và PaddleOCR, giảm cold start.
6. Environment variables:

| Key | Value |
|---|---|
| `ARTIFACT_REPO_ID` | `<hf-user>/klcn029-qwen-pointer-artifacts` |
| `ARTIFACT_REVISION` | `398ce7961eac9b3ccd1661116f9287bf2b0b6b20` |
| `HF_TOKEN` | token Hugging Face read-only |
| `PRELOAD_MODEL` | `1` |

7. Đặt execution timeout ít nhất 900 giây.
8. Tạo RunPod API key dành riêng cho endpoint, lưu lại `endpoint ID`.

Chạy kiểm tra trực tiếp endpoint bằng CV tổng hợp trước khi nối Render:

```powershell
$env:RUNPOD_ENDPOINT_ID = "..."
$env:RUNPOD_API_KEY = "..."
python deployment/runpod_qwen/smoke_endpoint.py
```

Kết quả đạt phải có `smoke: passed`, đúng model và
`cvpointer_output_parser_v1`. Script không gửi CV thật và không in API key.

Không đặt adapter hoặc API key trực tiếp vào Docker image. Worker tải adapter private, kiểm
tra hash, tải đúng base revision, khóa greedy decoding `max_new_tokens=768` và kiểm tra hash
Parser v1 trước khi nhận việc.

## 6. Tạo Render Blueprint

Trong Render chọn **New Blueprint**, kết nối GitHub repo và chọn `render.yaml`. Blueprint tạo:

- web service Docker;
- persistent disk 5 GB tại `/var/data`;
- secret Flask và webhook tự sinh;
- health check `/api/health`.

Render yêu cầu nhập hai secret:

| Key | Value |
|---|---|
| `RUNPOD_ENDPOINT_ID` | endpoint ID bước 5 |
| `RUNPOD_API_KEY` | API key RunPod dành cho web |

`PUBLIC_BASE_URL` được tự dựng từ `RENDER_EXTERNAL_HOSTNAME`. Nếu dùng domain riêng, đặt
thủ công `PUBLIC_BASE_URL=https://ten-mien-cua-ban` rồi redeploy.

## 7. Smoke test bắt buộc trước khi gửi link

1. Mở `/api/health`, xác nhận `status=ok`.
2. Dùng một PDF text tiếng Anh không chứa dữ liệu thật, không chọn đóng góp nghiên cứu.
3. Quan sát `IN_QUEUE -> IN_PROGRESS -> COMPLETED`.
4. Trang kết quả phải hiển thị:
   - `Qwen/Qwen3-4B-Instruct-2507`;
   - `cvpointer_output_parser_v1`;
   - `CVSchema 2.0`;
   - phương pháp `Qwen Pointer P0 + Parser v1 + deterministic matching baseline v1`.
5. Kiểm tra `/var/data/jobs/<token>` không còn `cv.pdf` và `jd.txt` sau khi hoàn tất.
6. Chạy lại với opt-in, lưu mã rút dữ liệu và xác nhận trang `/withdraw` xóa được PDF.
7. Chạy một PDF ảnh EN. Sau đó mới thử VI và ghi rõ cảnh báo OCR tiếng Việt.

Có thể tự động hóa bước 1-5 bằng CV tổng hợp, không chọn đóng góp nghiên cứu:

```powershell
python deployment/smoke_render_e2e.py https://<ten-service>.onrender.com
```

Chỉ coi baseline đã triển khai đầu cuối khi script in
`Render + RunPod end-to-end smoke test: PASSED`.

## 8. Tiêu chí mở cho ứng viên

- Smoke test đạt 2 ngôn ngữ và cả opt-in/opt-out.
- Không có CV/JD/raw output trong log Render, RunPod hoặc GitHub Actions.
- Giảng viên duyệt nội dung consent, nhà cung cấp, thời hạn lưu và người truy cập.
- Đặt spending limit trên RunPod và giới hạn hiện tại là 5 lượt/IP/giờ.
- Tải xuống bản sao dữ liệu nghiên cứu định kỳ; persistent disk một mình không thay thế backup.

## 9. Giới hạn baseline v1

- OCR tiếng Việt dự phòng đang dùng PaddleOCR Latin; pilot của nhóm cho thấy chất lượng thấp
  hơn VietOCR hybrid. Kết quả có OCR VI được gắn `ocr_quality_warning` và chưa dùng để tuyên
  bố độ chính xác.
- Matching là baseline quy tắc xác định, chưa phải gold-calibrated ranking.
- P0 không tự sửa JSON/span lỗi. Parser trả `needs_review`; web không âm thầm dùng raw output.
- Số liệu validation/test đã khóa vẫn là bằng chứng chính của model; traffic web không có gold
  label nên không được gọi là accuracy.
