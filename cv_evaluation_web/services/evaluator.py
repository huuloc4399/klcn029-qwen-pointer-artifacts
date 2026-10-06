"""Deterministic CV-JD scoring baseline extracted from the Colab rubric.

The web MVP keeps scoring reproducible and evidence based. Qwen, RAG and the
multi-agent strategy can later implement the same result contract.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import asdict, dataclass

from .pdf_extractor import DocumentAnalysis


SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "Java": ("java",),
    "JavaScript": ("javascript", "java script", "js"),
    "TypeScript": ("typescript", "type script"),
    "C#": ("c#", "c sharp"),
    "C++": ("c++",),
    ".NET": (".net", "dotnet"),
    "ASP.NET MVC": ("asp.net mvc", "asp net mvc"),
    "Spring Boot": ("spring boot",),
    "React": ("react", "reactjs", "react.js"),
    "Angular": ("angular",),
    "Vue.js": ("vue.js", "vuejs", "vue js"),
    "Node.js": ("node.js", "nodejs", "node js"),
    "FastAPI": ("fastapi",),
    "Flask": ("flask",),
    "Django": ("django",),
    "Laravel": ("laravel",),
    "Flutter": ("flutter",),
    "Kotlin": ("kotlin",),
    "Swift": ("swift",),
    "SQL": ("sql",),
    "MySQL": ("mysql",),
    "PostgreSQL": ("postgresql", "postgres"),
    "SQL Server": ("sql server", "mssql"),
    "MongoDB": ("mongodb", "mongo db"),
    "Redis": ("redis",),
    "REST API": ("rest api", "restful api", "restful"),
    "GraphQL": ("graphql",),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "Git": ("git",),
    "GitHub Actions": ("github actions",),
    "Jenkins": ("jenkins",),
    "CI/CD": ("ci/cd", "continuous integration", "continuous delivery"),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure",),
    "Google Cloud": ("google cloud", "gcp"),
    "Machine Learning": ("machine learning",),
    "Deep Learning": ("deep learning",),
    "Computer Vision": ("computer vision",),
    "NLP": ("natural language processing", "nlp"),
    "PyTorch": ("pytorch",),
    "TensorFlow": ("tensorflow",),
    "Scikit-learn": ("scikit-learn", "sklearn"),
    "Pandas": ("pandas",),
    "NumPy": ("numpy",),
    "OpenCV": ("opencv",),
    "Power BI": ("power bi",),
    "Tableau": ("tableau",),
    "UML": ("uml",),
    "Agile": ("agile",),
    "Scrum": ("scrum",),
    "Jira": ("jira",),
    "Unit Testing": ("unit testing", "unit test", "junit", "pytest", "xunit"),
    "Figma": ("figma",),
    "HTML": ("html",),
    "CSS": ("css",),
}

ACTION_VERBS = {
    "achieved", "analyzed", "architected", "automated", "built", "created", "designed",
    "developed", "deployed", "engineered", "implemented", "improved", "integrated", "led",
    "managed", "optimized", "refactored", "reduced", "streamlined", "tăng", "giảm", "xây dựng",
    "phát triển", "thiết kế", "triển khai", "tối ưu", "phân tích", "quản lý", "dẫn dắt",
}
PASSIVE_PHRASES = {
    "responsible for", "participated in", "helped with", "assisted with", "worked on",
    "chịu trách nhiệm", "tham gia vào", "hỗ trợ việc",
}
SECTION_GROUPS = {
    "summary": ("summary", "profile", "objective", "about me", "mục tiêu", "giới thiệu"),
    "skills": ("skills", "technical skills", "kỹ năng"),
    "experience": ("experience", "work experience", "employment", "kinh nghiệm"),
    "projects": ("projects", "project", "dự án"),
    "education": ("education", "academic", "học vấn", "giáo dục"),
}
STOP_WORDS = {
    "and", "the", "with", "for", "from", "that", "this", "you", "your", "our", "are", "will",
    "các", "và", "cho", "của", "với", "trong", "được", "một", "những", "ứng", "viên", "công",
    "việc", "yêu", "cầu", "mô", "tả", "job", "candidate", "experience", "skill", "skills",
}


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _contains_alias(text: str, alias: str) -> bool:
    folded_text = _fold(text)
    folded_alias = _fold(alias)
    if re.fullmatch(r"[a-z0-9 ]+", folded_alias):
        return re.search(rf"(?<![a-z0-9]){re.escape(folded_alias)}(?![a-z0-9])", folded_text) is not None
    return folded_alias in folded_text


def extract_skills(text: str) -> list[str]:
    found = []
    for canonical, aliases in SKILL_ALIASES.items():
        if any(_contains_alias(text, alias) for alias in aliases):
            found.append(canonical)
    return found


def _lexical_overlap(cv_text: str, jd_text: str) -> float:
    def tokens(value: str) -> set[str]:
        return {
            token for token in re.findall(r"[a-zA-ZÀ-ỹ][\w+#.-]{2,}", _fold(value))
            if token not in STOP_WORDS and not token.isdigit()
        }
    cv_tokens, jd_tokens = tokens(cv_text), tokens(jd_text)
    if not jd_tokens:
        return 0.0
    return min(1.0, len(cv_tokens & jd_tokens) / max(8, len(jd_tokens) * 0.55))


def _lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip(" •▪●-\t") for line in text.splitlines() if line.strip()]


def _section_presence(text: str) -> dict[str, bool]:
    folded = _fold(text)
    return {name: any(_fold(alias) in folded for alias in aliases) for name, aliases in SECTION_GROUPS.items()}


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


@dataclass(slots=True)
class EvaluationResult:
    total_score: float
    verdict: str
    scores: dict[str, float]
    score_notes: dict[str, str]
    cv_skills: list[str]
    jd_skills: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    must_have_coverage: float
    action_verbs_found: list[str]
    passive_phrases_found: list[str]
    quantified_lines: int
    strengths: list[str]
    improvements: list[str]
    extraction: dict
    method: str = "Deterministic web baseline v1"

    def to_dict(self) -> dict:
        return asdict(self)


def _structured_text(cv_schema: dict) -> str:
    """Flatten validated CVSchema 2.0 for deterministic downstream features."""

    parts: list[str] = []
    summary = cv_schema.get("summary")
    if isinstance(summary, str) and summary.strip():
        parts.append(summary)
    skills = cv_schema.get("skills") or {}
    for key in ("hard_skills", "soft_skills"):
        values = skills.get(key) if isinstance(skills, dict) else []
        if isinstance(values, list):
            parts.extend(str(value) for value in values if str(value).strip())
    for collection, fields in (
        ("experience", ("company", "job_title", "duration", "description")),
        ("projects", ("name", "role", "details")),
        ("education", ("degree", "university")),
    ):
        values = cv_schema.get(collection)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            for field in fields:
                value = item.get(field)
                if isinstance(value, str) and value.strip():
                    parts.append(value)
            technologies = item.get("technologies")
            if isinstance(technologies, list):
                parts.extend(str(value) for value in technologies if str(value).strip())
    for collection in ("certifications", "activities", "awards"):
        values = cv_schema.get(collection)
        if isinstance(values, list):
            parts.extend(str(value) for value in values if str(value).strip())
    return "\n".join(parts)


def evaluate(
    cv_document: DocumentAnalysis,
    jd_text: str,
    *,
    language: str = "auto",
    cv_schema: dict | None = None,
    method: str | None = None,
) -> EvaluationResult:
    cv_text = _structured_text(cv_schema) if cv_schema is not None else cv_document.text
    lines = _lines(cv_text)
    if cv_schema is None:
        sections = _section_presence(cv_text)
        cv_skills = extract_skills(cv_text)
    else:
        skills = cv_schema.get("skills") or {}
        declared: list[str] = []
        if isinstance(skills, dict):
            for key in ("hard_skills", "soft_skills"):
                values = skills.get(key)
                if isinstance(values, list):
                    declared.extend(str(value).strip() for value in values if str(value).strip())
        cv_skills = list(dict.fromkeys(declared + extract_skills(cv_text)))
        sections = {
            "summary": bool(str(cv_schema.get("summary", "")).strip()),
            "skills": bool(declared),
            "experience": bool(cv_schema.get("experience")),
            "projects": bool(cv_schema.get("projects")),
            "education": bool(cv_schema.get("education")),
        }
    jd_skills = extract_skills(jd_text)
    matched = sorted(set(cv_skills) & set(jd_skills))
    missing = sorted(set(jd_skills) - set(cv_skills))

    if jd_skills:
        coverage = len(matched) / len(jd_skills)
        semantic_note = f"Đối chiếu {len(matched)}/{len(jd_skills)} kỹ năng nhận diện được trong JD."
    else:
        coverage = _lexical_overlap(cv_text, jd_text)
        semantic_note = "JD không chứa kỹ năng trong từ điển v1; dùng độ phủ từ khóa nội dung."
    semantic_score = round(35 * coverage, 1)

    ats_score = 20.0
    ats_reasons: list[str] = []
    if cv_document.needs_ocr:
        ats_score -= 6
        ats_reasons.append("lớp văn bản thưa, cần OCR")
    if cv_document.character_count < 500:
        ats_score -= 3
        ats_reasons.append("nội dung trích xuất quá ngắn")
    if cv_document.likely_multi_column:
        ats_score -= 2
        ats_reasons.append("bố cục có dấu hiệu nhiều cột")
    if cv_document.page_count > 3:
        ats_score -= min(2, cv_document.page_count - 3)
        ats_reasons.append("CV dài hơn 3 trang")
    essential_present = sum((sections["skills"], sections["education"], sections["experience"] or sections["projects"]))
    ats_score -= (3 - essential_present) * 1.5
    if essential_present < 3:
        ats_reasons.append("thiếu tiêu đề phần quan trọng")
    ats_score = round(_clamp(ats_score, 0, 20), 1)

    quantified = [line for line in lines if re.search(r"(?:\d+[.,]?\d*\s*%|\b\d{2,}[+]?\b|\b\d+[xX]\b)", line)]
    action_found = sorted({verb for verb in ACTION_VERBS if _fold(verb) in _fold(cv_text)})
    passive_found = sorted({phrase for phrase in PASSIVE_PHRASES if _fold(phrase) in _fold(cv_text)})
    bullet_candidates = [line for line in lines if len(line.split()) >= 4]
    quant_ratio = min(1.0, len(quantified) / max(3, len(bullet_candidates) * 0.2))
    action_ratio = min(1.0, len(action_found) / max(3, len(bullet_candidates) * 0.15))
    impact_score = round(_clamp(5 + 17 * quant_ratio + 8 * action_ratio, 0, 30), 1)
    tone_score = round(_clamp(5 + 10 * action_ratio - 1.5 * len(passive_found), 0, 15), 1)

    total = round(ats_score + impact_score + semantic_score + tone_score, 1)
    verdict = "Rất phù hợp" if total >= 85 else "Phù hợp" if total >= 70 else "Cần bổ sung" if total >= 50 else "Cần cải thiện nhiều"

    strengths: list[str] = []
    if matched:
        strengths.append(f"Khớp {len(matched)} kỹ năng với JD: {', '.join(matched[:5])}.")
    if quantified:
        strengths.append(f"Có {len(quantified)} dòng chứa kết quả hoặc quy mô định lượng.")
    if action_found:
        strengths.append(f"Có động từ hành động rõ: {', '.join(action_found[:5])}.")
    if ats_score >= 16:
        strengths.append("PDF có cấu trúc và lớp văn bản tương đối thuận lợi cho hệ thống tuyển dụng.")
    if not strengths:
        strengths.append("CV đã cung cấp đủ dữ liệu cơ bản để hệ thống đưa ra đánh giá ban đầu.")

    improvements: list[str] = []
    if missing:
        improvements.append(
            "JD còn các kỹ năng chưa tìm thấy: " + ", ".join(missing[:6])
            + ". Chỉ bổ sung vào CV khi bạn thực sự có kinh nghiệm và kèm minh chứng."
        )
    if not quantified:
        improvements.append("Bổ sung số liệu thật cho thành tích, ví dụ thời gian giảm, số người dùng hoặc độ chính xác; không tự tạo số liệu.")
    if len(action_found) < 2:
        improvements.append("Bắt đầu mô tả kinh nghiệm bằng động từ hành động cụ thể như Developed, Implemented, Designed hoặc Tối ưu.")
    if passive_found:
        improvements.append("Thay cụm bị động như " + ", ".join(passive_found[:3]) + " bằng hành động và kết quả trực tiếp.")
    if not sections["summary"]:
        improvements.append("Thêm phần tóm tắt nghề nghiệp ngắn, nêu vị trí mục tiêu, năng lực chính và giá trị có thể đóng góp.")
    if cv_document.needs_ocr:
        improvements.append("PDF có lớp chữ không đầy đủ. Xuất lại CV thành PDF có thể chọn văn bản để tăng độ chính xác OCR và ATS.")
    if not improvements:
        improvements.append("Rà soát lại mỗi kỹ năng với một minh chứng cụ thể trong kinh nghiệm hoặc dự án.")

    return EvaluationResult(
        total_score=total,
        verdict=verdict,
        scores={"ats": ats_score, "impact": impact_score, "semantic": semantic_score, "tone": tone_score},
        score_notes={
            "ats": "; ".join(ats_reasons) if ats_reasons else "Cấu trúc PDF và các phần chính được nhận diện tốt.",
            "impact": f"{len(quantified)} dòng định lượng; {len(action_found)} nhóm động từ hành động.",
            "semantic": semantic_note,
            "tone": f"{len(action_found)} động từ hành động; {len(passive_found)} cụm bị động.",
        },
        cv_skills=cv_skills,
        jd_skills=jd_skills,
        matched_skills=matched,
        missing_skills=missing,
        must_have_coverage=round(coverage, 4),
        action_verbs_found=action_found,
        passive_phrases_found=passive_found,
        quantified_lines=len(quantified),
        strengths=strengths[:4],
        improvements=improvements[:5],
        extraction=cv_document.public_dict(),
        method=method or (
            "Qwen Pointer P0 + deterministic matching baseline v1"
            if cv_schema is not None
            else "Deterministic web baseline v1"
        ),
    )
