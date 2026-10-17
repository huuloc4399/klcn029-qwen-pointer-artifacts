# Danh mục tài liệu tham khảo của đề tài

Mỗi tài liệu được dùng ở đâu trong đề tài thì ghi vào cột "Dùng cho". Chỉ đưa vào báo cáo tài liệu ở trạng thái **Đã đối chiếu**: đã mở bản gốc (PDF hoặc trang nhà xuất bản), kiểm tra tác giả, năm, tên, nơi đăng, DOI, và kiểm tra đúng nội dung được trích. Bản BibTeX tương ứng nằm ở `tai_lieu_tham_khao.bib`; khóa trích dẫn giống cột "Khóa".

Trạng thái:
- **Đã đối chiếu**: dùng được trong báo cáo.
- **Có bản gốc**: file gốc đã lưu trong repo, cần đối chiếu nội dung trích.
- **Chưa đối chiếu**: thông tin thư mục do Claude ghi từ hiểu biết chung; phải kiểm DOI và nội dung trước khi dùng.
- **Thiếu thông tin**: mới có link, chưa đủ dữ liệu thư mục.

| Khóa | Tài liệu | Dùng cho | Trạng thái | Bản gốc / link |
|---|---|---|---|---|
| zhu2025layout | Zhu F., Zhou Y., Zhang Y., Yu J., Ji J., Hu H., Chen Z., Yang Z., Liu Z. (2025). *Layout-Aware Parsing Meets Efficient LLMs: A Unified, Scalable Framework for Resume Information Extraction and Evaluation*. arXiv:2510.09722. | Mô-đun trích xuất: phần kế thừa (layout-aware parsing, định tuyến prompt); `PROJECT_SCOPE_AND_DECISIONS.md` §4.1 | Có bản gốc | `2510.09722v1.pdf`, `2510.09722v1.md` |
| cohen1960kappa | Cohen J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological Measurement*, 20(1), 37–46. doi:10.1177/001316446002000104 | Kappa cho trạng thái tiêu chí và trạng thái yêu cầu (`iaa.py`) | Chưa đối chiếu | — |
| cohen1968weighted | Cohen J. (1968). Weighted kappa: Nominal scale agreement with provision for scaled disagreement or partial credit. *Psychological Bulletin*, 70(4), 213–220. doi:10.1037/h0026256 | Kappa có trọng số bậc hai (QWK) cho điểm 0–4 và mức phù hợp | Chưa đối chiếu | — |
| landis1977measurement | Landis J. R., Koch G. G. (1977). The measurement of observer agreement for categorical data. *Biometrics*, 33(1), 159–174. doi:10.2307/2529310 | Mức diễn giải kappa (thấp, trung bình, khá, rất cao) trong `iaa.py` và báo cáo | Chưa đối chiếu | — |
| efron1979bootstrap | Efron B. (1979). Bootstrap methods: Another look at the jackknife. *The Annals of Statistics*, 7(1), 1–26. doi:10.1214/aos/1176344552 | Khoảng tin cậy 95% bằng bootstrap (lấy mẫu lại theo CV) | Chưa đối chiếu | — |
| robertson2009bm25 | Robertson S., Zaragoza H. (2009). The probabilistic relevance framework: BM25 and beyond. *Foundations and Trends in Information Retrieval*, 3(4), 333–389. doi:10.1561/1500000019 | Bộ truy xuất BM25 của M3 và P | Chưa đối chiếu | — |
| lewis2020rag | Lewis P. et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. *Advances in Neural Information Processing Systems 33 (NeurIPS 2020)*. | Khái niệm RAG cho M3 và P | Chưa đối chiếu | — |
| baral_ijpams | Baral … (năm …). Tên bài: … *IJPAMS*. | Do nhóm cung cấp ngày 16/10 khi rà báo cáo | Thiếu thông tin | https://ijpams.com/journal/index.php/ijpams/article/view/178 |

## Cần bổ sung khi viết báo cáo

- Tài liệu cho **mô tả mức của rubric** và cho **ATS**: lấy từ cơ sở tri thức mà Khải đang kiểm nguồn. Mỗi nguồn được kiểm xong thì thêm vào bảng trên.
- Tài liệu cho **Qwen3** (model trích xuất và chấm) và **BGE-M3** (chỉ cần nếu báo cáo có dùng bộ truy xuất này): thêm khi viết mục thiết lập thực nghiệm.
- Tài liệu cho cách **lấy trung bình khi hai người lệch 1 điểm** và **phân xử bởi người thứ ba**: nếu không tìm được nguồn đã đối chiếu, trình bày đây là quy ước của đề tài và nêu lý do.
