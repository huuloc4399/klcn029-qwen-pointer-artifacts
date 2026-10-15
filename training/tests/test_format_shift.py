"""format_shift_v1: label invariance of the counterfactual inputs and the offline scorer.

The scorer is exercised with simulated runs whose errors are known in advance: a "base" run
that is perfect everywhere and a "fine-tuned" run that drops the summary under renamed headings
and copies grouped skill lines as single items. A Pointer run checks that multi-line spans in
the wrapped variants reconstruct the original labels.
Run from the project root: python -m unittest training/tests/test_format_shift.py -v
"""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from training.evaluation import evaluate_format_shift, format_shift
from training.evaluation.format_shift import VARIANTS, norm


def build_once():
    if not hasattr(build_once, "manifest"):
        build_once.manifest = format_shift.build()
    return build_once.manifest


def load(name):
    return [json.loads(line) for line in (format_shift.OUT_DIR / name).read_text(encoding="utf-8").splitlines()]


def write_run(folder: Path, model: str, outputs: dict[str, str]) -> Path:
    inputs_sha = evaluate_format_shift.sha256(format_shift.OUT_DIR / "inputs.jsonl")
    path = folder / f"{model}.zip"
    rows = [{"sample_id": sid, "raw_output": raw, "generated_tokens": 10, "hit_max_new_tokens": False}
            for sid, raw in outputs.items()]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("run/eval_config.json", json.dumps({"model_variant": model, "inputs_sha256": inputs_sha}))
        archive.writestr("run/predictions_raw.jsonl", "".join(json.dumps(r) + "\n" for r in rows))
    return path


def pointer_output(target: dict, source_lines: list[str]) -> str:
    """Pointer JSON for a target: long texts become the line spans that hold them."""
    normalized = [norm(line) for line in source_lines]

    def span(value):
        if not value:
            return None
        wanted = norm(value)
        for start in range(len(normalized)):
            joined = ""
            for end in range(start, len(normalized)):
                joined = (joined + " " + normalized[end]).strip()
                if joined == wanted:
                    return [start + 1, end + 1]
                if not wanted.startswith(joined):
                    break
        raise AssertionError(f"no span for {value[:40]}")

    pointer = {
        "personal_info": target["personal_info"], "summary_span": span(target.get("summary")),
        "skills": target["skills"],
        "experience": [{"company": e["company"], "job_title": e["job_title"], "duration": e["duration"],
                        "description_span": span(e["description"])} for e in target["experience"]],
        "projects": [{"name": p["name"], "role": p["role"], "technologies": p["technologies"],
                      "details_span": span(p["details"])} for p in target["projects"]],
        "education": target["education"], "certifications": target["certifications"],
        "activities": target["activities"], "awards": target["awards"],
    }
    return json.dumps(pointer, ensure_ascii=False)


class FormatShiftTests(unittest.TestCase):
    def test_dataset_is_deterministic_and_label_invariant(self):
        manifest = build_once()
        self.assertEqual((manifest["cv_count"], manifest["record_count"]), (20, 100))
        self.assertEqual(format_shift.build()["inputs_sha256"], manifest["inputs_sha256"])
        inputs, targets = load("inputs.jsonl"), {r["cv_id"]: r["target"] for r in load("targets.jsonl")}
        self.assertFalse(any("target" in r for r in inputs))
        for record in inputs:
            target = targets[record["cv_id"]]
            original = next(r for r in inputs if r["cv_id"] == record["cv_id"] and r["variant"] == "original")
            self.assertEqual(format_shift.findable(target, original["source_text"]) - format_shift.findable(target, record["source_text"]), set())
        grouped = next(r for r in inputs if r["variant"] == "grouped_skills")
        self.assertRegex(grouped["source_text"], r"\n(Technical|Tools|Technologies|Other): [^\n]+, [^\n]+")
        self.assertTrue(any(r["variant"] == "headings" and "Kỹ năng" in r["source_text"] for r in inputs))
        self.assertTrue(any(r["variant"] == "wrapped_text" and r["changes"]["long_lines_wrapped"] for r in inputs))

    def test_scorer_measures_known_format_sensitivity(self):
        build_once()
        inputs = load("inputs.jsonl")
        targets = {r["cv_id"]: r["target"] for r in load("targets.jsonl")}
        base, tuned, pointer = {}, {}, {}
        for record in inputs:
            target = targets[record["cv_id"]]
            base[record["sample_id"]] = json.dumps(target, ensure_ascii=False)
            damaged = json.loads(json.dumps(target))
            if record["variant"] in ("headings", "combined"):
                damaged["summary"] = ""
            if record["variant"] in ("grouped_skills", "combined"):
                damaged["skills"]["hard_skills"] = [", ".join(target["skills"]["hard_skills"])]
            tuned[record["sample_id"]] = json.dumps(damaged, ensure_ascii=False)
            pointer[record["sample_id"]] = pointer_output(target, record["pointer_source_text"].split("\n"))
        with tempfile.TemporaryDirectory() as folder:
            args = argparse.Namespace(base=str(write_run(Path(folder), "base", base)),
                                      adapter_stage1=str(write_run(Path(folder), "adapter_stage1", tuned)),
                                      pointer_stage2=str(write_run(Path(folder), "pointer_stage2", pointer)),
                                      out=str(Path(folder) / "results"))
            report = evaluate_format_shift.evaluate(args)
            self.assertTrue((Path(folder) / "results/REPORT.md").is_file())
        for variant in VARIANTS:
            self.assertEqual(report["models"]["base"]["variants"][variant]["micro_f1"], 100.0)
            # Multi-line spans in wrapped variants reconstruct the original labels exactly.
            self.assertEqual(report["models"]["pointer_stage2"]["variants"][variant]["micro_f1"], 100.0, variant)
        tuned_variants = report["models"]["adapter_stage1"]["variants"]
        self.assertEqual(tuned_variants["wrapped_text"]["delta_vs_original"], 0.0)
        self.assertLess(tuned_variants["headings"]["delta_vs_original"], 0)
        self.assertLess(tuned_variants["combined"]["delta_vs_original"], tuned_variants["grouped_skills"]["delta_vs_original"])
        self.assertEqual(tuned_variants["headings"]["fields"]["summary"], 0.0)
        did = report["difference_in_differences"]["adapter_stage1"]["grouped_skills"]
        self.assertLess(did["value"], 0)
        self.assertLess(did["ci95"][1], 0)


if __name__ == "__main__":
    unittest.main()
