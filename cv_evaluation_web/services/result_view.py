"""What the result page shows on top of a rubric v2 result.

Display only: nothing here changes a score a scorer produced. From the result it derives two scores
(CV quality from C1–C7, JD fit from C8 and the requirement table), a to-do list ranked by the points each
fix could add to the total, the criteria the scorer could not decide, and requirements that do not move
the score. From the extracted CV it counts a few things a reader can check at a glance.
"""

from __future__ import annotations

import re
from typing import Any

from services import rubric_scoring as rs
from services.evaluator import _fold
from services.rule_rubric import NUMBER, _evidence_text

CV_QUALITY = ("C1_structure", "C2_it_content", "C3_skills", "C4_projects", "C5_experience",
              "C6_certs_activities", "C7_ats")
JD_FIT = "C8_jd_fit"
# A reader may mark these as not applying to them (no work experience yet, no certificates, an employer
# that reads CVs by hand). The core of an IT CV (structure, content, skills, projects) and the JD fit always apply.
MAY_NOT_APPLY = ("C5_experience", "C6_certs_activities", "C7_ats")
# Same bands as every scorer's verdict.
VERDICTS = ((80, "Tốt"), (65, "Khá"), (50, "Trung bình"), (0, "Cần cải thiện"))
GOOD_ENOUGH = "Khá"
SEVERITY = ((5.0, "important", "Quan trọng"), (1.0, "should", "Nên sửa"), (0.0, "minor", "Gợi ý nhỏ"))


def verdict(score: float) -> str:
    return next(label for floor, label in VERDICTS if score >= floor)


def _weighted_share(criteria: list[dict[str, Any]], ids: tuple[str, ...]) -> float | None:
    usable = [c for c in criteria if c["id"] in ids and c.get("score") is not None]
    weight = sum(float(c["weight"]) for c in usable)
    if not weight:
        return None
    return round(100 * sum(float(c["weight"]) * c["score"] for c in usable) / (4 * weight), 1)


def _severity(gain: float) -> tuple[str, str]:
    return next((key, label) for floor, key, label in SEVERITY if gain >= floor)


def build(result: dict[str, Any]) -> dict[str, Any]:
    criteria = result.get("criteria") or []
    scored = [c for c in criteria if c.get("score") is not None]
    weight_scored = sum(float(c["weight"]) for c in scored)

    todos = []
    for c in scored:
        if c["score"] >= 4:
            continue
        gain = 100 * float(c["weight"]) * (4 - c["score"]) / (4 * weight_scored)
        key, label = _severity(gain)
        todos.append({"id": c["id"], "name": c["name"], "score": c["score"], "gain": round(gain, 1),
                      "severity": key, "severity_label": label, "suggestion": c.get("suggestion") or "",
                      "evidence": c.get("evidence") or "", "missing_in_cv": c.get("status") == "missing_in_cv",
                      "may_not_apply": c["id"] in MAY_NOT_APPLY})
    todos.sort(key=lambda t: -t["gain"])

    requirements = result.get("requirements") or []
    must = [r for r in requirements if r.get("type") == "must"]
    counts = {status: sum(r.get("status") == status for r in must)
              for status in ("met", "mentioned_only", "missing", "unclear")}
    c8 = next((c for c in criteria if c["id"] == JD_FIT), None)
    jd_fit = None if c8 is None or c8.get("score") is None else round(100 * c8["score"] / 4, 1)

    return {
        "cv_quality": _weighted_share(criteria, CV_QUALITY),
        "jd_fit": jd_fit,
        "must_counts": counts if must else None,
        "must_total": len(must),
        "todos": todos,
        "needs_verification": [{"id": c["id"], "name": c["name"], "reason": c.get("evidence") or ""}
                               for c in criteria if c.get("status") == "needs_verification"],
        "nice_missing": [r["text"] for r in requirements if r.get("type") != "must" and r.get("status") == "missing"],
        "unclear": [r["text"] for r in requirements if r.get("status") == "unclear"],
        "good_enough": GOOD_ENOUGH,
        # What the page needs to recompute the total when a reader marks a criterion as not applying.
        "score_data": [{"id": c["id"], "weight": float(c["weight"]), "score": c["score"]} for c in scored],
        "verdicts": [[floor, label] for floor, label in VERDICTS],
        "total_shown": result.get("total_shown", True),
    }


_BULLET_SPLIT = re.compile(r"[\n•●▪◦]+|(?<=[.;])\s+(?=[A-ZÀ-Ỹ])")


def _bullets(cv: dict[str, Any]) -> list[str]:
    texts = [str(p.get("details") or "") for p in cv.get("projects") or []]
    texts += [str(j.get("description") or "") for j in cv.get("experience") or []]
    lines = [line.strip(" -–*\t") for text in texts for line in _BULLET_SPLIT.split(text)]
    return [line for line in lines if len(line.split()) >= 3]


def cv_counts(cv_schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Counts read from the extracted CV, shown for reference; they add nothing to the score."""
    cv = rs.cv_payload(cv_schema)
    bullets = _bullets(cv)
    hard = [str(s) for s in (cv.get("skills") or {}).get("hard_skills") or [] if str(s).strip()]
    evidence = _fold(_evidence_text(cv))
    projects = cv.get("projects") or []
    out = []
    if bullets:
        out.append({"label": "Dòng mô tả dự án hoặc kinh nghiệm có số liệu", "value": sum(bool(NUMBER.search(b)) for b in bullets),
                    "total": len(bullets)})
    if hard:
        out.append({"label": "Kỹ năng xuất hiện trong dự án hoặc kinh nghiệm", "value": sum(_fold(s) in evidence for s in hard),
                    "total": len(hard)})
    if projects:
        out.append({"label": "Dự án có link sản phẩm hoặc mã nguồn",
                    "value": sum("[LINK]" in str(p) or "http" in str(p) for p in projects), "total": len(projects)})
    return out
