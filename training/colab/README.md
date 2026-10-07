# Colab QLoRA baseline

## Tệp sử dụng

- `Qwen3_Pointer_Colab_UI_Demo.ipynb`: giao diện CV Insight chạy trực tiếp trong Colab;
  người vận hành tải PDF, dán JD, chọn EN/VI, bấm đánh giá và tải bundle kết quả mà không
  phải sửa biến trong các cell.
- `Qwen3_Pointer_EndToEnd_CV_JD_Demo_Colab.ipynb`: baseline có người vận hành, chạy một
  CV + JD từ OCR đến Pointer Stage 2, frozen Parser v1, matching và ZIP kết quả; đây là
  phương án miễn phí thay cho deployment 24/7.
- `Qwen3_CVSchema2_QLoRA_Colab.ipynb`: notebook huấn luyện và phục hồi checkpoint.
- `Qwen3_CVSchema2_Hybrid_Pointer_Stage2_Colab.ipynb`: notebook ngày 2, tiếp tục QLoRA
  từ adapter v1 trên nhãn Hybrid Pointer v1; mặc định chạy smoke và lưu adapter v2 riêng.
- `Qwen3_Pointer_Stage2_Validation_Raw_Colab.ipynb`: sinh raw output của adapter Pointer full
  trên 75 validation, tự tiếp tục theo từng mẫu và tải ZIP; không parse, tính F1 hoặc mở test.
- `Qwen3_Pointer_Real80_Raw_Colab.ipynb`: chạy adapter Pointer full trên 80 CV thật
  (60 EN, 20 VI), lưu raw output theo từng CV và có thể tiếp tục sau khi Colab ngắt.
- `Qwen3_Pointer_Real80_Selective_Retry_P1_Colab.ipynb`: chạy lại đúng 9 CV thật bị
  Parser v1 từ chối ở P0, dùng prompt sửa theo lỗi cấu trúc và ngân sách 1280 token.
- `Qwen3_CVSchema2_Validation_Eval_Colab.ipynb`: notebook sinh và đánh giá đủ 75 mẫu
  validation, có resume theo từng mẫu trên Drive.
- `Qwen3_Base_CVSchema2_Validation_Raw_Colab.ipynb`: notebook chạy Qwen gốc trên cùng
  75 validation và lưu raw output; chưa áp dụng parser hoặc metric nội dung.
- `Qwen3_Base_CVSchema2_Locked_Test_Raw_Colab.ipynb`: sinh raw output của Qwen gốc trên
  75 mẫu test khóa.
- `Qwen3_Adapter_CVSchema2_Locked_Test_Raw_Colab.ipynb`: sinh raw output của adapter trên
  cùng 75 mẫu test khóa.
- `Qwen3_CVSchema2_Single_CV_Demo_Colab.ipynb`: upload và chạy thử riêng một CV PDF;
  ưu tiên text gốc, OCR theo ngôn ngữ, chạy adapter và Parser v1 rồi tải gói kết quả.
- `resume_parsing_vision_cvschema_v2.zip`: gói dữ liệu đã xác minh để tải lên lần đầu.
- `resume_parsing_vision_cvschema_v2.zip.sha256`: mã băm của gói tải lên.
- `resume_parsing_vision_cvschema_v2_pointer_v1.zip`: gói dữ liệu Hybrid Pointer v1 cho
  lần huấn luyện cải tiến.
- `resume_parsing_vision_cvschema_v2_pointer_v1.zip.sha256`: mã băm của gói pointer.
- `build_colab_notebook.py`: nguồn sinh notebook, giúp thay đổi notebook có thể review.
- `build_pointer_stage2_notebook.py`: nguồn sinh notebook continued QLoRA Hybrid Pointer.
- `build_pointer_validation_raw_notebook.py`: nguồn sinh notebook raw validation Pointer P0.
- `build_pointer_real80_raw_notebook.py`: nguồn sinh notebook baseline 80 CV thật.
- `build_pointer_real80_retry_notebook.py`: nguồn sinh notebook selective retry P1.
- `build_validation_evaluation_notebook.py`: nguồn sinh notebook đánh giá validation.
- `build_base_model_validation_notebook.py`: nguồn sinh notebook raw baseline Qwen gốc.
- `build_locked_test_notebooks.py`: nguồn sinh hai notebook test khóa.
- `build_single_cv_demo_notebook.py`: nguồn sinh notebook chạy thử một CV.
- `build_pointer_colab_ui_notebook.py`: sinh notebook giao diện từ pipeline đầu cuối đã
  khóa, đồng thời gắn hash cho ba đoạn OCR, extraction và evaluation nhúng trong UI.
- `package_colab_data.py`: đóng gói lại dữ liệu sau khi kiểm tra hash.
- `package_pointer_data.py`: kiểm tra và đóng gói xác định dataset Hybrid Pointer v1.
- `validate_colab_notebook.py`: kiểm tra cấu trúc và các hàng rào chống data leakage.
- `validate_pointer_stage2_notebook.py`: kiểm tra cú pháp từng cell, adapter cha, FP16,
  checkpoint/resume và việc test không đi vào Trainer.
- `validate_pointer_validation_raw_notebook.py`: kiểm tra hash adapter/dataset, raw-only và
  hàng rào cấm truy cập test/target/parser trong notebook validation.
- `validate_pointer_real80_raw_notebook.py`: kiểm tra hash input/adapter/parser, phân bố
  EN/VI, raw-only và hàng rào không nạp gold của notebook 80 CV thật.
- `validate_pointer_real80_retry_notebook.py`: kiểm tra gói 9 retry, liên kết P0,
  chiến lược retry, raw-only và việc không đưa gold/raw output cũ vào prompt.
- `validate_single_cv_demo_notebook.py`: kiểm tra cú pháp và cấu hình khóa của notebook
  chạy thử một CV.
- `validate_pointer_colab_ui_notebook.py`: kiểm tra thành phần giao diện, cú pháp và việc
  notebook không mở Gradio/tunnel/public web service.

## Chạy giao diện CV Insight trong Colab

1. Mở `Qwen3_Pointer_Colab_UI_Demo.ipynb`, chọn **Runtime > Change runtime type > T4 GPU**.
2. Tạo Colab Secret `HF_TOKEN` có quyền đọc repo private và bật quyền truy cập notebook.
3. Chạy lần lượt cell 1–6. Nếu pip yêu cầu khởi động lại runtime, khởi động lại rồi chạy
   tiếp từ cell 2.
4. Trong giao diện: chọn một PDF, dán JD ít nhất 80 ký tự, chọn ngôn ngữ và bấm
   **Đánh giá CV**. Giữ consent tắt nếu ứng viên không đồng ý đóng góp dữ liệu nghiên cứu.
5. Giao diện hiển thị điểm, kết luận, kỹ năng khớp/thiếu và gợi ý; bundle JSON/ZIP được
   tải xuống sau khi hoàn tất. Có thể đổi PDF/JD và bấm lại mà không nạp lại Qwen.

Khi checkbox đóng góp nghiên cứu được bật, mỗi hồ sơ được lưu vào
`MyDrive/KLCN029/pointer_e2e_demo/submissions/<submission_id>/`, gồm PDF gốc, JD,
`consent.json`, receipt và toàn bộ kết quả baseline. `submission_index.jsonl` là chỉ mục
để nhóm thống kê số CV đã thu thập. Giao diện hiển thị mã rút dữ liệu cần gửi lại ứng viên.
Khi checkbox tắt, notebook không sao chép PDF/JD vào Drive. Hồ sơ đã consent vẫn được lưu
cùng `failure.json` nếu OCR/model/parser lỗi, để nhóm có thể phân tích ca thất bại thực tế.
Khi ứng viên yêu cầu rút dữ liệu, nhập mã họ đã nhận vào cell quản trị số 7; notebook xóa
cả thư mục hồ sơ và dòng tương ứng trong chỉ mục.

Giao diện này chỉ hiện trong phiên Colab của người vận hành. Nó không tạo URL công khai
cho ứng viên và không chạy khi runtime đã đóng.

## Chạy thử riêng một CV

Ưu tiên notebook mới `Qwen3_Pointer_EndToEnd_CV_JD_Demo_Colab.ipynb`, vì notebook này
dùng adapter Pointer Stage 2 đã chốt và chạy tiếp matching. Nhập `JD_TEXT` ở cell 2, giữ
`RESEARCH_CONSENT=False` nếu chỉ thử nghiệm, rồi chạy cell 1–8. Adapter được lấy từ Drive;
nếu thiếu, notebook đọc private Hugging Face repo qua Colab Secret `HF_TOKEN`.

Notebook `Qwen3_CVSchema2_Single_CV_Demo_Colab.ipynb` bên dưới là bản thử Stage 1 cũ,
được giữ làm template OCR và không dùng làm kết quả cuối của đề tài.

1. Mở `Qwen3_CVSchema2_Single_CV_Demo_Colab.ipynb` trên Colab và chọn GPU T4.
2. Ở cell 2, chọn `LANGUAGE = "auto"`, `"vi"` hoặc `"en"`. Với PDF chỉ chứa ảnh,
   chọn rõ `"vi"` hoặc `"en"`.
3. Chạy cell 3. Notebook dùng adapter trên Drive; nếu chưa có, upload
   `final_adapter-full_1.zip` khi được hỏi.
4. Ở cell 4, upload đúng một CV PDF. Notebook hiển thị đường đi của từng trang và
   phần text đã ẩn thông tin cá nhân để kiểm tra trước.
5. Chạy tiếp đến cell 8. Colab tải về một ZIP chứa JSON CVSchema 2.0, raw output,
   kết quả Parser v1, nhật ký định tuyến OCR và manifest của lần chạy.

Notebook này phục vụ kiểm thử thao tác trên một CV, không dùng để tính metric báo cáo.
PDF gốc chỉ nằm trong phiên Colab; kết quả lưu trên Drive không chứa PDF gốc.

## Chạy baseline trên 80 CV thật

1. Tải `Qwen3_Pointer_Real80_Raw_Colab.ipynb` lên Colab và chọn GPU T4.
2. Chọn **Run all**. Khi notebook hỏi dữ liệu, upload
   `real_cv_pointer_inputs_v1.zip`. Gói này chứa 80 prompt đã ẩn email, điện thoại và
   các dòng tên phát hiện được; không chứa gold label.
3. Nếu adapter chưa có trên Drive, upload
   `qwen3_4b_cvschema2_pointer_stage2_full_v1_final_adapter.zip` khi được hỏi.
4. Giữ nguyên `EVAL_VERSION = "v1"`, `MAX_NEW_TOKENS = 768` và các hash đã khóa.
   Notebook tạo một JSON cho từng CV trong Drive. Nếu phiên ngắt, mở lại notebook và
   **Run all**; các mẫu đã hoàn tất với cùng `eval_id` sẽ được bỏ qua.
5. Cell cuối chỉ chạy khi đủ 80 mẫu, rồi tải
   `qwen3_4b_pointer_real80_raw_greedy_v1.zip`. Gửi lại ZIP này để áp dụng parser v1
   ngoại tuyến và lập bảng coverage, schema validity, token, thời gian theo EN/VI.

Artifact đang tiếp tục được lưu tại:

```text
MyDrive/KLCN029/evaluations/real_cv_pointer_stage2_full_v1/
└── qwen3_4b_pointer_real80_raw_greedy_v1/
    ├── samples/<sample_id>.json
    ├── predictions_raw.jsonl
    ├── sample_generation_metrics.csv
    ├── generation_summary.json
    ├── eval_config.json
    ├── _COMPLETE.json
    └── _FILE_MANIFEST.json
```

Vì bảng nhãn 80 CV thật chưa được điền, run này chưa báo precision, recall, F1 hay
exact match. Các chỉ số đó chỉ được tính sau khi gold được dán nhãn và khóa độc lập.

### Selective retry P1 sau baseline 80 CV

P0 dựng được CVSchema cho 71/80 CV. Chạy
`Qwen3_Pointer_Real80_Selective_Retry_P1_Colab.ipynb` trên T4 và upload
`real80_selective_retry_p1_v1.zip` khi được hỏi. Adapter full đã có trên Drive sẽ được
dùng lại; nếu chạy bằng tài khoản khác thì upload ZIP adapter full như P0.

Notebook chỉ chạy 9 mẫu `EN010`, `EN011`, `EN023`, `EN059`, `VI003`, `VI006`, `VI007`,
`VI008`, `VI010`. Nó không đọc gold và không chạy parser trên Colab. Kết quả tải xuống:

```text
qwen3_4b_pointer_real80_selective_retry_p1_v1.zip
```

Giữ nguyên `EVAL_VERSION = "v1"` và `MAX_NEW_TOKENS = 1280`. Sau khi nhận ZIP, evaluator
ngoại tuyến sẽ áp dụng cùng Parser v1 và ghép kết quả hợp lệ với 71 mẫu P0.

## Chạy ngày 2: Hybrid Pointer stage 2

1. Tải `Qwen3_CVSchema2_Hybrid_Pointer_Stage2_Colab.ipynb` lên Colab và chọn GPU T4.
2. Giữ `RUN_MODE = "smoke"`, `RUN_VERSION = "v1"`, sau đó chọn **Run all**.
3. Khi được hỏi, upload `resume_parsing_vision_cvschema_v2_pointer_v1.zip`; nếu adapter
   giai đoạn 1 chưa có đúng vị trí trên Drive, upload thêm `final_adapter-full_1.zip`.
4. Cell đo token phải báo không có mẫu vượt `MAX_LENGTH=5120`. Notebook sau đó nạp
   adapter v1 ở chế độ trainable và chạy đúng hai bước trên các mẫu train dài nhất.
5. Sau khi smoke hoàn tất, tải về hoặc giữ nguyên thư mục kết quả trên Drive. Đổi
   `RUN_MODE = "full"`, giữ nguyên `RUN_VERSION = "v1"` và **Run all** để tạo run đầy đủ.
6. Nếu Colab ngắt, mở lại notebook, giữ nguyên cấu hình của run và **Run all**. Notebook
   chỉ phục hồi checkpoint có archive, manifest hoàn tất và SHA-256 hợp lệ.

Hai run được tách tại:

```text
MyDrive/KLCN029/runs/qwen3_4b_cvschema2_pointer_stage2_smoke_v1/
MyDrive/KLCN029/runs/qwen3_4b_cvschema2_pointer_stage2_full_v1/
```

`validation` chỉ dùng cho eval loss và kiểm tra sinh sau huấn luyện. `test.jsonl` được kiểm
tra hash nhưng không được nạp vào `DatasetDict` hay `Trainer`.

## Cách chạy baseline giai đoạn 1

1. Mở notebook trong Google Colab và chọn GPU T4.
2. Giữ `RUN_MODE = "smoke"`, chọn gói ZIP khi hộp tải tệp xuất hiện và chạy hết notebook.
3. Sau khi smoke thành công, đổi thành `RUN_MODE = "full"`, giữ `RUN_VERSION = "v1"` và chạy lại từ đầu.
4. Nếu phiên bị ngắt, mở lại notebook, giữ nguyên `RUN_MODE`, `RUN_VERSION` và siêu tham số rồi chọn **Run all**. Notebook kiểm tra hash và tiếp tục checkpoint hoàn chỉnh gần nhất.
5. Nếu thay dữ liệu, learning rate, epoch hoặc LoRA, tăng `RUN_VERSION` để tạo run mới.

Sau khi run `full` hoàn tất, mở `Qwen3_CVSchema2_Validation_Eval_Colab.ipynb`, chọn
T4 GPU và **Run all**. Notebook dùng `final_adapter` hiện có trên Drive. Nếu thư mục đó
không còn, chọn ZIP adapter đã tải về khi notebook yêu cầu. Mỗi mẫu hoàn tất được lưu
riêng; sau khi Colab ngắt chỉ cần Run all lại để tiếp tục phần còn thiếu.

Không chạy đồng thời hai phiên Colab với cùng `RUN_MODE` và `RUN_VERSION`, vì cả hai sẽ ghi vào cùng thư mục checkpoint.

Dữ liệu được lưu một lần ở:

```text
MyDrive/KLCN029/data/resume_parsing_vision_cvschema_v2/
```

Artifact của từng run nằm tại:

```text
MyDrive/KLCN029/runs/<run_name>/
├── run_config.json
├── session_history.jsonl
├── zero_shot_sample.json
├── checkpoints/
│   ├── checkpoint-<step>.tar.gz
│   └── checkpoint-<step>.complete.json
├── tensorboard/
└── final_adapter/
    ├── adapter_model.safetensors
    ├── adapter_config.json
    ├── tokenizer files
    ├── trainer_state.json
    ├── metrics.json
    ├── run_config.json
    ├── _FILE_MANIFEST.json
    └── _COMPLETE
```

Kết quả đánh giá validation nằm tại:

```text
MyDrive/KLCN029/evaluations/qwen3_4b_cvschema2_stage1_full_v1/
└── cvschema2_validation_greedy_v1/
    ├── samples/<sample_id>.json
    ├── predictions.jsonl
    ├── sample_metrics.csv
    ├── field_metrics.csv
    └── summary.json
```

Notebook đánh giá chỉ mở `validation.jsonl`. Tập test khóa chỉ được chạy một lần sau
khi cấu hình và quy tắc decoding đã được chốt bằng validation.

Để tạo baseline trước huấn luyện, chạy `Qwen3_Base_CVSchema2_Validation_Raw_Colab.ipynb`.
Notebook giữ model revision, chat template, NF4 và greedy decoding giống lần đánh giá
adapter, nhưng không import PEFT hoặc nạp adapter. Raw output được lưu tại:

```text
MyDrive/KLCN029/evaluations/qwen3_4b_base_cvschema2/
└── qwen3_base_validation_raw_greedy_v1/
    ├── eval_config.json
    ├── generation_summary.json
    ├── predictions_raw.jsonl
    ├── sample_generation_metrics.csv
    └── samples/<sample_id>.json
```

Parser được áp dụng ngoại tuyến sau bằng cùng một phiên bản cho raw output của Qwen gốc
và adapter; notebook raw không đọc gold answer để tính accuracy.

## Giai đoạn test khóa

Chỉ bắt đầu sau khi parser v1 và cấu hình decoding đã được đóng băng. Chạy lần lượt:

1. `Qwen3_Base_CVSchema2_Locked_Test_Raw_Colab.ipynb`;
2. `Qwen3_Adapter_CVSchema2_Locked_Test_Raw_Colab.ipynb`.

Hai notebook chỉ đưa `messages[0:2]` vào model. Chúng không truy cập `target`, không gọi
parser và không tính metric. Khi Colab ngắt, chọn **Run all**; các mẫu đã có cùng
`eval_id` được giữ lại và notebook tiếp tục từ mẫu còn thiếu. Không đổi cấu hình hoặc
`OUTPUT_ID` giữa các lần tiếp tục.

Kết quả nằm tại:

```text
MyDrive/KLCN029/evaluations/locked_test/
├── qwen3_4b_base_cvschema2_test_raw_greedy_v1/
└── qwen3_4b_adapter_cvschema2_test_raw_greedy_v1/
```

Mỗi thư mục phải có `_COMPLETE.json`, `eval_config.json`, `generation_summary.json`,
`predictions_raw.jsonl`, `sample_generation_metrics.csv`, `LOCKED_TEST_OPENED.json` và
75 tệp trong `samples/`. Tải nguyên hai thư mục về máy; bước đánh giá ngoại tuyến sẽ
xác minh hash rồi áp dụng đúng `cvschema2_output_parser_v1` cho cả hai.

### Test khóa Hybrid Pointer

Sau khi P0 validation đạt 75/75 CVSchema hợp lệ và 440/440 non-null span exact, parser
`cvpointer_output_parser_v1` đã được đóng băng. Chạy:

```text
Qwen3_Pointer_Stage2_Locked_Test_Raw_Colab.ipynb
```

Notebook liên kết hợp đồng raw test với manifest parser đóng băng SHA-256
`6fbba87b448cdd9f6ac1cec4771c639d3d3422939c36f4c9453a23d3140c5746`. Nó chỉ đưa
system/user prompt vào model, không ghi target vào artifact, không parse và không tính metric
trên Colab. Kết quả tải xuống có tên:

```text
qwen3_4b_pointer_stage2_test_raw_greedy_v1.zip
```

## Cơ chế chống mất tiến trình

Trainer ghi checkpoint vào SSD của runtime trước. Callback đóng gói nguyên checkpoint gồm adapter, optimizer, scheduler, RNG và Trainer state thành một archive. Archive được chép sang tệp tạm trên Drive, đọc lại để kiểm tra SHA-256, rồi manifest `*.complete.json` mới được ghi. Resume chỉ chọn archive có manifest và hash hợp lệ.

Nếu Drive lỗi tạm thời, callback giữ checkpoint cục bộ và tiếp tục train; lần lưu kế tiếp sẽ thử lại. Adapter cuối dùng thư mục tạm và backup, nên notebook có thể khôi phục nếu phiên bị ngắt đúng lúc thay thế artifact cuối.

`run_config.json` chứa hash của toàn bộ hợp đồng huấn luyện: model/data revision, LoRA, lượng tử hóa, loss, optimizer, scheduler, batch, precision, seed và lịch save/eval. GPU, CUDA, Python, Torch và các phiên thực thi được ghi riêng trong `session_history.jsonl`; việc Colab cấp GPU khác không tự động làm mất khả năng resume vì precision đã khóa ở FP16.

Cách này mất nhiều nhất số bước kể từ checkpoint hoàn chỉnh gần nhất. Với run đầy đủ, `save_steps=20`, batch hiệu dụng là 8 mẫu và chỉ giữ ba checkpoint gần nhất.

## Cấu hình baseline

- Model: `Qwen/Qwen3-4B-Instruct-2507`, revision `1b4199c4f36b0cef378bfb12390c18780c18af4c`.
- QLoRA NF4, double quantization, rank 16, alpha 32, dropout 0,05, `all-linear`.
- FP16 được khóa cho mọi phiên để có thể resume khi Colab đổi loại GPU tương thích.
- Sau khi TRL tạo QLoRA adapter, notebook chuyển toàn bộ tham số trainable về FP32 trước
  khi tạo optimizer; điều này tránh FP16 GradScaler nhận gradient BF16 trên T4.
- Batch 1, gradient accumulation 8, learning rate `2e-4`.
- Một epoch cho baseline đầu tiên; chỉ tăng epoch bằng một run mới nếu validation ủng hộ.
- Loss chỉ tính trên completion JSON; `chunked_nll` giảm peak VRAM mà không đổi công thức NLL.
- `MAX_LENGTH=5120`; preflight đo token thật và dừng nếu có mẫu bị cắt.
- Preflight dùng hàm chat template prompt/completion của TRL và tokenize riêng
  hai phần, tránh báo lỗi sai do BPE gộp token ở ranh giới trước ký tự đầu của JSON.
- Dataset đưa vào Trainer đã có `input_ids` và `labels`; toàn bộ token prompt mang nhãn
  `-100`, còn JSON completion và EOS được giữ làm nhãn huấn luyện.
- Train 850 mẫu, validation 75 mẫu; test 75 mẫu không được nạp vào Trainer.

## Kiểm tra cục bộ

```powershell
python training/colab/build_colab_notebook.py
python training/colab/build_pointer_stage2_notebook.py
python training/colab/build_validation_evaluation_notebook.py
python training/colab/build_base_model_validation_notebook.py
python training/colab/build_locked_test_notebooks.py
python training/colab/build_pointer_validation_raw_notebook.py
python training/colab/build_pointer_real80_raw_notebook.py
python training/colab/build_pointer_real80_retry_notebook.py
python training/colab/build_pointer_locked_test_raw_notebook.py
python training/colab/build_pointer_e2e_demo_notebook.py
python training/colab/build_pointer_colab_ui_notebook.py
python training/colab/validate_colab_notebook.py
python training/colab/validate_pointer_stage2_notebook.py
python training/colab/validate_validation_evaluation_notebook.py
python training/colab/validate_base_model_validation_notebook.py
python training/colab/validate_locked_test_notebooks.py
python training/colab/validate_pointer_validation_raw_notebook.py
python training/colab/validate_pointer_real80_raw_notebook.py
python training/colab/validate_pointer_real80_retry_notebook.py
python training/colab/validate_pointer_locked_test_raw_notebook.py
python training/colab/validate_pointer_e2e_demo_notebook.py
python training/colab/validate_pointer_colab_ui_notebook.py
python training/colab/package_colab_data.py
```

Không thể xác nhận thời gian và VRAM chính xác nếu chưa chạy trên GPU Colab thực tế. Smoke run dùng 16 mẫu train dài nhất để phát hiện OOM trước khi chạy đầy đủ.

Cell kiểm tra nhanh báo riêng JSON nghiêm ngặt và JSON khôi phục được sau khi bỏ tiền tố
`<think>...</think>` hoặc Markdown fence. Các tiền tố này vẫn được tính là lỗi định dạng.
Toàn bộ output và trạng thái chạm giới hạn token được lưu tại
`quick_validation_sample.json`; màn hình chỉ rút gọn output quá dài.

## Tài liệu kỹ thuật

- [Qwen3-4B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [TRL SFTTrainer](https://huggingface.co/docs/trl/sft_trainer)
- [TRL PEFT integration](https://huggingface.co/docs/trl/peft_integration)
- [PEFT quantization guide](https://huggingface.co/docs/peft/developer_guides/quantization)
- [Transformers resume training](https://huggingface.co/docs/transformers/trainer_recipes#resume-training)
- [bitsandbytes quantization](https://huggingface.co/docs/transformers/quantization/bitsandbytes)
- [Google Colab FAQ](https://research.google.com/colaboratory/faq.html)
