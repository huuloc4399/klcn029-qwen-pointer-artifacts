"""Re-run the GGUF fidelity gate on a deployment host (ARM, Windows CPU/GPU) instead of Colab x86.

Same check as cell 6 of training/colab/Qwen3_Pointer_GGUF_Export_Colab.ipynb: N synthetic
validation CVs from gguf_fidelity_bundle_v1.zip are generated and compared with the recorded
P0 outputs (NF4 + LoRA on a Colab GPU). Synthetic data only. Run it from the API bundle folder
while the API itself is stopped, so the two do not compete for the CPU/GPU.

Default: the runtime code frozen inside the bundle (llama-cpp-python), as on the Oracle VM:
    docker compose run --rm -v ./gguf_fidelity_bundle_v1.zip:/tmp/bundle.zip:ro api \
        python fidelity_check.py /tmp/bundle.zip --samples 10
--app-runtime: the API's own load_runtime(), e.g. llama-server on Windows (LLAMA_SERVER_URL):
    python fidelity_check.py gguf_fidelity_bundle_v1.zip --samples 10 --app-runtime
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
import tempfile
import zipfile
from pathlib import Path


BUNDLE_SHA256 = "0700b90684d9ff00267a728ff24a3652fbc458951ec41b5c42b9461b4fa72248"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--max-f1-drop-points", type=float, default=1.0)
    parser.add_argument("--app-runtime", action="store_true",
                        help="measure the API's load_runtime() (e.g. llama-server) instead of the bundle runtime")
    parser.add_argument("--host", default="oracle_ampere_a1", help="label stored with the result")
    args = parser.parse_args()

    if sha256_file(args.bundle) != BUNDLE_SHA256:
        sys.exit("Fidelity bundle sai hash; dùng training/colab/artifacts/gguf_fidelity_bundle_v1.zip của repo.")
    bundle_dir = Path(tempfile.mkdtemp(prefix="fidelity-"))
    with zipfile.ZipFile(args.bundle) as archive:
        archive.extractall(bundle_dir)
    manifest = json.loads((bundle_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    for name, digest in manifest["files"].items():
        if sha256_file(bundle_dir / name) != digest:
            sys.exit(f"Sai hash trong bundle: {name}")
    runtime_dir = bundle_dir / "runtime"
    if args.app_runtime:
        # The API folder (current directory) provides app/, prompting and the frozen parser;
        # its manifest guarantees they match the build. Only metrics.py comes from the bundle.
        sys.path.insert(0, str(Path.cwd()))
        from app.llm_runtime import load_runtime
    else:
        # The bundle's runtime (same files the export notebook measured) takes precedence.
        sys.path.insert(0, str(runtime_dir))
        from app.llm_runtime import LlamaPointerRuntime, download_gguf

        def load_runtime():
            return LlamaPointerRuntime(*download_gguf())
    from prompting import build_messages
    from training.evaluation.pointer_parser import parse_pointer_output
    compute_field_metrics = load_module(
        "fidelity_metrics", runtime_dir / "training/evaluation/metrics.py").compute_field_metrics

    records = [json.loads(line) for line in (bundle_dir / "fidelity_set.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()][:args.samples]
    runtime = load_runtime()

    rows = []
    for index, record in enumerate(records, 1):
        messages, normalized = build_messages(record["source_text"])
        generation = runtime.generate(messages)
        parsed = parse_pointer_output(generation["raw_output"], normalized)
        rows.append({
            "sample_id": record["sample_id"],
            "cvschema_valid": parsed.cvschema_valid,
            "pointer_equal_p0": parsed.parsed_pointer == record["p0_reference"]["parsed_pointer"],
            "generated_tokens": generation["generated_tokens"],
            "runtime_seconds": generation["runtime_seconds"],
            "cvschema": parsed.reconstructed_cvschema if parsed.cvschema_valid else None,
        })
        print(index, {k: v for k, v in rows[-1].items() if k != "cvschema"}, flush=True)

    gold = {record["sample_id"]: record["gold_cvschema"] for record in records}
    gguf_f1 = compute_field_metrics(gold, {row["sample_id"]: row["cvschema"] for row in rows})["micro"]["f1"]
    p0_f1 = compute_field_metrics(gold, {
        record["sample_id"]: record["p0_reference"]["reconstructed_cvschema"] if record["p0_reference"]["cvschema_valid"] else None
        for record in records
    })["micro"]["f1"]
    times = [row["runtime_seconds"] for row in rows]
    fidelity = {
        "host": args.host,
        "gguf": runtime.artifact,
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
                          and fidelity["f1_drop_points"] <= args.max_f1_drop_points)
    print(json.dumps(fidelity, indent=2, ensure_ascii=False))
    if not fidelity["passed"]:
        sys.exit("CHƯA QUA cổng độ trung thực trên máy triển khai.")


if __name__ == "__main__":
    main()
