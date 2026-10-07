# Phương án Colab miễn phí cho baseline đầu cuối

Ngày chốt: 07/10/2026

## Quyết định

Tạm dừng triển khai Render + Runpod vì đề tài không có ngân sách hạ tầng. Adapter và mã
deployment đã được giữ lại để có thể tái sử dụng sau này. Luồng đang dùng là notebook Colab
có người vận hành, không mở tunnel hoặc web server công khai.

## Luồng chạy

```text
Người vận hành mở Colab T4
  -> nhập JD và tùy chọn consent
  -> upload một CV PDF
  -> PDF text / OCR EN / OCR VI hybrid
  -> Qwen3-4B + Pointer Stage 2 adapter
  -> frozen Parser v1 -> CVSchema 2.0 + evidence
  -> deterministic matching baseline
  -> tải ZIP kết quả
  -> chỉ lưu PDF/JD vào Drive khi consent=true
```

Notebook chính:

```text
training/colab/Qwen3_Pointer_EndToEnd_CV_JD_Demo_Colab.ipynb
```

## Chuẩn bị một lần

1. Tạo Hugging Face token chỉ có quyền đọc repo private
   `huuloc4399/klcn029-qwen-pointer-artifacts`.
2. Trong Colab chọn biểu tượng chìa khóa **Secrets**, tạo `HF_TOKEN`, bật quyền truy cập
   notebook. Không viết token trực tiếp vào cell.
3. Chọn runtime T4 GPU.
4. Giữ adapter trên Drive nếu đã có; notebook ưu tiên Drive và chỉ tải từ Hugging Face khi
   adapter không tồn tại.

## Cách chạy một CV

1. Mở notebook và chạy cell 1.
2. Nếu pip yêu cầu restart, restart runtime rồi chạy lại từ cell 2.
3. Ở cell 2 nhập `JD_TEXT`, chọn `LANGUAGE`; giữ `RESEARCH_CONSENT=False` khi chỉ demo.
4. Chạy cell 3–6 để xác minh adapter, OCR/parser và nạp model.
5. Cell 4 yêu cầu upload đúng một PDF.
6. Chạy cell 7–8. Chỉ dùng kết quả khi parser báo `status=success`.
7. Colab tải ZIP chứa CVSchema, evidence, kết quả matching, routing log và manifest.

Khi thử CV tiếp theo trong cùng runtime, chạy lại cell 2, 4, 7 và 8; không cần nạp lại model
ở cell 6 nếu cấu hình không đổi.

## Thu thập CV tự nguyện không cần server model

Có thể dùng Google Form để nhận CV, JD, ngôn ngữ và hai checkbox consent. Form chỉ làm
nhiệm vụ thu thập vào Drive; nhóm chạy Colab theo lô hoặc từng hồ sơ sau đó. Người tham gia
không nhận điểm ngay lập tức. Các trường tối thiểu:

- mã người tham gia tùy chọn;
- PDF CV;
- JD hoặc vị trí mục tiêu;
- ngôn ngữ EN/VI;
- đồng ý xử lý để đánh giá;
- đồng ý riêng cho đóng góp nghiên cứu;
- phiên bản chính sách dữ liệu.

Không bật chia sẻ công khai thư mục Drive chứa CV. Chỉ thành viên được phân công có quyền
truy cập. Khi xử lý một CV không đồng ý nghiên cứu, không sao chép PDF vào kho kết quả.

## Giới hạn cần ghi trong báo cáo

- Colab miễn phí không bảo đảm GPU, giới hạn sử dụng thay đổi và runtime có thể bị ngắt.
- Đây là demo/batch có người vận hành, không phải dịch vụ 24/7.
- Không dùng Gradio, ngrok hoặc tunnel để biến runtime miễn phí thành public web service.
- Thời gian đo trên Colab gồm inference của model; thời gian chờ người vận hành không đưa
  vào latency hệ thống.
- Kết quả traffic thật không có gold label nên không được gọi là accuracy.
