"""Rubric v2 scoring strategies M1–M4 on Groq, ported from MatchCV_JD&Baseline_Rubrics_V2.ipynb.

The rubric (8 criteria, 0–4 anchors, weights) is read from downstream/rubric/rubric_v2.json, the
same file the human raters use. Changes from the notebook so that strategies are compared under
the same conditions:
- every strategy gets the same inputs: CVSchema without personal data, the full JD and the PDF facts;
- C7 (ATS) is scored from the PDF analysis, not by the LLM, because the CV JSON carries no layout;
- prompts carry no score hints; the M4 critic may move an agent's score by at most one point, and
  that limit is enforced in code;
- the RAG query is built from the JD and the CV's skills rather than a fixed sentence;
- knowledge chunks and the rubric are internal team material; no academic attribution is shown.
"""

from __future__ import annotations

import copy
import json
import math
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import requests

from baseline_extraction.privacy import redact_text
from services import requirement_rules


ROOT = Path(__file__).resolve().parents[2]
RUBRIC_PATH = ROOT / "downstream/rubric/rubric_v2.json"
KB_PATH = ROOT / "downstream/rag/kb_v1.jsonl"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "qwen/qwen3.8-27b"

BASELINE = "baseline_rules"
STRATEGIES = {
    BASELINE: "Chấm theo quy tắc (không dùng LLM)",
    "m1_zero_shot": "M1 · Zero-shot",
    "m2_few_shot": "M2 · Few-shot",
    "m3_rag": "M3 · RAG",
    "m4_multi_agent": "M4 · Đa tác tử",
}
LLM_STRATEGIES = tuple(key for key in STRATEGIES if key != BASELINE)
ATS = "C7_ats"
HR_CRITERIA = ("C1_structure", "C5_experience", "C6_certs_activities")
TECH_CRITERIA = ("C2_it_content", "C3_skills", "C4_projects", "C8_jd_fit")
CV_FIELDS = ("summary", "skills", "experience", "projects", "education", "certifications", "activities", "awards")

FEW_SHOT_EXAMPLE = """Ví dụ chấm (CV và JD minh họa, không phải ứng viên đang chấm):
CV backend: 2 dự án Spring Boot có vai trò và đầu việc cụ thể nhưng không có số liệu; thực tập 3 tháng tại công ty
phần mềm, mô tả có công nghệ và đầu việc; không có chứng chỉ; mục tiêu ghi rõ thực tập sinh Java backend.
JD yêu cầu bắt buộc: Java, Spring Boot, MySQL, Docker, RESTful API.
- C1_structure: 3 — mục rõ, thứ tự hợp lý; còn vài dòng dài và khoảng trắng thừa.
- C2_it_content: 4 — mục tiêu, kỹ năng và dự án cùng hướng backend Java.
- C3_skills: 3 — kỹ năng chính có minh chứng trong dự án; kỹ năng bổ trợ chỉ được liệt kê.
- C4_projects: 3 — có vai trò, công nghệ, đầu việc; chưa có kết quả đo được.
- C5_experience: 3 — thực tập CNTT có đầu việc và công nghệ cụ thể.
- C6_certs_activities: 0 — CV chưa có chứng chỉ, giải thưởng hay hoạt động.
- C8_jd_fit: 3 — 4/5 yêu cầu bắt buộc có bằng chứng (thiếu Docker), khoảng 80% nhưng không có yêu cầu ưu tiên nào."""

Caller = Callable[[list[dict[str, str]], dict[str, Any], int], tuple[dict[str, Any], dict[str, int]]]
Retrieve = Callable[..., dict[str, Any]]


class ScoringError(RuntimeError):
    """User-facing reason why LLM scoring could not finish."""


def load_rubric(path: Path = RUBRIC_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_kb(path: Path = KB_PATH) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---- inputs ----------------------------------------------------------------------------------

LINK = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"]+|\b(?:github|gitlab|linkedin)\.com/[^\s<>\"]+")


def _scrub(value: Any) -> Any:
    """Mask emails and phones; replace every link by [LINK] so a project still shows it has one (C4)."""
    if isinstance(value, str):
        return redact_text(LINK.sub("[LINK]", value))
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items()}
    return value


def cv_payload(cv_schema: dict[str, Any]) -> dict[str, Any]:
    """CVSchema without personal_info; emails, phones and links inside other fields are masked too."""
    return _scrub({key: copy.deepcopy(cv_schema.get(key)) for key in CV_FIELDS})


def pdf_facts(document: dict[str, Any], cv_schema: dict[str, Any]) -> dict[str, Any]:
    skills = cv_schema.get("skills") or {}
    return {
        "page_count": document.get("page_count"),
        "pages_with_text_layer": document.get("native_text_pages"),
        "characters": document.get("character_count"),
        "needs_ocr": bool(document.get("needs_ocr")),
        "likely_multi_column": bool(document.get("likely_multi_column")),
        "sections_found": [name for name, present in (
            ("summary", bool(str(cv_schema.get("summary") or "").strip())),
            ("skills", bool(skills.get("hard_skills") or skills.get("soft_skills"))),
            ("experience", bool(cv_schema.get("experience"))),
            ("projects", bool(cv_schema.get("projects"))),
            ("education", bool(cv_schema.get("education"))),
            ("certifications/activities/awards", bool(cv_schema.get("certifications") or cv_schema.get("activities")
                                                      or cv_schema.get("awards"))),
        ) if present],
    }


def ats_from_pdf(facts: dict[str, Any]) -> dict[str, Any]:
    """C7 from the PDF analysis, following the anchors of rubric v2."""
    sections = set(facts["sections_found"])
    missing = [name for name in ("skills", "education") if name not in sections]
    if not {"experience", "projects"} & sections:
        missing.append("experience/projects")
    if facts["needs_ocr"] and not facts["pages_with_text_layer"]:
        return {"score": 0, "evidence": "PDF dạng ảnh: không có trang nào có lớp chữ chọn được.",
                "suggestion": "Xuất lại CV thành PDF có thể bôi đen và sao chép chữ."}
    if facts["needs_ocr"] or (facts["characters"] or 0) < 500:
        return {"score": 1, "evidence": "Lớp chữ của PDF thiếu hoặc quá ít so với nội dung hiển thị.",
                "suggestion": "Xuất lại CV từ trình soạn thảo thành PDF có lớp chữ đầy đủ, không chụp ảnh nội dung."}
    if facts["likely_multi_column"]:
        return {"score": 2, "evidence": "Bố cục có dấu hiệu nhiều cột; máy có thể đọc sai thứ tự.",
                "suggestion": "Chuyển sang bố cục một cột hoặc bảo đảm thứ tự đọc từ trên xuống."}
    issues = []
    if (facts["page_count"] or 0) > 2:
        issues.append(f"CV dài {facts['page_count']} trang")
    if missing:
        issues.append("không nhận ra mục " + ", ".join(missing))
    if issues:
        return {"score": 3, "evidence": "Lớp chữ đầy đủ, một cột; còn: " + "; ".join(issues) + ".",
                "suggestion": "Dùng tiêu đề mục phổ biến (Kỹ năng, Kinh nghiệm, Dự án, Học vấn) và rút gọn còn 1–2 trang."}
    return {"score": 4, "evidence": "PDF có lớp chữ đầy đủ, một cột, đủ các mục chính.",
            "suggestion": ""}


# ---- prompts and calls ------------------------------------------------------------------------

# The same rule list as the rater guide (services/requirement_rules.py), so prompts and labels cannot differ.
REQUIREMENT_GUIDE = requirement_rules.prompt_text()


def rubric_text(rubric: dict[str, Any], criteria: tuple[str, ...]) -> str:
    lines = []
    for criterion in rubric["criteria"]:
        if criterion["id"] not in criteria:
            continue
        lines.append(f"### {criterion['id']} — {criterion['name']} (trọng số {criterion['weight']})")
        lines.append(f"Cách chấm: {criterion['how_to_judge']}")
        lines += [f"  Mức {level}: {anchor}" for level, anchor in enumerate(criterion["anchors"])]
        if criterion["id"] == "C8_jd_fit":
            lines.append(REQUIREMENT_GUIDE)
    return "\n".join(lines)


def output_schema(criteria: tuple[str, ...], *, comment: bool) -> dict[str, Any]:
    item = {"type": "object", "additionalProperties": False, "required": ["score", "evidence", "suggestion"],
            "properties": {"score": {"type": "integer"}, "evidence": {"type": "string"}, "suggestion": {"type": "string"}}}
    properties = {criterion: item for criterion in criteria}
    if comment:
        properties["overall_comment"] = {"type": "string"}
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


SYSTEM_RULES = """Bạn là chuyên gia đánh giá CV ngành CNTT, chấm theo rubric nội bộ của nhóm nghiên cứu.
Quy tắc:
1. Chấm mỗi tiêu chí được giao bằng số nguyên 0–4, đúng theo mô tả neo của mức đó.
2. evidence: trích ngắn, nguyên văn từ CV (tối đa khoảng 25 từ). Nếu CV không có nội dung cho tiêu chí, ghi "CV chưa có ..." và cho 0.
3. suggestion: một gợi ý cụ thể bằng tiếng Việt. Không đề nghị thêm kỹ năng, số liệu, công ty hay dự án mà CV không có; dùng chỗ trống [số liệu thật] khi cần.
4. C8_jd_fit: đếm các yêu cầu bắt buộc của JD có bằng chứng trong CV (kỹ năng chỉ liệt kê, không có ngữ cảnh sử dụng, tính một nửa), tính tỉ lệ rồi chọn mức theo mô tả neo.
5. Không chấm theo tên, giới tính, ảnh, quê quán, trường học hay thông tin cá nhân.
6. C7_ats đã được chấm từ phân tích PDF và không thuộc phần việc của bạn.
7. Chỉ trả về JSON đúng schema."""


def build_user_message(facts: dict[str, Any], cv: dict[str, Any], jd_text: str, criteria_text: str,
                       context: str = "") -> str:
    parts = [f"## Rubric cho các tiêu chí cần chấm\n{criteria_text}"]
    if context:
        parts.append(context)
    parts += [f"## Thông tin PDF (dùng cho C1)\n{json.dumps(facts, ensure_ascii=False)}",
              f"## CV (CVSchema 2.0, đã che thông tin cá nhân)\n{json.dumps(cv, ensure_ascii=False)}",
              f"## JD\n{jd_text}"]
    return "\n\n".join(parts)


def groq_caller(api_key: str, *, model: str = GROQ_MODEL, timeout_seconds: float = 90.0,
                max_attempts: int = 3, max_wait: float = 20.0, sleep: Callable[[float], None] = time.sleep) -> Caller:
    """JSON-schema chat completion with retries on rate limits; falls back to json_object mode.

    A rate-limited call waits as long as Groq's retry-after asks, up to max_wait. The web keeps
    max_wait short so a visitor is not held; the offline runner allows a full per-minute window.
    A longer wait (a daily quota) fails at once and says how long to wait.
    """

    def call(messages: list[dict[str, str]], schema: dict[str, Any], max_tokens: int):
        response_format: dict[str, Any] = {"type": "json_schema",
                                           "json_schema": {"name": "rubric_scores", "strict": True, "schema": schema}}
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.post(
                    GROQ_CHAT_URL, timeout=timeout_seconds,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": model, "messages": messages, "temperature": 0, "seed": 42,
                          "reasoning_effort": "none", "max_tokens": max_tokens, "response_format": response_format})
            except requests.RequestException as exc:
                if attempt == max_attempts:
                    raise ScoringError("Không kết nối được dịch vụ Groq.") from exc
                sleep(2 * attempt)
                continue
            if response.status_code == 400 and response_format["type"] == "json_schema" and "response_format" in response.text:
                response_format = {"type": "json_object"}
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == max_attempts:
                    raise ScoringError("Dịch vụ Groq đang quá tải hoặc vượt hạn mức miễn phí. Hãy thử lại sau ít phút.")
                try:
                    wait = float(response.headers.get("retry-after", 0))
                except ValueError:
                    wait = 0
                if wait > max_wait:
                    raise ScoringError(f"Groq báo vượt hạn mức miễn phí; cần chờ khoảng {math.ceil(wait)} giây "
                                       "trước khi gọi tiếp.")
                sleep(min(max_wait, max(wait, 3.0 * attempt)))
                continue
            if response.status_code in (401, 403):
                raise ScoringError("Máy chủ web chưa được cấu hình đúng khóa Groq.")
            if response.status_code >= 400:
                raise ScoringError(f"Groq từ chối yêu cầu chấm điểm (HTTP {response.status_code}).")
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            try:
                parsed = json.loads(content[content.find("{"): content.rfind("}") + 1])
            except ValueError as exc:
                raise ScoringError("Groq trả về kết quả không phải JSON.") from exc
            usage = body.get("usage") or {}
            return parsed, {"input_tokens": int(usage.get("prompt_tokens") or 0),
                            "output_tokens": int(usage.get("completion_tokens") or 0)}
        raise ScoringError("Không nhận được kết quả chấm điểm từ Groq.")

    return call


def _clean_scores(raw: dict[str, Any], criteria: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    cleaned = {}
    for criterion in criteria:
        item = raw.get(criterion) if isinstance(raw.get(criterion), dict) else None
        if item is None and isinstance(raw.get("scores"), dict):
            item = raw["scores"].get(criterion)
        if not isinstance(item, dict) or "score" not in item:
            raise ScoringError(f"Kết quả chấm điểm thiếu tiêu chí {criterion}.")
        try:
            score = int(round(float(item["score"])))
        except (TypeError, ValueError) as exc:
            raise ScoringError(f"Điểm của {criterion} không hợp lệ.") from exc
        cleaned[criterion] = {"score": max(0, min(4, score)), "evidence": str(item.get("evidence") or "").strip()[:600],
                              "suggestion": str(item.get("suggestion") or "").strip()[:600]}
    return cleaned


# ---- retrieval -----------------------------------------------------------------------------

def _tokens(text: str) -> list[str]:
    folded = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return re.findall(r"[a-z0-9+#.]{2,}", folded)


def lexical_retrieve(query: str, kb: list[dict[str, Any]], top_k: int = 3,
                     roles: list[str] | None = None) -> list[dict[str, Any]]:
    """BM25 over the same KB (same role filter); used when the embedding server is unavailable."""
    kb = [row for row in kb if not roles or set(roles) & set(row.get("roles", []))]
    documents = [_tokens(f"{row['title']} {row['text']}") for row in kb]
    average = sum(map(len, documents)) / len(documents)
    frequency = Counter(term for document in documents for term in set(document))
    query_terms = set(_tokens(query))
    scored = []
    for row, document in zip(kb, documents):
        counts = Counter(document)
        score = 0.0
        for term in query_terms & counts.keys():
            idf = math.log(1 + (len(kb) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            tf = counts[term]
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(document) / average))
        scored.append((score, row))
    scored.sort(key=lambda item: -item[0])
    return [{"id": row["id"], "title": row["title"], "text": row["text"], "score": round(score, 4)}
            for score, row in scored[:top_k]]


def rag_query(cv: dict[str, Any], jd_text: str) -> str:
    """Query for the role-specific chunk: what the JD asks for and the CV's skills."""
    skills = (cv.get("skills") or {}).get("hard_skills") or []
    return f"{jd_text[:700]}\nKỹ năng trong CV: {', '.join(map(str, skills[:30]))}"


def cv_query(cv: dict[str, Any]) -> str:
    """Query for the CV-writing chunks: how the candidate currently presents summary, projects and work."""
    parts = [str(cv.get("summary") or "")]
    parts += [f"{p.get('name', '')}: {p.get('details', '')}" for p in cv.get("projects") or []]
    parts += [f"{e.get('job_title', '')}: {e.get('description', '')}" for e in cv.get("experience") or []]
    return "\n".join(part for part in parts if part.strip())[:1500] or "CV chưa có mô tả dự án hay kinh nghiệm"


def rag_context(cv: dict[str, Any], jd_text: str, retrieve: Retrieve | None,
                kb: list[dict[str, Any]] | None) -> tuple[str, dict[str, Any]]:
    """Prompt section with the retrieved knowledge, and what was retrieved (M3 and P share it)."""
    # One chunk about the role, found with the JD; two CV-writing chunks, found with the CV's own text.
    plan = ((rag_query(cv, jd_text), 1, ["backend", "frontend"]), (cv_query(cv), 2, ["all"]))
    try:
        if retrieve is None:
            raise ScoringError("no retriever")
        answers = [retrieve(query, top_k, roles) for query, top_k, roles in plan]
        chunks = [chunk for answer in answers for chunk in answer["results"]]
        backend = answers[0].get("backend", "bge-m3")
    except Exception:
        knowledge = kb or load_kb()
        chunks = [chunk for query, top_k, roles in plan for chunk in lexical_retrieve(query, knowledge, top_k, roles)]
        backend = "BM25 dự phòng (máy chủ embedding chưa sẵn sàng)"
    retrieval = {"backend": backend, "chunks": [{"id": c["id"], "title": c["title"], "score": c.get("score")}
                                                 for c in chunks]}
    context = "## Tri thức tham khảo nội bộ (dùng để viết gợi ý; không phải bằng chứng về ứng viên)\n" + \
              "\n\n".join(f"[{c['id']}] {c['title']}\n{c['text']}" for c in chunks)
    return context, retrieval


# ---- strategies -----------------------------------------------------------------------------

def score(strategy: str, *, cv_schema: dict[str, Any], jd_text: str, document: dict[str, Any], call: Caller,
          retrieve: Retrieve | None = None, rubric: dict[str, Any] | None = None, kb: list[dict[str, Any]] | None = None,
          progress: Callable[[str], None] = lambda message: None, model: str = GROQ_MODEL) -> dict[str, Any]:
    if strategy not in LLM_STRATEGIES:
        raise ValueError(f"Unknown LLM strategy {strategy}")
    rubric = rubric or load_rubric()
    llm_criteria = tuple(c["id"] for c in rubric["criteria"] if c["id"] != ATS)
    cv, facts = cv_payload(cv_schema), pdf_facts(document, cv_schema)
    ats = ats_from_pdf(facts)
    started = time.perf_counter()
    usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    retrieval = None
    comment = ""

    def run(criteria: tuple[str, ...], context: str = "", role: str = "", with_comment: bool = False,
            extra: str = "", max_tokens: int = 2200) -> tuple[dict[str, dict[str, Any]], str]:
        system = SYSTEM_RULES if not role else f"{SYSTEM_RULES}\nVai trò của bạn: {role}"
        user = build_user_message(facts, cv, jd_text, rubric_text(rubric, criteria), context)
        if extra:
            user += "\n\n" + extra
        raw, used = call([{"role": "system", "content": system}, {"role": "user", "content": user}],
                         output_schema(criteria, comment=with_comment), max_tokens)
        usage["calls"] += 1
        usage["input_tokens"] += used.get("input_tokens", 0)
        usage["output_tokens"] += used.get("output_tokens", 0)
        return _clean_scores(raw, criteria), str(raw.get("overall_comment") or "").strip()[:1200]

    if strategy == "m1_zero_shot":
        progress("Đang chấm 7 tiêu chí bằng M1 · Zero-shot...")
        scores, _ = run(llm_criteria)
    elif strategy == "m2_few_shot":
        progress("Đang chấm 7 tiêu chí bằng M2 · Few-shot...")
        scores, _ = run(llm_criteria, context=f"## Ví dụ chấm mẫu\n{FEW_SHOT_EXAMPLE}")
    elif strategy == "m3_rag":
        progress("Đang truy xuất tri thức tham khảo cho M3 · RAG...")
        context, retrieval = rag_context(cv, jd_text, retrieve, kb)
        progress("Đang chấm 7 tiêu chí bằng M3 · RAG...")
        scores, _ = run(llm_criteria, context=context)
    else:
        progress("M4 · Đa tác tử: tác tử nhân sự đang chấm C1, C5, C6 (bước 1/3)...")
        hr, _ = run(HR_CRITERIA, role="tác tử nhân sự: đánh giá cấu trúc, kinh nghiệm, chứng chỉ và hoạt động.")
        progress("M4 · Đa tác tử: tác tử kỹ thuật đang chấm C2, C3, C4, C8 (bước 2/3)...")
        tech, _ = run(TECH_CRITERIA, role="tác tử kỹ thuật: đánh giá nội dung chuyên môn, kỹ năng, dự án và mức khớp JD.")
        initial = {**hr, **tech}
        progress("M4 · Đa tác tử: tác tử phản biện đang rà soát và chốt điểm (bước 3/3)...")
        review = ("## Điểm ban đầu của hai tác tử\n" + json.dumps(initial, ensure_ascii=False)
                  + "\n\nRà soát điểm ban đầu đối chiếu với CV, JD và mô tả neo. Chỉ đổi điểm khi có bằng chứng rõ ràng, "
                    "tối đa 1 điểm cho mỗi tiêu chí. Viết overall_comment là nhận xét tổng thể 2–3 câu.")
        critic, comment = run(llm_criteria, role="tác tử phản biện: chốt điểm cuối cùng.", with_comment=True,
                              extra=review, max_tokens=2600)
        scores = {}
        for criterion in llm_criteria:
            base, final = initial[criterion]["score"], critic[criterion]["score"]
            scores[criterion] = {**critic[criterion], "score": max(base - 1, min(base + 1, final)),
                                 "initial_score": base}

    return aggregate(strategy, rubric, scores, ats, document=document, retrieval=retrieval, comment=comment,
                     usage=usage, latency=time.perf_counter() - started, model=model)


def aggregate(strategy: str, rubric: dict[str, Any], scores: dict[str, dict[str, Any]], ats: dict[str, Any], *,
              document: dict[str, Any], retrieval: dict[str, Any] | None, comment: str, usage: dict[str, int],
              latency: float, model: str) -> dict[str, Any]:
    criteria = []
    for criterion in rubric["criteria"]:
        item = ats if criterion["id"] == ATS else scores[criterion["id"]]
        criteria.append({
            "id": criterion["id"], "name": criterion["name"], "weight": criterion["weight"],
            "score": item["score"], "weighted": round(criterion["weight"] * item["score"] / 4, 2),
            "evidence": item["evidence"], "suggestion": item["suggestion"],
            "scored_by": "pdf" if criterion["id"] == ATS else ("critic" if "initial_score" in item else "llm"),
            "initial_score": item.get("initial_score"),
        })
    total = round(sum(item["weighted"] for item in criteria), 1)
    verdict = "Tốt" if total >= 80 else "Khá" if total >= 65 else "Trung bình" if total >= 50 else "Cần cải thiện"
    strengths = [f"{item['name']} ({item['score']}/4): {item['evidence']}"
                 for item in sorted(criteria, key=lambda c: -c["weighted"]) if item["score"] >= 3 and item["evidence"]]
    improvements = [f"{item['name']} ({item['score']}/4): {item['suggestion']}"
                    for item in sorted(criteria, key=lambda c: -(c["weight"] * (4 - c["score"])))
                    if item["score"] < 4 and item["suggestion"]]
    return {
        "result_type": "rubric_v2",
        "rubric_version": rubric["rubric_version"],
        "strategy": strategy,
        "method": f"{STRATEGIES[strategy]} · {model} · {rubric['rubric_version']}",
        "total_score": total,
        "verdict": verdict,
        "criteria": criteria,
        "strengths": strengths[:4],
        "improvements": improvements[:5],
        "overall_comment": comment,
        "retrieval": retrieval,
        "provider": "groq",
        "model": model,
        "calls": usage["calls"],
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "latency_seconds": round(latency, 2),
        "extraction": document,
    }
