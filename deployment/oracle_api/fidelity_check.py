"""Re-run the GGUF fidelity gate on the deployment VM (ARM llama.cpp instead of Colab x86).

Same check as cell 6 of training/colab/Qwen3_Pointer_GGUF_Export_Colab.ipynb: the runtime code
inside gguf_fidelity_bundle_v1.zip generates on N synthetic validation CVs and is compared with
the recorded P0 outputs (NF4 + LoRA on a Colab GPU). Synthetic data only.

Run with the API stopped so the two processes do not share the 2 OCPUs (see the guide):
    docker compose run --rm -v ./gguf_fidelity_bundle_v1.zip:/tmp/bundle.zip:ro api \
        python fidelity_check.py /tmp/bundle.zip --samples 10
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import tempfile
import zipfile
from pathlib import Path


BUNDLE_SHA256 = "0700b90684d9ff00267a728ff24a3652fbc458951ec41b5c42b9461b4fa72248"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--max-f1-drop-points", type=float, default=1.0)
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
    # The bundle's runtime (same files the export notebook measured) takes precedence over the app's.
    sys.path.insert(0, str(bundle_dir / "runtime"))
    from app.llm_runtime import LlamaPointerRuntime, download_gguf
    from prompting import build_messages
    from training.evaluation.metrics import compute_field_metrics
    from training.evaluation.pointer_parser import parse_pointer_output

    records = [json.loads(line) for line in (bundle_dir / "fidelity_set.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()][:args.samples]
    gguf_path, artifact = download_gguf()
    runtime = LlamaPointerRuntime(gguf_path, artifact)

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
        "host": "oracle_ampere_a1",
        "gguf": artifact,
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
    print(json.dumps(fidelity, indent=2))
    if not fidelity["passed"]:
        sys.exit("CHƯA QUA cổng độ trung thực trên máy triển khai.")


if __name__ == "__main__":
    main()
