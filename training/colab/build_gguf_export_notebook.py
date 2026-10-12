"""Generate Qwen3_Pointer_GGUF_Export_Colab.ipynb (merge LoRA -> GGUF -> fidelity gate -> upload).

Run after rebuilding the fidelity bundle so the embedded SHA-256 matches:
    python deployment/hf_space_api/fidelity/build_fidelity_bundle.py
    python training/colab/build_gguf_export_notebook.py

Two Python environments are used on Colab because they cannot share one: the merge and the
fidelity run use the latest transformers/peft/huggingface_hub, while llama.cpp's
convert_hf_to_gguf.py pins its own stack (transformers 4.57, torch 2.11, numpy 2.2,
protobuf < 5). The converter therefore runs in /content/convert-venv built from llama.cpp's
own requirements file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "training/colab/artifacts/gguf_fidelity_bundle_v1.zip"
OUT = ROOT / "training/colab/Qwen3_Pointer_GGUF_Export_Colab.ipynb"
BUNDLE_SHA256 = hashlib.sha256(BUNDLE.read_bytes()).hexdigest()

# Latest mutually compatible releases on 2026-10-12 (pip resolution for CPython 3.12 manylinux).
# llama-cpp-python must match deployment/hf_space_api/Dockerfile so the Space loads the GGUF
# with the same llama.cpp that wrote it.
MAIN_PACKAGES = [
    "transformers==5.19.0",
    "peft==0.21.2",
    "accelerate==1.15.0",
    "huggingface_hub==2.2.0",
    "tokenizers==0.23.3",
    "safetensors==0.8.0",
    "sentencepiece==0.2.2",
    "pydantic==2.14.1",
    "virtualenv==21.14.7",
]
LLAMA_CPP_PYTHON_TAG = "v0.3.36"

INTRO = """# Xuất Qwen3-4B + Pointer Stage 2 sang GGUF cho máy chủ CPU miễn phí

Notebook chạy **một lần** để tạo model cho API trên Hugging Face Spaces (CPU basic). Chọn runtime
**CPU**: llama.cpp được build giống hệt Dockerfile của Space nên thời gian đo ở bước 6 xấp xỉ trên Space.

**Cách chạy:** chạy cell 1. Cuối cell 1 runtime **tự khởi động lại** (Colab báo phiên bị ngắt, đó là bình
thường); sau đó chạy tiếp từ cell 2 đến cell 7. Không dùng "Run all" cho cell 1.

1. Cài bản mới nhất của transformers / peft / huggingface_hub và build `llama-cpp-python` 0.3.36 (AVX2).
   Script chuyển đổi của llama.cpp ghim thư viện riêng (transformers 4.57, torch 2.11) nên được cài
   trong môi trường tách biệt `/content/convert-venv` để không xung đột.
2. Cấu hình; Colab Secret `HF_TOKEN` cần quyền **write** vào repo artifact private.
3. Upload `training/colab/artifacts/gguf_fidelity_bundle_v1.zip` (mã runtime của Space, Parser v1
   đóng băng và 20 CV validation tổng hợp kèm output P0 đã đo).
4. Tải adapter đã khóa, kiểm tra hash, chat template và prompt ChatML của Space.
5. Gộp LoRA vào base FP16 → GGUF F16 → lượng tử hóa. Config/tokenizer lấy nguyên bản từ repo Qwen
   ở revision đã khóa; tên tensor sau gộp phải trùng base.
6. **Cổng độ trung thực**: chạy GGUF bằng đúng `LlamaPointerRuntime` của Space trên N CV validation,
   so CVSchema hợp lệ và Field Micro F1 với output P0 (NF4 + LoRA trên Colab GPU).
7. Chỉ upload GGUF khi qua cổng; in các biến cần dán vào Space.

Kết quả ở bước 6 là kiểm tra độ lệch do gộp/lượng tử hóa trên dữ liệu tổng hợp, không phải benchmark CV thật.
"""

CELLS = [
    f"""#@title 1. Cài thư viện (bản mới nhất) + build llama-cpp-python, rồi tự khởi động lại (~15–20 phút)
import json, os, subprocess, sys
from pathlib import Path

LLAMA_CPP_PYTHON_TAG = "{LLAMA_CPP_PYTHON_TAG}"
MAIN_PACKAGES = {json.dumps(MAIN_PACKAGES)}
CMAKE_ARGS = "-DGGML_NATIVE=OFF -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON -DGGML_BLAS=OFF -DLLAMA_CURL=OFF"
REPO = Path("/content/llama-cpp-python")
LLAMA_DIR = REPO / "vendor/llama.cpp"
VENV = Path("/content/convert-venv")
READY = Path("/content/.klcn029_gguf_env.json")

def run(command, **kwargs):
    print("$", " ".join(map(str, command)), flush=True)
    subprocess.check_call([str(part) for part in command], **kwargs)

def versions(python, modules):
    code = "import importlib, json, sys; print(json.dumps({{m: getattr(importlib.import_module(m), '__version__', '?') for m in sys.argv[1:]}}))"
    return json.loads(subprocess.check_output([str(python), "-c", code, *modules], text=True))

expected = {{"tag": LLAMA_CPP_PYTHON_TAG, "main_packages": MAIN_PACKAGES}}
if READY.exists() and json.loads(READY.read_text())["expected"] == expected:
    print("Môi trường đã sẵn sàng từ trước; chạy tiếp từ cell 2.")
    print(READY.read_text())
else:
    # Main kernel env: merge, fidelity run and upload use the latest releases.
    run([sys.executable, "-m", "pip", "install", "-q", "-U", *MAIN_PACKAGES])
    if not REPO.exists():
        run(["git", "clone", "--depth", "1", "--branch", LLAMA_CPP_PYTHON_TAG, "--recurse-submodules",
             "--shallow-submodules", "https://github.com/abetlen/llama-cpp-python", REPO])
    run([sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir", REPO],
        env=dict(os.environ, CMAKE_ARGS=CMAKE_ARGS))

    # Isolated converter env from llama.cpp's own requirements (same commit as llama-cpp-python).
    if not (VENV / "bin/python").exists():
        run([sys.executable, "-m", "virtualenv", "-q", VENV])
    run([VENV / "bin/pip", "install", "-q", "-r", LLAMA_DIR / "requirements/requirements-convert_hf_to_gguf.txt"])
    run([VENV / "bin/pip", "install", "-q", LLAMA_DIR / "gguf-py"])
    run([VENV / "bin/python", LLAMA_DIR / "convert_hf_to_gguf.py", "--help"], stdout=subprocess.DEVNULL)

    report = {{
        "expected": expected,
        "main": versions(sys.executable, ["transformers", "peft", "accelerate", "huggingface_hub", "tokenizers",
                                          "safetensors", "torch", "numpy", "pydantic", "llama_cpp"]),
        "converter": versions(VENV / "bin/python", ["transformers", "torch", "numpy", "gguf", "sentencepiece"]),
        "llama_cpp_commit": subprocess.check_output(["git", "-C", str(LLAMA_DIR), "rev-parse", "HEAD"], text=True).strip(),
    }}
    READY.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print("Cài đặt xong. Runtime sẽ khởi động lại để nạp thư viện mới — sau đó chạy tiếp từ cell 2.")
    os.kill(os.getpid(), 9)
""",
    f"""#@title 2. Cấu hình
import ctypes, gc, hashlib, json, os, shutil, statistics, subprocess, sys, time, zipfile
from pathlib import Path
from google.colab import files, userdata

ENV_REPORT = json.loads(Path("/content/.klcn029_gguf_env.json").read_text())
LLAMA_CPP_PYTHON_TAG = ENV_REPORT["expected"]["tag"]
LLAMA_DIR = Path("/content/llama-cpp-python/vendor/llama.cpp")
CONVERT_PYTHON = Path("/content/convert-venv/bin/python")

try:
    HF_TOKEN = userdata.get("HF_TOKEN")
except Exception as exc:
    raise RuntimeError("Thiếu Colab Secret HF_TOKEN hoặc chưa bật quyền cho notebook (biểu tượng chìa khóa).") from exc
MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
MODEL_REVISION = "1b4199c4f36b0cef378bfb12390c18780c18af4c"
ARTIFACT_REPO_ID = "huuloc4399/klcn029-qwen-pointer-artifacts"
ARTIFACT_REVISION = "398ce7961eac9b3ccd1661116f9287bf2b0b6b20"
EXPECTED_ADAPTER_MODEL_SHA256 = "8d68628e382593132010f20fb12cbb18d9477ca034c154811d109ec075a65f81"
CHAT_TEMPLATE_SHA256 = "40c21f34cf67d8c760ef72f8ad3ae5afad514299d4b06e91dd9a8d705af7b541"
FIDELITY_BUNDLE_SHA256 = "{BUNDLE_SHA256}"

QUANT = "Q4_K_M"  #@param ["Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"]
FIDELITY_SAMPLES = 10  #@param {{type:"integer"}}
MAX_F1_DROP_POINTS = 1.0  #@param {{type:"number"}}
FORCE_UPLOAD = False  #@param {{type:"boolean"}}

GGUF_PATH_IN_REPO = f"gguf/qwen3-4b-pointer-stage2-{{QUANT.lower()}}.gguf"
WORK = Path("/content/gguf_export")
WORK.mkdir(parents=True, exist_ok=True)

def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

import llama_cpp, peft, transformers, huggingface_hub
print({{"quant": QUANT, "target": GGUF_PATH_IN_REPO, "samples": FIDELITY_SAMPLES}})
print({{"transformers": transformers.__version__, "peft": peft.__version__,
       "huggingface_hub": huggingface_hub.__version__, "llama_cpp_python": llama_cpp.__version__,
       "converter": ENV_REPORT["converter"]}})
""",
    """#@title 3. Upload và xác minh fidelity bundle
bundle_path = WORK / "gguf_fidelity_bundle_v1.zip"
if not bundle_path.exists():
    print("Chọn tệp training/colab/artifacts/gguf_fidelity_bundle_v1.zip")
    uploaded = files.upload()
    bundle_path.write_bytes(uploaded[next(iter(uploaded))])
if sha256_file(bundle_path) != FIDELITY_BUNDLE_SHA256:
    raise RuntimeError("Fidelity bundle sai hash; hãy build lại bundle và notebook từ repo.")
bundle_dir = WORK / "fidelity"
with zipfile.ZipFile(bundle_path) as archive:
    archive.extractall(bundle_dir)
bundle_manifest = json.loads((bundle_dir / "MANIFEST.json").read_text(encoding="utf-8"))
for name, digest in bundle_manifest["files"].items():
    if sha256_file(bundle_dir / name) != digest:
        raise RuntimeError(f"Sai hash trong bundle: {name}")
sys.path.insert(0, str(bundle_dir / "runtime"))

from app.llm_runtime import LlamaPointerRuntime, render_chatml, MAX_NEW_TOKENS
from prompting import build_messages
from training.evaluation.pointer_parser import parse_pointer_output
from training.evaluation.metrics import compute_field_metrics
records = [json.loads(line) for line in (bundle_dir / "fidelity_set.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
records = records[:FIDELITY_SAMPLES]
print({"bundle_samples": bundle_manifest["samples"], "using": len(records)})
""",
    """#@title 4. Tải adapter đã khóa và kiểm tra prompt ChatML của Space
from huggingface_hub import snapshot_download
from transformers import AutoTokenizer

artifact_root = Path(snapshot_download(ARTIFACT_REPO_ID, revision=ARTIFACT_REVISION, token=HF_TOKEN,
                                       allow_patterns=["final_adapter/*"]))
adapter_dir = artifact_root / "final_adapter"
if sha256_file(adapter_dir / "adapter_model.safetensors") != EXPECTED_ADAPTER_MODEL_SHA256:
    raise RuntimeError("Adapter sai hash")
tokenizer = AutoTokenizer.from_pretrained(str(adapter_dir), trust_remote_code=False)
if hashlib.sha256(tokenizer.chat_template.encode("utf-8")).hexdigest() != CHAT_TEMPLATE_SHA256:
    raise RuntimeError("Sai chat template")
for record in records:
    messages, _ = build_messages(record["source_text"])
    if messages != record["messages"]:
        raise RuntimeError(f"Prompt contract lệch dữ liệu validation: {record['sample_id']}")
    expected = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    if render_chatml(messages) != expected:
        raise RuntimeError("render_chatml của Space khác chat template của tokenizer")
print("Prompt ChatML của Space khớp tokenizer cho", len(records), "CV")
""",
    """#@title 5. Gộp LoRA (FP16) -> GGUF F16 -> lượng tử hóa
import torch
from peft import PeftModel
from safetensors import safe_open
from transformers import AutoModelForCausalLM

def tensor_names(folder):
    names = set()
    for shard in sorted(Path(folder).glob("*.safetensors")):
        with safe_open(str(shard), framework="pt") as handle:
            names.update(handle.keys())
    return names

base_dir = Path(snapshot_download(MODEL_ID, revision=MODEL_REVISION, token=HF_TOKEN,
                                  allow_patterns=["*.json", "*.safetensors", "merges.txt", "vocab.json"]))
merged_dir = WORK / "merged_fp16"
if not (merged_dir / "MERGE_DONE.json").exists():
    shutil.rmtree(merged_dir, ignore_errors=True)
    started = time.perf_counter()
    base = AutoModelForCausalLM.from_pretrained(str(base_dir), dtype=torch.float16, trust_remote_code=False)
    merged = PeftModel.from_pretrained(base, str(adapter_dir), is_trainable=False).merge_and_unload()
    merged.save_pretrained(merged_dir, safe_serialization=True, max_shard_size="2GB")
    del base, merged
    gc.collect()
    # The converter runs llama.cpp's pinned transformers 4.57, so config and tokenizer files come
    # verbatim from the pinned Qwen snapshot instead of being re-serialized by transformers 5.
    for name in ("config.json", "generation_config.json", "tokenizer.json", "tokenizer_config.json",
                 "vocab.json", "merges.txt"):
        if (base_dir / name).exists():
            shutil.copy2(base_dir / name, merged_dir / name)
    base_names, merged_names = tensor_names(base_dir), tensor_names(merged_dir)
    if merged_names != base_names:
        raise RuntimeError(f"Tên tensor sau gộp khác base: thiếu {sorted(base_names - merged_names)[:5]}, "
                           f"thừa {sorted(merged_names - base_names)[:5]}")
    (merged_dir / "MERGE_DONE.json").write_text(json.dumps({
        "tensors": len(merged_names), "seconds": round(time.perf_counter() - started, 1)}))
print(json.loads((merged_dir / "MERGE_DONE.json").read_text()))

f16_path = WORK / "qwen3-4b-pointer-stage2-f16.gguf"
if not f16_path.exists():
    subprocess.check_call([str(CONVERT_PYTHON), str(LLAMA_DIR / "convert_hf_to_gguf.py"), str(merged_dir),
                           "--outtype", "f16", "--outfile", str(f16_path)])

gguf_path = WORK / Path(GGUF_PATH_IN_REPO).name
if not gguf_path.exists():
    params = llama_cpp.llama_model_quantize_default_params()
    params.ftype = getattr(llama_cpp, f"LLAMA_FTYPE_MOSTLY_{QUANT}")
    params.nthread = os.cpu_count() or 2
    if llama_cpp.llama_model_quantize(str(f16_path).encode(), str(gguf_path).encode(), ctypes.byref(params)) != 0:
        raise RuntimeError("llama_model_quantize thất bại")
gguf_sha256 = sha256_file(gguf_path)
print({"gguf": gguf_path.name, "bytes": gguf_path.stat().st_size, "sha256": gguf_sha256})
""",
    """#@title 6. Cổng độ trung thực: GGUF (runtime của Space) so với P0
runtime = LlamaPointerRuntime(gguf_path, {"filename": gguf_path.name, "sha256": gguf_sha256})
for record in records[:3]:
    prompt = render_chatml(build_messages(record["source_text"])[0])
    hf_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    llama_ids = runtime.llm.tokenize(prompt.encode("utf-8"), add_bos=False, special=True)
    if list(hf_ids) != list(llama_ids):
        raise RuntimeError(f"Tokenizer GGUF khác tokenizer HF: {record['sample_id']}")

rows = []
for index, record in enumerate(records, 1):
    messages, normalized = build_messages(record["source_text"])
    generation = runtime.generate(messages)
    parsed = parse_pointer_output(generation["raw_output"], normalized)
    rows.append({
        "sample_id": record["sample_id"],
        "status": parsed.status,
        "cvschema_valid": parsed.cvschema_valid,
        "pointer_equal_p0": parsed.parsed_pointer == record["p0_reference"]["parsed_pointer"],
        "input_tokens": generation["input_tokens"],
        "generated_tokens": generation["generated_tokens"],
        "hit_max_new_tokens": generation["hit_max_new_tokens"],
        "runtime_seconds": generation["runtime_seconds"],
        "cvschema": parsed.reconstructed_cvschema if parsed.cvschema_valid else None,
    })
    print(index, {k: v for k, v in rows[-1].items() if k != "cvschema"})

gold = {record["sample_id"]: record["gold_cvschema"] for record in records}
gguf_f1 = compute_field_metrics(gold, {row["sample_id"]: row["cvschema"] for row in rows})["micro"]["f1"]
p0_f1 = compute_field_metrics(gold, {
    record["sample_id"]: record["p0_reference"]["reconstructed_cvschema"] if record["p0_reference"]["cvschema_valid"] else None
    for record in records
})["micro"]["f1"]
times = [row["runtime_seconds"] for row in rows]
fidelity = {
    "quant": QUANT,
    "samples": len(rows),
    "cvschema_valid": sum(row["cvschema_valid"] for row in rows),
    "p0_cvschema_valid": sum(record["p0_reference"]["cvschema_valid"] for record in records),
    "pointer_equal_p0": sum(row["pointer_equal_p0"] for row in rows),
    "field_micro_f1_gguf": round(gguf_f1, 6),
    "field_micro_f1_p0": round(p0_f1, 6),
    "f1_drop_points": round((p0_f1 - gguf_f1) * 100, 3),
    "threads": runtime.threads,
    "seconds_first_cv": times[0],
    "seconds_mean_after_first": round(statistics.mean(times[1:]), 2) if len(times) > 1 else None,
    "seconds_max": max(times),
    "generated_tokens_mean": round(statistics.mean(row["generated_tokens"] for row in rows), 1),
}
fidelity["passed"] = (fidelity["cvschema_valid"] >= fidelity["p0_cvschema_valid"]
                      and fidelity["f1_drop_points"] <= MAX_F1_DROP_POINTS)
print(json.dumps(fidelity, indent=2))
if not fidelity["passed"]:
    print("CHƯA QUA cổng độ trung thực. Thử QUANT = 'Q5_K_M' hoặc 'Q6_K' rồi chạy lại từ cell 2 (bỏ qua merge đã có).")
""",
    """#@title 7. Upload GGUF + manifest và in cấu hình cho Space
from huggingface_hub import CommitOperationAdd, HfApi

if not fidelity["passed"] and not FORCE_UPLOAD:
    raise RuntimeError("Không upload vì GGUF chưa qua cổng độ trung thực.")
export_manifest = {
    "export_version": "klcn029_pointer_gguf_export_v2",
    "created_at_unix": int(time.time()),
    "base_model": {"id": MODEL_ID, "revision": MODEL_REVISION},
    "adapter": {"repo_id": ARTIFACT_REPO_ID, "revision": ARTIFACT_REVISION, "adapter_model_sha256": EXPECTED_ADAPTER_MODEL_SHA256},
    "merge": {"dtype": "float16", "method": "peft merge_and_unload", "config_and_tokenizer": "verbatim from base revision"},
    "llama_cpp_python": LLAMA_CPP_PYTHON_TAG,
    "environment": ENV_REPORT,
    "quantization": QUANT,
    "gguf": {"path_in_repo": GGUF_PATH_IN_REPO, "bytes": gguf_path.stat().st_size, "sha256": gguf_sha256},
    "decoding": {"greedy": True, "max_new_tokens": MAX_NEW_TOKENS, "repeat_penalty": 1.0},
    "fidelity": fidelity,
    "fidelity_bundle_sha256": FIDELITY_BUNDLE_SHA256,
    "forced_upload": bool(FORCE_UPLOAD and not fidelity["passed"]),
}
manifest_bytes = (json.dumps(export_manifest, indent=2) + "\\n").encode("utf-8")
commit = HfApi(token=HF_TOKEN).create_commit(
    repo_id=ARTIFACT_REPO_ID,
    operations=[
        CommitOperationAdd(path_in_repo=GGUF_PATH_IN_REPO, path_or_fileobj=str(gguf_path)),
        CommitOperationAdd(path_in_repo=GGUF_PATH_IN_REPO + ".manifest.json", path_or_fileobj=manifest_bytes),
    ],
    commit_message=f"Add Pointer Stage 2 GGUF {QUANT} for CPU Space",
)
(WORK / "gguf_export_manifest.json").write_bytes(manifest_bytes)
files.download(str(WORK / "gguf_export_manifest.json"))
print("Dán các biến sau vào Space (Settings > Variables):")
print(f"GGUF_REPO_ID={ARTIFACT_REPO_ID}")
print(f"GGUF_FILENAME={GGUF_PATH_IN_REPO}")
print(f"GGUF_REVISION={commit.oid}")
print(f"GGUF_SHA256={gguf_sha256}")
""",
]


def cell(kind: str, source: str) -> dict:
    lines = source.splitlines(keepends=True)
    if kind == "markdown":
        return {"cell_type": "markdown", "metadata": {}, "source": lines}
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": lines}


def main() -> None:
    notebook = {
        "cells": [cell("markdown", INTRO)] + [cell("code", source) for source in CELLS],
        "metadata": {
            "colab": {"provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 0,
    }
    for source in CELLS:
        compile(source, "<cell>", "exec")
    OUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} (fidelity bundle {BUNDLE_SHA256[:12]}…)")


if __name__ == "__main__":
    main()
