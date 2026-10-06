#!/usr/bin/env python3
"""Evaluate one raw Hybrid Pointer validation artifact without opening test data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import statistics
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from training.evaluation.metrics import compute_field_metrics, mismatch_details
from training.evaluation.pointer_parser import (
    POINTER_PARSER_CONTRACT,
    POINTER_PARSER_VERSION,
    parse_pointer_output,
)


EVALUATOR_VERSION = "pointer_validation_evaluator_v1"
EXPECTED_EVAL_ID = "8f7f05439755108e933f79e6d01fea2133648697056c81c29d041181236ce23b"
EXPECTED_VALIDATION_SHA256 = "d0b8525b4b1ad9624cbc0db35a26fdca9cf749134e0db3ada843444724abae45"
EXPECTED_ADAPTER_MODEL_SHA256 = "8d68628e382593132010f20fb12cbb18d9477ca034c154811d109ec075a65f81"
EXPECTED_SAMPLE_COUNT = 75


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.part-{os.getpid()}")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def safe_members(archive: zipfile.ZipFile) -> list[str]:
    if archive.testzip() is not None:
        raise ValueError("ZIP contains a member with a CRC failure")
    names = [item.filename for item in archive.infolist() if not item.is_dir()]
    if len(names) != len(set(names)):
        raise ValueError("ZIP contains duplicate member names")
    for name in names:
        path = PurePosixPath(name.replace("\\", "/"))
        if not name or path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Unsafe ZIP member: {name}")
    return names


def load_raw_artifact(zip_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with zipfile.ZipFile(zip_path) as archive:
        names = safe_members(archive)
        roots = {PurePosixPath(name).parts[0] for name in names}
        if len(roots) != 1:
            raise ValueError(f"Expected one ZIP root, found {sorted(roots)}")
        root = next(iter(roots))

        def member(relative: str) -> str:
            return f"{root}/{relative}"

        required = {
            member("_COMPLETE.json"),
            member("_FILE_MANIFEST.json"),
            member("eval_config.json"),
            member("generation_summary.json"),
            member("predictions_raw.jsonl"),
            member("sample_generation_metrics.csv"),
        }
        missing = sorted(required - set(names))
        if missing:
            raise ValueError(f"Missing ZIP members: {missing}")

        config = json.load(archive.open(member("eval_config.json")))
        generation = json.load(archive.open(member("generation_summary.json")))
        complete = json.load(archive.open(member("_COMPLETE.json")))
        manifest = json.load(archive.open(member("_FILE_MANIFEST.json")))

        for relative, expected in manifest["files"].items():
            payload = archive.read(member(relative))
            if len(payload) != expected["size"]:
                raise ValueError(f"Size mismatch in {relative}")
            if sha256_bytes(payload) != expected["sha256"]:
                raise ValueError(f"SHA-256 mismatch in {relative}")

        prediction_bytes = archive.read(member("predictions_raw.jsonl"))
        rows = [
            json.loads(line)
            for line in prediction_bytes.decode("utf-8").splitlines()
            if line.strip()
        ]
        sample_names = {
            name for name in names if name.startswith(member("samples/")) and name.endswith(".json")
        }
        expected_sample_names = {member(f"samples/{row['sample_id']}.json") for row in rows}
        if sample_names != expected_sample_names:
            raise ValueError("Per-sample JSON members do not match predictions_raw.jsonl")
        for row in rows:
            stored = json.load(archive.open(member(f"samples/{row['sample_id']}.json")))
            if stored != row:
                raise ValueError(f"Per-sample JSON differs for {row['sample_id']}")

    raw_sha = sha256_bytes(prediction_bytes)
    if complete.get("predictions_raw_sha256") != raw_sha:
        raise ValueError("_COMPLETE predictions hash mismatch")
    if generation.get("predictions_raw_sha256") != raw_sha:
        raise ValueError("generation_summary predictions hash mismatch")
    if config.get("eval_id") != EXPECTED_EVAL_ID:
        raise ValueError("Unexpected eval_id")
    if config.get("validation_sha256") != EXPECTED_VALIDATION_SHA256:
        raise ValueError("Unexpected validation hash in eval config")
    if config.get("adapter_model_sha256") != EXPECTED_ADAPTER_MODEL_SHA256:
        raise ValueError("Unexpected adapter model hash")
    if config.get("split") != "validation" or config.get("test_loaded") is not False:
        raise ValueError("Artifact is not a validation-only run")
    if config.get("raw_output_only") is not True or config.get("parser_applied") is not False:
        raise ValueError("Artifact is not raw output")
    if generation.get("sample_count") != EXPECTED_SAMPLE_COUNT:
        raise ValueError("Generation summary sample count mismatch")
    if complete.get("sample_count") != EXPECTED_SAMPLE_COUNT:
        raise ValueError("Completion marker sample count mismatch")

    sample_ids = [row.get("sample_id") for row in rows]
    if len(rows) != EXPECTED_SAMPLE_COUNT or len(sample_ids) != len(set(sample_ids)):
        raise ValueError("Expected 75 unique prediction rows")
    if {row.get("eval_id") for row in rows} != {EXPECTED_EVAL_ID}:
        raise ValueError("Prediction rows have inconsistent eval_id")
    if any(row.get("split") != "validation" for row in rows):
        raise ValueError("Prediction row outside validation split")
    if any(not isinstance(row.get("raw_output"), str) for row in rows):
        raise ValueError("Prediction contains a non-string raw output")
    return rows, {
        "root": root,
        "config": config,
        "generation": generation,
        "complete": complete,
        "predictions_raw_sha256": raw_sha,
    }


def load_gold(path: Path) -> tuple[dict[str, dict[str, Any]], str]:
    digest = sha256_file(path)
    if digest != EXPECTED_VALIDATION_SHA256:
        raise ValueError(f"Unexpected validation SHA-256: {digest}")
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != EXPECTED_SAMPLE_COUNT:
        raise ValueError(f"Expected 75 gold rows, found {len(rows)}")
    indexed = {row["sample_id"]: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError("Duplicate gold sample_id")
    return indexed, digest


def iter_span_slots(pointer: dict[str, Any] | None) -> Iterable[tuple[str, Any]]:
    if not isinstance(pointer, dict):
        return
    yield "summary_span", pointer.get("summary_span", "__MISSING__")
    experience = pointer.get("experience")
    if isinstance(experience, list):
        for index, item in enumerate(experience):
            value = item.get("description_span", "__MISSING__") if isinstance(item, dict) else "__MISSING__"
            yield f"experience[{index}].description_span", value
    projects = pointer.get("projects")
    if isinstance(projects, list):
        for index, item in enumerate(projects):
            value = item.get("details_span", "__MISSING__") if isinstance(item, dict) else "__MISSING__"
            yield f"projects[{index}].details_span", value


def span_metrics(sample_pairs: list[tuple[dict[str, Any] | None, dict[str, Any]]]) -> dict[str, Any]:
    aggregate = Counter()
    by_type: dict[str, Counter[str]] = {
        "summary_span": Counter(),
        "experience.description_span": Counter(),
        "projects.details_span": Counter(),
    }
    for prediction, gold in sample_pairs:
        predicted = dict(iter_span_slots(prediction))
        for path, expected in iter_span_slots(gold):
            field_type = (
                "summary_span"
                if path == "summary_span"
                else "experience.description_span"
                if path.startswith("experience[")
                else "projects.details_span"
            )
            actual = predicted.get(path, "__MISSING__")
            non_null = expected is not None
            exact = actual == expected
            aggregate["all_slots"] += 1
            by_type[field_type]["all_slots"] += 1
            if exact:
                aggregate["all_exact"] += 1
                by_type[field_type]["all_exact"] += 1
            if non_null:
                aggregate["non_null_gold"] += 1
                by_type[field_type]["non_null_gold"] += 1
                if exact:
                    aggregate["non_null_exact"] += 1
                    by_type[field_type]["non_null_exact"] += 1
    def finish(counts: Counter[str]) -> dict[str, Any]:
        return {
            **counts,
            "all_slots_accuracy": counts["all_exact"] / counts["all_slots"] if counts["all_slots"] else None,
            "non_null_gold_accuracy": counts["non_null_exact"] / counts["non_null_gold"] if counts["non_null_gold"] else None,
        }
    return {"overall": finish(aggregate), "by_type": {key: finish(value) for key, value in by_type.items()}}


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def evaluate(zip_path: Path, validation_path: Path, output_dir: Path) -> dict[str, Any]:
    rows, artifact = load_raw_artifact(zip_path)
    gold, validation_sha = load_gold(validation_path)
    by_id = {row["sample_id"]: row for row in rows}
    if set(by_id) != set(gold):
        raise ValueError("Prediction sample IDs do not match validation gold")

    reconstructed: dict[str, dict[str, Any] | None] = {}
    sample_results: list[dict[str, Any]] = []
    recovery_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    pointer_pairs: list[tuple[dict[str, Any] | None, dict[str, Any]]] = []

    for sample_id in sorted(gold):
        source = by_id[sample_id]
        target = gold[sample_id]
        result = parse_pointer_output(source["raw_output"], target["source_text"])
        prediction = result.reconstructed_cvschema if result.cvschema_valid else None
        reconstructed[sample_id] = prediction
        pointer_pairs.append((result.parsed_pointer, target["target_pointer"]))
        recovery = "+".join(result.recovery_steps) if result.recovery_steps else "none"
        recovery_counts[recovery] += 1
        for issue in result.issues:
            issue_counts[f"{issue.category}:{issue.code}"] += 1
        pointer_exact = result.parsed_pointer == target["target_pointer"]
        cvschema_exact = prediction == target["target_cvschema"]
        mismatches = mismatch_details(prediction, target["target_cvschema"])
        expected_spans = dict(iter_span_slots(target["target_pointer"]))
        actual_spans = dict(iter_span_slots(result.parsed_pointer))
        span_errors = {
            path: {"expected": expected, "actual": actual_spans.get(path, "__MISSING__")}
            for path, expected in expected_spans.items()
            if actual_spans.get(path, "__MISSING__") != expected
        }
        sample_results.append({
            "sample_id": sample_id,
            "strict_json": result.strict_json,
            "recoverable_json": result.recoverable_json,
            "recovery_steps": list(result.recovery_steps),
            "pointer_schema_valid": result.pointer_schema_valid,
            "span_contract_valid": result.span_contract_valid,
            "cvschema_valid": result.cvschema_valid,
            "skill_policy_valid": result.skill_policy_valid,
            "pointer_exact": pointer_exact,
            "cvschema_exact": cvschema_exact,
            "retry_targets": list(result.retry_targets),
            "issues": [issue.__dict__ for issue in result.issues],
            "span_errors": span_errors,
            "field_mismatches": mismatches,
            "input_tokens": source.get("input_tokens"),
            "generated_tokens": source.get("generated_tokens"),
            "runtime_seconds": source.get("runtime_seconds"),
            "ended_with_eos": source.get("ended_with_eos"),
            "hit_max_new_tokens": source.get("hit_max_new_tokens"),
            "parsed_pointer": result.parsed_pointer,
            "reconstructed_cvschema": prediction,
            "evidence": result.evidence,
        })

    field_metrics = compute_field_metrics(
        {sample_id: row["target_cvschema"] for sample_id, row in gold.items()},
        reconstructed,
    )
    spans = span_metrics(pointer_pairs)
    counts = {
        key: sum(bool(row[key]) for row in sample_results)
        for key in [
            "strict_json", "recoverable_json", "pointer_schema_valid",
            "span_contract_valid", "cvschema_valid", "skill_policy_valid",
            "pointer_exact", "cvschema_exact",
        ]
    }
    long_fields = ["summary", "experience.description", "projects.details"]
    long_tp = sum(field_metrics["by_field"][field]["tp"] for field in long_fields)
    long_fp = sum(field_metrics["by_field"][field]["fp"] for field in long_fields)
    long_fn = sum(field_metrics["by_field"][field]["fn"] for field in long_fields)
    long_precision = long_tp / (long_tp + long_fp) if long_tp + long_fp else 0.0
    long_recall = long_tp / (long_tp + long_fn) if long_tp + long_fn else 0.0
    long_f1 = 2 * long_precision * long_recall / (long_precision + long_recall) if long_precision + long_recall else 0.0
    runtimes = [float(row["runtime_seconds"]) for row in rows]
    input_tokens = [int(row["input_tokens"]) for row in rows]
    output_tokens = [int(row["generated_tokens"]) for row in rows]

    summary = {
        "evaluator_version": EVALUATOR_VERSION,
        "parser_version": POINTER_PARSER_VERSION,
        "sample_count": EXPECTED_SAMPLE_COUNT,
        "artifact_integrity": "PASS",
        "provenance": {
            "raw_zip": str(zip_path.resolve()),
            "raw_zip_sha256": sha256_file(zip_path),
            "predictions_raw_sha256": artifact["predictions_raw_sha256"],
            "eval_id": EXPECTED_EVAL_ID,
            "validation": str(validation_path.resolve()),
            "validation_sha256": validation_sha,
            "adapter_model_sha256": EXPECTED_ADAPTER_MODEL_SHA256,
            "parser_contract": POINTER_PARSER_CONTRACT,
        },
        "generation": artifact["generation"],
        "counts": counts,
        "rates": {key: value / EXPECTED_SAMPLE_COUNT for key, value in counts.items()},
        "recovery_counts": dict(recovery_counts),
        "issue_counts": dict(issue_counts),
        "span_metrics": spans,
        "field_metrics": field_metrics,
        "long_text_micro": {
            "fields": long_fields,
            "tp": long_tp, "fp": long_fp, "fn": long_fn,
            "precision": long_precision, "recall": long_recall, "f1": long_f1,
        },
        "efficiency": {
            "input_tokens_total": sum(input_tokens),
            "input_tokens_mean": statistics.mean(input_tokens),
            "generated_tokens_total": sum(output_tokens),
            "generated_tokens_mean": statistics.mean(output_tokens),
            "runtime_seconds_total": sum(runtimes),
            "runtime_seconds_mean": statistics.mean(runtimes),
            "runtime_seconds_p50": percentile(runtimes, 0.50),
            "runtime_seconds_p95": percentile(runtimes, 0.95),
        },
        "error_sample_ids": [row["sample_id"] for row in sample_results if not row["cvschema_exact"]],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(output_dir / "evaluation_summary.json", json_dump(summary))
    atomic_write(
        output_dir / "sample_results.jsonl",
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in sample_results),
    )
    with (output_dir / "field_metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "tp", "fp", "fn", "support", "precision", "recall", "f1"])
        writer.writeheader()
        for field, values in field_metrics["by_field"].items():
            writer.writerow({"field": field, **values})
    with (output_dir / "error_analysis.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "pointer_exact", "cvschema_exact", "recovery_steps", "issues", "span_errors", "field_mismatches"])
        writer.writeheader()
        for row in sample_results:
            if not row["cvschema_exact"] or not row["pointer_exact"] or row["issues"]:
                writer.writerow({
                    "sample_id": row["sample_id"],
                    "pointer_exact": row["pointer_exact"],
                    "cvschema_exact": row["cvschema_exact"],
                    "recovery_steps": json.dumps(row["recovery_steps"], ensure_ascii=False),
                    "issues": json.dumps(row["issues"], ensure_ascii=False),
                    "span_errors": json.dumps(row["span_errors"], ensure_ascii=False),
                    "field_mismatches": json.dumps(row["field_mismatches"], ensure_ascii=False),
                })

    def pct(value: float) -> str:
        return f"{value * 100:.2f}%"

    report = f"""# Kết quả validation P0 — Hybrid Pointer Stage 2 full v1

## Kết luận

Artifact raw đạt kiểm tra toàn vẹn và có đủ {EXPECTED_SAMPLE_COUNT}/{EXPECTED_SAMPLE_COUNT} mẫu validation.
Parser được áp dụng ngoại tuyến; tập test chưa được mở.

## Chất lượng đầu ra

| Chỉ tiêu | Kết quả |
|---|---:|
| Strict JSON | {counts['strict_json']}/{EXPECTED_SAMPLE_COUNT} ({pct(summary['rates']['strict_json'])}) |
| Recoverable JSON | {counts['recoverable_json']}/{EXPECTED_SAMPLE_COUNT} ({pct(summary['rates']['recoverable_json'])}) |
| Pointer schema hợp lệ | {counts['pointer_schema_valid']}/{EXPECTED_SAMPLE_COUNT} ({pct(summary['rates']['pointer_schema_valid'])}) |
| Span contract hợp lệ | {counts['span_contract_valid']}/{EXPECTED_SAMPLE_COUNT} ({pct(summary['rates']['span_contract_valid'])}) |
| CVSchema 2.0 hợp lệ | {counts['cvschema_valid']}/{EXPECTED_SAMPLE_COUNT} ({pct(summary['rates']['cvschema_valid'])}) |
| Pointer document exact | {counts['pointer_exact']}/{EXPECTED_SAMPLE_COUNT} ({pct(summary['rates']['pointer_exact'])}) |
| CVSchema document exact | {counts['cvschema_exact']}/{EXPECTED_SAMPLE_COUNT} ({pct(summary['rates']['cvschema_exact'])}) |
| Span exact, gold khác null | {spans['overall']['non_null_exact']}/{spans['overall']['non_null_gold']} ({pct(spans['overall']['non_null_gold_accuracy'])}) |
| Field Micro F1 | {field_metrics['micro']['f1']:.6f} |
| Macro F1 trên field có support | {field_metrics['macro_f1_supported_fields']:.6f} |
| Long-text Micro F1 | {long_f1:.6f} |

## Hiệu năng sinh

| Chỉ tiêu | Giá trị |
|---|---:|
| Output token trung bình | {summary['efficiency']['generated_tokens_mean']:.2f} |
| Latency trung bình | {summary['efficiency']['runtime_seconds_mean']:.2f} giây/CV |
| Latency p50 / p95 | {summary['efficiency']['runtime_seconds_p50']:.2f} / {summary['efficiency']['runtime_seconds_p95']:.2f} giây |
| Kết thúc bằng EOS | {artifact['generation']['ended_with_eos_count']}/{EXPECTED_SAMPLE_COUNT} |
| Chạm max token | {artifact['generation']['hit_max_new_tokens_count']}/{EXPECTED_SAMPLE_COUNT} |

## Diễn giải

- `Recoverable JSON` cho phép duy nhất các wrapper đã khóa trong Parser v1.
- `Span contract hợp lệ` chỉ cho biết khoảng dòng nằm trong tài liệu và đúng kiểu; `span exact` mới đo model chọn đúng dòng.
- Field F1 được tính sau khi dựng lại CVSchema 2.0 bằng exact set match, Unicode NFKC, casefold và chuẩn hóa khoảng trắng.
- Kết quả này chỉ thuộc validation synthetic English. Chưa đại diện cho pipeline OCR trên 80 CV thật EN/VI.
"""
    atomic_write(output_dir / "validation_report.md", report)

    source_files = [
        Path(__file__),
        Path(__file__).with_name("pointer_parser.py"),
        Path(__file__).with_name("metrics.py"),
    ]
    for source in source_files:
        shutil.copy2(source, output_dir / f"source_{source.name}")
    manifest = {
        "evaluator_version": EVALUATOR_VERSION,
        "files": {
            path.name: {"size": path.stat().st_size, "sha256": sha256_file(path)}
            for path in sorted(output_dir.iterdir()) if path.is_file()
        },
    }
    atomic_write(output_dir / "result_manifest.json", json_dump(manifest))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-zip", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = evaluate(args.raw_zip, args.validation, args.output_dir)
    print(json_dump({
        "status": "PASS",
        "counts": summary["counts"],
        "span_non_null": summary["span_metrics"]["overall"],
        "field_micro_f1": summary["field_metrics"]["micro"]["f1"],
        "long_text_micro_f1": summary["long_text_micro"]["f1"],
        "output_dir": str(args.output_dir),
    }), end="")


if __name__ == "__main__":
    main()
