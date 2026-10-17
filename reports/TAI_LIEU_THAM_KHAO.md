# Danh mục tài liệu tham khảo của đề tài

Mỗi tài liệu được dùng ở đâu trong đề tài thì ghi vào cột "Dùng cho". Chỉ đưa vào báo cáo tài liệu ở trạng thái **Đã đối chiếu**: đã mở bản gốc (PDF hoặc trang nhà xuất bản), kiểm tra tác giả, năm, tên, nơi đăng, DOI, và kiểm tra đúng nội dung được trích. Bản BibTeX tương ứng nằm ở `tai_lieu_tham_khao.bib`; khóa trích dẫn giống cột "Khóa".

Nguyên tắc với model: trích **đúng phiên bản** đã dùng (model card của checkpoint đó, kèm trích dẫn chính thức mà nhà phát triển ghi trên model card); với model qua API, trích thêm trang của nhà cung cấp vì họ có thể phục vụ bản lượng tử hóa. Không dùng báo cáo của thế hệ khác.

Trạng thái (hai bước: đúng thông tin thư mục, rồi đúng nội dung được trích):
- **Đã đối chiếu**: đã mở bản gốc, đúng thư mục và đúng nội dung được trích. Dùng được trong báo cáo.
- **Đã kiểm thư mục**: đã mở trang gốc (arXiv, nhà xuất bản), tên, tác giả, năm đúng. Người viết phải đọc đoạn liên quan và đối chiếu nội dung khi trích vào chương, rồi đổi sang "Đã đối chiếu".
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
| lewis2020rag | Lewis P., Perez E., Piktus A., Petroni F. et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. *NeurIPS 2020*. arXiv:2005.11401 | Khái niệm RAG cho M3 và P | Đã kiểm thư mục (arXiv, 17/10/2026; ghi chú tác giả: được nhận đăng NeurIPS 2020) | https://arxiv.org/abs/2005.11401 |
| qwen38 | Qwen Team (2026, tháng 8). *Qwen3.8-Max: A New Bar for Coding and Cowork*. Blog, https://qwen.ai/blog?id=qwen3.8 | Model chấm điểm `qwen/qwen3.8-27b` (M1–M4, P). Đây là trích dẫn chính thức Qwen ghi trên model card của Qwen3.8-27B | Có trích dẫn chính thức (đọc trên model card 17/10/2026); chưa mở bài blog | https://huggingface.co/Qwen/Qwen3.8-27B |
| qwen38_27b_card | Qwen Team. *Qwen3.8-27B* (model card), Hugging Face. Truy cập 17/10/2026 | Mô tả đúng phiên bản dùng để chấm: 27B tham số, dense, có chế độ thinking và instruct, giấy phép Apache-2.0 | Đã đối chiếu (17/10/2026) | https://huggingface.co/Qwen/Qwen3.8-27B |
| groq_qwen38_27b | Groq. *Qwen 3.8 27B* (trang model, GroqDocs). Truy cập 17/10/2026 | Bản Groq phục vụ: trạng thái Preview, lượng tử hóa TruePoint, context 131 072, đầu ra tối đa 16 384 token, khuyến nghị tham số | Đã đối chiếu (17/10/2026); trạng thái theo ngày lưu ở `minh_chung/I01_TRANG_THAI_MODEL_GROQ.md` | https://console.groq.com/docs/model/qwen/qwen3.8-27b |
| qwen3technicalreport | Qwen Team (2025). *Qwen3 Technical Report*. arXiv:2505.09388 | Model trích xuất Qwen3-4B-Instruct-2507 (huấn luyện QLoRA). Đây là trích dẫn chính thức trên model card của bản 4B. **Không** dùng cho Qwen3.8 (thế hệ khác, kiến trúc khác) | Đã kiểm thư mục (arXiv, 17/10/2026) | https://arxiv.org/abs/2505.09388 |
| baral2026analyzer | Baral R., Samantaray S. (2026). AI Resume Analyzer: A Survey and Implementation Report on Intelligent Resume Evaluation Using Large Language Models. *International Journal of Pharmacy with Medical Sciences*, 6(2(1)), 60–66. doi:10.64751/ijpams.2026.v6.n2(1).178 | Do nhóm cung cấp ngày 16/10 khi rà báo cáo | Đã kiểm thư mục (17/10/2026). **Cảnh báo:** bài về AI đăng trên tạp chí dược, dấu hiệu tạp chí kém chất lượng; chỉ dùng nếu không có nguồn thay thế, và không dùng làm căn cứ chính | https://ijpams.com/journal/index.php/ijpams/article/view/178 |

## Tài liệu ứng viên đã kiểm thư mục (17/10/2026)

Claude đã mở trang arXiv của từng bài, kiểm tên, tác giả đầu, ngày đăng. Chưa đối chiếu nội dung: người viết đọc đoạn liên quan trước khi trích.

| Khóa | Tài liệu | Dùng cho (chương) | Link |
|---|---|---|---|
| hu2021lora | Hu E. J., Shen Y., Wallis P., Allen-Zhu Z. et al. (2021). LoRA: Low-Rank Adaptation of Large Language Models. arXiv:2106.09685 | Huấn luyện Qwen3-4B cho trích xuất (chương 2, 3) | https://arxiv.org/abs/2106.09685 |
| dettmers2023qlora | Dettmers T., Pagnoni A., Holtzman A., Zettlemoyer L. (2023). QLoRA: Efficient Finetuning of Quantized LLMs. arXiv:2305.14314 | Huấn luyện QLoRA (chương 2, 3) | https://arxiv.org/abs/2305.14314 |
| cui2025paddleocr | Cui C., Sun T., Lin M., Gao T. et al. (2025). PaddleOCR 3.0 Technical Report. arXiv:2507.05595 | Nhánh OCR của mô-đun trích xuất (đề tài dùng `paddleocr>=3.0`) | https://arxiv.org/abs/2507.05595 |
| zheng2023judge | Zheng L., Chiang W.-L., Sheng Y., Zhuang S. et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. arXiv:2306.05685 | Dùng LLM để chấm (chương 2) | https://arxiv.org/abs/2306.05685 |
| liu2023geval | Liu Y., Iter D., Xu Y., Wang S. et al. (2023). G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment. arXiv:2303.16634 | Chấm theo tiêu chí bằng LLM, so độ khớp với người (chương 2) | https://arxiv.org/abs/2303.16634 |
| gao2023alce | Gao T., Yen H., Yu J., Chen D. (2023). Enabling Large Language Models to Generate Text with Citations. EMNLP 2023. arXiv:2305.14627 | Sinh kèm trích dẫn và kiểm trích dẫn, nền của bước kiểm chứng trong P (chương 2, 3) | https://arxiv.org/abs/2305.14627 |
| geifman2017selective | Geifman Y., El-Yaniv R. (2017). Selective Classification for Deep Neural Networks. arXiv:1705.08500 | Từ chối chấm khi không chắc, độ bao phủ (P, `COVERAGE_MIN`) | https://arxiv.org/abs/1705.08500 |
| gan2024agents | Gan C., Zhang Q., Mori T. (2024). Application of LLM Agents in Recruitment: A Novel Framework for Resume Screening. arXiv:2401.08315 | Công trình liên quan về sàng lọc CV bằng LLM (chương 2) | https://arxiv.org/abs/2401.08315 |
| chen2024m3 | Chen J., Xiao S., Zhang P., Luo K. et al. (2024). M3-Embedding (BGE-M3). arXiv:2402.03216 | Chỉ khi báo cáo nhắc tới bộ truy xuất BGE-M3 | https://arxiv.org/abs/2402.03216 |

Ghi chú: arXiv:1705.08500 trên trang arXiv không ghi nơi đăng; nếu muốn ghi hội nghị (NeurIPS 2017) thì kiểm trên trang của hội nghị.

## Còn thiếu theo chương

| Chủ đề | Cần cho | Tình trạng |
|---|---|---|
| Hướng dẫn viết CV, ATS, mô tả mức rubric | Chương 2, rubric (R03), cơ sở tri thức | Khải đang kiểm theo trang "Kiểm nguồn cơ sở tri thức KLCN029" |
| Công trình liên quan về trích xuất CV và chấm CV bằng LLM | Chương 2 | Có zhu2025layout, gan2024agents; nên thêm 2–3 bài có phản biện (hội nghị, tạp chí uy tín) thay cho bài Baral |
| Sai lệch, công bằng khi dùng LLM trong tuyển dụng | Chương 2 hoặc phần hạn chế | Chưa có; nhóm quyết định có cần không |
| Lấy trung bình khi lệch 1 điểm, người thứ ba phân xử | Phương pháp gán nhãn | Chưa có; nếu không tìm được nguồn thì trình bày là quy ước của đề tài |
| Đánh giá gợi ý sửa bằng so sánh cặp mù | Kiểm chứng H2 | Tùy cách chốt H2 với giảng viên |
| Thư viện phần mềm (PyMuPDF, Hugging Face PEFT, TRL) | Thiết lập thực nghiệm | Trích theo trang chính thức hoặc kho mã, kèm phiên bản dùng |

## Cần bổ sung khi viết báo cáo

- Tài liệu cho **mô tả mức của rubric** và cho **ATS**: lấy từ cơ sở tri thức mà Khải đang kiểm nguồn. Mỗi nguồn được kiểm xong thì thêm vào bảng trên.
- Tài liệu cho **BGE-M3**: chỉ cần nếu báo cáo có dùng bộ truy xuất này.
- Tài liệu cho cách **lấy trung bình khi hai người lệch 1 điểm** và **phân xử bởi người thứ ba**: nếu không tìm được nguồn đã đối chiếu, trình bày đây là quy ước của đề tài và nêu lý do.
