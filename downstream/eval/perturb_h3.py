"""Hypothesis H3: does P tell a section lost by the extractor apart from a section the CV really lacks?

For 10 test-split CVs (each with its same-track JD) three scoring inputs are built from the gold CVSchema:

- orig: the gold CVSchema and the real PDF analysis;
- misread: one section (projects, or experience when there are no projects) removed from the CVSchema,
  while the PDF analysis is unchanged — the text is in the PDF but the extractor lost it;
- missing: the same CVSchema as misread, with the PDF's character count scaled down by the same share
  — the CV really has no such section.

misread and missing send the LLM the same CV; only the PDF facts differ. A scorer that cannot abstain
treats both alike. P should mark the affected criterion needs_verification for misread and score it
0 for missing, so its total moves less on misread than on missing.

    python -m downstream.eval.perturb_h3 build
    python -m downstream.eval.perturb_h3 run --run-id h3_v1 --strategies baseline_rules m3_rag p_grounded p_no_abstain
    python -m downstream.eval.perturb_h3 report --run-id h3_v1

Variants hold real CV content; they live under the git-ignored cv_inputs_v1/.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from downstream.eval import cv_inputs, iaa, run_strategies as runner

OUT = cv_inputs.OUT / "h3_v1"
KINDS = ("orig", "misread", "missing")
AFFECTED = {"projects": "C4_projects", "experience": "C5_experience"}
N_CVS = 10


def _text_len(cv_schema: dict[str, Any]) -> int:
    rubric_scoring, _ = runner._web()
    return len(runner._grounded()._flatten(rubric_scoring.cv_payload(cv_schema)))


def build(out: Path = OUT, n: int = N_CVS) -> dict[str, Any]:
    pairs = [p for p in runner.load_pairs(split="test") if p["intended_fit"] == "same_track"]
    chosen, rows, files = [], [], {}
    for pair in sorted(pairs, key=lambda p: p["pair_id"]):
        cv = cv_inputs.load("gold", pair["cv_id"])
        section = "projects" if cv and cv.get("projects") else "experience" if cv and cv.get("experience") else None
        if section:
            chosen.append((pair, cv, section))
        if len(chosen) == n:
            break
    for sub in ("variants", "documents"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    for pair, cv, section in chosen:
        document = cv_inputs.load_document(pair["cv_id"])
        cut = copy.deepcopy(cv)
        cut[section] = []
        share = _text_len(cut) / max(1, _text_len(cv))
        variants = {
            "orig": (cv, document),
            "misread": (cut, document),
            "missing": (cut, {**document, "character_count": round(document["character_count"] * share)}),
        }
        for kind, (schema, doc) in variants.items():
            vid = f"{pair['pair_id']}-{kind}"
            for sub, value in (("variants", schema), ("documents", doc)):
                data = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
                (out / sub / f"{vid}.json").write_bytes(data)
                files[f"{sub}/{vid}.json"] = hashlib.sha256(data).hexdigest()
            rows.append({"pair_id": vid, "cv_id": vid, "jd_id": pair["jd_id"], "split": "h3", "intended_fit": kind,
                         "source_pair": pair["pair_id"], "removed_section": section, "affected": AFFECTED[section]})
    with (out / "pairs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    manifest = {"version": "h3_v1", "source_manifest_sha256": cv_inputs.manifest_sha(), "pairs": len(chosen),
                "removed": {r["source_pair"]: r["removed_section"] for r in rows}, "files": files}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_rows(out: Path = OUT) -> list[dict[str, str]]:
    with (out / "pairs.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# ---------- report ----------

def summarize(records: list[dict[str, Any]], rows: list[dict[str, str]]) -> dict[str, Any]:
    meta = {r["pair_id"]: r for r in rows}
    latest = runner.latest(records)
    by: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in latest.values():
        if record["status"] != "ok" or record["repeat"] != 1:
            continue
        row = meta[record["pair_id"]]
        by[(record["strategy"], row["source_pair"], row["intended_fit"])] = record
    out: dict[str, Any] = {}
    for strategy in sorted({k[0] for k in by}, key=list(runner.all_strategies()).index):
        stats = {kind: {"n": 0, "abstained": 0, "scored_zero": 0, "scored_positive": 0, "drop": [],
                        "requirements_unclear": 0, "requirements_missing": 0} for kind in ("misread", "missing")}
        for source in sorted({k[1] for k in by if k[0] == strategy}):
            orig = by.get((strategy, source, "orig"))
            if orig is None:
                continue
            affected = next(r["affected"] for r in rows if r["source_pair"] == source)
            for kind in ("misread", "missing"):
                record = by.get((strategy, source, kind))
                if record is None:
                    continue
                s = stats[kind]
                s["n"] += 1
                score = record["criteria"][affected]["score"]
                s["abstained" if score is None else "scored_zero" if score == 0 else "scored_positive"] += 1
                s["drop"].append(orig["total_score"] - record["total_score"])
                before = {k: v["status"] for k, v in (orig.get("requirements") or {}).items()}
                for req_id, value in (record.get("requirements") or {}).items():
                    if before.get(req_id) in ("met", "mentioned_only") and value["status"] != before[req_id]:
                        s["requirements_unclear" if value["status"] == "unclear" else "requirements_missing"] += 1
        for s in stats.values():
            s["mean_drop"] = iaa._mean(s.pop("drop"))
        out[strategy] = stats
    return out


def markdown(summary: dict[str, Any], run_id: str) -> str:
    f = iaa._f
    lines = [f"# Phép thử H3 · {run_id}", "",
             "Mỗi CV có ba đầu vào: gốc, \"đọc lỗi\" (trích xuất mất một mục, PDF còn nguyên chữ) và \"thiếu thật\" "
             "(CV không có mục đó, PDF ít chữ tương ứng). Hai biến thể sau gửi cùng một CV cho LLM; chỉ phân tích PDF khác nhau.",
             "Kỳ vọng: tiêu chí bị ảnh hưởng (C4 khi mất mục dự án, C5 khi mất mục kinh nghiệm) được đánh dấu cần xác minh "
             "khi đọc lỗi, và bị chấm 0 khi thiếu thật.", "",
             "| Chiến lược | Biến thể | n | Cần xác minh | Chấm 0 | Chấm > 0 | Điểm tổng giảm (TB) | Yêu cầu met → unclear | Yêu cầu met → khác |",
             "|---|---|---|---|---|---|---|---|---|"]
    for strategy, stats in summary.items():
        for kind, label in (("misread", "đọc lỗi"), ("missing", "thiếu thật")):
            s = stats[kind]
            lines.append(f"| {strategy} | {label} | {s['n']} | {s['abstained']} | {s['scored_zero']} | {s['scored_positive']} | "
                         f"{f(s['mean_drop'], 1)} | {s['requirements_unclear']} | {s['requirements_missing']} |")
    lines += ["", "Điểm tổng giảm = điểm của đầu vào gốc trừ điểm của biến thể. Với P đó là Q trên các tiêu chí chấm được.",
              "Sai lệch H3 = chênh lệch giữa mức giảm khi đọc lỗi và mức giảm khi thiếu thật; chiến lược không thể "
              "từ chối chấm cho hai mức giảm gần như nhau."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="H3 perturbation test: misread versus truly missing sections.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    r = sub.add_parser("run")
    r.add_argument("--run-id", required=True)
    r.add_argument("--strategies", nargs="+", default=["baseline_rules", "m3_rag", "p_grounded", "p_no_abstain"])
    r.add_argument("--retriever", choices=("bm25", "bge-m3"), default="bm25")
    r.add_argument("--embed-url", default=os.getenv("EMBED_SERVER_URL", "http://127.0.0.1:8093"))
    r.add_argument("--min-interval", type=float, default=2.5)
    r.add_argument("--max-calls", type=int)
    r.add_argument("--max-wait", type=float, default=90.0,
                   help="longest rate-limit wait in seconds; a longer one (daily quota) stops the run")
    p = sub.add_parser("report")
    p.add_argument("--run-id", required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if args.command == "build":
        manifest = build()
        print(f"{manifest['pairs']} CV x 3 variants -> {OUT} (removed: {manifest['removed']})")
        return 0
    run_dir = runner.RESULTS / args.run_id
    rows = load_rows()
    if args.command == "report":
        summary = summarize(runner._read_jsonl(run_dir / "predictions.jsonl"), rows)
        text = markdown(summary, args.run_id)
        (run_dir / "H3_REPORT.md").write_text(text, encoding="utf-8")
        (run_dir / "h3_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(text)
        return 0
    rubric_scoring, _ = runner._web()
    model = os.getenv("GROQ_MODEL") or rubric_scoring.GROQ_MODEL
    key = os.getenv("GROQ_API_KEY", "").strip()
    call = runner.throttled(rubric_scoring.groq_caller(key, model=model, max_attempts=6, max_wait=args.max_wait),
                            args.min_interval) if key else None
    retrieve = runner.bge_m3_retriever(args.embed_url) if args.retriever == "bge-m3" else runner.bm25_retriever(rubric_scoring)
    config = runner.conditions(model=model, retriever=args.retriever, split="h3", inputs_root=OUT, pairs_path=OUT / "pairs.csv")
    load = lambda source, vid: json.loads((OUT / "variants" / f"{vid}.json").read_text(encoding="utf-8"))  # noqa: E731
    document = lambda vid: json.loads((OUT / "documents" / f"{vid}.json").read_text(encoding="utf-8"))  # noqa: E731
    try:
        counts = runner.run(run_dir=run_dir, pairs=rows, strategies=args.strategies, inputs=["gold"], repeats=1,
                            config=config, call=call, retrieve=retrieve, load_cv=load, load_document=document,
                            max_calls=args.max_calls)
    except runner.QuotaExhausted as exc:
        print(f"Dừng: {exc} Kết quả đã lưu; chạy lại cùng lệnh sau để tiếp tục.")
        return 2
    print(f"{run_dir}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
