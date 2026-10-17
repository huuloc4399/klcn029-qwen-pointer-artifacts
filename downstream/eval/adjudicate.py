"""Adjudication of two raters' labels into FINAL labels.

Round 1 (iaa.py's disagreements.csv) holds the large gaps: scores ≥2 apart, met against missing,
overall fit ≥2 apart. Round 2 lists what is left that cannot be averaged: the other requirement
mismatches (met / mentioned_only, mentioned_only / missing, anything with unclear) and round-1 rows
left without a decision. The third rater fills `decision` (the final value) and `adjudicator_note`.

`final` merges A, B and the decisions:
- the raters agree → that value;
- a decision exists → the decision (a later round overrides an earlier one);
- a criterion score or overall fit 1 apart → the mean (x.5), as is usual for two raters;
- missing_in_cv against scored with both 0 → missing_in_cv, score 0;
- anything else without a decision is an error, so no FINAL is written with holes.
By default C8 is then replaced by the rubric band of the final requirement statuses (C8 is defined
from them); --no-c8-from-requirements keeps the merged C8 and only warns where the two differ. It also
warns when a JD-independent criterion differs between two pairs of the same CV.

    python -m downstream.eval.adjudicate round2 A.jsonl B.jsonl --round1 disagreements.csv --out round2.csv
    python -m downstream.eval.adjudicate final A.jsonl B.jsonl --decisions round1.csv round2.csv --out FINAL.jsonl

The CSVs and FINAL quote CVs: keep them under downstream/data/labels_v1/ (git-ignored).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from downstream.eval import iaa

REQ_STATUSES = ("met", "mentioned_only", "missing", "unclear")
ALIASES = {"mention_only": "mentioned_only", "mentioned only": "mentioned_only"}  # unambiguous typos seen in decisions
JD_INDEPENDENT = ("C1_structure", "C2_it_content", "C3_skills", "C6_certs_activities", "C7_ats")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=iaa.DISAGREEMENT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({**row, "decision": row.get("decision", ""), "adjudicator_note": row.get("adjudicator_note", "")}
                         for row in rows)


def _aligned(path_a: Path, path_b: Path) -> list[tuple[dict, dict]]:
    a, _ = iaa.load(path_a)
    b, _ = iaa.load(path_b)
    aligned, warnings = iaa.align(a, b)
    for warning in warnings:
        print(f"Cảnh báo: {warning}", file=sys.stderr)
    return aligned


def round2_rows(aligned: list[tuple[dict, dict]], round1: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = [{**r, "kind": f"{r['kind']} (vòng 1 chưa có quyết định)"} for r in round1 if not r["decision"].strip()]
    for ra, rb in aligned:
        base = {"pair_id": ra["pair_id"], "cv_id": ra["cv_id"], "jd_id": ra["jd_id"]}
        for req_id, va in ra["requirements"].items():
            vb = rb["requirements"].get(req_id)
            if vb is None or va["status"] == vb["status"]:
                continue
            ranked = va["status"] in iaa.REQ_RANK and vb["status"] in iaa.REQ_RANK
            if ranked and abs(iaa.REQ_RANK[va["status"]] - iaa.REQ_RANK[vb["status"]]) >= iaa.ADJUDICATE_GAP:
                continue  # met against missing: round 1
            rows.append(iaa.requirement_row(base, req_id, va, vb, f"yêu cầu: {va['status']} so với {vb['status']}"))
    return sorted(rows, key=lambda r: (r["pair_id"], r["item"]))


# ---------- FINAL ----------

def _key(row: dict[str, str]) -> tuple[str, str]:
    """(pair_id, criterion id / req_id / overall_fit) of a decision row."""
    return row["pair_id"], row["item"].split(" · ")[0].strip()


def read_decisions(paths: list[Path]) -> tuple[dict[tuple[str, str], dict[str, str]], list[str], list[str]]:
    """Filled decisions by key (later files override earlier ones), the errors found, and typos read as aliases."""
    decisions, errors, notes = {}, [], []
    for path in paths:
        for line, row in enumerate(read_csv(path), start=2):
            value = row["decision"].strip()
            if not value:
                continue
            if value in ALIASES:
                errors_fixed = f"{path.name}: '{value}' đọc là '{ALIASES[value]}'"
                if errors_fixed not in notes:
                    notes.append(errors_fixed)
                value = ALIASES[value]
            key = _key(row)
            if key[1] == "overall_fit":
                ok = value in {"1", "2", "3", "4", "5"}
            elif key[1].startswith("C") and "_" in key[1]:
                ok = value in {"0", "1", "2", "3", "4"}
            else:
                ok = value in REQ_STATUSES
            if not ok:
                errors.append(f"{path.name} dòng {line} ({key[0]}, {key[1]}): quyết định '{value}' không hợp lệ")
                continue
            decisions[key] = {**row, "decision": value, "source_file": path.name}
    return decisions, errors, notes


def _number(value: str) -> int:
    return int(value)


def _criterion(pair_id: str, cid: str, va: dict, vb: dict, decided: dict | None) -> tuple[dict | None, str]:
    """(final criterion, how it was decided); None when it needs a decision that is missing."""
    keep = {k: va.get(k) for k in ("evidence_section", "quote", "reason")}
    if decided is not None:
        score = _number(decided["decision"])
        source = va if va.get("score") == score else vb if vb.get("score") == score else None
        status = source["status"] if source and source["status"] in iaa.SCORED else "scored"
        evidence = {k: (source or va).get(k) for k in ("evidence_section", "quote", "reason")}
        return {"status": status, "score": score, **evidence, "note": decided.get("adjudicator_note", "")}, "decision"
    if va["status"] == vb["status"] and va.get("score") == vb.get("score"):
        return {"status": va["status"], "score": va.get("score"), **keep, "note": ""}, "agreed"
    a_num, b_num = va["status"] in iaa.SCORED, vb["status"] in iaa.SCORED
    if a_num and b_num and va["score"] is not None and vb["score"] is not None:
        if va["score"] == vb["score"]:  # missing_in_cv against scored, both 0
            return {"status": "missing_in_cv", "score": va["score"], **keep, "note": ""}, "agreed_score"
        if abs(va["score"] - vb["score"]) == 1:
            return {"status": "scored", "score": (va["score"] + vb["score"]) / 2, **keep, "note": ""}, "mean"
    return None, "missing_decision"


def final_records(aligned: list[tuple[dict, dict]], decisions: dict[tuple[str, str], dict[str, str]],
                  c8_band=None, c8_from_requirements: bool = False) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """(FINAL records, errors, warnings).

    c8_from_requirements: C8 is the band of the final requirement statuses, as the rubric defines it; the
    raters' own C8 stays in their files for agreement. Without a band (too many unclear) the merged C8 stays.
    """
    records, errors, warnings = [], [], []
    for ra, rb in aligned:
        pid = ra["pair_id"]
        criteria, how = {}, {}
        for cid, va in ra["criteria"].items():
            vb = rb["criteria"][cid]
            item, source = _criterion(pid, cid, va, vb, decisions.get((pid, cid)))
            if item is None:
                errors.append(f"{pid} {cid}: A {va['status']} {va.get('score')}, B {vb['status']} {vb.get('score')} "
                              "cần quyết định")
                continue
            criteria[cid], how[cid] = item, source
        requirements = {}
        for req_id, va in ra["requirements"].items():
            vb = rb["requirements"].get(req_id, va)
            decided = decisions.get((pid, req_id))
            if decided is not None:
                status = decided["decision"]
                source = va if va["status"] == status else vb if vb["status"] == status else va
                requirements[req_id] = {"type": va["type"], "text": va["text"], "status": status,
                                        "evidence_section": source["evidence_section"], "quote": source["quote"],
                                        "note": decided.get("adjudicator_note", "")}
                how[req_id] = "decision"
            elif va["status"] == vb["status"]:
                requirements[req_id] = {**{k: va[k] for k in ("type", "text", "status", "evidence_section", "quote")},
                                        "note": ""}
                how[req_id] = "agreed"
            else:
                errors.append(f"{pid} {req_id}: A {va['status']}, B {vb['status']} cần quyết định")
        decided_fit = decisions.get((pid, "overall_fit"))
        if decided_fit is not None:
            fit, how["overall_fit"] = _number(decided_fit["decision"]), "decision"
        elif ra["overall_fit"] == rb["overall_fit"]:
            fit, how["overall_fit"] = ra["overall_fit"], "agreed"
        elif abs(ra["overall_fit"] - rb["overall_fit"]) == 1:
            fit, how["overall_fit"] = (ra["overall_fit"] + rb["overall_fit"]) / 2, "mean"
        else:
            fit = None
            errors.append(f"{pid} overall_fit: A {ra['overall_fit']}, B {rb['overall_fit']} cần quyết định")
        records.append({"pair_id": pid, "cv_id": ra["cv_id"], "jd_id": ra["jd_id"], "rater_id": "FINAL",
                        "rubric_version": ra["rubric_version"], "rubric_sha256": ra.get("rubric_sha256"),
                        "pairs_sha256": ra.get("pairs_sha256"), "overall_fit": fit, "comment": "", "suggestions": [],
                        "minutes": None, "criteria": criteria, "requirements": requirements, "final_source": how})
    # The same CV must keep its JD-independent scores across its pairs.
    by_cv: dict[str, list[dict]] = {}
    for record in records:
        by_cv.setdefault(record["cv_id"], []).append(record)
    for cv_id, group in sorted(by_cv.items()):
        for cid in JD_INDEPENDENT:
            values = {r["pair_id"]: (r["criteria"].get(cid) or {}).get("score") for r in group}
            if len(set(values.values())) > 1:
                warnings.append(f"{cv_id} {cid} khác nhau giữa các cặp: {values}")
    if c8_band is not None:
        for record in records:
            band, why = c8_band(list(record["requirements"].values()))
            c8 = (record["criteria"].get("C8_jd_fit") or {}).get("score")
            if c8_from_requirements and band is not None and "C8_jd_fit" in record["criteria"]:
                item = record["criteria"]["C8_jd_fit"]
                record["criteria"]["C8_jd_fit"] = {**item, "status": "scored", "score": band,
                                                   "note": f"tính từ yêu cầu sau phân xử: {why} (trước đó {c8})"}
                record["final_source"]["C8_jd_fit"] = "from_requirements"
            elif band is not None and c8 is not None and band != c8:
                warnings.append(f"{record['pair_id']} C8 = {c8} nhưng các yêu cầu sau phân xử cho mức {band} "
                                f"({record['final_source'].get('C8_jd_fit')})")
    return records, errors, warnings


def _c8_band():
    from downstream.eval import run_strategies
    return run_strategies._grounded().c8_from_requirements  # the rubric's C8 bands, shared with the web app


def main() -> int:
    parser = argparse.ArgumentParser(description="Adjudication rounds and FINAL labels from two raters.")
    sub = parser.add_subparsers(dest="command", required=True)
    r2 = sub.add_parser("round2")
    r2.add_argument("a", type=Path)
    r2.add_argument("b", type=Path)
    r2.add_argument("--round1", type=Path, required=True)
    r2.add_argument("--out", type=Path, required=True)
    fin = sub.add_parser("final")
    fin.add_argument("a", type=Path)
    fin.add_argument("b", type=Path)
    fin.add_argument("--decisions", type=Path, nargs="+", required=True, help="round 1 first, later rounds after")
    fin.add_argument("--out", type=Path, required=True)
    fin.add_argument("--c8-from-requirements", action=argparse.BooleanOptionalAction, default=True,
                     help="C8 = the rubric band of the final requirement statuses (default)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    aligned = _aligned(args.a, args.b)
    if args.command == "round2":
        rows = round2_rows(aligned, read_csv(args.round1))
        write_csv(args.out, rows)
        kinds: dict[str, int] = {}
        for row in rows:
            kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
        print(f"{args.out}: {len(rows)} dòng cần phân xử " + json.dumps(kinds, ensure_ascii=False))
        return 0
    decisions, errors, notes = read_decisions(args.decisions)
    for note in notes:
        print(f"Ghi chú: {note}")
    records, missing, warnings = final_records(aligned, decisions, _c8_band(), args.c8_from_requirements)
    for warning in warnings:
        print(f"Cảnh báo: {warning}")
    if errors or missing:
        for error in errors + missing:
            print(f"Lỗi: {error}")
        print(f"Chưa ghi {args.out}: còn {len(errors) + len(missing)} lỗi.")
        return 1
    args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    sources: dict[str, int] = {}
    for record in records:
        for source in record["final_source"].values():
            sources[source] = sources.get(source, 0) + 1
    print(f"{args.out}: {len(records)} cặp; cách chốt " + json.dumps(sources, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
