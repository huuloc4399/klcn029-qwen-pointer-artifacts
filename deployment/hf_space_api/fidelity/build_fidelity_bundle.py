"""Package what the GGUF export notebook needs to check the quantized model against frozen P0.

The bundle holds the exact Space runtime code (app/llm_runtime.py, prompting, frozen Parser
v1, metrics, deployment policy) and the first N synthetic validation CVs with their gold
CVSchema and the P0 (Colab, NF4 + LoRA) outputs recorded in
training/evaluation/results/pointer_stage2_validation_p0_v1. Synthetic data only (CC-BY-4.0),
no real CVs.

Usage: python deployment/hf_space_api/fidelity/build_fidelity_bundle.py [--samples 20]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FROZEN = ROOT / "training/evaluation/frozen/cvpointer_output_parser_v1"
VALIDATION = ROOT / "training/data/resume_parsing_vision_cvschema_v2_pointer_v1/validation.jsonl"
P0_RESULTS = ROOT / "training/evaluation/results/pointer_stage2_validation_p0_v1/sample_results.jsonl"
OUT = ROOT / "training/colab/artifacts/gguf_fidelity_bundle_v1.zip"
FILES = {
    "runtime/app/__init__.py": ROOT / "deployment/hf_space_api/app/__init__.py",
    "runtime/app/llm_runtime.py": ROOT / "deployment/hf_space_api/app/llm_runtime.py",
    "runtime/prompting.py": ROOT / "deployment/runpod_qwen/prompting.py",
    "runtime/prompt_contract.json": ROOT / "deployment/runpod_qwen/prompt_contract.json",
    "runtime/baseline_extraction/__init__.py": ROOT / "baseline_extraction/__init__.py",
    "runtime/baseline_extraction/schema.py": FROZEN / "schema.py",
    "runtime/training/__init__.py": ROOT / "training/__init__.py",
    "runtime/training/evaluation/__init__.py": ROOT / "training/evaluation/__init__.py",
    "runtime/training/evaluation/parser.py": FROZEN / "parser.py",
    "runtime/training/evaluation/pointer_parser.py": FROZEN / "pointer_parser.py",
    "runtime/training/evaluation/metrics.py": FROZEN / "metrics.py",
    "runtime/training/evaluation/deployment_policy.py": ROOT / "training/evaluation/deployment_policy.py",
}


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=20)
    args = parser.parse_args()

    references = {row["sample_id"]: row for row in jsonl(P0_RESULTS)}
    records = []
    for row in jsonl(VALIDATION)[: args.samples]:
        reference = references[row["sample_id"]]
        records.append({
            "sample_id": row["sample_id"],
            "source_text": row["source_text"],
            "messages": row["messages"][:2],
            "gold_cvschema": row["target_cvschema"],
            "p0_reference": {
                "parsed_pointer": reference["parsed_pointer"],
                "reconstructed_cvschema": reference["reconstructed_cvschema"],
                "cvschema_valid": reference["cvschema_valid"],
                "generated_tokens": reference["generated_tokens"],
                "runtime_seconds_colab_t4": reference["runtime_seconds"],
            },
        })
    fidelity = "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"

    hashes = {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, source in FILES.items():
            data = source.read_bytes()
            bundle.writestr(name, data)
            hashes[name] = hashlib.sha256(data).hexdigest()
        bundle.writestr("fidelity_set.jsonl", fidelity)
        hashes["fidelity_set.jsonl"] = hashlib.sha256(fidelity.encode("utf-8")).hexdigest()
        manifest = {
            "bundle": "gguf_fidelity_bundle_v1",
            "samples": len(records),
            "source_split": "resume_parsing_vision_cvschema_v2_pointer_v1/validation",
            "p0_reference": str(P0_RESULTS.relative_to(ROOT)).replace("\\", "/"),
            "files": hashes,
        }
        bundle.writestr("MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {OUT} ({len(records)} samples, {OUT.stat().st_size // 1024} KiB)")
    print("sha256", hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
