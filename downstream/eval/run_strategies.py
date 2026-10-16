"""Run the scoring strategies on CV–JD pairs under one set of conditions, then compare them with human labels.

Every strategy gets the same pairs, the same CVSchema input (gold, B0 output or P1 output), the same
JD text, rubric v2 and the same PDF facts. The LLM strategies are the web app's own code
(cv_evaluation_web/services/rubric_scoring.py), so what is measured is what the demo runs.

    python -m downstream.eval.cv_inputs                      # once: gold/B0/P1 inputs and PDF facts
    python -m downstream.eval.run_strategies run --run-id dev_v1 --split dev --inputs gold b0 \\
        --strategies baseline_rules m1_zero_shot m2_few_shot m3_rag m4_multi_agent
    python -m downstream.eval.run_strategies report --run-id dev_v1 --labels downstream/data/labels_v1/FINAL.jsonl

`run` needs GROQ_API_KEY in the environment for the LLM strategies. It appends to
downstream/results/<run_id>/predictions.jsonl and skips what is already there, so a run stopped by
the Groq rate limit continues where it stopped. The fixed conditions (model, rubric, knowledge base,
inputs, scorer code, pairs) are hashed into run_config.json; resuming with different conditions is
refused. The results folder quotes CVs and is git-ignored; copy REPORT.md out for the thesis.

After a change to one scorer file, a new run can take over the finished predictions of strategies whose
code did not change (checked by hash), e.g. M1–M4 when only grounded_scoring.py changed:
--reuse-from dev_v1 --reuse-strategies m1_zero_shot m2_few_shot m3_rag m4_multi_agent.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from downstream.eval import cv_inputs, iaa

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "downstream/results"
PAIRS = ROOT / "downstream/data/pairs_v1/pairs.csv"
JD_TEXT = ROOT / "downstream/data/jd_v1"
WEB = ROOT / "cv_evaluation_web"
JD_GOLD = ROOT / "downstream/data/jd_gold_v1"
SCORER_FILES = (WEB / "services/rubric_scoring.py", WEB / "services/rule_rubric.py", WEB / "services/evaluator.py",
                WEB / "services/grounded_scoring.py", WEB / "services/requirement_rules.py")
INPUTS = cv_inputs.SOURCES


def _web():
    """The web app's scorers; its modules import each other as `services.*`."""
    if str(WEB) not in sys.path:
        sys.path.insert(0, str(WEB))
    from services import rubric_scoring
    from services.rule_rubric import score_rules
    return rubric_scoring, score_rules


def _grounded():
    _web()
    from services import grounded_scoring
    return grounded_scoring


def all_strategies() -> dict[str, str]:
    rubric_scoring, _ = _web()
    return {**rubric_scoring.STRATEGIES, **_grounded().STRATEGIES}


def jd_requirements(jd_id: str) -> list[dict[str, str]]:
    """The JD gold's atomic requirements, with the req_ids of the rating workbook."""
    from downstream.data.build_rating_workbook import requirements
    jd = json.loads((JD_GOLD / f"{jd_id}.json").read_text(encoding="utf-8"))
    return [{"req_id": rid, "type": kind, "text": text} for rid, kind, text in requirements(jd_id, jd)]


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def load_pairs(path: Path = PAIRS, split: str | None = None) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [r for r in rows if split in (None, "all", r["split"])]


# ---------- retrieval for M3 ----------

def bm25_retriever(rubric_scoring) -> Callable[..., dict[str, Any]]:
    kb = rubric_scoring.load_kb()

    def retrieve(query: str, top_k: int = 3, roles: list[str] | None = None) -> dict[str, Any]:
        return {"backend": "BM25", "results": rubric_scoring.lexical_retrieve(query, kb, top_k, roles)}
    return retrieve


def bge_m3_retriever(embed_url: str) -> Callable[..., dict[str, Any]]:
    """Same Retriever class as the API host, talking to a local llama-server running bge-m3."""
    spec = importlib.util.spec_from_file_location("klcn_retrieval", ROOT / "deployment/hf_space_api/app/retrieval.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    retriever = module.Retriever(module.LlamaServerEmbedder(embed_url))

    def retrieve(query: str, top_k: int = 3, roles: list[str] | None = None) -> dict[str, Any]:
        return {"backend": "bge-m3", "results": retriever.retrieve(query, top_k, roles)}
    return retrieve


def throttled(call: Callable, min_interval: float, sleep: Callable[[float], None] = time.sleep,
              clock: Callable[[], float] = time.monotonic) -> Callable:
    """Space out LLM calls to stay under the free-tier request rate."""
    last = [-1e9]

    def wrapped(*args, **kwargs):
        wait = min_interval - (clock() - last[0])
        if wait > 0:
            sleep(wait)
        try:
            return call(*args, **kwargs)
        finally:
            last[0] = clock()
    return wrapped


# ---------- run ----------

def conditions(*, model: str, retriever: str, split: str, inputs_root: Path, pairs_path: Path) -> dict[str, Any]:
    """What must stay identical for predictions to be comparable inside one run."""
    rubric_scoring, _ = _web()
    grounded = _grounded()
    return {
        "model": model,
        "p_coverage_min": grounded.COVERAGE_MIN, "p_low_text_ratio": grounded.LOW_TEXT_RATIO,
        "temperature": 0, "seed": 42, "reasoning_effort": "none",
        "retriever": retriever,
        "split": split,
        "rubric_version": rubric_scoring.load_rubric()["rubric_version"],
        "rubric_sha256": _sha_file(rubric_scoring.RUBRIC_PATH),
        "kb_sha256": _sha_file(rubric_scoring.KB_PATH),
        "pairs_sha256": _sha_file(pairs_path),
        "inputs_manifest_sha256": cv_inputs.manifest_sha(inputs_root),
        "scorer_code_sha256": {p.name: _sha_file(p) for p in SCORER_FILES},
    }


def _key(record: dict[str, Any]) -> tuple:
    return record["strategy"], record["input"], record["pair_id"], record["repeat"]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _compact(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_score": result["total_score"], "verdict": result["verdict"],
        "total_shown": result.get("total_shown", True), "coverage": result.get("coverage", 1.0),
        "criteria": {c["id"]: {"status": c.get("status", "scored"), "score": c["score"], "scored_by": c["scored_by"],
                               "initial_score": c.get("initial_score"), "evidence": c["evidence"],
                               "suggestion": c["suggestion"], "evidence_checked": c.get("evidence_checked"),
                               "rescored": c.get("rescored", False)} for c in result["criteria"]},
        "requirements": {r["req_id"]: {"type": r["type"], "status": r["status"], "claimed": r.get("claimed"),
                                       "quote": r.get("quote", ""), "check_note": r.get("check_note", "")}
                         for r in result.get("requirements") or []},
        "verification": result.get("verification"), "content_flags": result.get("content_flags", []),
        "overall_comment": result.get("overall_comment", ""),
        "retrieval": result.get("retrieval"),
        "calls": result.get("calls", 0), "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0), "latency_seconds": result.get("latency_seconds", 0.0),
    }


class QuotaExhausted(RuntimeError):
    pass


def strategy_files(strategy: str) -> tuple[str, ...]:
    """Scorer files whose code decides a strategy's output: M1–M4 live in rubric_scoring.py, with the JD
    requirement rules of their prompts in requirement_rules.py."""
    rubric_scoring, _ = _web()
    if strategy == rubric_scoring.BASELINE:
        return "rubric_scoring.py", "rule_rubric.py", "evaluator.py", "requirement_rules.py"
    if strategy in rubric_scoring.STRATEGIES:
        return "rubric_scoring.py", "requirement_rules.py"
    return tuple(p.name for p in SCORER_FILES)


def reuse_records(run_dir: Path, source_dir: Path, strategies: list[str], conditions_now: dict[str, Any],
                  pair_ids: set[str], inputs: list[str]) -> int:
    """Copy finished predictions of another run whose conditions and strategy code are the same.

    Everything but the scorer hashes must match, and so must the hashes of the files each reused strategy
    runs on; otherwise the copy is refused. Copied records keep their content and gain "reused_from".
    """
    source = json.loads((source_dir / "run_config.json").read_text(encoding="utf-8"))
    then = source["conditions"]
    other = sorted(k for k in set(then) | set(conditions_now)
                   if k != "scorer_code_sha256" and then.get(k) != conditions_now.get(k))
    if other:
        raise SystemExit(f"Cannot reuse {source_dir.name}: conditions differ ({', '.join(other)}).")
    for strategy in strategies:
        changed = [f for f in strategy_files(strategy)
                   if then["scorer_code_sha256"].get(f) != conditions_now["scorer_code_sha256"].get(f)]
        if changed:
            raise SystemExit(f"Cannot reuse {strategy} from {source_dir.name}: {', '.join(changed)} changed since.")
    out = run_dir / "predictions.jsonl"
    have = {_key(r) for r in _read_jsonl(out) if r["status"] in ("ok", "extraction_invalid")}
    previous = latest(_read_jsonl(source_dir / "predictions.jsonl")).values()
    copied = [{**r, "reused_from": source["run_id"]} for r in previous
              if r["strategy"] in strategies and r["input"] in inputs and r["pair_id"] in pair_ids
              and r["status"] in ("ok", "extraction_invalid") and _key(r) not in have]
    with out.open("a", encoding="utf-8") as handle:
        for record in copied:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    config_path = run_dir / "run_config.json"
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    saved.setdefault("reused", []).append({
        "from": source["run_id"], "source_git_commit": source.get("git_commit"), "strategies": sorted(strategies),
        "records": len(copied), "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    config_path.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(copied)


def run(*, run_dir: Path, pairs: list[dict[str, str]], strategies: list[str], inputs: list[str], repeats: int,
        config: dict[str, Any], call: Callable | None, retrieve: Callable | None,
        load_cv: Callable[[str, str], dict | None] = cv_inputs.load,
        load_document: Callable[[str], dict] = cv_inputs.load_document,
        jd_text: Callable[[str], str] = lambda jd: (JD_TEXT / f"{jd}.txt").read_text(encoding="utf-8"),
        requirements: Callable[[str], list[dict[str, str]]] = jd_requirements,
        max_calls: int | None = None, log: Callable[[str], None] = print,
        reuse_from: Path | None = None, reuse_strategies: Iterable[str] = ()) -> dict[str, int]:
    rubric_scoring, score_rules = _web()
    grounded = _grounded()
    from services.rule_rubric import requirement_statuses
    run_dir.mkdir(parents=True, exist_ok=True)
    config_path, out = run_dir / "run_config.json", run_dir / "predictions.jsonl"
    fixed = {k: v for k, v in config.items()}
    if config_path.is_file():
        saved = json.loads(config_path.read_text(encoding="utf-8"))
        if saved["conditions"] != fixed:
            changed = sorted(k for k in set(saved["conditions"]) | set(fixed) if saved["conditions"].get(k) != fixed.get(k))
            raise SystemExit(f"{run_dir.name}: conditions differ from the saved run ({', '.join(changed)}). "
                             "Use a new --run-id.")
        saved["strategies"] = sorted(set(saved["strategies"]) | set(strategies))
        saved["inputs"] = sorted(set(saved["inputs"]) | set(inputs))
        saved["repeats"] = max(saved["repeats"], repeats)
        saved["resumed_at"] = saved.get("resumed_at", []) + [datetime.now(timezone.utc).isoformat(timespec="seconds")]
    else:
        saved = {"run_id": run_dir.name, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "git_commit": _git_commit(), "conditions": fixed, "strategies": sorted(strategies),
                 "inputs": sorted(inputs), "repeats": repeats, "pair_ids": [p["pair_id"] for p in pairs]}
    config_path.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if reuse_from is not None:
        reused = [s for s in reuse_strategies if s in strategies]
        n = reuse_records(run_dir, reuse_from, reused, fixed, {p["pair_id"] for p in pairs}, inputs)
        log(f"Dùng lại {n} kết quả của {reuse_from.name} cho {', '.join(reused)}.")

    done = {_key(r) for r in _read_jsonl(out) if r["status"] in ("ok", "extraction_invalid")}
    counts = {"ok": 0, "skipped": 0, "extraction_invalid": 0, "error": 0}
    calls_used = 0
    rubric = rubric_scoring.load_rubric()
    with out.open("a", encoding="utf-8") as handle:
        for strategy in strategies:
            for source in inputs:
                for pair in pairs:
                    for repeat in range(1, (1 if strategy == rubric_scoring.BASELINE else repeats) + 1):
                        record = {"strategy": strategy, "input": source, "pair_id": pair["pair_id"],
                                  "cv_id": pair["cv_id"], "jd_id": pair["jd_id"], "split": pair["split"], "repeat": repeat}
                        if _key(record) in done:
                            counts["skipped"] += 1
                            continue
                        cv_schema = load_cv(source, pair["cv_id"])
                        record["scored_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                        if cv_schema is None:
                            record.update(status="extraction_invalid")
                        elif strategy == rubric_scoring.BASELINE:
                            result = score_rules(cv_schema=cv_schema, jd_text=jd_text(pair["jd_id"]),
                                                 document=load_document(pair["cv_id"]), rubric=rubric)
                            result["requirements"] = requirement_statuses(cv_schema, requirements(pair["jd_id"]))
                            record.update(status="ok", **_compact(result))
                        else:
                            if call is None:
                                raise SystemExit("GROQ_API_KEY is not set; only baseline_rules can run.")
                            if max_calls is not None and calls_used >= max_calls:
                                log(f"Dừng sau {calls_used} lần gọi (--max-calls). Chạy lại cùng lệnh để tiếp tục.")
                                return counts
                            try:
                                common = dict(cv_schema=cv_schema, jd_text=jd_text(pair["jd_id"]),
                                              document=load_document(pair["cv_id"]), call=call, retrieve=retrieve,
                                              rubric=rubric, model=config["model"])
                                if strategy in grounded.STRATEGIES:
                                    result = grounded.score(strategy, requirements=requirements(pair["jd_id"]), **common)
                                else:
                                    result = rubric_scoring.score(strategy, **common)
                            except rubric_scoring.ScoringError as exc:
                                record.update(status="error", error=str(exc))
                                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                                handle.flush()
                                counts["error"] += 1
                                if "hạn mức" in str(exc) or "quá tải" in str(exc):
                                    raise QuotaExhausted(str(exc)) from exc
                                continue
                            calls_used += result.get("calls", 0)
                            record.update(status="ok", **_compact(result))
                        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                        handle.flush()
                        counts[record["status"]] += 1
                        log(f"{strategy} · {source} · {pair['pair_id']} #{repeat}: {record['status']}"
                            + (f" {record['total_score']}" if record["status"] == "ok" else ""))
    return counts


# ---------- report ----------

def latest(predictions: Iterable[dict[str, Any]]) -> dict[tuple, dict[str, Any]]:
    """Last record per (strategy, input, pair, repeat): a later retry replaces an earlier error."""
    out: dict[tuple, dict[str, Any]] = {}
    for record in predictions:
        out[_key(record)] = record
    return out


def _criterion_pairs(rows: list[tuple[dict, dict]], criterion: str | None = None) -> tuple[list[int], list[int]]:
    """(human, model) scores where the human could score the criterion (scored or missing_in_cv) and
    the model gave a score (P may abstain)."""
    human, model = [], []
    for label, pred in rows:
        for cid, value in label["criteria"].items():
            if criterion not in (None, cid) or value["status"] not in iaa.SCORED or value["score"] is None:
                continue
            if cid in pred["criteria"] and pred["criteria"][cid]["score"] is not None:
                human.append(value["score"])
                model.append(pred["criteria"][cid]["score"])
    return human, model


def abstention(rows: list[tuple[dict, dict]]) -> float | None:
    """Share of the criteria a human could score on which the model abstained."""
    flags = [pred["criteria"].get(cid, {}).get("score") is None
             for label, pred in rows for cid, value in label["criteria"].items() if value["status"] in iaa.SCORED]
    return iaa._mean(flags)


REQ_STATUSES = ["met", "mentioned_only", "missing", "unclear"]


# Requirement kinds: "dictionary" names a skill the dictionary knows, so code can check the quote names it;
# "concept" (Responsive web design, OOP, Teamwork) can only be checked by words.
REQUIREMENT_KINDS = ("dictionary", "concept")


def requirement_kinds(jd_ids: Iterable[str]) -> dict[tuple[str, str], str]:
    _web()
    from services.evaluator import extract_skills
    return {(jd_id, r["req_id"]): "dictionary" if extract_skills(r["text"]) else "concept"
            for jd_id in sorted(set(jd_ids)) if (JD_GOLD / f"{jd_id}.json").is_file() for r in jd_requirements(jd_id)}


def _requirement_stats(human: list[str], model: list[str]) -> dict[str, Any]:
    present = lambda s: "co" if s in ("met", "mentioned_only") else "khong"  # noqa: E731
    return {"n": len(human), "kappa": iaa.kappa(human, model, REQ_STATUSES),
            "agreement": iaa._mean(h == m for h, m in zip(human, model)),
            "kappa_present": iaa.kappa([present(s) for s in human], [present(s) for s in model], ["co", "khong"])}


def requirement_agreement(rows: list[tuple[dict, dict]],
                          kinds: dict[tuple[str, str], str] | None = None) -> dict[str, Any]:
    """Model requirement statuses against the human ones, matched by req_id; per kind when kinds are given."""
    triples = []
    for label, pred in rows:
        for req_id, value in (label.get("requirements") or {}).items():
            got = (pred.get("requirements") or {}).get(req_id)
            if got and value.get("status") in REQ_STATUSES and got["status"] in REQ_STATUSES:
                kind = (kinds or {}).get((pred.get("jd_id") or label.get("jd_id"), req_id))
                triples.append((kind, value["status"], got["status"]))
    out = _requirement_stats([h for _, h, _ in triples], [m for _, _, m in triples])
    if kinds is not None:
        out["by_kind"] = {kind: _requirement_stats([h for k, h, _ in triples if k == kind],
                                                   [m for k, _, m in triples if k == kind])
                          for kind in REQUIREMENT_KINDS}
    return out


def agreement(rows: list[tuple[dict, dict]], weights: dict[str, float]) -> dict[str, float | None]:
    human, model = _criterion_pairs(rows)
    totals = [(iaa._total(label, weights), pred["total_score"]) for label, pred in rows]
    totals = [(h, m) for h, m in totals if h is not None]
    fit = [(label["overall_fit"], pred["total_score"]) for label, pred in rows if label.get("overall_fit")]
    return {
        "qwk": iaa.kappa(human, model, iaa.SCORES, weighted=True),
        "mae": iaa._mean(abs(h - m) for h, m in zip(human, model)),
        "spearman_fit": iaa.spearman([h for h, _ in fit], [m for _, m in fit]),
        "spearman_total": iaa.spearman([h for h, _ in totals], [m for _, m in totals]),
        "mean_abs_total_diff": iaa._mean(abs(h - m) for h, m in totals),
        "abstention": abstention(rows),
    }


def _bootstrap(rows_by_group: dict[str, list[tuple[dict, dict]]], weights: dict[str, float], reps: int, seed: int,
               reference: str | None) -> dict[str, dict[str, Any]]:
    """95% intervals per group, and for the difference to the reference group on the same CVs."""
    cvs = sorted({label["cv_id"] for rows in rows_by_group.values() for label, _ in rows})
    if len(cvs) < 2 or reps <= 0:
        return {}
    index = {g: {} for g in rows_by_group}
    for group, rows in rows_by_group.items():
        for row in rows:
            index[group].setdefault(row[0]["cv_id"], []).append(row)
    rng = random.Random(seed)
    samples: dict[str, dict[str, list[float]]] = {}
    for _ in range(reps):
        drawn = [rng.choice(cvs) for _ in cvs]
        stats = {g: agreement([row for cv in drawn for row in index[g].get(cv, [])], weights) for g in rows_by_group}
        for group, values in stats.items():
            for metric, value in values.items():
                if value is not None:
                    samples.setdefault(group, {}).setdefault(metric, []).append(value)
                ref = stats.get(reference) if reference and group != reference else None
                if ref and value is not None and ref[metric] is not None:
                    samples.setdefault(group, {}).setdefault(f"diff_vs_ref.{metric}", []).append(value - ref[metric])
    out: dict[str, dict[str, Any]] = {}
    for group, metrics in samples.items():
        for metric, values in metrics.items():
            values.sort()
            out.setdefault(group, {})[metric] = {"low": values[int(0.025 * (len(values) - 1))],
                                                 "high": values[int(0.975 * (len(values) - 1))], "reps": len(values)}
    return out


def compliance(pred: dict[str, Any], criteria: list[str]) -> bool:
    """All 8 criteria; an integer 0–4, or no score only as needs_verification; evidence for every LLM score above 0."""
    items = pred.get("criteria") or {}
    if set(items) != set(criteria):
        return False
    for value in items.values():
        if value["score"] is None:
            if value.get("status") != "needs_verification":
                return False
            continue
        if not isinstance(value["score"], int) or not 0 <= value["score"] <= 4:
            return False
        if value["scored_by"] in ("llm", "critic", "llm_verified") and value["score"] > 0 and not str(value["evidence"]).strip():
            return False
    return True


def report(run_dir: Path, labels_path: Path, *, reference: str | None = "m3_rag", reps: int = 2000,
           seed: int = 42) -> dict[str, Any]:
    rubric_scoring, _ = _web()
    rubric = rubric_scoring.load_rubric()
    criteria = [c["id"] for c in rubric["criteria"]]
    weights = {c["id"]: float(c["weight"]) for c in rubric["criteria"]}
    labels, label_info = iaa.load(labels_path)
    labels = {r["pair_id"]: r for r in labels}
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    records = latest(_read_jsonl(run_dir / "predictions.jsonl"))

    groups: dict[tuple[str, str], list[dict]] = {}
    for record in records.values():
        groups.setdefault((record["input"], record["strategy"]), []).append(record)
    order = [s for s in all_strategies() if any(k[1] == s for k in groups)]
    kinds = requirement_kinds(r["jd_id"] for r in records.values())
    out: dict[str, Any] = {"run_id": config["run_id"], "labels": label_info["file"], "conditions": config["conditions"],
                           "reference": reference, "bootstrap_reps": reps, "seed": seed, "inputs": {}}
    for source in [i for i in INPUTS if any(k[0] == i for k in groups)]:
        first: dict[str, list[tuple[dict, dict]]] = {}
        table: dict[str, Any] = {}
        for strategy in order:
            recs = groups.get((source, strategy), [])
            if not recs:
                continue
            ok = [r for r in recs if r["status"] == "ok"]
            rows = [(labels[r["pair_id"]], r) for r in ok if r["repeat"] == 1 and r["pair_id"] in labels]
            first[strategy] = rows
            by_pair: dict[str, list[float]] = {}
            for r in ok:
                by_pair.setdefault(r["pair_id"], []).append(r["total_score"])
            spread = [statistics.pstdev(v) for v in by_pair.values() if len(v) > 1]
            table[strategy] = {
                "pairs_scored": len({r["pair_id"] for r in ok}), "pairs_with_labels": len(rows),
                "errors": sum(r["status"] == "error" for r in recs),
                "extraction_invalid": len({r["pair_id"] for r in recs if r["status"] == "extraction_invalid"}),
                **agreement(rows, weights),
                "per_criterion_qwk": {c: iaa.kappa(*_criterion_pairs(rows, c), iaa.SCORES, weighted=True) for c in criteria},
                "per_criterion_mae": {c: iaa._mean(abs(h - m) for h, m in zip(*_criterion_pairs(rows, c))) for c in criteria},
                "mean_total": iaa._mean(r["total_score"] for r in ok),
                "total_shown_rate": iaa._mean(r.get("total_shown", True) for r in ok),
                "requirements": requirement_agreement(rows, kinds),
                "evidence_valid_rate": iaa._mean(
                    r["verification"]["evidence_valid"] / r["verification"]["evidence_total"]
                    for r in ok if r.get("verification") and r["verification"]["evidence_total"]),
                "compliance": iaa._mean(compliance(r, criteria) for r in ok),
                "repeat_std_total": iaa._mean(spread) if spread else None,
                "calls_per_pair": iaa._mean(r["calls"] for r in ok),
                "input_tokens_per_pair": iaa._mean(r["input_tokens"] for r in ok),
                "output_tokens_per_pair": iaa._mean(r["output_tokens"] for r in ok),
                "latency_seconds_per_pair": iaa._mean(r["latency_seconds"] for r in ok),
            }
        ref = reference if reference in first else None
        out["inputs"][source] = {"strategies": table, "bootstrap_95ci": _bootstrap(first, weights, reps, seed, ref),
                                 "reference": ref}
    human_rows = [labels[p] for p in config["pair_ids"] if p in labels]
    out["human_label_pairs"] = len(human_rows)
    (run_dir / "report.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "REPORT.md").write_text(markdown(out, rubric), encoding="utf-8")
    return out


INPUT_NAMES = {"gold": "CVSchema gold (oracle)", "b0": "Trích xuất B0 (Qwen3-4B gốc)", "p1": "Trích xuất P1 (Pointer)"}


def markdown(out: dict[str, Any], rubric: dict) -> str:
    f, pct = iaa._f, iaa._pct
    c = out["conditions"]
    lines = [f"# So sánh chiến lược chấm · {out['run_id']}", "",
             f"- Model `{c['model']}`, nhiệt độ {c['temperature']}, seed {c['seed']}; truy xuất M3: {c['retriever']}; "
             f"rubric `{c['rubric_version']}`; tập `{c['split']}`.",
             f"- Nhãn người: `{out['labels']}` ({out['human_label_pairs']} cặp của run có nhãn). "
             f"Khoảng tin cậy 95%: bootstrap theo CV, {out['bootstrap_reps']} lần.",
             "- Điểm tiêu chí so với các ô người chấm được (scored, missing_in_cv = 0); ô not_applicable và unreadable "
             "không tính. Tuân thủ rubric: đủ 8 tiêu chí, điểm nguyên 0–4, có bằng chứng cho mọi điểm LLM lớn hơn 0.", ""]
    for source, data in out["inputs"].items():
        ci, ref = data["bootstrap_95ci"], data["reference"]
        lines += [f"## Đầu vào: {INPUT_NAMES.get(source, source)}", "",
                  "| Chiến lược | Cặp | Lỗi | Kappa bậc hai | KTC 95% | MAE | Spearman với mức phù hợp | KTC 95% | "
                  "Spearman với tổng của người | Chênh tổng | Tuân thủ | Độ lệch giữa các lần chạy | Gọi/cặp | Token vào/ra | Giây/cặp |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for strategy, v in data["strategies"].items():
            g = ci.get(strategy, {})
            band = lambda m: "–" if m not in g else f"[{g[m]['low']:.2f}; {g[m]['high']:.2f}]"  # noqa: E731
            lines.append(f"| {strategy} | {v['pairs_with_labels']}/{v['pairs_scored']} | {v['errors']} | {f(v['qwk'])} | "
                         f"{band('qwk')} | {f(v['mae'])} | {f(v['spearman_fit'])} | {band('spearman_fit')} | "
                         f"{f(v['spearman_total'])} | {f(v['mean_abs_total_diff'], 1)} | {pct(v['compliance'])} | "
                         f"{f(v['repeat_std_total'], 1)} | {f(v['calls_per_pair'], 1)} | "
                         f"{f(v['input_tokens_per_pair'], 0)}/{f(v['output_tokens_per_pair'], 0)} | "
                         f"{f(v['latency_seconds_per_pair'], 1)} |")
        if ref:
            lines += ["", f"Chênh lệch so với `{ref}` trên cùng CV (KTC 95%; khoảng chứa 0 nghĩa là chưa phân biệt được):", ""]
            for strategy, g in ci.items():
                if strategy == ref:
                    continue
                parts = [f"{m.split('.')[-1]} [{g[m]['low']:+.2f}; {g[m]['high']:+.2f}]"
                         for m in ("diff_vs_ref.qwk", "diff_vs_ref.mae", "diff_vs_ref.spearman_fit") if m in g]
                if parts:
                    lines.append(f"- {strategy}: " + ", ".join(parts))
        lines += ["", "Yêu cầu JD (so với trạng thái người chấm theo req_id), từ chối chấm và bằng chứng:", "",
                  "| Chiến lược | Số yêu cầu | Kappa 4 trạng thái | Trùng | Kappa có/không | Tỉ lệ từ chối chấm | "
                  "Tỉ lệ hiện điểm tổng | Trích dẫn hợp lệ |", "|---|---|---|---|---|---|---|---|"]
        for strategy, v in data["strategies"].items():
            req = v["requirements"]
            lines.append(f"| {strategy} | {req['n']} | {f(req['kappa'])} | {pct(req['agreement'])} | "
                         f"{f(req['kappa_present'])} | {pct(v['abstention'])} | {pct(v['total_shown_rate'])} | "
                         f"{pct(v['evidence_valid_rate'])} |")
        lines += ["", "Yêu cầu JD theo loại: từ điển (code kiểm được trích dẫn có nêu kỹ năng) và khái niệm "
                  "(Responsive, OOP, Teamwork…, code chỉ kiểm được theo từ):", "",
                  "| Chiến lược | Từ điển: số | Kappa 4 trạng thái | Kappa có/không | Khái niệm: số | Kappa 4 trạng thái | "
                  "Kappa có/không |", "|---|---|---|---|---|---|---|"]
        for strategy, v in data["strategies"].items():
            by = v["requirements"].get("by_kind") or {}
            cells = []
            for kind in REQUIREMENT_KINDS:
                k = by.get(kind) or {"n": 0, "kappa": None, "kappa_present": None}
                cells += [str(k["n"]), f(k["kappa"]), f(k["kappa_present"])]
            lines.append(f"| {strategy} | " + " | ".join(cells) + " |")
        lines += ["", "Kappa bậc hai theo tiêu chí:", "",
                  "| Chiến lược | " + " | ".join(cr["id"].split("_")[0] for cr in rubric["criteria"]) + " |",
                  "|---|" + "---|" * len(rubric["criteria"])]
        for strategy, v in data["strategies"].items():
            lines.append(f"| {strategy} | " + " | ".join(f(v["per_criterion_qwk"][cr["id"]]) for cr in rubric["criteria"]) + " |")
        lines.append("")
    return "\n".join(lines) + "\n"


# ---------- CLI ----------

def main() -> int:
    parser = argparse.ArgumentParser(description="Run scoring strategies on CV–JD pairs and compare them with human labels.")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--run-id", required=True)
    r.add_argument("--split", choices=("dev", "test", "all"), default="dev")
    r.add_argument("--strategies", nargs="+", default=["baseline_rules"])
    r.add_argument("--inputs", nargs="+", choices=INPUTS, default=["gold"])
    r.add_argument("--repeats", type=int, default=1, help="runs per LLM strategy and pair, for stability")
    r.add_argument("--pairs", nargs="+", help="only these pair_ids (a smoke test)")
    r.add_argument("--retriever", choices=("bm25", "bge-m3"), default="bm25")
    r.add_argument("--embed-url", default=os.getenv("EMBED_SERVER_URL", "http://127.0.0.1:8093"))
    r.add_argument("--model", default=None)
    r.add_argument("--min-interval", type=float, default=2.5, help="seconds between Groq calls")
    r.add_argument("--max-calls", type=int, help="stop after this many Groq calls; rerun to continue")
    r.add_argument("--max-wait", type=float, default=90.0,
                   help="longest rate-limit wait in seconds; a longer one (daily quota) stops the run")
    r.add_argument("--reuse-from", help="copy finished predictions from this run id when conditions and code match")
    r.add_argument("--reuse-strategies", nargs="+", default=[],
                   help="strategies to copy with --reuse-from (their scorer files must be unchanged)")
    p = sub.add_parser("report")
    p.add_argument("--run-id", required=True)
    p.add_argument("--labels", type=Path, required=True, help="FINAL.jsonl, or a rater workbook/JSONL")
    p.add_argument("--reference", default="m3_rag")
    p.add_argument("--bootstrap", type=int, default=2000)
    p.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    rubric_scoring, _ = _web()
    run_dir = RESULTS / args.run_id

    if args.command == "report":
        out = report(run_dir, args.labels, reference=args.reference, reps=args.bootstrap, seed=args.seed)
        print((run_dir / "REPORT.md").read_text(encoding="utf-8"))
        return 0 if out["human_label_pairs"] else 1

    unknown = [s for s in args.strategies if s not in all_strategies()]
    if unknown:
        parser.error(f"unknown strategies {unknown}; choose from {list(all_strategies())}")
    pairs = load_pairs(split=args.split)
    if args.pairs:
        pairs = [p for p in pairs if p["pair_id"] in set(args.pairs)]
    model = args.model or os.getenv("GROQ_MODEL") or rubric_scoring.GROQ_MODEL
    key = os.getenv("GROQ_API_KEY", "").strip()
    call = throttled(rubric_scoring.groq_caller(key, model=model, max_attempts=6, max_wait=args.max_wait),
                     args.min_interval) if key else None
    retrieve = bge_m3_retriever(args.embed_url) if args.retriever == "bge-m3" else bm25_retriever(rubric_scoring)
    config = conditions(model=model, retriever=args.retriever, split=args.split,
                        inputs_root=cv_inputs.OUT, pairs_path=PAIRS)
    try:
        counts = run(run_dir=run_dir, pairs=pairs, strategies=args.strategies, inputs=args.inputs,
                     repeats=args.repeats, config=config, call=call, retrieve=retrieve, max_calls=args.max_calls,
                     reuse_from=RESULTS / args.reuse_from if args.reuse_from else None,
                     reuse_strategies=args.reuse_strategies)
    except QuotaExhausted as exc:
        print(f"Dừng: {exc} Kết quả đã lưu; chạy lại cùng lệnh sau để tiếp tục.")
        return 2
    print(f"{run_dir}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
