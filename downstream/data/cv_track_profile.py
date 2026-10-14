"""Which job track do the real CVs aim at? Sets the backend/frontend mix of the JD set (module A).

Each unique real CV gets a track from two signals:
1. the role it states (objective, title or summary near the top), e.g. "Backend Developer",
   "lập trình viên front-end", "Data Analyst";
2. otherwise, weighted technology keywords across the whole CV.

GOLD40 CVs are also classified from their human-checked CVSchema, as a check on the raw-text
classifier. Only aggregate counts are printed; per-CV labels go to a gitignored results file.

    python -m downstream.data.cv_track_profile
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REAL80 = ROOT / "experiments/baseline80/real_cv_pointer_inputs_v1/all_80_pointer_inputs.jsonl"
GOLD_DIR = ROOT / "annotation/gold_v2"
OUT = ROOT / "downstream/results/cv_tracks_v1.json"

TRACKS = ("backend", "frontend", "fullstack", "mobile", "data_ai", "qa_test", "ba_other")

# Stated roles, matched on accent-folded lowercase text near the top of the CV.
ROLE_PATTERNS = {
    "fullstack": [r"full[\s-]?stack"],
    "backend": [r"back[\s-]?end (developer|engineer|dev|intern)", r"(lap trinh vien|thuc tap sinh|developer|intern) back[\s-]?end",
                r"\b(java|\.net|php|node\.?js|python) (developer|backend|intern)"],
    "frontend": [r"front[\s-]?end (developer|engineer|dev|intern)", r"(lap trinh vien|thuc tap sinh|developer|intern) front[\s-]?end",
                 r"\b(react|reactjs|vue|angular|web ui) (developer|intern)", r"ui/ux (developer|designer)"],
    "mobile": [r"(mobile|android|ios|flutter) (developer|engineer|intern)", r"lap trinh (vien )?(di dong|mobile|android|ios)"],
    "data_ai": [r"data (analyst|engineer|scientist)", r"(ai|machine learning|ml) (engineer|intern|developer)",
                r"phan tich du lieu", r"ky su (ai|du lieu)"],
    "qa_test": [r"\b(tester|qa|qc)\b", r"(software )?test(ing)? (engineer|intern)", r"kiem thu"],
    "ba_other": [r"business analyst", r"phan tich nghiep vu", r"(network|system) (engineer|administrator)", r"quan tri mang"],
}

# Technology evidence: keyword -> weight. JavaScript/TypeScript/Git/SQL are shared, so they are left out.
KEYWORDS = {
    "backend": {"java": 1, "spring": 2, "spring boot": 1, ".net": 2, "asp.net": 1, "c#": 1, "node.js": 2, "nodejs": 2,
                "express": 1, "nestjs": 2, "django": 2, "flask": 2, "fastapi": 2, "laravel": 2, "php": 2,
                "ruby on rails": 2, "golang": 2, "rest api": 1, "restful": 1, "microservice": 2, "hibernate": 1,
                "jpa": 1, "entity framework": 1, "mysql": 1, "postgresql": 1, "sql server": 1, "mongodb": 1,
                "redis": 1, "kafka": 1, "rabbitmq": 1, "backend": 2, "back-end": 2, "back end": 2},
    "frontend": {"react": 2, "reactjs": 2, "next.js": 2, "nextjs": 2, "vue": 2, "nuxt": 2, "angular": 2, "html": 1,
                 "css": 1, "scss": 1, "sass": 1, "tailwind": 2, "bootstrap": 1, "jquery": 1, "redux": 2, "figma": 1,
                 "responsive": 1, "frontend": 2, "front-end": 2, "front end": 2, "ui/ux": 1},
    "mobile": {"flutter": 3, "dart": 2, "kotlin": 2, "swift": 2, "android": 2, "ios": 2, "react native": 3, "xamarin": 2},
    "data_ai": {"machine learning": 2, "deep learning": 2, "pytorch": 2, "tensorflow": 2, "pandas": 1, "numpy": 1,
                "scikit-learn": 2, "power bi": 2, "tableau": 2, "data analysis": 2, "nlp": 2, "computer vision": 2,
                "opencv": 2, "yolo": 2, "llm": 1},
    "qa_test": {"selenium": 2, "test case": 2, "testcase": 2, "manual test": 2, "automation test": 2, "jira": 1,
                "postman": 1, "kiem thu": 2, "tester": 2},
    "ba_other": {"business analyst": 3, "use case": 1, "bpmn": 2, "ccna": 2, "cisco": 1},
}


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    return "".join(c for c in text if not unicodedata.combining(c))


def keyword_scores(text: str) -> dict[str, int]:
    folded = fold(text)
    scores = {}
    for track, words in KEYWORDS.items():
        total = 0
        for word, weight in words.items():
            pattern = r"(?<![\w.#+])" + re.escape(fold(word)) + r"(?![\w#+])"
            total += weight * min(3, len(re.findall(pattern, folded)))  # cap repeats of one keyword
        scores[track] = total
    return scores


def stated_role(text: str, head_lines: int = 25) -> str | None:
    head = fold("\n".join(text.splitlines()[:head_lines]))
    found = [track for track, patterns in ROLE_PATTERNS.items() if any(re.search(p, head) for p in patterns)]
    if "fullstack" in found or {"backend", "frontend"} <= set(found):
        return "fullstack"
    return found[0] if len(found) == 1 else None


def from_keywords(scores: dict[str, int]) -> str:
    ranked = sorted(scores.items(), key=lambda item: -item[1])
    (top, first), (_, second) = ranked[0], ranked[1]
    if first < 4:
        return "ba_other"
    back, front = scores["backend"], scores["frontend"]
    if {top, ranked[1][0]} == {"backend", "frontend"} and min(back, front) >= 0.6 * max(back, front):
        return "fullstack"
    return top


def classify(text: str) -> dict:
    scores = keyword_scores(text)
    role = stated_role(text)
    return {"track": role or from_keywords(scores), "basis": "stated_role" if role else "keywords",
            "keyword_track": from_keywords(scores), "scores": scores}


def gold_text(cv: dict) -> str:
    """CVSchema fields that say what the candidate does, without contact details."""
    parts = [cv.get("summary", "")]
    skills = cv.get("skills") or {}
    parts += skills.get("hard_skills", [])
    for item in cv.get("experience", []):
        parts += [item.get("job_title", ""), item.get("description", "")]
    for item in cv.get("projects", []):
        parts += [item.get("name", ""), item.get("role", ""), item.get("details", ""), " ".join(item.get("technologies", []))]
    return "\n".join(str(p) for p in parts if p)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    rows = [json.loads(line) for line in REAL80.read_text(encoding="utf-8").splitlines() if line.strip()]
    unique = [r for r in rows if r["is_primary"] and not r["is_duplicate"]]
    gold_ids = {p.stem for p in GOLD_DIR.glob("*.json") if not p.stem.endswith(".status") and not p.stem.startswith("_")}

    per_cv = {}
    for row in unique:
        result = classify(row["source_text"])
        result.update(language=row["language"], in_gold40=row["sample_id"] in gold_ids)
        per_cv[row["sample_id"]] = result
    agreement = Counter()
    for cv_id in sorted(gold_ids & set(per_cv)):
        gold = json.loads((GOLD_DIR / f"{cv_id}.json").read_text(encoding="utf-8"))
        gold_track = classify(gold_text(gold))["keyword_track"]
        per_cv[cv_id]["gold_keyword_track"] = gold_track
        agreement[gold_track == per_cv[cv_id]["keyword_track"]] += 1

    def table(ids):
        return dict(Counter(per_cv[i]["track"] for i in ids).most_common())

    all_ids = sorted(per_cv)
    gold_list = [i for i in all_ids if per_cv[i]["in_gold40"]]
    summary = {
        "unique_cvs": len(all_ids),
        "all": table(all_ids),
        "by_language": {lang: table([i for i in all_ids if per_cv[i]["language"] == lang]) for lang in ("en", "vi")},
        "gold40": table(gold_list),
        "gold40_by_language": {lang: table([i for i in gold_list if per_cv[i]["language"] == lang]) for lang in ("en", "vi")},
        "basis": dict(Counter(per_cv[i]["basis"] for i in all_ids)),
        "stated_vs_keyword_agree": sum(1 for i in all_ids if per_cv[i]["basis"] == "stated_role"
                                       and per_cv[i]["track"] == per_cv[i]["keyword_track"]),
        "gold40_rawtext_vs_goldschema_keyword_agree": f"{agreement[True]}/{sum(agreement.values())}",
        "mean_scores_by_track": {
            t: {k: round(sum(per_cv[i]["scores"][k] for i in all_ids if per_cv[i]["track"] == t)
                         / max(1, sum(1 for i in all_ids if per_cv[i]["track"] == t)), 1) for k in KEYWORDS}
            for t in TRACKS if any(per_cv[i]["track"] == t for i in all_ids)},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "per_cv": per_cv}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
