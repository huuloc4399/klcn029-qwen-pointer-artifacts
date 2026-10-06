# RunPod worker: Qwen Pointer P0

Queue-based worker nhận `source_text` hoặc `pdf_base64`, tạo đúng prompt đã dùng khi train,
chạy Qwen3-4B + adapter Pointer Stage 2, rồi áp dụng frozen Parser v1. Worker chỉ trả
CVSchema 2.0 đã hợp lệ, evidence và manifest; không trả raw generation cho web.

## Build

Từ gốc repository:

```bash
docker build -f deployment/runpod_qwen/Dockerfile -t klcn029-qwen-pointer:local .
```

Biến môi trường bắt buộc:

```text
ARTIFACT_REPO_ID=<private Hugging Face repo>
ARTIFACT_REVISION=<artifact commit SHA>
HF_TOKEN=<read-only token>
```

Input native text:

```json
{"input":{"language":"en","source_text":"SUMMARY\nBackend developer...","page_count":1,"native_text_pages":1}}
```

Input PDF cần OCR dùng `pdf_base64`, tối đa 6 MB và 12 trang. Với PDF ảnh phải chọn `en`
hoặc `vi`; không dùng `auto` vì worker không có đủ chữ để nhận diện ngôn ngữ trước OCR.

## Test hợp đồng không cần GPU

```bash
python deployment/runpod_qwen/test_handler.py -v
```
