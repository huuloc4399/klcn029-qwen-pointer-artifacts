"""Apply the pre-registered, label-free rule for P's COVERAGE_MIN (downstream/eval/DANG_KY_TRUOC.md §3).

For each candidate threshold, the share of p_grounded results on the dev run whose total would be
shown: coverage ≥ threshold and C3, (C4 or C5), C8 scored. The rule takes the highest candidate whose
share, pooled over the gold and b0 inputs, is at least MIN_SHOWN. It reads predictions only, never
human labels, so it cannot be tuned towards agreement with the raters.

    python -m downstream.eval.lock_config --run-id dev_v2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from downstream.eval import run_strategies

CANDIDATES = (0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90)
MIN_SHOWN = 0.80
MIN_RESULTS = 0.90  # share of the run's pairs × inputs that must have a p_grounded result
STRATEGY = "p_grounded"
INPUTS = ("gold", "b0")
REQUIRED = (("C3_skills",), ("C4_projects", "C5_experience"), ("C8_jd_fit",))


def shown(record: dict[str, Any], threshold: float) -> bool:
    scored = {c for c, v in record["criteria"].items() if v.get("score") is not None}
    return record["coverage"] >= threshold and all(any(c in scored for c in group) for group in REQUIRED)


def coverage_rule(records: list[dict[str, Any]], expected: int) -> dict[str, Any]:
    ok = [r for r in records if r["strategy"] == STRATEGY and r["status"] == "ok" and r["input"] in INPUTS
          and r.get("repeat", 1) == 1]
    out: dict[str, Any] = {"strategy": STRATEGY, "inputs": list(INPUTS), "results": len(ok), "expected": expected,
                           "min_shown": MIN_SHOWN, "candidates": {}}
    if expected == 0 or len(ok) < MIN_RESULTS * expected:
        out["chosen"] = None
        out["reason"] = f"chỉ có {len(ok)}/{expected} kết quả, cần ít nhất {MIN_RESULTS:.0%}"
        return out
    for threshold in CANDIDATES:
        out["candidates"][threshold] = {
            "pooled": sum(shown(r, threshold) for r in ok) / len(ok),
            **{i: (sum(shown(r, threshold) for r in ok if r["input"] == i) /
                   max(1, sum(r["input"] == i for r in ok))) for i in INPUTS}}
    passing = [t for t in CANDIDATES if out["candidates"][t]["pooled"] >= MIN_SHOWN]
    out["chosen"] = max(passing) if passing else min(CANDIDATES)
    out["reason"] = ("ngưỡng cao nhất có tỉ lệ hiện điểm tổng ≥ 80%" if passing
                     else "không ngưỡng nào đạt 80%; lấy ngưỡng thấp nhất và báo cáo như một phát hiện")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-registered, label-free choice of P's COVERAGE_MIN on dev.")
    parser.add_argument("--run-id", default="dev_v2")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    run_dir = run_strategies.RESULTS / args.run_id
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    records = list(run_strategies.latest(run_strategies._read_jsonl(run_dir / "predictions.jsonl")).values())
    expected = len(config["pair_ids"]) * len([i for i in INPUTS if i in config["inputs"]])
    result = coverage_rule(records, expected)
    (run_dir / "coverage_rule.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["chosen"] is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
