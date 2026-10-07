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
  -> frozen Parser v1 -> real-CV acceptance v2 -> CVSchema 2.0 + evidence
  -> deterministic matching baseline
  -> tải ZIP kết quả
  -> chỉ lưu PDF/JD vào Drive khi consent=true
```

Lớp acceptance không sửa Parser v1. Nó chỉ cho phép tiếp tục khi lỗi duy nhất là allowlist
soft skill cũ từ dữ liệu synthetic, trong khi cấu trúc, span, CVSchema và evidence đều hợp
lệ. Quyết định này được lưu riêng để báo cáo benchmark vẫn dùng đúng Parser v1 đóng băng.

Matching mặc định là B1 deterministic. Giao diện cũng cho phép chọn M1 zero-shot, M2
few-shot và M3 RAG thử nghiệm qua Groq Qwen 3.8 27B. Ba chế độ API chỉ chạy khi có
`GROQ_API_KEY` trong Colab Secrets và người vận hành bật đồng thuận gửi CVSchema đã bỏ
`personal_info` cùng JD đến Groq. Điểm ATS vẫn do bộ phân tích PDF deterministic cung cấp.

Notebook giao diện chính:

```text
training/colab/Qwen3_Pointer_Colab_UI_Demo.ipynb
```

Notebook tuyến tính dùng để kiểm tra từng bước và làm nguồn cho giao diện:

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

1. Mở notebook giao diện và chạy cell 1.
2. Nếu pip yêu cầu restart, restart runtime rồi chạy lại từ cell 2.
3. Chạy cell 2–5 để xác minh adapter, Parser v1 và nạp model.
4. Chạy cell 6 để mở giao diện CV Insight.
5. Chọn đúng một PDF, dán JD ít nhất 80 ký tự, chọn ngôn ngữ và consent rồi bấm
   **Đánh giá CV**.
6. Chỉ dùng kết quả khi giao diện báo hoàn tất. Colab tải ZIP chứa CVSchema, evidence,
   kết quả matching, routing log và manifest.

Khi consent được bật, notebook lưu bản nghiên cứu tại:

```text
MyDrive/KLCN029/pointer_e2e_demo/
├── submission_index.jsonl
└── submissions/<submission_id>/
    ├── cv.pdf
    ├── jd.txt
    ├── consent.json
    ├── receipt.json
    └── result/
```

`consent.json` ghi phiên bản đồng thuận, thời điểm, mục đích, hash PDF/JD và dữ liệu được
giữ lại. Giao diện trả mã rút dữ liệu cho ứng viên; Drive chỉ lưu hash của mã này. Nếu
consent tắt, PDF/JD không được sao chép vào thư mục nghiên cứu. Nếu baseline lỗi sau khi
đã nhận một PDF/JD hợp lệ, hồ sơ có consent vẫn được giữ cùng `failure.json`; nhờ đó nhóm
không làm mất các trường hợp thật mà OCR, model hoặc parser chưa xử lý được.

Khi thử CV tiếp theo trong cùng runtime, thay PDF/JD ngay trên giao diện và bấm lại; không
cần nạp lại model. Notebook tuyến tính vẫn được giữ để truy vết lỗi từng công đoạn.

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
