"""Propose the CV–JD pairs for human rating (module A, step 2).

Design, fixed in reports/PROJECT_SCOPE_AND_DECISIONS.md §8:
- 24 GOLD40 CVs whose track is backend, fullstack, frontend or mobile (data/AI, QA and BA CVs
  are out of scope). GOLD40 has gold CVSchema, so scoring can run on gold and on extracted input.
- Each CV gets two JDs: one in its own track and one in the other track, so fit scores spread
  from low to high. Fullstack CVs get one backend and one frontend JD. Mobile CVs count as backend.
- The same-track JD is the one whose requirements best overlap the CV's skills, so same-track
  pairs are realistic; long JDs (> 15 requirements) are used fewer times.
- Split by CV: 8 CVs (16 pairs) dev, 16 CVs (32 pairs) test, stratified by track and language.

Deterministic for a given seed. Writes pairs.csv (ids only) and a summary; the team reviews it
before building the rater workbooks.

    python -m downstream.data.make_pairs
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from downstream.data import jd_catalog
from downstream.data.cv_track_profile import GOLD_DIR, REAL80, TRACKS, classify, fold

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "downstream/data/pairs_v1"
OVERRIDES = OUT_DIR / "cv_track_overrides.csv"
OVERRIDE_COLUMNS = ["cv_id", "track", "ly_do"]
IN_SCOPE = {"backend": "backend", "mobile": "backend", "frontend": "frontend", "fullstack": "fullstack"}
CV_COUNT, DEV_CV_COUNT = 24, 8
MIN_USE = 2  # pairs per JD at least


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def jd_capacity(requirement_count: int) -> int:
    """How many pairs one JD may join: long JDs cost raters more time per pair."""
    return 2 if requirement_count > 20 else 5 if requirement_count > 15 else 7


def cv_terms(cv: dict) -> set[str]:
    skills = cv.get("skills") or {}
    values = list(skills.get("hard_skills", []))
    for project in cv.get("projects", []):
        values += project.get("technologies", [])
    return {fold(v).strip() for v in values if len(str(v).strip()) >= 2}


def overlap(terms: set[str], requirements: list[str]) -> int:
    """Number of JD requirements that mention one of the CV's skill names as a whole word."""
    hits = 0
    for requirement in requirements:
        text = fold(requirement)
        if any(re.search(r"(?<![\w.#+])" + re.escape(term) + r"(?![\w#+])", text) for term in terms):
            hits += 1
    return hits


def read_overrides(path: Path, known_cvs: set[str]) -> dict[str, dict[str, str]]:
    """Track labels checked by a person on the PDF; they replace the heuristic label.

    Accepts what Excel writes back (BOM, ';' separator). Every row needs a known cv_id, a valid
    track and a reason; a CV may appear once.
    """
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"{path.name}: không phải UTF-8; trong Excel chọn Save As → 'CSV UTF-8'") from None
    header = text.splitlines()[0] if text.strip() else ""
    reader = csv.DictReader(text.splitlines(), delimiter=";" if header.count(";") > header.count(",") else ",")
    if reader.fieldnames != OVERRIDE_COLUMNS:
        raise ValueError(f"{path.name}: cột phải là {OVERRIDE_COLUMNS}, đang có {reader.fieldnames}")
    overrides, errors = {}, []
    for line, row in enumerate(reader, 2):
        row = {k: (v or "").strip() for k, v in row.items()}
        if not any(row.values()):
            continue
        cv, track = row["cv_id"].upper(), row["track"].lower()
        if cv not in known_cvs:
            errors.append(f"dòng {line}: '{row['cv_id']}' không phải CV GOLD40")
        elif cv in overrides:
            errors.append(f"dòng {line}: {cv} xuất hiện hơn một lần")
        if track not in TRACKS:
            errors.append(f"dòng {line}: track '{row['track']}' phải thuộc {list(TRACKS)}")
        if not row["ly_do"]:
            errors.append(f"dòng {line}: cần ghi ly_do")
        overrides[cv] = {"track": track, "ly_do": row["ly_do"]}
    if errors:
        raise ValueError(f"{path.name}: " + "; ".join(errors))
    return overrides


def select_cvs(tracks: dict[str, dict], seed: int) -> list[str]:
    """In-scope GOLD40 CVs; if more than CV_COUNT, drop from the largest (track, language) groups."""
    pool = sorted(cv for cv, t in tracks.items() if t["track"] in IN_SCOPE)
    rng = random.Random(seed)
    while len(pool) > CV_COUNT:
        groups = Counter((tracks[c]["track"], tracks[c]["language"]) for c in pool)
        # Prefer dropping mobile (its JDs are borrowed from backend), then the largest group.
        key = max(groups, key=lambda g: (g[0] == "mobile", groups[g], g))
        candidates = sorted(c for c in pool if (tracks[c]["track"], tracks[c]["language"]) == key)
        pool.remove(rng.choice(candidates))
    return pool


def split_dev(cvs: list[str], tracks: dict[str, dict], seed: int) -> set[str]:
    """Largest-remainder allocation of DEV_CV_COUNT across tracks, alternating languages inside a track."""
    by_track = defaultdict(list)
    for cv in cvs:
        by_track[tracks[cv]["track"]].append(cv)
    share = {t: len(v) * DEV_CV_COUNT / len(cvs) for t, v in by_track.items()}
    quota = {t: int(s) for t, s in share.items()}
    for t in sorted(share, key=lambda t: (-(share[t] - quota[t]), -len(by_track[t]), t))[: DEV_CV_COUNT - sum(quota.values())]:
        quota[t] += 1
    dev = set()
    for track, members in by_track.items():
        order = sorted(members, key=lambda c: sha256_text(f"{seed}:{c}"))
        en = [c for c in order if tracks[c]["language"] == "en"]
        vi = [c for c in order if tracks[c]["language"] == "vi"]
        interleaved = [c for pair in zip(en, vi) for c in pair] + en[len(vi):] + vi[len(en):]
        dev.update(interleaved[: quota[track]])
    return dev


def assign(cvs: list[str], tracks: dict, terms: dict, jds: dict, seed: int) -> list[dict]:
    rng = random.Random(seed)
    load = Counter()
    capacity = {j: jd_capacity(len(d["must"]) + len(d["nice"])) for j, d in jds.items()}
    by_role = defaultdict(list)
    for jd_id, jd in jds.items():
        by_role[jd["role"]].append(jd_id)

    def pick(cv: str, role: str, best_fit: bool) -> str:
        options = [j for j in by_role[role] if load[j] < capacity[j]]
        if not options:
            raise RuntimeError(f"no {role} JD left with capacity for {cv}")
        if best_fit:
            # Share of must-haves the CV mentions (a raw count would favour long JDs). Any JD within
            # 60% of the best share is good enough; among those take the least-used, then random.
            score = {j: overlap(terms[cv], jds[j]["must"]) / len(jds[j]["must"]) for j in options}
            top = max(score.values())
            options = [j for j in options if score[j] >= 0.6 * top]
        least = min(load[j] for j in options)
        chosen = rng.choice(sorted(j for j in options if load[j] == least))
        load[chosen] += 1
        return chosen

    pairs = []
    # Fullstack and frontend CVs first: frontend JDs are the scarce ones.
    order = sorted(cvs, key=lambda c: ({"frontend": 0, "fullstack": 1}.get(tracks[c]["track"], 2), sha256_text(f"{seed}:{c}")))
    for cv in order:
        track = IN_SCOPE[tracks[cv]["track"]]
        if track == "fullstack":
            plan = [("backend", True, "same_track"), ("frontend", True, "same_track")]
        else:
            other = "frontend" if track == "backend" else "backend"
            plan = [(track, True, "same_track"), (other, False, "other_track")]
        for role, best_fit, fit in plan:
            pairs.append({"cv_id": cv, "jd_id": pick(cv, role, best_fit), "intended_fit": fit})

    # Every JD must be rated a few times. Move same-track pairs from the busiest JD of the same
    # role to an under-used one, taking the CV that fits the under-used JD best.
    share = lambda cv, j: overlap(terms[cv], jds[j]["must"]) / len(jds[j]["must"])
    for target in sorted(jds):
        while load[target] < MIN_USE:
            role = jds[target]["role"]
            donors = [p for p in pairs if p["intended_fit"] == "same_track" and jds[p["jd_id"]]["role"] == role
                      and load[p["jd_id"]] > MIN_USE and not any(q["cv_id"] == p["cv_id"] and q["jd_id"] == target for q in pairs)]
            if not donors:
                break
            moved = max(donors, key=lambda p: (share(p["cv_id"], target), load[p["jd_id"]], p["cv_id"]))
            load[moved["jd_id"]] -= 1
            moved["jd_id"] = target
            load[target] += 1
    return pairs


def build(seed: int = 20261014, out_dir: Path = OUT_DIR, overrides_path: Path = OVERRIDES) -> dict:
    rows = {json.loads(l)["sample_id"]: json.loads(l) for l in REAL80.read_text(encoding="utf-8").splitlines() if l.strip()}
    gold_ids = sorted(p.stem for p in GOLD_DIR.glob("*.json") if re.fullmatch(r"(EN|VI)\d{3}", p.stem))
    tracks, terms = {}, {}
    for cv in gold_ids:
        result = classify(rows[cv]["source_text"])
        tracks[cv] = {"track": result["track"], "language": rows[cv]["language"], "heuristic": result["track"],
                      "basis": result["basis"], "source": "heuristic"}
        terms[cv] = cv_terms(json.loads((GOLD_DIR / f"{cv}.json").read_text(encoding="utf-8")))
    overrides = read_overrides(overrides_path, set(gold_ids))
    for cv, row in overrides.items():
        tracks[cv].update(track=row["track"], source="override")

    manifest = {r["jd_id"]: r for r in jd_catalog.read_manifest(jd_catalog.JD_DIR / "jd_manifest.csv")}
    jds = {}
    for jd_id, row in manifest.items():
        gold = json.loads((jd_catalog.GOLD_DIR / f"{jd_id}.json").read_text(encoding="utf-8"))["requirements"]
        jds[jd_id] = {"role": row["role"], "language": row["language"], "must": gold["must_have"], "nice": gold["nice_to_have"]}

    cvs = select_cvs(tracks, seed)
    dev = split_dev(cvs, tracks, seed)
    pairs = assign(cvs, tracks, terms, jds, seed)
    pairs.sort(key=lambda p: (p["cv_id"] not in dev, p["cv_id"], p["intended_fit"] != "same_track", p["jd_id"]))
    for i, pair in enumerate(pairs, 1):
        pair.update(pair_id=f"P{i:03d}", split="dev" if pair["cv_id"] in dev else "test",
                    cv_track=tracks[pair["cv_id"]]["track"], cv_track_source=tracks[pair["cv_id"]]["source"],
                    cv_language=tracks[pair["cv_id"]]["language"],
                    jd_role=jds[pair["jd_id"]]["role"],
                    skill_overlap=overlap(terms[pair["cv_id"]], jds[pair["jd_id"]]["must"] + jds[pair["jd_id"]]["nice"]))

    out_dir.mkdir(parents=True, exist_ok=True)
    columns = ["pair_id", "cv_id", "jd_id", "split", "intended_fit", "cv_track", "cv_track_source", "cv_language", "jd_role",
               "skill_overlap"]
    with (out_dir / "pairs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")  # same bytes after git checkout
        writer.writeheader()
        writer.writerows({c: p[c] for c in columns} for p in pairs)

    write_review(out_dir / "cv_track_review.csv", gold_ids, tracks, set(cvs), dev, overrides)

    jd_load = Counter(p["jd_id"] for p in pairs)
    summary = {
        "version": "pairs_v1", "seed": seed,
        "inputs_sha256": {"jd_manifest": sha256_text((jd_catalog.JD_DIR / "jd_manifest.csv").read_text(encoding="utf-8").replace("\r\n", "\n")),
                          "pairs_csv": sha256_text((out_dir / "pairs.csv").read_text(encoding="utf-8"))},
        "cv_count": len(cvs), "pair_count": len(pairs),
        "track_overrides": {cv: f"{tracks[cv]['heuristic']} -> {row['track']}" for cv, row in sorted(overrides.items())},
        "split": dict(Counter(p["split"] for p in pairs)),
        "cvs_by_track_language": {f"{t}/{l}": n for (t, l), n in sorted(Counter((tracks[c]["track"], tracks[c]["language"]) for c in cvs).items())},
        "dev_cvs_by_track": dict(Counter(tracks[c]["track"] for c in dev)),
        "excluded_in_scope_cvs": sorted(set(c for c, t in tracks.items() if t["track"] in IN_SCOPE) - set(cvs)),
        "pairs_by_fit": dict(Counter(p["intended_fit"] for p in pairs)),
        "jd_load": {j: f"{jd_load[j]}/{jd_capacity(len(d['must']) + len(d['nice']))}" for j, d in sorted(jds.items())},
        "same_track_overlap_mean": round(sum(p["skill_overlap"] for p in pairs if p["intended_fit"] == "same_track")
                                         / max(1, sum(p["intended_fit"] == "same_track" for p in pairs)), 2),
        "other_track_overlap_mean": round(sum(p["skill_overlap"] for p in pairs if p["intended_fit"] == "other_track")
                                          / max(1, sum(p["intended_fit"] == "other_track" for p in pairs)), 2),
        "notes": [
            "CV tracks come from the heuristic in downstream/data/cv_track_profile.py; review them on the PDFs before rating.",
            "intended_fit, cv_track, split and skill_overlap are design data: build_rating_workbook does not show them to raters.",
        ],
    }
    (out_dir / "PAIRS_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return summary


def write_review(path: Path, gold_ids: list[str], tracks: dict, selected: set[str], dev: set[str], overrides: dict) -> None:
    """Checklist of all GOLD40 CVs for the PDF review, readable in Excel (UTF-8 with BOM).

    Fill a disagreement into cv_track_overrides.csv, not here: this file is rewritten on every run.
    """
    columns = ["cv_id", "ngon_ngu", "track_heuristic", "can_cu", "track_dang_dung", "nguon", "duoc_chon", "split",
               "ly_do_ghi_de"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for cv in gold_ids:
            t = tracks[cv]
            writer.writerow([cv, t["language"], t["heuristic"],
                             "vai trò ghi trong CV" if t["basis"] == "stated_role" else "đếm từ khóa",
                             t["track"], t["source"], "có" if cv in selected else "không",
                             ("dev" if cv in dev else "test") if cv in selected else "",
                             overrides.get(cv, {}).get("ly_do", "")])


def main() -> None:
    parser = argparse.ArgumentParser(description="Propose CV–JD pairs for human rating.")
    parser.add_argument("--seed", type=int, default=20261014)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        summary = build(args.seed)
    except ValueError as error:
        print(f"LỖI  {error}")
        raise SystemExit(1)
    except PermissionError as error:
        print(f"LỖI  không ghi được {Path(error.filename).name}: tệp đang mở trong Excel; đóng tệp rồi chạy lại")
        raise SystemExit(1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
