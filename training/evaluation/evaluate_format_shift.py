"""Score the format_shift_v1 counterfactual runs (offline; no model calls, labels never sent to Colab).

Inputs: the raw-output ZIPs downloaded from Qwen3_Format_Shift_Counterfactual_Colab.ipynb, any
subset of base (B0), adapter_stage1 (B1) and pointer_stage2 (P0). Parsing and metrics are the
frozen ones used for every earlier benchmark (normalized exact set, Field Micro F1).

For each model the CVs with all five variants are used. Reported per variant: Field Micro F1,
CVSchema-valid count and key fields; the paired change against "original" on the same CVs with
a CV-level bootstrap CI; and, when B0 is present, the difference-in-differences
(fine-tuned drop minus base drop on the same CVs and variant), the direct test of whether
fine-tuning made the model more sensitive to CV format than the base model.

Usage (from the project root):
    python -m training.evaluation.evaluate_format_shift \
        --base format_shift_v1_base_raw_greedy.zip \
        --adapter-stage1 format_shift_v1_adapter_stage1_raw_greedy.zip \
        --pointer-stage2 format_shift_v1_pointer_stage2_raw_greedy.zip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import zipfile
from pathlib import Path
from typing import Any

from training.evaluation.format_shift import OUT_DIR as DATA_DIR, VARIANTS
from training.evaluation.metrics import FIELD_EXTRACTORS, compute_field_metrics, field_items, precision_recall_f1
from training.evaluation.parser import parse_cvschema_output
from training.evaluation.pointer_parser import parse_pointer_output

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "training/evaluation/results/format_shift_v1"
MODELS = {"base": "B0 (Qwen gốc, Full JSON)", "adapter_stage1": "B1 (adapter stage 1, Full JSON)",
          "pointer_stage2": "P0 (adapter Pointer stage 2)"}
KEY_FIELDS = ("summary", "skills.hard_skills", "skills.soft_skills", "experience.description", "projects.details")
BOOTSTRAP = 2000


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_run(path: Path, model: str, inputs_sha: str) -> dict[str, dict]:
    with zipfile.ZipFile(path) as archive:
        names = {Path(name).name: name for name in archive.namelist()}
        config = json.loads(archive.read(names["eval_config.json"]))
        rows = [json.loads(line) for line in archive.read(names["predictions_raw.jsonl"]).decode("utf-8").splitlines() if line.strip()]
    if config["model_variant"] != model:
        raise SystemExit(f"{path.name} is a {config['model_variant']} run, not {model}")
    if config["inputs_sha256"] != inputs_sha:
        raise SystemExit(f"{path.name} was generated from different inputs; rebuild with the same format_shift_v1 data")
    return {row["sample_id"]: row for row in rows}


def parse(model: str, raw: str, record: dict) -> dict | None:
    if model == "pointer_stage2":
        result = parse_pointer_output(raw, record["pointer_source_text"])
        return result.reconstructed_cvschema if result.cvschema_valid else None
    result = parse_cvschema_output(raw)
    return result.parsed_value if result.schema_valid else None


def cv_counts(gold: dict, prediction: dict | None) -> list[int]:
    totals = [0, 0, 0]
    for field in FIELD_EXTRACTORS:
        expected, actual = field_items(gold, field), field_items(prediction, field)
        totals[0] += len(expected & actual)
        totals[1] += len(actual - expected)
        totals[2] += len(expected - actual)
    return totals


def f1_of(counts: list[list[int]]) -> float:
    return precision_recall_f1(*(sum(c[i] for c in counts) for i in range(3)))["f1"] or 0.0


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))]


def bootstrap(cvs: list[str], statistic) -> list[float]:
    rng = random.Random(42)
    samples = [statistic([rng.choice(cvs) for _ in cvs]) for _ in range(BOOTSTRAP)]
    return [round(percentile(samples, 0.025) * 100, 2), round(percentile(samples, 0.975) * 100, 2)]


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    inputs_path, targets_path = DATA_DIR / "inputs.jsonl", DATA_DIR / "targets.jsonl"
    inputs = {r["sample_id"]: r for r in map(json.loads, inputs_path.read_text(encoding="utf-8").splitlines())}
    gold = {r["cv_id"]: r["target"] for r in map(json.loads, targets_path.read_text(encoding="utf-8").splitlines())}
    inputs_sha = sha256(inputs_path)
    runs = {model: Path(getattr(args, model)) for model in MODELS if getattr(args, model)}
    if not runs:
        raise SystemExit("Pass at least one result ZIP")

    per_cv: dict[str, dict[str, dict[str, list[int]]]] = {}
    report: dict[str, Any] = {"experiment": "format_shift_v1", "inputs_sha256": inputs_sha, "models": {},
                              "difference_in_differences": {}, "provenance": {}}
    sample_rows = []
    for model, path in runs.items():
        raw = load_run(path, model, inputs_sha)
        report["provenance"][model] = {"zip": path.name, "zip_sha256": sha256(path)}
        cvs = sorted(cv for cv in gold if all(f"{cv}__{variant}" in raw for variant in VARIANTS))
        if not cvs:
            raise SystemExit(f"{path.name}: no CV has all five variants yet")
        per_cv[model] = {variant: {} for variant in VARIANTS}
        model_report = {"label": MODELS[model], "complete_cvs": len(cvs), "variants": {}}
        for variant in VARIANTS:
            predictions, valid, hit_limit = {}, 0, 0
            for cv in cvs:
                row = raw[f"{cv}__{variant}"]
                predictions[cv] = parse(model, row["raw_output"], inputs[row["sample_id"]])
                valid += predictions[cv] is not None
                hit_limit += bool(row.get("hit_max_new_tokens"))
                per_cv[model][variant][cv] = cv_counts(gold[cv], predictions[cv])
                sample_rows.append({"model": model, "cv_id": cv, "variant": variant, "cvschema_valid": predictions[cv] is not None,
                                    "tp_fp_fn": per_cv[model][variant][cv], "generated_tokens": row.get("generated_tokens"),
                                    "hit_max_new_tokens": bool(row.get("hit_max_new_tokens"))})
            metrics = compute_field_metrics({cv: gold[cv] for cv in cvs}, predictions)
            entry = {
                "micro_f1": round(metrics["micro"]["f1"] * 100, 2),
                "cvschema_valid": f"{valid}/{len(cvs)}", "hit_max_new_tokens": hit_limit,
                "fields": {field: (None if metrics["by_field"][field]["f1"] is None
                                   else round(metrics["by_field"][field]["f1"] * 100, 2)) for field in KEY_FIELDS},
            }
            if variant != "original":
                base_counts, variant_counts = per_cv[model]["original"], per_cv[model][variant]
                entry["delta_vs_original"] = round((f1_of(list(variant_counts.values())) - f1_of(list(base_counts.values()))) * 100, 2)
                entry["delta_ci95"] = bootstrap(cvs, lambda chosen, b=base_counts, v=variant_counts:
                                                f1_of([v[c] for c in chosen]) - f1_of([b[c] for c in chosen]))
            model_report["variants"][variant] = entry
        report["models"][model] = model_report

    if "base" in per_cv:
        for model in (m for m in per_cv if m != "base"):
            common = sorted(set(per_cv["base"]["original"]) & set(per_cv[model]["original"]))
            report["difference_in_differences"][model] = {}
            for variant in VARIANTS[1:]:
                def did(chosen, m=model, v=variant):
                    drop_model = f1_of([per_cv[m][v][c] for c in chosen]) - f1_of([per_cv[m]["original"][c] for c in chosen])
                    drop_base = f1_of([per_cv["base"][v][c] for c in chosen]) - f1_of([per_cv["base"]["original"][c] for c in chosen])
                    return drop_model - drop_base
                report["difference_in_differences"][model][variant] = {
                    "cvs": len(common), "value": round(did(common) * 100, 2), "ci95": bootstrap(common, did)}

    out = Path(getattr(args, "out", None) or RESULTS)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "sample_results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in sample_rows), encoding="utf-8")
    (out / "REPORT.md").write_text(render(report), encoding="utf-8")
    return report


def render(report: dict[str, Any]) -> str:
    lines = ["# format_shift_v1: độ nhạy với định dạng CV (dữ liệu tổng hợp, nhãn giữ nguyên)", "",
             "Field Micro F1 (%), normalized exact set, parser/metric đã khóa. Δ là thay đổi so với `original` trên cùng CV; "
             "CI 95% bootstrap theo CV (2.000 lần, seed 42).", ""]
    header = "| Model | CV | " + " | ".join(VARIANTS) + " |"
    lines += [header, "|---|---:|" + "---:|" * len(VARIANTS)]
    for model, data in report["models"].items():
        cells = []
        for variant in VARIANTS:
            entry = data["variants"][variant]
            text = f"{entry['micro_f1']:.2f}"
            if "delta_vs_original" in entry:
                text += f" (Δ {entry['delta_vs_original']:+.2f})"
            cells.append(text)
        lines.append(f"| {data['label']} | {data['complete_cvs']} | " + " | ".join(cells) + " |")
    lines += ["", "## CVSchema hợp lệ và trường chính", ""]
    for model, data in report["models"].items():
        lines += [f"**{data['label']}**", "", "| Biến thể | Hợp lệ | " + " | ".join(KEY_FIELDS) + " | Δ CI 95% |",
                  "|---|---:|" + "---:|" * len(KEY_FIELDS) + "---|"]
        for variant, entry in data["variants"].items():
            fields = " | ".join("—" if entry["fields"][f] is None else f"{entry['fields'][f]:.2f}" for f in KEY_FIELDS)
            ci = entry.get("delta_ci95")
            lines.append(f"| {variant} | {entry['cvschema_valid']} | {fields} | {'—' if not ci else f'[{ci[0]:+.2f}; {ci[1]:+.2f}]'} |")
        lines.append("")
    if report["difference_in_differences"]:
        lines += ["## Fine-tune nhạy hơn model gốc bao nhiêu? (difference-in-differences)", "",
                  "Giá trị = (Δ của model fine-tune) − (Δ của B0) trên cùng CV và biến thể, đơn vị điểm %. "
                  "Âm và CI không chứa 0 nghĩa là fine-tune mất điểm vì đổi định dạng nhiều hơn model gốc.", "",
                  "| Model | Biến thể | CV | DiD | CI 95% |", "|---|---|---:|---:|---|"]
        for model, variants in report["difference_in_differences"].items():
            for variant, entry in variants.items():
                lines.append(f"| {MODELS[model]} | {variant} | {entry['cvs']} | {entry['value']:+.2f} | "
                             f"[{entry['ci95'][0]:+.2f}; {entry['ci95'][1]:+.2f}] |")
        lines.append("")
    lines += ["## Giới hạn", "",
              "- 20 CV tổng hợp, một nguồn sinh; biến thể mô phỏng một số khác biệt bề mặt của CV thật, không phải CV thật.",
              "- Nhãn giữ nguyên tuyệt đối (kiểm tra tự động khi tạo dữ liệu), nên thay đổi F1 chỉ đến từ định dạng đầu vào.",
              "- Không thay thế đánh giá trên CV thật; dùng để kiểm chứng giả thuyết nguyên nhân rút ra từ GOLD40.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score format_shift_v1 raw outputs")
    parser.add_argument("--base", help="ZIP of the base (B0) run")
    parser.add_argument("--adapter-stage1", dest="adapter_stage1", help="ZIP of the stage-1 adapter (B1) run")
    parser.add_argument("--pointer-stage2", dest="pointer_stage2", help="ZIP of the Pointer stage-2 (P0) run")
    parser.add_argument("--out", default=str(RESULTS), help="result folder")
    args = parser.parse_args()
    report = evaluate(args)
    print(json.dumps({m: {v: e["micro_f1"] for v, e in d["variants"].items()} for m, d in report["models"].items()},
                     ensure_ascii=False, indent=2))
    print(f"Report: {Path(args.out) / 'REPORT.md'}")


if __name__ == "__main__":
    main()
