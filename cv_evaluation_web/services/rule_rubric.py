"""Rule-based rubric v2 scorer: the no-LLM baseline (S0) with the same 8 criteria and output as M1–M4.

Every criterion is scored 0–4 from the extracted CVSchema, the JD text and the PDF facts with fixed,
documented rules that follow the anchors of downstream/rubric/rubric_v2.json. The rules are coarse
on purpose: they are a reproducible reference point, not a replacement for a reader.
"""

from __future__ import annotations

import re
from typing import Any

from services import rubric_scoring as rs
from services.evaluator import _fold, _lexical_overlap, extract_skills, skills_with_implied

ROLE_WORDS = ("developer", "engineer", "backend", "back-end", "frontend", "front-end", "fullstack", "full-stack",
              "lap trinh", "ky su", "intern", "thuc tap", "software", "web", "mobile", "data", "tester", "qa")
TEAM_WORDS = ("team", "nhom", "leader", "truong nhom", "collaborat", "phoi hop", "present", "thuyet trinh")
JUNIOR_JD = re.compile(r"(?i)\b(intern|internship|fresher|thực tập|thuc tap|sinh viên|sinh vien|graduate|mới tốt nghiệp)\b")
NUMBER = re.compile(r"\d+\s*(%|\+|người|users?|x\b|k\b|giây|ms|s\b|lần)|\d{2,}")


def _text(value: Any) -> str:
    return " ".join(str(item) for item in value) if isinstance(value, list) else str(value or "")


def _evidence_text(cv: dict[str, Any]) -> str:
    parts = []
    for project in cv.get("projects") or []:
        parts += [_text(project.get("technologies")), str(project.get("details") or ""), str(project.get("role") or "")]
    for job in cv.get("experience") or []:
        parts += [str(job.get("job_title") or ""), str(job.get("description") or "")]
    return "\n".join(parts)


def _item(score: int, evidence: str, suggestion: str) -> dict[str, Any]:
    return {"score": max(0, min(4, score)), "evidence": evidence[:600], "suggestion": suggestion[:600]}


def _project_level(project: dict[str, Any]) -> int:
    details = str(project.get("details") or "").strip()
    has_role, has_tech = bool(str(project.get("role") or "").strip()), bool(project.get("technologies"))
    if not (details or has_role or has_tech):
        return 1 if str(project.get("name") or "").strip() else 0
    if len(details) < 40:
        return 1 if not (has_role or has_tech) else 2
    if not (has_role and has_tech) and len(details) < 80:
        return 2
    level = 3 if has_role or has_tech else 2
    return 4 if level == 3 and (NUMBER.search(details) or "[LINK]" in details) else level


USAGE_SECTIONS = ("experience", "projects", "certifications", "activities", "awards")
LISTING_SECTIONS = ("skills", "summary", "education")
STOPWORDS = {"and", "or", "the", "with", "for", "of", "in", "to", "a", "an", "e.g", "other", "experience", "knowledge",
             "skills", "skill", "basic", "good", "understanding", "va", "hoac", "co", "cac", "kinh", "nghiem", "kien",
             "thuc", "ky", "nang", "biet", "su", "dung", "ve", "voi", "la"}


def _values(node: Any) -> str:
    if isinstance(node, dict):
        return " ".join(_values(v) for v in node.values())
    if isinstance(node, list):
        return " ".join(_values(v) for v in node)
    return "" if node is None else str(node)


def _section_text(cv: dict[str, Any], sections: tuple[str, ...]) -> str:
    """Folded text of those sections' values (field names left out so they cannot match)."""
    return _fold(" \n ".join(_values(cv.get(k)) for k in sections))


def requirement_statuses(cv_schema: dict[str, Any], requirements: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Keyword method (K) for module D: met / mentioned_only / missing / unclear per JD requirement.

    A requirement's terms are its dictionary skills, or else its content words. Found where skills are
    used (projects, experience, certificates) → met; only in skills, summary or education →
    mentioned_only; nowhere → missing; no term to look for → unclear.
    """
    cv = rs.cv_payload(cv_schema)
    usage, listing = _section_text(cv, USAGE_SECTIONS), _section_text(cv, LISTING_SECTIONS)
    out = []
    for req in requirements:
        skills = extract_skills(req["text"])
        if skills:
            def found(text: str) -> bool:
                return bool(set(skills) & skills_with_implied(text))
            in_usage, in_listing = found(usage), found(listing)
        else:
            words = [w for w in re.findall(r"[a-z0-9+#.]{3,}", _fold(req["text"])) if w not in STOPWORDS]
            if not words:
                out.append({**req, "status": "unclear"})
                continue
            need = max(1, (len(words) + 1) // 2)
            in_usage = sum(w in usage for w in words) >= need
            in_listing = sum(w in listing for w in words) >= need
        status = "met" if in_usage else "mentioned_only" if in_listing else "missing"
        out.append({**req, "status": status})
    return out


def score_rules(*, cv_schema: dict[str, Any], jd_text: str, document: dict[str, Any],
                rubric: dict[str, Any] | None = None) -> dict[str, Any]:
    rubric = rubric or rs.load_rubric()
    cv, facts = rs.cv_payload(cv_schema), rs.pdf_facts(document, cv_schema)
    skills = cv.get("skills") or {}
    hard = [str(s) for s in skills.get("hard_skills") or [] if str(s).strip()]
    soft = [str(s) for s in skills.get("soft_skills") or [] if str(s).strip()]
    projects, jobs = cv.get("projects") or [], cv.get("experience") or []
    evidence_text = _evidence_text(cv)
    folded_evidence = _fold(evidence_text)
    sections = set(facts["sections_found"])
    scores: dict[str, dict[str, Any]] = {}

    # C1: core sections and length (layout itself belongs to C7).
    core = [name for name in ("summary", "skills", "education") if name in sections]
    core += ["experience/projects"] if {"experience", "projects"} & sections else []
    pages = facts["page_count"] or 0
    c1 = len(core) if len(core) < 4 else (4 if pages <= 2 else 3)
    scores["C1_structure"] = _item(c1, f"Nhận ra {len(core)}/4 nhóm mục chính ({', '.join(core) or 'không có'}); {pages} trang.",
                                   "" if c1 == 4 else "Dùng đủ các mục Mục tiêu, Kỹ năng, Dự án hoặc Kinh nghiệm, Học vấn và giữ CV trong 1–2 trang.")

    # C2: IT content and a clear direction that the projects back up.
    cv_skills = extract_skills("\n".join([str(cv.get("summary") or ""), _text(hard), evidence_text]))
    summary_role = any(word in _fold(str(cv.get("summary") or "")) for word in ROLE_WORDS)
    used = [skill for skill in cv_skills if skill in extract_skills(evidence_text)]
    c2 = 0 if not cv_skills else 1 if len(cv_skills) < 3 else 2 if not summary_role else 4 if len(used) >= 3 else 3
    scores["C2_it_content"] = _item(c2, f"{len(cv_skills)} công nghệ CNTT nhận diện được; {len(used)} có trong dự án hoặc kinh nghiệm; "
                                        f"mục tiêu {'có' if summary_role else 'chưa'} nêu hướng nghề.",
                                    "" if c2 == 4 else "Nêu rõ vị trí và hướng chuyên môn trong mục tiêu, và cho thấy công nghệ đó trong dự án.")

    # C3: listed skills that are used somewhere, plus soft skills.
    evidenced = [skill for skill in hard if _fold(skill) in folded_evidence]
    share = len(evidenced) / len(hard) if hard else 0
    if not hard:
        c3 = 0
    elif not evidenced:
        c3 = 1
    elif share < 0.5 or not soft:
        c3 = 2
    else:
        c3 = 4 if share >= 0.75 and any(word in folded_evidence for word in TEAM_WORDS) else 3
    scores["C3_skills"] = _item(c3, f"{len(evidenced)}/{len(hard)} kỹ năng chuyên môn có trong dự án hoặc kinh nghiệm; "
                                    f"{len(soft)} kỹ năng bổ trợ.",
                                "" if c3 == 4 else "Cho mỗi kỹ năng chính một minh chứng sử dụng trong dự án; nêu kỹ năng bổ trợ kèm ngữ cảnh.")

    # C4: the best-described project.
    levels = [(_project_level(project), project) for project in projects]
    c4, best = max(levels, key=lambda item: item[0]) if levels else (0, {})
    scores["C4_projects"] = _item(c4, f"{len(projects)} dự án; dự án mô tả tốt nhất: {str(best.get('name') or '')[:80]}." if projects
                                  else "CV chưa có dự án.",
                                  "" if c4 == 4 else "Với 1–2 dự án liên quan nhất, nêu vai trò, công nghệ, việc đã làm và kết quả đo được.")

    # C5: IT experience; for intern/fresher JDs a good project may substitute (max 2).
    it_jobs = [job for job in jobs if extract_skills(f"{job.get('job_title', '')} {job.get('description', '')}")
               or any(word in _fold(str(job.get("job_title") or "")) for word in ROLE_WORDS)]
    if it_jobs:
        detail = max(len(str(job.get("description") or "")) for job in it_jobs)
        quantified = any(NUMBER.search(str(job.get("description") or "")) for job in it_jobs)
        c5 = 2 if detail < 60 else 4 if quantified else 3
        note = f"{len(it_jobs)} kinh nghiệm hoặc thực tập CNTT."
    elif jobs:
        c5, note = 1, "Có kinh nghiệm nhưng không thuộc CNTT."
    elif c4 >= 3 and JUNIOR_JD.search(jd_text):
        c5, note = 2, "Chưa có kinh nghiệm; JD thực tập/fresher nên tính dự án thay thế."
    else:
        c5, note = 0, "CV chưa có kinh nghiệm làm việc hoặc thực tập."
    scores["C5_experience"] = _item(c5, note, "" if c5 == 4 else
                                    "Ghi thời gian, vai trò, công nghệ và việc đã làm cho mỗi kinh nghiệm hoặc thực tập; thêm kết quả nếu có.")

    # C6: certificates, awards and activities.
    extras = [str(item) for key in ("certifications", "awards", "activities") for item in cv.get(key) or [] if str(item).strip()]
    dated = [item for item in extras if re.search(r"(19|20)\d{2}", item)]
    c6 = 0 if not extras else 4 if len(extras) >= 3 and dated else 3 if dated else 2
    scores["C6_certs_activities"] = _item(c6, f"{len(extras)} chứng chỉ, giải thưởng hoặc hoạt động; {len(dated)} có năm." if extras
                                          else "CV chưa có chứng chỉ, giải thưởng hay hoạt động.",
                                          "" if c6 == 4 else "Ghi rõ đơn vị cấp và năm; chỉ thêm mục liên quan đến nghề mà bạn thực sự có.")

    # C8: JD skills found in the CV; used in a project counts 1, only listed counts 0.5.
    jd_skills = extract_skills(jd_text)
    if jd_skills:
        listed = set(extract_skills(_text(hard)))
        in_use = set(extract_skills(evidence_text))
        points = sum(1.0 if skill in in_use else 0.5 if skill in listed else 0.0 for skill in jd_skills)
        coverage = points / len(jd_skills)
        missing = [skill for skill in jd_skills if skill not in in_use | listed]
        note = f"Đáp ứng khoảng {coverage:.0%} kỹ năng nhận diện được trong JD ({len(jd_skills)} kỹ năng)" + \
               (f"; chưa thấy: {', '.join(missing[:6])}." if missing else ".")
    else:
        coverage = _lexical_overlap("\n".join([_text(hard), evidence_text, str(cv.get("summary") or "")]), jd_text)
        missing, note = [], f"JD không có kỹ năng trong từ điển; dùng độ trùng từ khóa ({coverage:.0%})."
    c8 = 0 if coverage < 0.2 else 1 if coverage < 0.4 else 2 if coverage < 0.6 else 3 if coverage < 0.8 else 4
    scores["C8_jd_fit"] = _item(c8, note, "" if c8 == 4 else
                                ("Chỉ ghi các yêu cầu còn thiếu khi bạn đã thực sự dùng; nếu chưa, hãy làm một dự án nhỏ để có minh chứng."
                                 if missing else "Đưa các kỹ năng JD yêu cầu vào phần mô tả dự án nơi bạn đã dùng chúng."))

    result = rs.aggregate(rs.BASELINE, rubric, scores, rs.ats_from_pdf(facts), document=document, retrieval=None,
                          comment="", usage={"calls": 0, "input_tokens": 0, "output_tokens": 0}, latency=0.0,
                          model="rules")
    result["method"] = f"{rs.STRATEGIES[rs.BASELINE]} · {rubric['rubric_version']}"
    result["provider"] = "rules"
    for criterion in result["criteria"]:
        if criterion["scored_by"] == "llm":
            criterion["scored_by"] = "rule"
    return result
