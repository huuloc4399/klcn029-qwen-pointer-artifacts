"""Build a zero-cost, operator-assisted Colab demo for the frozen Pointer baseline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "training/colab/Qwen3_CVSchema2_Single_CV_Demo_Colab.ipynb"
OUTPUT = ROOT / "training/colab/Qwen3_Pointer_EndToEnd_CV_JD_Demo_Colab.ipynb"


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def set_source(cell: dict, value: str) -> None:
    cell["source"] = value.strip().splitlines(keepends=True)
    if cell["source"] and not cell["source"][-1].endswith("\n"):
        cell["source"][-1] += "\n"
    if cell["cell_type"] == "code":
        cell["execution_count"] = None
        cell["outputs"] = []


def build() -> None:
    notebook = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    cells = notebook["cells"]

    set_source(cells[0], """
# Baseline đầu cuối trên một CV: OCR → Qwen Pointer → Parser → Matching

Notebook này chạy hoàn toàn trong giao diện Colab, không mở web server hoặc tunnel:

1. Upload một CV PDF và nhập JD.
2. Dùng text PDF khi có; OCR EN bằng PaddleOCR, OCR VI bằng Paddle detection + VietOCR.
3. Nạp đúng `Qwen3-4B-Instruct-2507` và adapter Pointer Stage 2 full.
4. Sinh CVPointerSchema, áp dụng frozen Parser v1 để dựng CVSchema 2.0 và evidence.
5. Chạy deterministic CV–JD matching baseline, hiển thị điểm và góp ý.
6. Chỉ lưu PDF/JD vào Drive khi bật `RESEARCH_CONSENT`.

Chọn **Runtime → Change runtime type → T4 GPU**, sau đó chạy cell 1–8. Khi thử CV tiếp
theo, giữ model ở cell 6 và chạy lại cell 2, 4, 7, 8.
""")

    install = """#@title 1. Cài đúng phiên bản thư viện
%pip install -q --upgrade "transformers==5.17.0" "peft==0.21.0" "accelerate==1.15.0" "bitsandbytes==0.50.2" "huggingface_hub==1.32.0" "tokenizers==0.23.2" "sentencepiece==0.2.1" "pydantic>=2.11,<3" "pymupdf==1.26.7" "paddleocr==3.7.0" "paddlepaddle==3.3.1" "vietocr==0.3.13" "setuptools==80.9.0" "Pillow==10.2.0" "numpy==2.3.5"
"""
    set_source(cells[1], install)

    config = ''.join(cells[2]["source"])
    config = config.replace(
        'SAVE_RESULT_TO_DRIVE = True #@param {type:"boolean"}',
        'JD_TEXT = "" #@param {type:"string"}\n'
        'RESEARCH_CONSENT = False #@param {type:"boolean"}\n'
        'PARTICIPANT_CODE = "" #@param {type:"string"}',
    )
    config = config.replace('MAX_NEW_TOKENS = 1280', 'MAX_NEW_TOKENS = 768\nMAX_INPUT_TOKENS = 5120\nMAX_PDF_PAGES = 12')
    config = config.replace(
        'ADAPTER_DIR = DRIVE_ROOT / "runs/qwen3_4b_cvschema2_stage1_full_v1/final_adapter"',
        'ADAPTER_DIR = DRIVE_ROOT / "runs/qwen3_4b_cvschema2_pointer_stage2_full_v1/final_adapter"',
    )
    config = config.replace('RESULT_ROOT = DRIVE_ROOT / "single_cv_trials"', 'RESULT_ROOT = DRIVE_ROOT / "pointer_e2e_demo"')
    config = config.replace('PARSER_VERSION = "cvschema2_output_parser_v1"', 'PARSER_VERSION = "cvpointer_output_parser_v1"')
    config = config.replace('EXPECTED_ADAPTER_ZIP_SHA256 = "bb9dc701b0a898de0a0e890bb540144b93321c31bba791b707ec45d5b68e00f5"', 'EXPECTED_ADAPTER_ZIP_SHA256 = "274aeb95e78f5717b04af9fd0045e5215fd247533bd9572c73c73e8242f86b4b"')
    config += """
ARTIFACT_REPO_ID = "huuloc4399/klcn029-qwen-pointer-artifacts"
ARTIFACT_REVISION = "398ce7961eac9b3ccd1661116f9287bf2b0b6b20"
EXPECTED_ADAPTER_MODEL_SHA256 = "8d68628e382593132010f20fb12cbb18d9477ca034c154811d109ec075a65f81"
if len(JD_TEXT.strip()) < 80:
    print("LƯU Ý: Hãy nhập JD_TEXT ít nhất 80 ký tự trước khi chạy cell 8.")
"""
    set_source(cells[2], config)

    set_source(cells[3], r'''#@title 3. Chuẩn bị và xác minh adapter Pointer Stage 2
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def safe_extract_zip(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP adapter lỗi CRC")
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if root != target and root not in target.parents:
                raise RuntimeError(f"ZIP chứa đường dẫn không an toàn: {member.filename}")
        archive.extractall(destination)

def verify_adapter_directory(path: Path) -> str:
    required = ["adapter_model.safetensors", "adapter_config.json", "tokenizer_config.json", "chat_template.jinja", "_FILE_MANIFEST.json", "_COMPLETE"]
    missing = [name for name in required if not (path / name).is_file()]
    if missing:
        raise RuntimeError(f"Adapter thiếu tệp: {missing}")
    if sha256_file(path / "adapter_model.safetensors") != EXPECTED_ADAPTER_MODEL_SHA256:
        raise RuntimeError("Sai hash adapter_model.safetensors")
    return sha256_file(path / "_FILE_MANIFEST.json")

if not (ADAPTER_DIR / "adapter_model.safetensors").is_file():
    hf_token = None
    try:
        from google.colab import userdata
        hf_token = userdata.get("HF_TOKEN")
    except Exception:
        pass
    if hf_token:
        from huggingface_hub import snapshot_download
        snapshot = Path(snapshot_download(
            repo_id=ARTIFACT_REPO_ID,
            revision=ARTIFACT_REVISION,
            token=hf_token,
            allow_patterns=["final_adapter/*"],
        ))
        ADAPTER_DIR = snapshot / "final_adapter"
    else:
        print("Không thấy adapter trên Drive hoặc HF_TOKEN trong Colab Secrets.")
        print("Chọn qwen3_4b_cvschema2_pointer_stage2_full_v1_final_adapter.zip")
        uploaded = files.upload()
        candidates = [name for name in uploaded if name.lower().endswith(".zip")]
        if len(candidates) != 1:
            raise RuntimeError("Cần tải đúng một ZIP adapter")
        upload_path = LOCAL_ROOT / Path(candidates[0]).name
        upload_path.write_bytes(uploaded[candidates[0]])
        if sha256_file(upload_path) != EXPECTED_ADAPTER_ZIP_SHA256:
            raise RuntimeError("Sai hash ZIP adapter")
        staging = LOCAL_ROOT / "adapter_extract"
        if staging.exists(): shutil.rmtree(staging)
        safe_extract_zip(upload_path, staging)
        roots = [p.parent for p in staging.rglob("adapter_model.safetensors")]
        if len(roots) != 1:
            raise RuntimeError(f"Không tìm thấy duy nhất adapter: {roots}")
        temporary = ADAPTER_DIR.with_name(ADAPTER_DIR.name + ".tmp")
        if temporary.exists(): shutil.rmtree(temporary)
        temporary.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(roots[0], temporary)
        if ADAPTER_DIR.exists(): shutil.rmtree(ADAPTER_DIR)
        os.replace(temporary, ADAPTER_DIR)

adapter_manifest_sha256 = verify_adapter_directory(ADAPTER_DIR)
print({"adapter": str(ADAPTER_DIR), "weights_verified": True, "manifest_sha256": adapter_manifest_sha256})
''')

    ocr = ''.join(cells[4]["source"])
    ocr = ocr.replace(
        'if len(document) == 0:\n        raise RuntimeError("PDF không có trang.")',
        'if len(document) == 0:\n        raise RuntimeError("PDF không có trang.")\n    if len(document) > MAX_PDF_PAGES:\n        raise RuntimeError(f"PDF vượt quá {MAX_PDF_PAGES} trang")',
    )
    ocr = ocr.replace('source_parts.append(f"[SOURCE p{index}]\\n{redacted}")', 'source_parts.append(redacted)')
    set_source(cells[4], ocr.replace('#@title 4. Upload một CV PDF và trích xuất text hoặc OCR', '#@title 4. Upload một CV PDF và chạy bộ định tuyến OCR'))

    runtime_sources = {
        "baseline_extraction/schema.py": source("training/evaluation/frozen/cvpointer_output_parser_v1/schema.py"),
        "training/evaluation/parser.py": source("training/evaluation/frozen/cvpointer_output_parser_v1/parser.py"),
        "training/evaluation/pointer_parser.py": source("training/evaluation/frozen/cvpointer_output_parser_v1/pointer_parser.py"),
        "services/pdf_extractor.py": source("cv_evaluation_web/services/pdf_extractor.py"),
        "services/evaluator.py": source("cv_evaluation_web/services/evaluator.py"),
    }
    hashes = {name: sha(value) for name, value in runtime_sources.items()}
    set_source(cells[5], f'''#@title 5. Nạp frozen Parser v1 và matching baseline
import sys

RUNTIME_SOURCES = {runtime_sources!r}
EXPECTED_SOURCE_HASHES = {hashes!r}
parser_runtime = LOCAL_ROOT / "pointer_runtime"
for relative, content in RUNTIME_SOURCES.items():
    target = parser_runtime / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\\n")
for package in ("baseline_extraction", "training", "training/evaluation", "services"):
    folder = parser_runtime / package
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "__init__.py").write_text("", encoding="utf-8", newline="\\n")
for relative, expected in EXPECTED_SOURCE_HASHES.items():
    observed = hashlib.sha256((parser_runtime / relative).read_bytes()).hexdigest()
    if observed != expected:
        raise RuntimeError(f"Sai hash runtime: {{relative}}")
sys.path.insert(0, str(parser_runtime))

from training.evaluation.pointer_parser import POINTER_PARSER_VERSION, parse_pointer_output
from services.pdf_extractor import DocumentAnalysis
from services.evaluator import evaluate
if POINTER_PARSER_VERSION != "cvpointer_output_parser_v1":
    raise RuntimeError(f"Sai parser version: {{POINTER_PARSER_VERSION}}")
print({{"parser": POINTER_PARSER_VERSION, "runtime_sources_verified": True}})
''')

    set_source(cells[6], r'''#@title 6. Nạp Qwen 4-bit và adapter (chỉ chạy một lần mỗi runtime)
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

tokenizer = AutoTokenizer.from_pretrained(str(ADAPTER_DIR), trust_remote_code=False, use_fast=True)
if tokenizer.pad_token_id is None:
    tokenizer.pad_token = tokenizer.eos_token
actual_chat_hash = hashlib.sha256(tokenizer.chat_template.encode("utf-8")).hexdigest()
if actual_chat_hash != CHAT_TEMPLATE_SHA256:
    raise RuntimeError(f"Sai chat template hash: {actual_chat_hash}")

bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, revision=MODEL_REVISION, quantization_config=bnb_config,
    device_map={"": 0}, dtype=torch.float16, attn_implementation="sdpa",
    trust_remote_code=False,
)
model = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR), is_trainable=False)
model.eval(); model.config.use_cache = True
print({"model": MODEL_ID, "revision": MODEL_REVISION, "device": str(next(model.parameters()).device)})
''')

    prompt_contract = json.loads(source("deployment/runpod_qwen/prompt_contract.json"))
    set_source(cells[7], f'''#@title 7. Sinh Pointer JSON và áp dụng Parser v1
PROMPT_CONTRACT = {prompt_contract!r}
for field in ("system_prompt", "user_prefix"):
    if hashlib.sha256(PROMPT_CONTRACT[field].encode("utf-8")).hexdigest() != PROMPT_CONTRACT[field + "_sha256"]:
        raise RuntimeError(f"Sai prompt contract: {{field}}")

normalized_source = "\\n".join(line.strip() for line in source_text.splitlines() if line.strip())
indexed = "\\n".join(PROMPT_CONTRACT["line_format"].format(line_number=i, text=line) for i, line in enumerate(normalized_source.splitlines(), 1))
messages = [
    {{"role": "system", "content": PROMPT_CONTRACT["system_prompt"]}},
    {{"role": "user", "content": PROMPT_CONTRACT["user_prefix"] + "\\n\\n" + indexed}},
]
prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
encoded = tokenizer(prompt, return_tensors="pt")
input_tokens = int(encoded["input_ids"].shape[1])
if input_tokens > MAX_INPUT_TOKENS:
    raise RuntimeError(f"Prompt có {{input_tokens}} token, vượt {{MAX_INPUT_TOKENS}}; không cắt ngầm")
encoded = {{key: value.to(model.device) for key, value in encoded.items()}}
torch.cuda.synchronize(); started = time.perf_counter()
with torch.inference_mode():
    generated = model.generate(**encoded, do_sample=False, max_new_tokens=MAX_NEW_TOKENS, pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id, use_cache=True)
torch.cuda.synchronize(); runtime_seconds = time.perf_counter() - started
new_ids = generated[0, input_tokens:]
raw_output = tokenizer.decode(new_ids, skip_special_tokens=True).strip()
generated_tokens = int(new_ids.numel())
parse_result = parse_pointer_output(raw_output, normalized_source)
parse_payload = parse_result.to_dict()
print(json.dumps({{"status": parse_result.status, "input_tokens": input_tokens, "generated_tokens": generated_tokens, "runtime_seconds": runtime_seconds, "issues": parse_payload["issues"]}}, ensure_ascii=False, indent=2))
if parse_result.status == "success":
    print(json.dumps(parse_result.reconstructed_cvschema, ensure_ascii=False, indent=2))
''')

    set_source(cells[8], r'''#@title 8. Matching CV–JD, lưu theo consent và tải bundle
if len(JD_TEXT.strip()) < 80:
    raise RuntimeError("JD_TEXT phải có ít nhất 80 ký tự")
if parse_result.status != "success" or parse_result.reconstructed_cvschema is None:
    raise RuntimeError("Pointer output chưa vượt Parser v1; xem issues ở cell 7")

native_pages = sum(item["route"] == "native_text" for item in routing_log)
needs_ocr = any(item["route"].startswith("ocr_") for item in routing_log)
document = DocumentAnalysis(
    text=normalized_source, page_count=len(pages), native_text_pages=native_pages,
    character_count=len(normalized_source), block_count=0,
    likely_multi_column=False, needs_ocr=needs_ocr,
)
evaluation = evaluate(
    document, JD_TEXT.strip(), language=resolved_language,
    cv_schema=parse_result.reconstructed_cvschema,
    method="Qwen Pointer P0 + Parser v1 + deterministic matching baseline v1",
).to_dict()

timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(original_name).stem)[:60] or "cv"
run_id = f"{timestamp}_{safe_stem}"
local_output = LOCAL_ROOT / "output" / run_id
local_output.mkdir(parents=True, exist_ok=False)
manifest = {
    "run_id": run_id, "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "input": {"filename": original_name, "pdf_sha256": pdf_sha256, "language": resolved_language, "pages": len(pages)},
    "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "adapter_model_sha256": EXPECTED_ADAPTER_MODEL_SHA256},
    "generation": {"do_sample": False, "max_new_tokens": MAX_NEW_TOKENS, "input_tokens": input_tokens, "generated_tokens": generated_tokens, "runtime_seconds": runtime_seconds},
    "parser": {"version": POINTER_PARSER_VERSION, "status": parse_result.status},
    "research_consent": bool(RESEARCH_CONSENT),
}
for name, value in {
    "cvschema2.json": parse_result.reconstructed_cvschema,
    "evidence.json": parse_result.evidence,
    "parse_result.json": parse_payload,
    "evaluation.json": evaluation,
    "routing_log.json": routing_log,
    "manifest.json": manifest,
}.items():
    (local_output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
(local_output / "source_redacted.txt").write_text(normalized_source, encoding="utf-8")
(local_output / "raw_output.txt").write_text(raw_output, encoding="utf-8")

research_receipt = None
if RESEARCH_CONSENT:
    import secrets
    submission_id = secrets.token_hex(12)
    withdrawal_code = secrets.token_urlsafe(18)
    target = RESULT_ROOT / "submissions" / submission_id
    target.mkdir(parents=True, exist_ok=False)
    shutil.copy2(PDF_PATH, target / "cv.pdf")
    (target / "jd.txt").write_text(JD_TEXT.strip(), encoding="utf-8")
    shutil.copytree(local_output, target / "result")
    receipt = {"submission_id": submission_id, "participant_code": PARTICIPANT_CODE[:80], "withdrawal_hash": hashlib.sha256(withdrawal_code.encode()).hexdigest()}
    (target / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    research_receipt = {"submission_id": submission_id, "withdrawal_code": withdrawal_code}

bundle_path = Path(shutil.make_archive(str(LOCAL_ROOT / f"pointer_e2e_{run_id}"), "zip", local_output))
PDF_PATH.unlink(missing_ok=True)
print(json.dumps({"total_score": evaluation["total_score"], "verdict": evaluation["verdict"], "matched_skills": evaluation["matched_skills"], "missing_skills": evaluation["missing_skills"], "research_receipt": research_receipt}, ensure_ascii=False, indent=2))
files.download(str(bundle_path))
''')

    set_source(cells[9], """
## Cách đọc và vận hành

- Chỉ dùng kết quả khi cell 7 báo `status = success`.
- `cvschema2.json` và `evidence.json` là đầu ra mô đun trích xuất.
- `evaluation.json` là đầu ra matching riêng, không phải chức năng của model trích xuất.
- Khi `RESEARCH_CONSENT=False`, PDF bị xóa khỏi runtime sau khi tạo bundle và không lưu Drive.
- Khi consent bật, lưu mã rút dữ liệu được in ở cell 8.
- Liên kết Colab không phải dịch vụ 24/7. Người vận hành phải mở notebook và xử lý từng CV.
""")

    cells.append({
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": '''#@title 9. Rút dữ liệu đã đóng góp (chỉ chạy khi có yêu cầu)
WITHDRAWAL_CODE_TO_DELETE = "" #@param {type:"string"}
if WITHDRAWAL_CODE_TO_DELETE.strip():
    code_hash = hashlib.sha256(WITHDRAWAL_CODE_TO_DELETE.strip().encode()).hexdigest()
    matches = []
    for receipt_path in (RESULT_ROOT / "submissions").glob("*/receipt.json"):
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("withdrawal_hash") == code_hash:
            matches.append(receipt_path.parent)
    if len(matches) != 1:
        raise RuntimeError("Không tìm thấy duy nhất một hồ sơ cho mã rút dữ liệu")
    shutil.rmtree(matches[0])
    print("Đã xóa hồ sơ nghiên cứu:", matches[0].name)
else:
    print("Để trống nếu không có yêu cầu rút dữ liệu.")
'''.splitlines(keepends=True),
    })

    notebook["metadata"]["colab"]["name"] = OUTPUT.name
    OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    build()
