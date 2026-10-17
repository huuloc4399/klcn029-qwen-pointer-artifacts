"""Evidence for the rubric's fixed choices: how much do the conclusions depend on them?

1. Criteria and overall fit: Spearman of each criterion's human score with the human overall fit
   (1–5), with 95% bootstrap intervals over CVs. A criterion with a large weight should not be one that
   says nothing about fit.
2. Weight sensitivity: draw weight vectors around the rubric's (Dirichlet, mean = rubric weights) and
   named alternatives (equal weights, C8 doubled, C8 removed). For each: how the human totals re-rank
   (Spearman with the rubric total), how well totals follow the human fit, and — given a run — whether the
   strategies keep their order of agreement with the human totals.
3. C8 sensitivity: other band edges and other credit for mentioned_only; how many pairs change C8 and
   how well C8 follows the human fit.

Labels are human only (FINAL or a rater file); nothing here is tuned, it only reports.

    python -m downstream.eval.sensitivity --labels downstream/data/labels_v1/FINAL_dev.jsonl --run-id dev_v2
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Callable

from downstream.data.build_rating_workbook import RUBRIC
from downstream.eval import iaa, run_strategies

BASE_EDGES = (0.2, 0.4, 0.6, 0.8)
BASE_HALF = 0.5


def rubric_weights() -> dict[str, float]:
    rubric = json.loads(Path(RUBRIC).read_text(encoding="utf-8")) if not isinstance(RUBRIC, dict) else RUBRIC
    return {c["id"]: float(c["weight"]) for c in rubric["criteria"]}


def _score(record: dict, criterion: str) -> float | None:
    item = record["criteria"].get(criterion) or {}
    return item.get("score") if item.get("status") in iaa.SCORED else None


def _bootstrap(records: list[dict], statistic: Callable[[list[dict]], float | None], reps: int, seed: int
               ) -> tuple[float | None, float | None]:
    by_cv: dict[str, list[dict]] = {}
    for r in records:
        by_cv.setdefault(r["cv_id"], []).append(r)
    cvs, rng, values = sorted(by_cv), random.Random(seed), []
    for _ in range(reps):
        sample = [r for cv in (rng.choice(cvs) for _ in cvs) for r in by_cv[cv]]
        value = statistic(sample)
        if value is not None:
            values.append(value)
    if not values:
        return None, None
    values.sort()
    return values[int(0.025 * (len(values) - 1))], values[int(0.975 * (len(values) - 1))]


def criterion_fit(records: list[dict], weights: dict[str, float], reps: int = 2000, seed: int = 42) -> dict[str, Any]:
    out = {}
    for criterion in weights:
        def rho(sample: list[dict], c: str = criterion) -> float | None:
            pairs = [(_score(r, c), r["overall_fit"]) for r in sample if _score(r, c) is not None and r.get("overall_fit")]
            return iaa.spearman([a for a, _ in pairs], [b for _, b in pairs]) if len(pairs) > 2 else None
        low, high = _bootstrap(records, rho, reps, seed)
        out[criterion] = {"weight": weights[criterion], "spearman_fit": rho(records), "low": low, "high": high}
    return out


def _dirichlet(rng: random.Random, weights: dict[str, float], concentration: float) -> dict[str, float]:
    total = sum(weights.values())
    draw = {c: rng.gammavariate(concentration * w / total, 1.0) for c, w in weights.items()}
    scale = total / sum(draw.values())
    return {c: v * scale for c, v in draw.items()}


def alternatives(weights: dict[str, float]) -> dict[str, dict[str, float]]:
    return {"rubric": dict(weights), "equal": {c: 1.0 for c in weights},
            "c8_doubled": {**weights, "C8_jd_fit": 2 * weights["C8_jd_fit"]},
            "no_c8": {**weights, "C8_jd_fit": 0.0}}


def _strategy_rhos(rows_by_strategy: dict[str, list[tuple[dict, dict]]], weights: dict[str, float]) -> dict[str, float]:
    out = {}
    for strategy, rows in rows_by_strategy.items():
        pairs = [(iaa._total(label, weights), iaa._total(pred, weights)) for label, pred in rows]
        pairs = [(h, m) for h, m in pairs if h is not None and m is not None]
        value = iaa.spearman([h for h, _ in pairs], [m for _, m in pairs]) if len(pairs) > 2 else None
        if value is not None:
            out[strategy] = value
    return out


def weight_sensitivity(records: list[dict], weights: dict[str, float], rows_by_strategy: dict | None = None,
                       draws: int = 2000, concentration: float = 50.0, seed: int = 42) -> dict[str, Any]:
    base_totals = [iaa._total(r, weights) for r in records]
    fits = [r["overall_fit"] for r in records]

    def describe(w: dict[str, float]) -> dict[str, Any]:
        totals = [iaa._total(r, w) for r in records]
        out = {"spearman_with_rubric_total": iaa.spearman(base_totals, totals),
               "spearman_with_fit": iaa.spearman(totals, fits)}
        if rows_by_strategy:
            out["strategy_spearman_total"] = _strategy_rhos(rows_by_strategy, w)
        return out

    named = {name: describe(w) for name, w in alternatives(weights).items()}
    rng = random.Random(seed)
    base_order = sorted(named["rubric"].get("strategy_spearman_total", {}).items(), key=lambda kv: -kv[1])
    base_rank = [s for s, _ in base_order]
    rerank, with_fit, same_order, same_top = [], [], 0, 0
    for _ in range(draws):
        w = _dirichlet(rng, weights, concentration)
        d = describe(w)
        rerank.append(d["spearman_with_rubric_total"])
        with_fit.append(d["spearman_with_fit"])
        if rows_by_strategy:
            order = [s for s, _ in sorted(d["strategy_spearman_total"].items(), key=lambda kv: -kv[1])]
            same_order += order == base_rank
            same_top += bool(order) and bool(base_rank) and order[0] == base_rank[0]

    def q(values: list[float]) -> dict[str, float]:
        values = sorted(v for v in values if v is not None)
        return {"p05": values[int(0.05 * (len(values) - 1))], "median": statistics.median(values),
                "p95": values[int(0.95 * (len(values) - 1))]}

    out = {"draws": draws, "concentration": concentration, "named": named,
           "random_spearman_with_rubric_total": q(rerank), "random_spearman_with_fit": q(with_fit)}
    if rows_by_strategy:
        out.update(base_strategy_order=base_rank, share_same_order=same_order / draws, share_same_top=same_top / draws)
    return out


def c8_band(requirements: list[dict], edges: tuple[float, ...] = BASE_EDGES, half: float = BASE_HALF) -> int | None:
    """The rubric's C8 rule with adjustable band edges and credit for mentioned_only."""
    value = {"met": 1.0, "mentioned_only": half, "missing": 0.0}
    must = [r for r in requirements if r["type"] == "must" and r["status"] in value]
    nice = [r for r in requirements if r["type"] != "must"]  # an undecided nice-to-have still exists
    unclear = sum(1 for r in requirements if r["type"] == "must" and r["status"] == "unclear")
    if not must or unclear > len(must):
        return None
    share = sum(value[r["status"]] for r in must) / len(must)
    level = sum(share >= e for e in edges)
    if level == 4 and nice and not any(r["status"] in ("met", "mentioned_only") for r in nice):
        level = 3
    return level


C8_VARIANTS = {
    "rubric": (BASE_EDGES, BASE_HALF),
    "edges_minus_0.05": (tuple(e - 0.05 for e in BASE_EDGES), BASE_HALF),
    "edges_plus_0.05": (tuple(e + 0.05 for e in BASE_EDGES), BASE_HALF),
    "mentioned_only_0.25": (BASE_EDGES, 0.25),
    "mentioned_only_0.75": (BASE_EDGES, 0.75),
    "mentioned_only_1.0": (BASE_EDGES, 1.0),
    "mentioned_only_0": (BASE_EDGES, 0.0),
}


def c8_sensitivity(records: list[dict]) -> dict[str, Any]:
    base = {r["pair_id"]: c8_band(list(r["requirements"].values())) for r in records}
    out = {}
    for name, (edges, half) in C8_VARIANTS.items():
        levels = {r["pair_id"]: c8_band(list(r["requirements"].values()), edges, half) for r in records}
        pairs = [(levels[r["pair_id"]], r["overall_fit"]) for r in records if levels[r["pair_id"]] is not None]
        out[name] = {"changed_pairs": sum(levels[p] != base[p] for p in base),
                     "mean_abs_change": statistics.mean(abs(levels[p] - base[p]) for p in base
                                                        if levels[p] is not None and base[p] is not None),
                     "spearman_with_fit": iaa.spearman([a for a, _ in pairs], [b for _, b in pairs])}
    return out


def _f(value: float | None, digits: int = 2) -> str:
    return "–" if value is None else f"{value:.{digits}f}".replace(".", ",")


def markdown(result: dict[str, Any]) -> str:
    lines = [f"# Phân tích độ nhạy rubric · {result['labels']}", "",
             f"{result['pairs']} cặp, {result['cvs']} CV; khoảng tin cậy 95% bootstrap theo CV. Chỉ báo cáo, không dùng "
             "để chỉnh rubric.", "", "## 1. Từng tiêu chí so với mức phù hợp của người", "",
             "| Tiêu chí | Trọng số | Spearman với mức phù hợp | KTC 95% |", "|---|---|---|---|"]
    for c, v in result["criterion_fit"].items():
        lines.append(f"| {c} | {v['weight']:.0f} | {_f(v['spearman_fit'])} | [{_f(v['low'])}; {_f(v['high'])}] |")
    w = result["weights"]
    lines += ["", "## 2. Độ nhạy của trọng số", "",
              f"{w['draws']} bộ trọng số ngẫu nhiên quanh trọng số rubric (Dirichlet, độ tập trung {w['concentration']:.0f}) "
              "và vài bộ thay thế.", "",
              "| Bộ trọng số | Spearman với tổng theo rubric | Spearman tổng với mức phù hợp |", "|---|---|---|"]
    for name, v in w["named"].items():
        lines.append(f"| {name} | {_f(v['spearman_with_rubric_total'])} | {_f(v['spearman_with_fit'])} |")
    r1, r2 = w["random_spearman_with_rubric_total"], w["random_spearman_with_fit"]
    lines.append(f"| ngẫu nhiên (5% / trung vị / 95%) | {_f(r1['p05'])} / {_f(r1['median'])} / {_f(r1['p95'])} | "
                 f"{_f(r2['p05'])} / {_f(r2['median'])} / {_f(r2['p95'])} |")
    if "base_strategy_order" in w:
        lines += ["", f"Thứ tự chiến lược theo Spearman điểm tổng với người (trọng số rubric): "
                      f"{' > '.join(w['base_strategy_order'])}. Giữ nguyên thứ tự ở {w['share_same_order']:.0%} bộ trọng số "
                      f"ngẫu nhiên; giữ chiến lược đứng đầu ở {w['share_same_top']:.0%}.", "",
                  "| Chiến lược | " + " | ".join(w["named"]) + " |", "|---|" + "---|" * len(w["named"])]
        for s in w["base_strategy_order"]:
            lines.append(f"| {s} | " + " | ".join(_f(v["strategy_spearman_total"].get(s)) for v in w["named"].values()) + " |")
    lines += ["", "## 3. Độ nhạy của luật C8", "",
              "| Biến thể | Số cặp đổi C8 | Đổi trung bình (mức) | Spearman C8 với mức phù hợp |", "|---|---|---|---|"]
    for name, v in result["c8"].items():
        lines.append(f"| {name} | {v['changed_pairs']} | {_f(v['mean_abs_change'])} | {_f(v['spearman_with_fit'])} |")
    return "\n".join(lines) + "\n"


def run(labels_path: Path, run_id: str | None, out_dir: Path, reps: int = 2000, seed: int = 42) -> dict[str, Any]:
    records, _ = iaa.load(labels_path)
    weights = rubric_weights()
    rows_by_strategy = None
    if run_id:
        run_dir = run_strategies.RESULTS / run_id
        labels = {r["pair_id"]: r for r in records}
        preds = run_strategies.latest(run_strategies._read_jsonl(run_dir / "predictions.jsonl")).values()
        rows_by_strategy = {}
        for p in preds:
            if p["status"] == "ok" and p.get("repeat", 1) == 1 and p["input"] == "gold" and p["pair_id"] in labels:
                rows_by_strategy.setdefault(p["strategy"], []).append((labels[p["pair_id"]], p))
        rows_by_strategy = {s: rows for s, rows in rows_by_strategy.items() if len(rows) == len(labels)}
    result = {"labels": labels_path.name, "run_id": run_id, "pairs": len(records),
              "cvs": len({r["cv_id"] for r in records}),
              "criterion_fit": criterion_fit(records, weights, reps, seed),
              "weights": weight_sensitivity(records, weights, rows_by_strategy, draws=reps, seed=seed),
              "c8": c8_sensitivity(records)}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sensitivity.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "SENSITIVITY.md").write_text(markdown(result), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Sensitivity of conclusions to rubric weights and the C8 rule.")
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--run-id", help="also check whether the strategies keep their order (gold input)")
    parser.add_argument("--out-dir", type=Path, default=Path("downstream/results/sensitivity_dev"))
    parser.add_argument("--reps", type=int, default=2000)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    run(args.labels, args.run_id, args.out_dir, args.reps)
    print((args.out_dir / "SENSITIVITY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
