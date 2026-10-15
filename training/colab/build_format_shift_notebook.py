"""Generate Qwen3_Format_Shift_Counterfactual_Colab.ipynb (raw generation for format_shift_v1).

One notebook, three runs: MODEL_VARIANT = base (B0), adapter_stage1 (B1) or pointer_stage2 (P0).
Model revision, NF4 quantization, greedy decoding, token budgets and prompts are the ones used
for the earlier validation/GOLD40 runs; only the input texts differ. The notebook never sees
labels and runs no parser or metric; scoring is offline with
training/evaluation/evaluate_format_shift.py.

Run after building the inputs (python -m training.evaluation.format_shift), so the embedded
hashes match training/colab/artifacts/format_shift_v1_inputs.zip.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "training/colab/artifacts/format_shift_v1_inputs.zip"
INPUTS = ROOT / "training/data/format_shift_v1/inputs.jsonl"
OUT = ROOT / "training/colab/Qwen3_Format_Shift_Counterfactual_Colab.ipynb"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


INTRO = """# Thí nghiệm kiểm chứng: model có phụ thuộc định dạng CV tổng hợp không? (format_shift_v1)

20 CV **tổng hợp** của tập validation, mỗi CV 5 biến thể có **cùng nhãn**: `original`, `headings`
(đổi tiêu đề mục, một nửa sang tiếng Việt), `grouped_skills` (kỹ năng gộp dạng `Nhóm: a, b, c`),
`wrapped_text` (summary/mô tả/chi tiết ngắt nhiều dòng như khi trích PDF), `combined` (cả ba).
Nếu F1 của một model giảm mạnh giữa các biến thể của cùng CV thì model phụ thuộc vào định dạng,
không phải nội dung. Không dùng CV thật hay GOLD40.

**Chạy 3 lần**, mỗi lần chọn một `MODEL_VARIANT` ở cell 2: `base` (B0, ~2 giờ), `adapter_stage1`
(B1, ~2,7 giờ), `pointer_stage2` (P0, ~1,7 giờ). Runtime → Change runtime type → **T4 GPU**.

1. Chạy cell 1. Nếu cell 2 báo sai phiên bản thư viện: Runtime → Restart session rồi chạy từ cell 2.
2. Cell 3 hỏi `format_shift_v1_inputs.zip` (trong `training/colab/artifacts/`) ở lần đầu.
3. Cell 4 dùng adapter đã có trên Drive nếu đúng hash; nếu chưa có thì hỏi ZIP:
   `final_adapter-full_1.zip` cho B1, `qwen3_4b_cvschema2_pointer_stage2_full_v1_final_adapter.zip` cho P0.
4. Cell 7 lưu từng mẫu vào Drive. Bị ngắt thì kết nối lại và chạy cell 1 → 7: chỉ mẫu đang dở
   phải chạy lại. Thứ tự là từng CV với đủ 5 biến thể, nên dừng giữa chừng vẫn so cặp được.
5. Cell 8 đóng gói và tải ZIP kết quả (được cả khi chưa xong hết, để chấm phần đã có).

Cấu hình giữ như các lần đo trước: Qwen3-4B-Instruct-2507 revision cố định, NF4 double quant,
FP16, greedy, Full JSON 1.280 token, Pointer 768 token, cùng prompt và chat template.
"""

CELLS = [
    """#@title 1. Cài đúng phiên bản thư viện
%pip install -q --upgrade "transformers==5.17.0" "peft==0.21.0" "accelerate==1.15.0" "bitsandbytes==0.50.2" "huggingface_hub==1.32.0" "tokenizers==0.23.2" "sentencepiece==0.2.1"
""",
    f"""#@title 2. Chọn model, mount Drive, kiểm tra GPU và phiên bản
MODEL_VARIANT = "base"  #@param ["base", "adapter_stage1", "pointer_stage2"]

from google.colab import drive, files
drive.mount("/content/drive")

import hashlib, json, os, random, shutil, sys, time, zipfile
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import torch

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
MODEL_REVISION = "1b4199c4f36b0cef378bfb12390c18780c18af4c"
CHAT_TEMPLATE_SHA256 = "40c21f34cf67d8c760ef72f8ad3ae5afad514299d4b06e91dd9a8d705af7b541"
INPUT_ZIP_SHA256 = "{sha(PACKAGE)}"
INPUTS_SHA256 = "{sha(INPUTS)}"
VARIANTS = ("original", "headings", "grouped_skills", "wrapped_text", "combined")
ADAPTERS = {{
    "adapter_stage1": {{
        "zip": "final_adapter-full_1.zip",
        "zip_sha256": "bb9dc701b0a898de0a0e890bb540144b93321c31bba791b707ec45d5b68e00f5",
        "model_sha256": "670e5725e07258ff2f5d1e68c54824c78ab1087d9143065fcdab02f0703f5fbf",
        "drive_dir": "runs/qwen3_4b_cvschema2_stage1_full_v1/final_adapter",
    }},
    "pointer_stage2": {{
        "zip": "qwen3_4b_cvschema2_pointer_stage2_full_v1_final_adapter.zip",
        "zip_sha256": "274aeb95e78f5717b04af9fd0045e5215fd247533bd9572c73c73e8242f86b4b",
        "model_sha256": "8d68628e382593132010f20fb12cbb18d9477ca034c154811d109ec075a65f81",
        "drive_dir": "runs/qwen3_4b_cvschema2_pointer_stage2_full_v1/final_adapter",
    }},
}}
if MODEL_VARIANT not in ("base", *ADAPTERS):
    raise RuntimeError("MODEL_VARIANT không hợp lệ")
POINTER = MODEL_VARIANT == "pointer_stage2"
MAX_NEW_TOKENS = 768 if POINTER else 1280
MAX_INPUT_TOKENS = 5120 if POINTER else 8192
SEED = 42

DRIVE_ROOT = Path("/content/drive/MyDrive/KLCN029")
DATA_DIR = DRIVE_ROOT / "data/format_shift_v1"
OUTPUT_ID = f"format_shift_v1_{{MODEL_VARIANT}}_raw_greedy"
OUTPUT_DIR = DRIVE_ROOT / "evaluations/format_shift_v1" / OUTPUT_ID
SAMPLE_DIR = OUTPUT_DIR / "samples"
LOCAL_WORK = Path("/content/format_shift_work")
for path in (SAMPLE_DIR, LOCAL_WORK):
    path.mkdir(parents=True, exist_ok=True)

SOFTWARE_PINS = {{"transformers": "5.17.0", "accelerate": "1.15.0", "bitsandbytes": "0.50.2",
                  "huggingface_hub": "1.32.0", "tokenizers": "0.23.2", "sentencepiece": "0.2.1", "peft": "0.21.0"}}
for package, expected in SOFTWARE_PINS.items():
    if version(package) != expected:
        raise RuntimeError(f"{{package}}: cần {{expected}}, đang có {{version(package)}}. Runtime → Restart session rồi chạy lại từ cell 2.")
if not torch.cuda.is_available():
    raise RuntimeError("Chọn Runtime → Change runtime type → T4 GPU.")
gpu_name = torch.cuda.get_device_name(0)
if "T4" not in gpu_name.upper():
    print(f"Cảnh báo: các lần đo trước dùng T4; GPU hiện tại là {{gpu_name!r}}.")
random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)
torch.backends.cuda.matmul.allow_tf32 = False
print({{"model_variant": MODEL_VARIANT, "gpu": gpu_name, "max_new_tokens": MAX_NEW_TOKENS, "output_dir": str(OUTPUT_DIR)}})
""",
    """#@title 3. Nạp và xác minh 100 đầu vào (không có nhãn)
def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def canonical_sha256(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def atomic_write_json(path, payload):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)

def safe_extract(zip_path, destination):
    root = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP lỗi CRC")
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if root != target and root not in target.parents:
                raise RuntimeError(f"Đường dẫn không an toàn trong ZIP: {member.filename}")
        archive.extractall(destination)

inputs_path = DATA_DIR / "inputs.jsonl"
if not inputs_path.is_file() or sha256_file(inputs_path) != INPUTS_SHA256:
    print("Chọn format_shift_v1_inputs.zip")
    uploaded = files.upload()
    name = next(n for n in uploaded if n.lower().endswith(".zip"))
    local_zip = LOCAL_WORK / name
    local_zip.write_bytes(uploaded[name])
    if sha256_file(local_zip) != INPUT_ZIP_SHA256:
        raise RuntimeError("Sai ZIP đầu vào format_shift_v1")
    staging = LOCAL_WORK / "inputs"
    shutil.rmtree(staging, ignore_errors=True)
    safe_extract(local_zip, staging)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(staging / "format_shift_v1/inputs.jsonl", inputs_path)
if sha256_file(inputs_path) != INPUTS_SHA256:
    raise RuntimeError("Sai SHA-256 của inputs.jsonl")
records = [json.loads(line) for line in inputs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
for record in records:
    if any(key in record for key in ("target", "target_cvschema", "target_pointer")):
        raise RuntimeError("Phát hiện nhãn trong đầu vào")
    if hashlib.sha256(record["source_text"].encode()).hexdigest() != record["source_text_sha256"]:
        raise RuntimeError(f"Sai hash văn bản: {record['sample_id']}")
print({"records": len(records), "cvs": len({r["cv_id"] for r in records}), "variants": sorted({r["variant"] for r in records})})
""",
    """#@title 4. Xác minh adapter (B0 bỏ qua)
ADAPTER_DIR = None
adapter_model_sha256 = None
if MODEL_VARIANT != "base":
    spec = ADAPTERS[MODEL_VARIANT]
    ADAPTER_DIR = DRIVE_ROOT / spec["drive_dir"]

    def adapter_ok(path):
        return ((path / "_COMPLETE").is_file() and (path / "adapter_model.safetensors").is_file()
                and sha256_file(path / "adapter_model.safetensors") == spec["model_sha256"])

    if not adapter_ok(ADAPTER_DIR):
        print(f"Chọn {spec['zip']}")
        uploaded = files.upload()
        name = next(n for n in uploaded if n.lower().endswith(".zip"))
        local_zip = LOCAL_WORK / name
        local_zip.write_bytes(uploaded[name])
        del uploaded
        if sha256_file(local_zip) != spec["zip_sha256"]:
            raise RuntimeError(f"Sai ZIP adapter; cần đúng {spec['zip']}")
        staging = LOCAL_WORK / "adapter"
        shutil.rmtree(staging, ignore_errors=True)
        safe_extract(local_zip, staging)
        if ADAPTER_DIR.exists():
            ADAPTER_DIR.rename(ADAPTER_DIR.with_name(ADAPTER_DIR.name + f".invalid_{int(time.time())}"))
        ADAPTER_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staging / "final_adapter", ADAPTER_DIR)
    if not adapter_ok(ADAPTER_DIR):
        raise RuntimeError("Adapter trên Drive sai hash")
    adapter_model_sha256 = spec["model_sha256"]
    print({"adapter": str(ADAPTER_DIR), "verified": True})
else:
    print("B0: Qwen gốc, không nạp adapter")
""",
    """#@title 5. Tokenizer, chat template và hợp đồng đánh giá
from transformers import AutoTokenizer

tokenizer_source = str(ADAPTER_DIR) if ADAPTER_DIR else MODEL_ID
tokenizer = AutoTokenizer.from_pretrained(tokenizer_source, revision=None if ADAPTER_DIR else MODEL_REVISION,
                                          trust_remote_code=False)
if tokenizer.pad_token_id is None:
    tokenizer.pad_token = tokenizer.eos_token
if hashlib.sha256(tokenizer.chat_template.encode("utf-8")).hexdigest() != CHAT_TEMPLATE_SHA256:
    raise RuntimeError("Sai chat template")

eval_contract = {
    "experiment": "format_shift_v1", "model_variant": MODEL_VARIANT,
    "model_id": MODEL_ID, "model_revision": MODEL_REVISION, "adapter_model_sha256": adapter_model_sha256,
    "inputs_sha256": INPUTS_SHA256, "prompt": "pointer_messages" if POINTER else "fulljson_messages",
    "generation": {"do_sample": False, "max_new_tokens": MAX_NEW_TOKENS, "seed": SEED},
    "quantization": {"load_in_4bit": True, "bnb_4bit_quant_type": "nf4", "bnb_4bit_use_double_quant": True,
                     "bnb_4bit_compute_dtype": "float16"},
    "chat_template_sha256": CHAT_TEMPLATE_SHA256, "software_pins": SOFTWARE_PINS,
    "labels_loaded": False, "parser_applied": False,
}
eval_id = canonical_sha256(eval_contract)
config_path = OUTPUT_DIR / "eval_config.json"
if config_path.exists() and json.loads(config_path.read_text(encoding="utf-8")) != {"eval_id": eval_id, **eval_contract}:
    raise RuntimeError("eval_config.json trên Drive khác cấu hình hiện tại; đổi OUTPUT_ID hoặc xoá thư mục cũ.")
atomic_write_json(config_path, {"eval_id": eval_id, **eval_contract})
print({"eval_id": eval_id})
""",
    """#@title 6. Nạp model 4-bit
from transformers import AutoModelForCausalLM, BitsAndBytesConfig

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, revision=MODEL_REVISION,
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                           bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16),
    device_map={"": 0}, dtype=torch.float16, attn_implementation="sdpa", trust_remote_code=False,
)
if ADAPTER_DIR:
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, str(ADAPTER_DIR), is_trainable=False)
model.eval()
model.config.use_cache = True
print({"model_variant": MODEL_VARIANT, "device": str(next(model.parameters()).device)})
""",
    """#@title 7. Sinh raw output, lưu từng mẫu, tự tiếp tục khi chạy lại
def prompt_for(record):
    messages = record["pointer_messages"] if POINTER else record["fulljson_messages"]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

def saved_ok(path, record, prompt_sha):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (payload.get("eval_id") == eval_id and payload.get("sample_id") == record["sample_id"]
            and payload.get("prompt_sha256") == prompt_sha and isinstance(payload.get("raw_output"), str))

prompts = {}
for record in records:
    prompt = prompt_for(record)
    length = len(tokenizer(prompt, truncation=False)["input_ids"])
    if length > MAX_INPUT_TOKENS:
        raise RuntimeError(f"{record['sample_id']}: {length} token vượt {MAX_INPUT_TOKENS}; không cắt.")
    prompts[record["sample_id"]] = (prompt, hashlib.sha256(prompt.encode()).hexdigest(), length)
done_before = sum(saved_ok(SAMPLE_DIR / f"{r['sample_id']}.json", r, prompts[r["sample_id"]][1]) for r in records)
print({"preflight": "passed", "already_saved": done_before, "remaining": len(records) - done_before})

session_started, generated_now = time.perf_counter(), 0
for index, record in enumerate(records, 1):
    sample_path = SAMPLE_DIR / f"{record['sample_id']}.json"
    prompt, prompt_sha, input_tokens = prompts[record["sample_id"]]
    if saved_ok(sample_path, record, prompt_sha):
        continue
    encoded = tokenizer(prompt, return_tensors="pt", truncation=False)
    input_ids = encoded["input_ids"].to(model.device)
    torch.cuda.synchronize()
    started = time.perf_counter()
    with torch.inference_mode():
        generated = model.generate(input_ids=input_ids, attention_mask=encoded["attention_mask"].to(model.device),
                                   do_sample=False, max_new_tokens=MAX_NEW_TOKENS,
                                   pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id,
                                   use_cache=True)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    new_ids = generated[0, input_ids.shape[1]:]
    output_tokens = int(new_ids.numel())
    ended_with_eos = bool(output_tokens and int(new_ids[-1].item()) == int(tokenizer.eos_token_id))
    atomic_write_json(sample_path, {
        "eval_id": eval_id, "sample_id": record["sample_id"], "cv_id": record["cv_id"], "variant": record["variant"],
        "model_variant": MODEL_VARIANT, "prompt_sha256": prompt_sha, "source_text_sha256": record["source_text_sha256"],
        "raw_output": tokenizer.decode(new_ids, skip_special_tokens=True).strip(),
        "input_tokens": input_tokens, "generated_tokens": output_tokens, "ended_with_eos": ended_with_eos,
        "hit_max_new_tokens": output_tokens >= MAX_NEW_TOKENS and not ended_with_eos,
        "runtime_seconds": round(elapsed, 3), "gpu": gpu_name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    generated_now += 1
    mean = (time.perf_counter() - session_started) / generated_now
    remaining = sum(not (SAMPLE_DIR / f"{r['sample_id']}.json").exists() for r in records)
    print(f"{index}/{len(records)} {record['sample_id']}: {output_tokens} token, {elapsed:.0f}s; còn {remaining} mẫu, ~{remaining * mean / 60:.0f} phút")
print("Đã sinh xong toàn bộ mẫu." if all((SAMPLE_DIR / f"{r['sample_id']}.json").exists() for r in records) else "Chưa xong; chạy lại cell 7.")
""",
    """#@title 8. Đóng gói và tải ZIP kết quả (chạy được cả khi chưa xong)
rows = []
for record in records:
    path = SAMPLE_DIR / f"{record['sample_id']}.json"
    if path.exists() and saved_ok(path, record, prompts[record["sample_id"]][1]):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
complete_cvs = sorted(cv for cv in {r["cv_id"] for r in records}
                      if sum(row["cv_id"] == cv for row in rows) == len(VARIANTS))
summary = {
    "eval_id": eval_id, "model_variant": MODEL_VARIANT, "samples": len(rows), "expected": len(records),
    "complete_cv_count": len(complete_cvs), "complete": len(rows) == len(records),
    "hit_max_new_tokens": sum(r["hit_max_new_tokens"] for r in rows),
    "runtime_seconds_total": round(sum(r["runtime_seconds"] for r in rows), 1),
    "generated_tokens_total": sum(r["generated_tokens"] for r in rows),
}
atomic_write_json(OUTPUT_DIR / "generation_summary.json", summary)
(OUTPUT_DIR / "predictions_raw.jsonl").write_text(
    "".join(json.dumps(r, ensure_ascii=False) + "\\n" for r in rows), encoding="utf-8")
local_zip = Path("/content") / f"{OUTPUT_ID}.zip"
with zipfile.ZipFile(local_zip, "w", zipfile.ZIP_DEFLATED) as archive:
    for name in ("eval_config.json", "generation_summary.json", "predictions_raw.jsonl"):
        archive.write(OUTPUT_DIR / name, f"{OUTPUT_ID}/{name}")
print(summary)
files.download(str(local_zip))
""",
]


def cell(kind: str, source: str, index: int) -> dict:
    lines = source.splitlines(keepends=True)
    base = {"id": f"format-shift-{index}", "metadata": {}, "source": lines}
    if kind == "markdown":
        return {"cell_type": "markdown", **base}
    return {"cell_type": "code", "execution_count": None, "outputs": [], **base}


def main() -> None:
    for source in CELLS:
        compile(source.replace("%pip", "#pip"), "<cell>", "exec")
    notebook = {
        "cells": [cell("markdown", INTRO, 0)] + [cell("code", source, i) for i, source in enumerate(CELLS, 1)],
        "metadata": {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"},
                     "kernelspec": {"display_name": "Python 3", "name": "python3"},
                     "language_info": {"name": "python"}},
        "nbformat": 4, "nbformat_minor": 0,
    }
    OUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
