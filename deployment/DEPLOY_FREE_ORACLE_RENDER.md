# Triển khai miễn phí: API trên Oracle Cloud Always Free, web trên Render

Ngày soạn: 12/10/2026. Thay cho phương án Hugging Face Space (`DEPLOY_FREE_HF_RENDER.md`). Từ khoảng
tháng 7/2026, tài khoản Hugging Face miễn phí không còn tạo được Docker Space trên CPU basic; tạo Space
trả lỗi `402 Payment Required` và yêu cầu gói PRO (9 USD/tháng). Repo model private trên Hugging Face
vẫn dùng bình thường để lưu GGUF.

## 1. Kiến trúc

```text
Trình duyệt ── Render (free): cv_evaluation_web, không đổi
                 │  POST /v1/jobs, GET /v1/jobs/{id}  (X-API-Key, HTTPS)
                 ▼
Oracle Cloud VM Always Free: Ampere A1, 2 OCPU, 12 GB RAM, Ubuntu 24.04 aarch64
  Caddy (HTTPS tự động, Let's Encrypt) → API FastAPI (cùng mã với deployment/hf_space_api)
  GGUF, trọng số VietOCR/Paddle lưu trong volume Docker, chỉ tải lần đầu
                 ▲ tải GGUF bằng token read
Hugging Face model repo private: gguf/qwen3-4b-pointer-stage2-q4_k_m.gguf
```

Mã API giữ nguyên. Thư mục `deployment/oracle_api/` chỉ thêm phần cho máy ARM:

| Tệp | Vai trò |
|---|---|
| `Dockerfile` | build llama.cpp cho CPU của VM (NEON), cài Paddle từ index chính thức của Paddle vì PyPI không có bản aarch64 |
| `docker-compose.yml`, `Caddyfile` | API + Caddy; Caddy tự lấy và gia hạn chứng chỉ HTTPS |
| `.env.example` | mẫu biến môi trường; bản thật `.env` chỉ nằm trên VM |
| `setup_vm.sh` | cài Docker, mở cổng 80/443 trong firewall của VM |
| `fidelity_check.py` (từ `deployment/hf_space_api/fidelity/`) | chạy lại cổng độ trung thực ngay trên VM |
| `build_bundle.py` | gom mã API + các tệp trên thành `dist/oracle_api` để chép lên VM |

**Giới hạn và đánh đổi (cần ghi trong báo cáo):**

- Hạn mức Always Free của Ampere A1 vừa bị giảm từ 4 OCPU/24 GB xuống 2 OCPU/12 GB. Chỉ tạo đúng
  2 OCPU, 12 GB để không phát sinh phí. Đăng ký cần thẻ để xác minh.
- Máy ảo có thể báo `Out of host capacity` khi tạo. Khi đó thử lại vào lúc khác hoặc đổi
  availability domain.
- Oracle có thể thu hồi máy Always Free "nhàn rỗi" nếu trong 7 ngày CPU, mạng và bộ nhớ đều dưới 20%.
  API giữ model trong RAM (khoảng 4 GB trên 12 GB) nên bộ nhớ thường trên ngưỡng này, nhưng vẫn nên kiểm
  tra máy định kỳ.
- Số đo fidelity và thời gian trong manifest GGUF là trên Colab x86. llama.cpp trên ARM dùng kernel
  khác, nên greedy output có thể lệch nhẹ. Bước 6 đo lại trên chính VM; báo cáo dùng số đo này.
- Mỗi CV dự kiến khoảng 5–7 phút với 2 OCPU, API xử lý tuần tự. Hàng đợi tối đa 8 CV.

## 2. Chuẩn bị khóa

| Khóa | Dùng ở | Ghi chú |
|---|---|---|
| `HF_TOKEN` read | `.env` trên VM | fine-grained, chỉ đọc repo `huuloc4399/klcn029-qwen-pointer-artifacts` |
| `API_KEY` | `.env` trên VM và `EXTRACTION_API_KEY` trên Render | chuỗi ngẫu nhiên, **không** dùng token Hugging Face |

Sinh `API_KEY` trên máy của bạn rồi chỉ dán trực tiếp vào `.env` và Render:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 3. Tạo máy ảo

1. Đăng ký Oracle Cloud Free Tier, chọn home region (máy Always Free phải nằm ở home region).
2. Compute → Instances → Create instance:
   - Image: **Canonical Ubuntu 24.04** (bản aarch64).
   - Shape: **VM.Standard.A1.Flex**, 2 OCPU, 12 GB RAM.
   - Networking: VCN mới, subnet public, **Assign a public IPv4 address**.
   - SSH keys: tải lên public key. Trên Windows, tạo key bằng lệnh `ssh-keygen -t ed25519`, rồi
     chọn tệp `C:\Users\<bạn>\.ssh\id_ed25519.pub`.
   - Boot volume: giữ mặc định (50 GB, nằm trong hạn mức free 200 GB).
3. Mở cổng ở VCN: Networking → Virtual cloud networks → VCN → Security Lists → Default → Add Ingress
   Rules: hai rule `0.0.0.0/0`, TCP, destination port `80` và `443`.
4. Ghi lại public IP. Nếu không có tên miền riêng, dùng `API_DOMAIN=<ip-đổi-dấu-chấm-thành-gạch>.sslip.io`,
   ví dụ IP `129.146.10.20` thì `129-146-10-20.sslip.io`. Caddy vẫn lấy được chứng chỉ HTTPS cho tên này.

## 4. Chép mã lên VM

Trên máy Windows, ở thư mục dự án:

```bash
python deployment/oracle_api/build_bundle.py
```

```bash
scp dist/oracle_api.tar.gz ubuntu@<public-ip>:~
```

```bash
ssh ubuntu@<public-ip> "mkdir -p ~/klcn029-api && tar -xzf ~/oracle_api.tar.gz -C ~/klcn029-api"
```

Lệnh giải nén ghi đè mã cũ nhưng không đụng tới `.env`, nên dùng được cho cả lần đầu và lần cập nhật.

## 5. Cài đặt và khởi động trên VM

```bash
ssh ubuntu@<public-ip>
```

```bash
bash ~/klcn029-api/setup_vm.sh
```

Đăng xuất (`exit`), SSH lại để nhóm `docker` có hiệu lực, rồi tạo `.env`:

```bash
cd ~/klcn029-api && cp .env.example .env && nano .env
```

Điền `API_DOMAIN`, `API_KEY`, `HF_TOKEN`, `GGUF_REVISION`. `GGUF_REPO_ID`, `GGUF_FILENAME`, `GGUF_SHA256` đã
điền sẵn theo bản xuất ngày 12/10/2026. Sau đó build và chạy. Lần đầu mất khoảng 30–60 phút vì phải
biên dịch llama.cpp và cài OCR trên 2 nhân ARM:

```bash
docker compose up -d --build
```

```bash
docker compose logs -f api
```

Chờ dòng `Model ready`. Lần đầu API tải GGUF 2,5 GB vào volume; các lần khởi động sau không tải lại.
Kiểm tra từ máy bất kỳ: mở `https://<API_DOMAIN>/health`, phải thấy `"model": "ready"`.

Nếu bước cài OCR lỗi, đặt `WITH_OCR=0` trong `.env` rồi chạy lại `docker compose up -d --build`. Khi đó
PDF dạng ảnh bị từ chối với thông báo rõ ràng; PDF có lớp chữ vẫn chạy.

## 6. Đo lại cổng độ trung thực trên VM (khoảng 1 giờ)

Dừng API để phép đo không tranh CPU, chạy 10 CV tổng hợp, rồi bật lại:

```bash
docker compose stop api
```

```bash
docker compose run --rm -v ./gguf_fidelity_bundle_v1.zip:/tmp/bundle.zip:ro api python fidelity_check.py /tmp/bundle.zip --samples 10
```

```bash
docker compose start api
```

Lưu JSON cuối cùng vào báo cáo. Yêu cầu `"passed": true`: số CVSchema hợp lệ không ít hơn P0 và Field
Micro F1 giảm không quá 1 điểm. Nếu không qua, xuất lại GGUF với `QUANT = "Q5_K_M"` bằng notebook rồi
cập nhật `GGUF_FILENAME`, `GGUF_REVISION`, `GGUF_SHA256` trong `.env`.

## 7. Kiểm tra API từ máy Windows

```powershell
$env:EXTRACTION_API_URL = "https://<API_DOMAIN>"
$env:EXTRACTION_API_KEY = "<API_KEY>"
python deployment/hf_space_api/smoke_api.py
```

Kết quả mong đợi: `smoke: passed`. Script chỉ gửi một CV tổng hợp. Không đặt `EXTRACTION_HF_TOKEN`.

## 8. Web trên Render

Như mục 5 của `DEPLOY_FREE_HF_RENDER.md` (Blueprint, branch `deploy/free-tier`, `render.yaml`), với:

- `EXTRACTION_API_URL` = `https://<API_DOMAIN>`
- `EXTRACTION_API_KEY` = `API_KEY`
- `EXTRACTION_HF_TOKEN` = để trống

Mở `https://<tên-service>.onrender.com/api/health`, phải có `"pipeline_mode": "hf_space"` (tên chế độ
giữ nguyên vì web gọi cùng một API). Sau đó chạy các ca kiểm tra đầu cuối ở mục 6 của
`DEPLOY_FREE_HF_RENDER.md`.

## 9. Vận hành

- **Cập nhật mã API:** chạy lại `build_bundle.py` và hai lệnh `scp`/`ssh … tar` ở mục 4, rồi trên VM
  chạy `docker compose up -d --build`.
- **Cập nhật model:** sửa ba biến `GGUF_*` trong `.env`, rồi `docker compose up -d`. API từ chối
  khởi động nếu hash GGUF không khớp.
- **Khởi động lại máy:** container tự chạy lại (`restart: unless-stopped`).
- **Nhật ký:** `docker compose logs --tail 200 api`. API không log nội dung CV.
- **Hàng đợi:** trang xử lý hiện số CV đứng trước và thời gian dự kiến (dạng khoảng). Ước tính lấy
  trung vị thời gian của 10 CV gần nhất; khi chưa có CV nào thì dùng `JOB_SECONDS_ESTIMATE` (mặc định
  330 giây, số đo của bản Q4_K_M). Sau khi có số đo trên VM ở bước 6, có thể đặt biến này trong `.env`.
- **Đánh giá mức độ hài lòng:** web chuyển mỗi đánh giá (1–5 sao, góp ý đã che email/số điện thoại,
  điểm, ngôn ngữ, tuyến xử lý, thời gian model) sang API, API ghi vào
  `/data/feedback/feedback.jsonl` trong volume. Không có CV, JD hay mã tác vụ. Xem tổng hợp:

  ```powershell
  curl.exe -H "X-API-Key: <API_KEY>" https://<API_DOMAIN>/v1/feedback/summary
  ```

  Tải toàn bộ về máy để phân tích cho báo cáo (chạy trên VM, rồi `scp` tệp về):

  ```bash
  docker compose cp api:/data/feedback/feedback.jsonl ./feedback.jsonl
  ```

  Sau khi `scp` tệp về máy, xuất báo cáo Excel bằng
  `python deployment/tools/export_feedback.py feedback.jsonl` (xem `DEPLOY_HOME_TUNNEL.md` mục 7).
  Mỗi kết quả chỉ nhận một đánh giá. Đánh giá chứa góp ý tự do, nên xử lý như dữ liệu người tham gia:
  không đưa tệp này lên kho mã nguồn.
- **Bảo mật:** chỉ mở cổng 22, 80, 443. Mọi route `/v1` yêu cầu `X-API-Key`. `.env` không được commit
  (đã có trong `.gitignore`) và không được đưa vào image (`.dockerignore`).
- Nếu lộ `API_KEY` hoặc `HF_TOKEN`: tạo khóa mới, sửa `.env`, `docker compose up -d`, cập nhật Render.
