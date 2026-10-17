# Thư mục minh chứng

Mỗi tài liệu ở đây trả lời câu hỏi "vì sao làm như vậy" cho một hoặc vài quyết định trong **Sổ quyết định và minh chứng KLCN029** (trang Claude Docs của nhóm), theo mã quyết định. Khi xong tất cả các mô-đun, các tài liệu này được gom vào báo cáo cuối; cột "Đưa vào" gợi ý chỗ đặt.

Quy ước:
- Mỗi tài liệu ghi ngày cập nhật, mã quyết định, và nguồn của từng số liệu (file, commit, lần chạy).
- Không chứa nội dung CV hay thông tin cá nhân; chỉ số liệu tổng hợp.
- Tài liệu tham khảo dùng đến phải có trong `../TAI_LIEU_THAM_KHAO.md`. Chỉ trích những tài liệu đã đối chiếu.
- Sửa nội dung thì ghi ngày cập nhật mới. Không xóa số liệu cũ; ghi rõ số đã thay bằng số nào.

## Mục lục

| Mã | Tài liệu | Nội dung | Đưa vào |
|---|---|---|---|
| I01 | [I01_LY_DO_CHON_MODEL.md](I01_LY_DO_CHON_MODEL.md) | Vì sao chấm bằng `qwen/qwen3.8-27b` qua Groq; chi phí đo được; rủi ro hạn mức và trạng thái Preview | Thiết lập thực nghiệm; hạn chế |
| I01 | [I01_TRANG_THAI_MODEL_GROQ.md](I01_TRANG_THAI_MODEL_GROQ.md) | Trạng thái model trên Groq theo từng ngày chạy, và cách ghi vào ngày chạy test | Thiết lập thực nghiệm; phụ lục |
| P05, P06 | [P06_CACH_LAP_DANH_SACH_TU.md](P06_CACH_LAP_DANH_SACH_TU.md) | Nguồn và nguyên tắc lập 4 danh sách từ; phạm vi tác động; kiểm soát việc chỉnh theo dữ liệu | Phương pháp P; hạn chế |
| M08 | [M08_DE_XUAT_KIEM_CHUNG_H1_H2.md](M08_DE_XUAT_KIEM_CHUNG_H1_H2.md) | Đề xuất cách kiểm chứng H1 và H2, chờ chốt với giảng viên | Phương pháp: thiết kế thực nghiệm |
| R02, R04 | [../PHAN_TICH_DO_NHAY_RUBRIC_DEV.md](../PHAN_TICH_DO_NHAY_RUBRIC_DEV.md) | Độ nhạy của trọng số rubric và luật C8 trên nhãn dev | Rubric; thảo luận |
| D01–D10 | [../MO_TA_QUY_TRINH_GAN_NHAN_CV_JD.md](../MO_TA_QUY_TRINH_GAN_NHAN_CV_JD.md) | Quy trình gán nhãn, độ đồng thuận, phân xử | Phương pháp: tập nhãn chuẩn |
| P01, M05, M06 | [../../downstream/eval/DANG_KY_TRUOC.md](../../downstream/eval/DANG_KY_TRUOC.md) | Đăng ký trước: cấu hình cố định, luật chọn `COVERAGE_MIN`, so sánh chính | Phương pháp: thiết kế thực nghiệm |
| — | [../TAI_LIEU_THAM_KHAO.md](../TAI_LIEU_THAM_KHAO.md) | Danh mục tài liệu và trạng thái đối chiếu | Tài liệu tham khảo |

## Còn thiếu (theo Sổ quyết định)

- R03: nguồn cho mô tả mức và ATS (Khải).
- R07: hạn chế của luật C7 so với người chấm.
- P07: số lần hỏi lại và số điểm được cứu của P (khi P chạy xong).
- M08: chốt đề xuất H1/H2 với GVHD (đã có bản đề xuất).
- M01–M04: đối chiếu bản gốc các tài liệu thống kê.
- Kết quả tập test và phép thử H3: thêm tài liệu riêng khi có.
