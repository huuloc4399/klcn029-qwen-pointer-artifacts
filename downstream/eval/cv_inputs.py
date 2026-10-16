"""CVSchema inputs for the end-to-end experiments: gold, B0 output and P1 output, plus PDF facts.

The B0 and P1 outputs are parsed exactly as in the locked GOLD40 evaluation
(training/evaluation/evaluate_gold40_comparison.py): same ZIPs, same frozen parsers, same
integrity checks. An output that is not a valid CVSchema is kept as missing, so the scoring step
records "extraction_invalid" for that pair instead of silently falling back to gold.

    python -m downstream.eval.cv_inputs

Writes downstream/data/cv_inputs_v1/{gold,b0,p1}/<cv_id>.json, documents/<cv_id>.json (the PDF
analysis the web app shows the scorer) and MANIFEST.json. The folder holds real CV content and
is git-ignored.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "downstream/data/cv_inputs_v1"
PAIRS = ROOT / "downstream/data/pairs_v1/pairs.csv"
SOURCES = ("gold", "b0", "p1")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def pair_cv_ids(pairs: Path = PAIRS) -> list[str]:
    with pairs.open(encoding="utf-8", newline="") as handle:
        return sorted({row["cv_id"] for row in csv.DictReader(handle)})


def extraction_outputs() -> tuple[dict[str, dict[str, dict | None]], dict[str, Any]]:
    """{source: {cv_id: CVSchema dict or None}} for gold, B0 and P1 on GOLD40, with provenance."""
    from training.evaluation import evaluate_gold40_comparison as cmp

    rows = [json.loads(line) for line in (cmp.INPUTS / "gold40_inputs.jsonl").read_text(encoding="utf-8").splitlines()]
    inputs = {row["sample_id"]: row for row in rows}
    gold, _, _, _, _ = cmp.load_gold(inputs)
    base_zip = ROOT / "training/qwen3_4b_base_cvschema2_gold40_raw_greedy_v1.zip"
    b0_rows, b0_artifact = cmp.load_fulljson(base_zip, "base", inputs)
    b0 = {}
    for cv_id, row in b0_rows.items():
        result = cmp.parse_cvschema_output(row["raw_output"])
        b0[cv_id] = result.parsed_value if result.schema_valid else None

    pointer_inputs, _ = cmp.load_inputs(ROOT / "experiments/baseline80/real_cv_pointer_inputs_v1/all_80_pointer_inputs.jsonl")
    p0_zip = ROOT / "training/qwen3_4b_pointer_real80_raw_greedy_v1.zip"
    p1_zip = ROOT / "training/qwen3_4b_pointer_real80_selective_retry_p1_v1.zip"
    p0_rows, _ = cmp.load_raw_artifact(p0_zip)
    retries, _ = cmp.load_retry_artifact(p1_zip)
    p1 = {}
    retry = {r["sample_id"]: r for r in retries}
    for row in p0_rows:
        cv_id = row["sample_id"]
        if cv_id not in gold:
            continue
        source_text = pointer_inputs[cv_id]["source_text"]
        result = cmp.parse_pointer_output(row["raw_output"], source_text)
        if cv_id in retry:
            if retry[cv_id]["p0_raw_output_sha256"] != cmp.sha256_bytes(row["raw_output"].encode()):
                raise ValueError(f"P1 retry not bound to P0 output: {cv_id}")
            result = cmp.parse_pointer_output(retry[cv_id]["raw_output"], source_text)
        p1[cv_id] = result.reconstructed_cvschema if result.cvschema_valid else None

    provenance = {
        "gold_manifest_sha256": cmp.sha256_file(cmp.GOLD_MANIFEST),
        "b0_zip_sha256": b0_artifact["zip_sha256"],
        "p0_zip_sha256": cmp.sha256_file(p0_zip),
        "p1_zip_sha256": cmp.sha256_file(p1_zip),
        "parsers": "frozen parser v1 (CVSchema) and pointer parser v1, as in gold40_b0_b1_p0_p1_v1",
    }
    return {"gold": gold, "b0": b0, "p1": p1}, provenance


def document_facts(cv_ids: list[str]) -> dict[str, dict[str, Any]]:
    """The PDF analysis the web app passes to the scorer (page count, text layer, layout)."""
    sys.path.insert(0, str(ROOT / "cv_evaluation_web"))
    from services.pdf_extractor import extract_pdf
    from downstream.data.package_rater import cv_pdf_paths

    paths = cv_pdf_paths(set(cv_ids))
    return {cv_id: extract_pdf(paths[cv_id]).public_dict() for cv_id in cv_ids}


def prepare(out: Path = OUT, pairs: Path = PAIRS) -> dict[str, Any]:
    cv_ids = pair_cv_ids(pairs)
    outputs, provenance = extraction_outputs()
    documents = document_facts(cv_ids)
    files: dict[str, str] = {}
    invalid: dict[str, list[str]] = {}
    for source in SOURCES:
        (out / source).mkdir(parents=True, exist_ok=True)
        for cv_id in cv_ids:
            if cv_id not in outputs[source]:
                raise KeyError(f"{cv_id} is not in GOLD40")
            value = outputs[source][cv_id]
            path = out / source / f"{cv_id}.json"
            if value is None:
                invalid.setdefault(source, []).append(cv_id)
                path.unlink(missing_ok=True)
                continue
            data = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
            path.write_bytes(data)
            files[f"{source}/{cv_id}.json"] = _sha(data)
    (out / "documents").mkdir(parents=True, exist_ok=True)
    for cv_id, facts in documents.items():
        data = json.dumps(facts, ensure_ascii=False, indent=2).encode("utf-8")
        (out / "documents" / f"{cv_id}.json").write_bytes(data)
        files[f"documents/{cv_id}.json"] = _sha(data)
    manifest = {
        "version": "cv_inputs_v1",
        "pairs_sha256": _sha(pairs.read_bytes().replace(b"\r\n", b"\n")),
        "cv_ids": cv_ids,
        "sources": list(SOURCES),
        "invalid_extraction": invalid,
        "provenance": provenance,
        "files": files,
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def load(source: str, cv_id: str, root: Path = OUT) -> dict[str, Any] | None:
    path = root / source / f"{cv_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def load_document(cv_id: str, root: Path = OUT) -> dict[str, Any]:
    return json.loads((root / "documents" / f"{cv_id}.json").read_text(encoding="utf-8"))


def manifest_sha(root: Path = OUT) -> str:
    return _sha((root / "MANIFEST.json").read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description="Write gold/B0/P1 CVSchema inputs for the CV–JD pairs.")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    manifest = prepare(args.out)
    counts = {s: sum(1 for k in manifest["files"] if k.startswith(f"{s}/")) for s in SOURCES}
    print(f"{len(manifest['cv_ids'])} CV; valid inputs per source: {counts}; "
          f"invalid extraction: { {k: len(v) for k, v in manifest['invalid_extraction'].items()} or 'none'}")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
