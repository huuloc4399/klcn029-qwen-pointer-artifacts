"""Inter-rater agreement between two CV–JD rating files, and the list of cases to adjudicate.

Inputs are two rater workbooks (.xlsx, only pairs that pass ratings_io.check are used) or their
JSONL exports. Pairs are matched by pair_id, requirements by (pair_id, req_id).

Metrics (module A, step 6 of the plan):
- criteria 0–4: quadratic weighted kappa per criterion and pooled, exact and ±1 agreement, MAE,
  mean score per rater (systematic bias); a separate kappa on the criterion status;
- JD requirements: Cohen's kappa on the four statuses, and on "present in CV" (met or
  mentioned_only) against the rest;
- overall fit 1–5: Spearman and quadratic weighted kappa;
- rubric total (Σ w·s / 4Σw over scored criteria): Spearman and mean absolute difference.
95% intervals come from a bootstrap that resamples CVs, since the two pairs of a CV are not independent.

    python -m downstream.eval.iaa downstream/data/labels_v1/pilot_rater_A.xlsx downstream/data/labels_v1/pilot_rater_B.jsonl --out-dir downstream/data/labels_v1/iaa_pilot

The out-dir gets iaa_report.json, IAA_REPORT.md (aggregates only) and disagreements.csv. The CSV
quotes the CVs, so keep it under labels_v1/ (git-ignored).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

from downstream.data import ratings_io
from downstream.data.build_rating_workbook import RUBRIC

SCORES = [0, 1, 2, 3, 4]
FIT_LEVELS = [1, 2, 3, 4, 5]
SCORED = ("scored", "missing_in_cv")  # statuses that carry a number (missing_in_cv counts as 0)
REQ_RANK = {"missing": 0, "mentioned_only": 1, "met": 2}  # unclear is outside the order
ADJUDICATE_GAP = 2


# ---------- statistics ----------

def kappa(a: list, b: list, categories: list, weighted: bool = False) -> float | None:
    """Cohen's kappa; weighted=True uses quadratic weights over the order of `categories`.

    None when it is undefined: no items, or both raters used a single identical category so that
    chance agreement is already 1.
    """
    if not a or len(a) != len(b):
        return None
    index = {c: i for i, c in enumerate(categories)}
    k, n = len(categories), len(a)
    observed = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        observed[index[x]][index[y]] += 1 / n
    row = [sum(r) for r in observed]
    col = [sum(observed[i][j] for i in range(k)) for j in range(k)]

    def weight(i: int, j: int) -> float:
        if weighted:
            return (i - j) ** 2 / (k - 1) ** 2
        return 0.0 if i == j else 1.0

    disagreement = sum(weight(i, j) * observed[i][j] for i in range(k) for j in range(k))
    expected = sum(weight(i, j) * row[i] * col[j] for i in range(k) for j in range(k))
    if expected <= 1e-12:
        return None
    return 1 - disagreement / expected


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for position in range(i, j + 1):
            ranks[order[position]] = (i + j) / 2 + 1  # ties share the average rank
        i = j + 1
    return ranks


def spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3 or len(a) != len(b):
        return None
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va, vb = sum((x - ma) ** 2 for x in ra), sum((y - mb) ** 2 for y in rb)
    if va == 0 or vb == 0:
        return None
    return cov / math.sqrt(va * vb)


def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return sum(values) / len(values) if values else None


def landis_koch(value: float | None) -> str:
    """Conventional reading of kappa (Landis and Koch, 1977); a label, not a pass mark."""
    if value is None:
        return "không xác định"
    for bound, label in ((0.0, "kém"), (0.2, "rất thấp"), (0.4, "thấp"), (0.6, "trung bình"), (0.8, "khá")):
        if value <= bound:
            return label
    return "rất cao"


# ---------- loading ----------

def load(path: Path) -> tuple[list[dict], dict[str, Any]]:
    """Records of the complete pairs, and what was left out."""
    if path.suffix.lower() == ".jsonl":
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return records, {"file": path.name, "pairs_in_file": len(records), "incomplete_pairs": [], "workbook_issues": 0}
    book = ratings_io.read(path)
    issues = ratings_io.check(book)
    broken = {issue.pair_id for issue in issues}
    records = [r for r in ratings_io.to_records(book) if r["pair_id"] not in broken]
    total = len(book["overall"])
    return records, {"file": path.name, "pairs_in_file": total,
                     "incomplete_pairs": sorted(p for p in broken if p),
                     "workbook_issues": sum(1 for i in issues if not i.pair_id)}


def align(a: list[dict], b: list[dict]) -> tuple[list[tuple[dict, dict]], list[str]]:
    """Pairs rated completely by both raters, in pair_id order, plus warnings about mismatches."""
    by_id = {r["pair_id"]: r for r in b}
    aligned, warnings = [], []
    for ra in sorted(a, key=lambda r: r["pair_id"]):
        rb = by_id.get(ra["pair_id"])
        if rb is None:
            continue
        if (ra["cv_id"], ra["jd_id"]) != (rb["cv_id"], rb["jd_id"]):
            warnings.append(f"{ra['pair_id']}: hai file ghi CV/JD khác nhau, bỏ qua cặp này")
            continue
        aligned.append((ra, rb))
    for key in ("rubric_version", "rubric_sha256", "pairs_sha256"):
        values = {r.get(key) for pair in aligned for r in pair}
        if len(values) > 1:
            warnings.append(f"Hai file dùng {key} khác nhau: {sorted(map(str, values))}")
    return aligned, warnings


# ---------- metrics ----------

def _total(record: dict, weights: dict[str, float]) -> float | None:
    scored = [(weights[c], v["score"]) for c, v in record["criteria"].items()
              if v["status"] in SCORED and v["score"] is not None and c in weights]
    denominator = sum(w for w, _ in scored)
    return 100 * sum(w * s for w, s in scored) / (4 * denominator) if denominator else None


def _requirement_rows(aligned: list[tuple[dict, dict]]) -> list[tuple[str, str, dict, dict]]:
    rows = []
    for ra, rb in aligned:
        for req_id, va in ra["requirements"].items():
            vb = rb["requirements"].get(req_id)
            if vb is not None:
                rows.append((ra["pair_id"], req_id, va, vb))
    return rows


def compute(aligned: list[tuple[dict, dict]], rubric: dict) -> dict[str, Any]:
    criteria = [c["id"] for c in rubric["criteria"]]
    weights = {c["id"]: float(c["weight"]) for c in rubric["criteria"]}
    statuses = list(rubric["criterion_statuses"])
    req_statuses = list(rubric["requirement_statuses"])
    out: dict[str, Any] = {"pairs": len(aligned), "cvs": len({ra["cv_id"] for ra, _ in aligned}), "criteria": {}}

    pooled_a, pooled_b, status_a, status_b = [], [], [], []
    for criterion in criteria:
        a, b = [], []
        for ra, rb in aligned:
            va, vb = ra["criteria"].get(criterion), rb["criteria"].get(criterion)
            if va is None or vb is None:
                continue
            status_a.append(va["status"])
            status_b.append(vb["status"])
            if va["status"] in SCORED and vb["status"] in SCORED and va["score"] is not None and vb["score"] is not None:
                a.append(va["score"])
                b.append(vb["score"])
        pooled_a += a
        pooled_b += b
        gaps = [abs(x - y) for x, y in zip(a, b)]
        out["criteria"][criterion] = {
            "n": len(a),
            "qwk": kappa(a, b, SCORES, weighted=True),
            "exact": _mean(g == 0 for g in gaps),
            "within_1": _mean(g <= 1 for g in gaps),
            "mae": _mean(gaps),
            "mean_a": _mean(a), "mean_b": _mean(b),
            "gap_ge_2": sum(g >= ADJUDICATE_GAP for g in gaps),
        }
    pooled_gaps = [abs(x - y) for x, y in zip(pooled_a, pooled_b)]
    out["criteria_pooled"] = {"n": len(pooled_a), "qwk": kappa(pooled_a, pooled_b, SCORES, weighted=True),
                              "exact": _mean(g == 0 for g in pooled_gaps), "within_1": _mean(g <= 1 for g in pooled_gaps),
                              "mae": _mean(pooled_gaps)}
    out["criterion_status"] = {"n": len(status_a), "kappa": kappa(status_a, status_b, statuses),
                               "agreement": _mean(x == y for x, y in zip(status_a, status_b)),
                               "confusion": _confusion(status_a, status_b)}

    rows = _requirement_rows(aligned)
    ra_status = [va["status"] for _, _, va, _ in rows]
    rb_status = [vb["status"] for _, _, _, vb in rows]
    present = lambda s: "co" if s in ("met", "mentioned_only") else "khong"  # noqa: E731
    must = [(va["status"], vb["status"]) for _, _, va, vb in rows if va.get("type") == "must"]
    out["requirements"] = {
        "n": len(rows),
        "kappa": kappa(ra_status, rb_status, req_statuses),
        "agreement": _mean(x == y for x, y in zip(ra_status, rb_status)),
        "kappa_present": kappa([present(s) for s in ra_status], [present(s) for s in rb_status], ["co", "khong"]),
        "kappa_must": kappa([x for x, _ in must], [y for _, y in must], req_statuses),
        "n_must": len(must),
        "confusion": _confusion(ra_status, rb_status),
    }

    fit_a = [ra["overall_fit"] for ra, rb in aligned if ra["overall_fit"] and rb["overall_fit"]]
    fit_b = [rb["overall_fit"] for ra, rb in aligned if ra["overall_fit"] and rb["overall_fit"]]
    fit_gaps = [abs(x - y) for x, y in zip(fit_a, fit_b)]
    out["overall_fit"] = {"n": len(fit_a), "spearman": spearman(fit_a, fit_b),
                          "qwk": kappa(fit_a, fit_b, FIT_LEVELS, weighted=True),
                          "exact": _mean(g == 0 for g in fit_gaps), "within_1": _mean(g <= 1 for g in fit_gaps),
                          "mean_a": _mean(fit_a), "mean_b": _mean(fit_b)}

    totals = [(_total(ra, weights), _total(rb, weights)) for ra, rb in aligned]
    totals = [(x, y) for x, y in totals if x is not None and y is not None]
    out["rubric_total"] = {"n": len(totals), "spearman": spearman([x for x, _ in totals], [y for _, y in totals]),
                           "mean_abs_diff": _mean(abs(x - y) for x, y in totals),
                           "mean_a": _mean(x for x, _ in totals), "mean_b": _mean(y for _, y in totals)}
    return out


def _confusion(a: list[str], b: list[str]) -> dict[str, int]:
    return {f"{x} | {y}": n for (x, y), n in sorted(Counter(zip(a, b)).items())}


def headline(metrics: dict[str, Any]) -> dict[str, float | None]:
    """The numbers that get a bootstrap interval."""
    values = {f"qwk.{c}": v["qwk"] for c, v in metrics["criteria"].items()}
    values.update({
        "qwk.pooled": metrics["criteria_pooled"]["qwk"],
        "kappa.criterion_status": metrics["criterion_status"]["kappa"],
        "kappa.requirements": metrics["requirements"]["kappa"],
        "kappa.requirements_present": metrics["requirements"]["kappa_present"],
        "spearman.overall_fit": metrics["overall_fit"]["spearman"],
        "spearman.rubric_total": metrics["rubric_total"]["spearman"],
    })
    return values


def bootstrap(aligned: list[tuple[dict, dict]], rubric: dict, reps: int, seed: int,
              stat: Callable[[list[tuple[dict, dict]], dict], dict[str, float | None]] | None = None
              ) -> dict[str, dict[str, Any]]:
    """Percentile 95% intervals, resampling CVs with replacement (all pairs of a drawn CV come along)."""
    stat = stat or (lambda rows, rb: headline(compute(rows, rb)))
    by_cv: dict[str, list[tuple[dict, dict]]] = {}
    for pair in aligned:
        by_cv.setdefault(pair[0]["cv_id"], []).append(pair)
    cvs = sorted(by_cv)
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {}
    for _ in range(reps if len(cvs) >= 2 else 0):
        drawn = [pair for _ in cvs for pair in by_cv[rng.choice(cvs)]]
        for key, value in stat(drawn, rubric).items():
            if value is not None:
                samples.setdefault(key, []).append(value)
    out = {}
    for key, values in samples.items():
        values.sort()
        out[key] = {"low": values[int(0.025 * (len(values) - 1))], "high": values[int(0.975 * (len(values) - 1))],
                    "valid_reps": len(values)}
    return out


# ---------- adjudication list ----------

DISAGREEMENT_COLUMNS = ["pair_id", "cv_id", "jd_id", "item", "kind", "value_A", "value_B", "status_A", "status_B",
                        "section_A", "section_B", "quote_A", "quote_B", "reason_A", "reason_B",
                        "decision", "adjudicator_note"]


def disagreements(aligned: list[tuple[dict, dict]]) -> list[dict[str, Any]]:
    """Cases for the third rater: score gaps ≥ 2, one rater scoring where the other could not,
    met against missing, and overall fit gaps ≥ 2."""
    rows = []
    for ra, rb in aligned:
        base = {"pair_id": ra["pair_id"], "cv_id": ra["cv_id"], "jd_id": ra["jd_id"]}
        for criterion, va in ra["criteria"].items():
            vb = rb["criteria"].get(criterion)
            if vb is None:
                continue
            a_scored, b_scored = va["status"] in SCORED, vb["status"] in SCORED
            if a_scored and b_scored and va["score"] is not None and vb["score"] is not None:
                if abs(va["score"] - vb["score"]) < ADJUDICATE_GAP:
                    continue
                kind = f"điểm lệch {abs(va['score'] - vb['score'])}"
            elif va["status"] != vb["status"] and (a_scored or b_scored):
                kind = "một người chấm được, người kia không"
            else:
                continue
            rows.append({**base, "item": criterion, "kind": kind, "value_A": va["score"], "value_B": vb["score"],
                         "status_A": va["status"], "status_B": vb["status"],
                         "section_A": va["evidence_section"], "section_B": vb["evidence_section"],
                         "quote_A": va["quote"], "quote_B": vb["quote"], "reason_A": va["reason"], "reason_B": vb["reason"]})
        for req_id, va in ra["requirements"].items():
            vb = rb["requirements"].get(req_id)
            if vb is None or va["status"] not in REQ_RANK or vb["status"] not in REQ_RANK:
                continue
            if abs(REQ_RANK[va["status"]] - REQ_RANK[vb["status"]]) < ADJUDICATE_GAP:
                continue
            rows.append({**base, "item": f"{req_id} · {va['text']}", "kind": "yêu cầu: met so với missing",
                         "value_A": va["status"], "value_B": vb["status"], "status_A": va["status"],
                         "status_B": vb["status"], "section_A": va["evidence_section"], "section_B": vb["evidence_section"],
                         "quote_A": va["quote"], "quote_B": vb["quote"], "reason_A": va["note"], "reason_B": vb["note"]})
        if ra["overall_fit"] and rb["overall_fit"] and abs(ra["overall_fit"] - rb["overall_fit"]) >= ADJUDICATE_GAP:
            rows.append({**base, "item": "overall_fit", "kind": f"mức phù hợp lệch {abs(ra['overall_fit'] - rb['overall_fit'])}",
                         "value_A": ra["overall_fit"], "value_B": rb["overall_fit"], "status_A": "", "status_B": "",
                         "section_A": "", "section_B": "", "quote_A": "", "quote_B": "",
                         "reason_A": ra["comment"], "reason_B": rb["comment"]})
    return rows


# ---------- report ----------

def _f(value: float | None, digits: int = 2) -> str:
    return "–" if value is None else f"{value:.{digits}f}"


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{value:.0%}"


def _ci(intervals: dict, key: str) -> str:
    ci = intervals.get(key)
    return "–" if not ci else f"[{ci['low']:.2f}; {ci['high']:.2f}]"


def markdown(report: dict[str, Any], rubric: dict) -> str:
    m, ci = report["metrics"], report["bootstrap_95ci"]
    names = {c["id"]: c.get("name", c["id"]) for c in rubric["criteria"]}
    lines = [
        "# Đồng thuận giữa hai người chấm",
        "",
        f"- File A: `{report['rater_a']['file']}` ({len(report['rater_a']['records'])} cặp hoàn chỉnh / "
        f"{report['rater_a']['pairs_in_file']}); file B: `{report['rater_b']['file']}` "
        f"({len(report['rater_b']['records'])} / {report['rater_b']['pairs_in_file']}).",
        f"- Tính trên **{m['pairs']} cặp chung** của **{m['cvs']} CV**; rubric `{report['rubric_version']}`.",
        f"- Khoảng tin cậy 95%: bootstrap theo CV, {report['bootstrap_reps']} lần, seed {report['seed']}.",
    ]
    lines += [f"- Cảnh báo: {w}" for w in report["warnings"]]
    if m["pairs"] < 10:
        lines.append("- Ít cặp: khoảng tin cậy rất rộng, chỉ dùng để tìm chỗ hướng dẫn chưa rõ, không dùng để kết luận.")
    lines += [
        "",
        "## Điểm tiêu chí 0–4",
        "",
        "| Tiêu chí | n | Kappa bậc hai | KTC 95% | Mức | Trùng | Lệch ≤1 | MAE | TB A | TB B | Lệch ≥2 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for criterion, v in m["criteria"].items():
        lines.append(f"| {criterion} {names[criterion]} | {v['n']} | {_f(v['qwk'])} | {_ci(ci, 'qwk.' + criterion)} | "
                     f"{landis_koch(v['qwk'])} | {_pct(v['exact'])} | {_pct(v['within_1'])} | {_f(v['mae'])} | "
                     f"{_f(v['mean_a'])} | {_f(v['mean_b'])} | {v['gap_ge_2']} |")
    p = m["criteria_pooled"]
    lines += [f"| **Gộp 8 tiêu chí** | {p['n']} | {_f(p['qwk'])} | {_ci(ci, 'qwk.pooled')} | {landis_koch(p['qwk'])} | "
              f"{_pct(p['exact'])} | {_pct(p['within_1'])} | {_f(p['mae'])} | | | |",
              "",
              "Kappa không xác định khi cả hai người cho cùng một mức ở mọi cặp; khi đó xem cột Trùng.",
              "",
              f"Trạng thái tiêu chí (scored, missing_in_cv, not_applicable, unreadable): kappa "
              f"{_f(m['criterion_status']['kappa'])} {_ci(ci, 'kappa.criterion_status')}, trùng "
              f"{_pct(m['criterion_status']['agreement'])} trên {m['criterion_status']['n']} dòng.",
              "",
              "## Yêu cầu của JD",
              ""]
    r = m["requirements"]
    lines += [f"- {r['n']} yêu cầu được cả hai chấm. Kappa 4 trạng thái: **{_f(r['kappa'])}** "
              f"{_ci(ci, 'kappa.requirements')} ({landis_koch(r['kappa'])}); trùng {_pct(r['agreement'])}.",
              f"- Gộp thành có trong CV (met, mentioned_only) hay không: kappa {_f(r['kappa_present'])} "
              f"{_ci(ci, 'kappa.requirements_present')}.",
              f"- Riêng yêu cầu bắt buộc ({r['n_must']}): kappa {_f(r['kappa_must'])}.",
              "",
              "| A \\| B | Số dòng |",
              "|---|---|"]
    lines += [f"| {k} | {n} |" for k, n in r["confusion"].items()]
    o, t = m["overall_fit"], m["rubric_total"]
    lines += ["",
              "## Mức phù hợp tổng thể và điểm tổng",
              "",
              f"- Mức phù hợp 1–5 ({o['n']} cặp): Spearman **{_f(o['spearman'])}** {_ci(ci, 'spearman.overall_fit')}, "
              f"kappa bậc hai {_f(o['qwk'])}, trùng {_pct(o['exact'])}, lệch ≤1 {_pct(o['within_1'])}; "
              f"trung bình A {_f(o['mean_a'])}, B {_f(o['mean_b'])}.",
              f"- Điểm tổng rubric 0–100 ({t['n']} cặp): Spearman **{_f(t['spearman'])}** "
              f"{_ci(ci, 'spearman.rubric_total')}, chênh tuyệt đối trung bình {_f(t['mean_abs_diff'], 1)} điểm; "
              f"trung bình A {_f(t['mean_a'], 1)}, B {_f(t['mean_b'], 1)}.",
              "",
              "## Cần phân xử",
              "",
              f"{report['disagreement_count']} mục trong `disagreements.csv` (điểm lệch ≥2, một người chấm được còn người kia "
              "không, met so với missing, mức phù hợp lệch ≥2). Người thứ ba ghi cột `decision` và `adjudicator_note`.",
              ""]
    by_kind = Counter(row["kind"] for row in report["disagreement_rows"])
    lines += [f"- {kind}: {n}" for kind, n in sorted(by_kind.items())]
    return "\n".join(lines) + "\n"


def run(path_a: Path, path_b: Path, out_dir: Path | None, reps: int = 2000, seed: int = 42,
        rubric_path: Path = RUBRIC) -> dict[str, Any]:
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    records_a, info_a = load(path_a)
    records_b, info_b = load(path_b)
    aligned, warnings = align(records_a, records_b)
    rows = disagreements(aligned)
    report = {
        "rubric_version": rubric["rubric_version"],
        "rater_a": {**info_a, "records": [r["pair_id"] for r in records_a],
                    "rater_id": records_a[0]["rater_id"] if records_a else ""},
        "rater_b": {**info_b, "records": [r["pair_id"] for r in records_b],
                    "rater_id": records_b[0]["rater_id"] if records_b else ""},
        "warnings": warnings, "bootstrap_reps": reps, "seed": seed,
        "metrics": compute(aligned, rubric),
        "bootstrap_95ci": bootstrap(aligned, rubric, reps, seed),
        "disagreement_count": len(rows),
        "disagreement_rows": rows,
    }
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        public = {k: v for k, v in report.items() if k != "disagreement_rows"}
        (out_dir / "iaa_report.json").write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out_dir / "IAA_REPORT.md").write_text(markdown(report, rubric), encoding="utf-8")
        with (out_dir / "disagreements.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=DISAGREEMENT_COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows({**row, "decision": "", "adjudicator_note": ""} for row in rows)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Agreement between two CV–JD rating files.")
    parser.add_argument("rater_a", type=Path, help="workbook (.xlsx) or export (.jsonl)")
    parser.add_argument("rater_b", type=Path)
    parser.add_argument("--out-dir", type=Path, help="writes iaa_report.json, IAA_REPORT.md, disagreements.csv")
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    report = run(args.rater_a, args.rater_b, args.out_dir, args.bootstrap, args.seed)
    for info in (report["rater_a"], report["rater_b"]):
        if info["incomplete_pairs"]:
            print(f"{info['file']}: {len(info['incomplete_pairs'])} cặp chưa xong bị bỏ qua "
                  f"(xem bằng python -m downstream.data.ratings_io check)")
    if report["metrics"]["pairs"] == 0:
        print("Không có cặp nào cả hai người đều chấm xong.")
        return 1
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    print(markdown(report, rubric))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
