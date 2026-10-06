# Trạng thái baseline Render + RunPod Serverless

Ngày khóa: 06/10/2026

## Phạm vi đã hoàn thành

```text
PDF + JD + consent
  -> Render/Flask: kiểm tra PDF, CSRF, rate limit, PII masking
  -> RunPod /run: hàng đợi GPU bất đồng bộ
  -> PDF text hoặc PaddleOCR fallback
  -> Qwen3-4B-Instruct-2507 + Pointer Stage 2 adapter
  -> frozen Parser v1 -> CVSchema 2.0 + evidence
  -> deterministic CV-JD matching baseline v1
  -> điểm, kỹ năng khớp/thiếu và góp ý
  -> lưu nghiên cứu chỉ khi opt-in; hỗ trợ mã rút dữ liệu
```

Mô đun Qwen chỉ làm trích xuất. Điểm và gợi ý do mô đun matching riêng tạo ra từ
CVSchema đã được kiểm tra.

## Artifact đã khóa

| Thành phần | Giá trị |
|---|---|
| Base model | `Qwen/Qwen3-4B-Instruct-2507` |
| Base revision | `1b4199c4f36b0cef378bfb12390c18780c18af4c` |
| Adapter ZIP SHA-256 | `274aeb95e78f5717b04af9fd0045e5215fd247533bd9572c73c73e8242f86b4b` |
| Adapter weights SHA-256 | `8d68628e382593132010f20fb12cbb18d9477ca034c154811d109ec075a65f81` |
| Hugging Face artifact revision | `398ce7961eac9b3ccd1661116f9287bf2b0b6b20` |
| Parser | `cvpointer_output_parser_v1` |
| Prompt contract | `cvpointer_prompt_v1` |
| Decoding | greedy, `max_new_tokens=768` |

## Bằng chứng kiểm thử local

- Web: 8/8 test đạt.
- Worker không GPU: 2/2 contract test đạt.
- ZIP adapter: CRC đạt, đúng hash trọng số và cấu trúc `final_adapter/`.
- Parser: ba hash nguồn khớp manifest worker.
- `render.yaml` và GitHub Actions workflow đọc được bằng YAML parser.
- HTTP Waitress thật: GET trang chủ, CSRF upload, PDF tổng hợp, kết quả opt-out,
  CSP và `X-Frame-Options` đều đạt.
- Git staging dùng danh sách trắng; không có PDF, DOCX, notebook, ZIP model,
  SQLite, thư mục dữ liệu hoặc mẫu khóa API.

## Chưa thể xác nhận nếu chưa có cloud account

- Docker image build thành công trên GitHub Actions.
- Qwen nạp thành công trên GPU RunPod và vượt smoke endpoint.
- Render gọi RunPod, nhận job hoàn tất và vượt smoke đầu cuối.
- Thời gian cold start, thời gian model, delay hàng đợi và chi phí mỗi CV.

Các mục này phải lấy từ lần chạy thật. Web đã ghi `input_tokens`, `generated_tokens`,
`model_runtime_seconds`, RunPod delay/execution time và tuyến OCR vào kết quả tạm hoặc
hồ sơ opt-in để phục vụ báo cáo.

## Cổng chất lượng trước khi phát link

1. `smoke_endpoint.py` in `smoke: passed`.
2. `smoke_render_e2e.py` in `Render + RunPod end-to-end smoke test: PASSED`.
3. Kiểm tra opt-in, mã rút và opt-out trên disk Render.
4. Thử ít nhất một CV EN text, một CV VI text và một PDF ảnh EN.
5. CV ảnh VI phải hiện cảnh báo chất lượng OCR; chưa dùng để tuyên bố độ chính xác.
