# Downstream: chấm điểm, so khớp CV–JD và nhãn tham chiếu

Thư mục này chứa các module sau trích xuất CV: dữ liệu JD, nhãn chấm của người, rubric, so khớp,
chấm điểm và RAG. Kế hoạch chi tiết nằm ở
[HUONG_DAN_HOAN_THIEN_THEO_MODULE_KLCN029_2026-10-13.docx](../reports/HUONG_DAN_HOAN_THIEN_THEO_MODULE_KLCN029_2026-10-13.docx).

## Module A: file Excel chấm cặp CV–JD

| Tệp | Vai trò |
|---|---|
| `rubric/rubric_v2.json` | Rubric 8 tiêu chí theo đề cương: trọng số, cách chấm, mô tả neo 0–4, trạng thái. **Bản nháp**, khóa sau vòng chấm thử 10 cặp. |
| `data/build_rating_workbook.py` | Tạo file Excel cho từng người chấm từ `pairs.csv`, JD gold và rubric. |
| `data/ratings_io.py` | Kiểm tra file đã chấm và xuất JSONL. |
| `templates/CV_JD_RATING_TEMPLATE_v1_DEMO.xlsx` | Bản mẫu với 3 cặp và 2 JD hư cấu, dùng để xem trước và tập chấm. |
| `data/examples/` | Dữ liệu hư cấu cho bản mẫu và test. |

### Chuẩn bị đầu vào

- `data/jd_v1/<jd_id>.txt`: nội dung JD do nhóm viết lại, kèm `jd_manifest.csv`. Cách thêm JD và
  khung nội dung: [data/jd_v1/README.md](data/jd_v1/README.md). Kiểm tra bằng
  `python -m downstream.data.jd_catalog check`.
- `data/jd_gold_v1/<jd_id>.json`: JD gold theo `JDSchema` (`baseline_extraction/schema.py`), tạo khung
  rỗng bằng `python -m downstream.data.jd_catalog init-gold`. Mỗi phần tử `must_have` hoặc
  `nice_to_have` là một yêu cầu nguyên tử; người chấm sẽ đánh giá đúng danh sách này.
- `data/pairs_v1/pairs.csv`: các cột `pair_id,cv_id,jd_id,split,intended_fit`, có thể thêm `cv_file`
  để chỉ tệp PDF. Cột `split` và `intended_fit` **không** được đưa vào file của người chấm.

### Tạo file cho người chấm

```bash
python -m downstream.data.build_rating_workbook --pairs downstream/data/pairs_v1/pairs.csv --jd-gold downstream/data/jd_gold_v1 --jd-text downstream/data/jd_v1 --rater A --out downstream/data/labels_v1/rater_A.xlsx --lock
```

Chạy lại với `--rater B` cho người thứ hai. Hai file có cùng các cặp nhưng thứ tự khác nhau, để giảm
ảnh hưởng của thứ tự chấm. Thứ tự cố định theo mã người chấm và `--seed`.

Trong file:

- Người chấm nhập ở cột trắng, chọn giá trị từ danh sách thả xuống; cột màu xám là thông tin cố định.
- Mặc định file không khóa. `--lock` khóa cột xám và các sheet tham khảo, chỉ để cột nhập liệu sửa được.
  Khóa không có mật khẩu: mở bằng Review → Unprotect Sheet.
- Sửa rubric trong `rubric/rubric_v2.json` rồi tạo lại file, không sửa sheet `RUBRIC` trong Excel.
- Cột `kiem_tra` hiện `OK` khi dòng đã đủ thông tin.
- Sheet `TIEN_DO` đếm số cặp đã xong.
- Sheet ẩn `META` lưu phiên bản rubric và mã băm SHA-256 của rubric, `pairs.csv` và JD gold.

### Kiểm tra và xuất nhãn

```bash
python -m downstream.data.ratings_io check downstream/data/labels_v1/rater_A.xlsx
```

```bash
python -m downstream.data.ratings_io export downstream/data/labels_v1/rater_A.xlsx --out downstream/data/labels_v1/rater_A.jsonl
```

Lệnh `check` lặp lại các kiểm tra trong Excel. Ngoài ra nó bắt thêm những lỗi Excel không chặn được:
giá trị dán đè qua danh sách thả xuống, dòng bị xóa hoặc đổi thứ tự, và file được tạo cho một phiên bản
rubric khác. `export` từ chối xuất khi còn lỗi; thêm `--allow-incomplete` để chỉ xuất các cặp đã xong.

### Quy tắc

- `labels_v1/` chứa trích dẫn từ CV thật nên đã được gitignore. Lưu ở thư mục riêng của nhóm.
- Sau vòng chấm thử, mọi thay đổi rubric phải tăng `rubric_version` và tạo lại file. File cũ sẽ bị
  `check` báo lệch phiên bản.

Test: `python -m unittest downstream/tests/test_rating_workbook.py -v`
