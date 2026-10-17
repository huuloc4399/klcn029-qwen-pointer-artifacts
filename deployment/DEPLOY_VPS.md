# Triển khai toàn bộ demo lên một VPS

Ngày soạn: 18/10/2026. Áp dụng cho VPS Ubuntu 24.04 (hoặc 22.04), x86_64, ảo hóa KVM, tối thiểu 2 vCPU, 8 GB RAM và 30 GB ổ đĩa. Thay cho các phương án Render + Oracle, Hugging Face Space và laptop + tunnel. Mã của web và API không đổi.

## 1. Kiến trúc

```text
Trình duyệt ──HTTPS──► Caddy (cổng 80/443, tự lấy chứng chỉ)
                          │
                          ▼
                       web (Flask, gunicorn :10000)  ──HTTPS──► Groq (chấm điểm theo rubric)
                          │  http://api:7860, X-API-Key, chỉ trong mạng nội bộ Docker
                          ▼
                       api (FastAPI): PDF → OCR (PaddleOCR/VietOCR) → Qwen3-4B Pointer GGUF (llama.cpp) → Parser v1
```

- Chỉ Caddy mở ra Internet. API trích xuất nằm trong mạng nội bộ Docker, không ai từ ngoài gọi trực tiếp được.
- Truy xuất RAG dùng BM25 có sẵn trong web, không chạy thêm model nhúng, để tiết kiệm RAM.
- Bộ cài gồm `deployment/vps/` (Compose, Caddy, Dockerfile của API, script cài đặt) và script đóng gói `deployment/vps/build_bundle.py`.

## 2. Chuẩn bị

| Cần | Ghi chú |
|---|---|
| VPS | Ubuntu 24.04, có quyền root, **KVM** (OpenVZ/LXC thường không chạy được Docker); cổng 80, 443 không bị chặn ở tường lửa của nhà cung cấp |
| Máy tính của nhóm | Windows có sẵn `ssh` và `scp` trong PowerShell; Python để đóng gói và chạy kiểm tra |
| Token Hugging Face | Loại fine-grained, **chỉ đọc**, có quyền với repo artifact riêng tư (để tải GGUF). Không dùng token có quyền ghi |
| Khóa Groq | Khóa đang dùng cho các chiến lược M1–M4 và P |

**Không gửi mật khẩu VPS, token hay nội dung `.env` vào cuộc trò chuyện hay nhóm chat.** Mỗi người tự nhập trên máy của mình.

## 3. Các bước

**Bước 1: đóng gói trên máy của nhóm** (từ thư mục gốc dự án):

```powershell
python deployment/vps/build_bundle.py
scp dist/vps_bundle.tar.gz root@<IP>:~
```

Gói không chứa `.env`, thư mục `.secrets`, hay dữ liệu thật trong `cv_evaluation_web/data`. Script sẽ dừng nếu phát hiện file khóa lọt vào.

**Bước 2: đăng nhập VPS, giải nén và cài đặt**

```bash
ssh root@<IP>
mkdir -p ~/klcn029 && tar -xzf ~/vps_bundle.tar.gz -C ~/klcn029 && cd ~/klcn029
bash setup_vps.sh
```

Script này làm 4 việc:
1. Kiểm tra máy là x86_64 và không phải OpenVZ/LXC.
2. Cài Docker và Compose.
3. Tạo 6 GB swap.
4. Bật tường lửa: chỉ mở cổng 22, 80, 443.

Cuối cùng script in loại CPU và RAM; **chụp lại phần này để ghi vào báo cáo**. Xong thì thoát ra rồi đăng nhập lại.

**Bước 3: điền `.env`**

```bash
cd ~/klcn029 && cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # chạy 3 lần: API_KEY, CV_WEB_SECRET_KEY, CV_WEB_ADMIN_KEY
nano .env
```

- `DOMAIN`: nếu không có tên miền, dùng IP đổi dấu chấm thành gạch ngang, thêm `.sslip.io`. Ví dụ IP `103.20.30.40` thì ghi `103-20-30-40.sslip.io`.
- `HF_TOKEN`, `GROQ_API_KEY`: dán token và khóa của nhóm.
- `LLAMA_THREADS`: bằng số vCPU của VPS (gói 2 nhân thì để 2).
- `WITH_OCR=1` nếu muốn nhận PDF dạng ảnh. Nếu bị thiếu RAM ở bước 5, đổi thành 0.

**Bước 4: dựng và chạy**

```bash
docker compose up -d --build
docker compose logs -f api      # chờ dòng "Model ready"; Ctrl+C để thoát xem log
```

- **Lần đầu mất khoảng 20–40 phút:** biên dịch llama.cpp cho đúng CPU của VPS, cài Paddle/Torch, tải GGUF 2,5 GB. Các lần khởi động sau không tải lại.
- API kiểm tra hash của GGUF và của toàn bộ file mã khi khởi động. Nếu báo sai hash, không bỏ qua bước kiểm tra; xem mục 5.

**Bước 5: kiểm tra**

1. Mở `https://<DOMAIN>` trên trình duyệt. Trang chủ phải hiện, có ổ khóa HTTPS.
2. Từ máy của nhóm, chạy thử đầu cuối với một CV tổng hợp (không dùng CV thật):
   ```powershell
   python deployment/smoke_render_e2e.py https://<DOMAIN>
   ```
3. Trên VPS, ghi lại tài nguyên khi đang xử lý một CV:
   ```bash
   docker stats --no-stream
   free -h
   ```
4. Thử 3 loại CV: tiếng Anh có lớp chữ, tiếng Việt có lớp chữ, PDF dạng ảnh. Ghi thời gian xử lý (trang kết quả có mục "Pipeline đã xác minh" với số giây chạy model).

## 4. Vận hành

| Việc | Lệnh (trên VPS, trong `~/klcn029`) |
|---|---|
| Xem log | `docker compose logs --tail 200 web` (hoặc `api`, `caddy`) |
| Khởi động lại | `docker compose restart` |
| Cập nhật mã | Trên máy nhóm: đóng gói lại và `scp`. Trên VPS: `tar -xzf ~/vps_bundle.tar.gz -C ~/klcn029 && docker compose up -d --build` (giải nén đè không động tới `.env`) |
| Dừng tạm | `docker compose stop` |
| Sau khi bảo vệ | Tải về các đánh giá mức hài lòng qua trang `/admin`, rồi hủy VPS |

- Đánh giá mức hài lòng nằm trong volume `web_data`. Bản lưu CV cho nghiên cứu mặc định tắt (`CV_WEB_RESEARCH_ENABLED=0`). Chỉ bật khi nhóm đã thống nhất cách bảo quản dữ liệu trên VPS.
- Web và API không ghi nội dung CV vào log.

## 5. Sự cố thường gặp

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Trình duyệt không mở được trang, Caddy báo lỗi chứng chỉ | Cổng 80/443 bị chặn ở tường lửa hoặc lớp chống DDoS của nhà cung cấp; hoặc `DOMAIN` sai | Mở cổng trong trang quản lý của nhà cung cấp; kiểm tra `DOMAIN` khớp IP. Caddy tự thử lại và tự chuyển sang ZeroSSL nếu Let's Encrypt từ chối |
| API bị tắt giữa chừng, log có "Killed" hoặc mã 137 | Thiếu RAM | Kiểm tra swap (`swapon --show`); đặt `WITH_OCR=0` rồi `docker compose up -d --build` |
| Xử lý một CV quá lâu | Ít vCPU | Kiểm tra `LLAMA_THREADS` bằng số vCPU; nâng gói VPS nếu cần |
| API báo sai hash GGUF hoặc file mã | Tải lỗi, hoặc gói cũ | Xóa file tải dở (`docker compose down` rồi `docker volume rm klcn029_api_cache`), đóng gói lại từ đúng commit |
| Web báo không kết nối được máy chủ trích xuất | API chưa sẵn sàng (đang tải model), hoặc `API_KEY` sai | Chờ dòng "Model ready"; kiểm tra `.env` |

## 6. Ghi vào báo cáo

- Cấu hình VPS (nhà cung cấp, vị trí máy, vCPU, RAM, loại CPU theo output của `setup_vps.sh`), ngày triển khai, commit của gói.
- Thời gian xử lý một CV theo từng loại PDF, RAM lúc cao nhất.
- Giới hạn: một CV được xử lý tại một thời điểm; model chạy trên CPU; bản demo dùng Pointer P1, khác với B0 là cấu hình có độ chính xác trích xuất cao nhất trên GOLD40 (`reports/PROJECT_SCOPE_AND_DECISIONS.md` §8.2).
