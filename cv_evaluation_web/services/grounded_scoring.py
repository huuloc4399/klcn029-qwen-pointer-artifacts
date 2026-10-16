"""Method P: rubric scoring with verified evidence and abstention (the thesis's proposed method).

P keeps M3's model, rubric and retrieved knowledge, and changes what happens around the LLM:

1. Structured evidence. Each criterion C1–C6 returns a status, a score and quotes tied to a CVSchema
   field (projects[0].details). Each JD requirement returns met / mentioned_only / missing / unclear
   with one quote.
2. Verification in code. A quote counts only if, after normalisation, it is a substring of the field
   it points to (or of that field's section). A score above 0 left without valid evidence is asked
   again once for that criterion alone; still none → needs_verification. A requirement claimed "met"
   must be quoted from where the skill is used (projects, experience, certificates); quoted only from
   the skills list or summary it becomes mentioned_only; a quote that is not in the CV makes it missing.
3. Missing versus misread. When the extracted CV holds far less text than the PDF's text layer, content
   may have been lost, so a "missing" judgement is not trusted: the criterion becomes
   needs_verification and the requirement unclear, instead of scoring 0.
4. C8 is computed from the verified requirement statuses with the rubric's bands; C7 comes from the
   PDF analysis as in every strategy.
5. Aggregation with coverage: Q over the criteria that could be scored, C = their share of the weight.
   The total is shown only when C ≥ COVERAGE_MIN and C3, C4 or C5, and C8 are scored.

The ablations of module E switch parts off: verify=False keeps every LLM score as given (no
verification, no second ask); abstain=False never marks needs_verification.
"""

from __future__ import annotations

import re
import time
import unicodedata
from typing import Any, Callable

from services import rubric_scoring as rs
from services.evaluator import extract_skills

STRATEGIES = {
    "p_grounded": "P · Chấm có kiểm chứng bằng chứng",
    "p_no_verify": "P − kiểm chứng (ablation)",
    "p_no_abstain": "P − từ chối chấm (ablation)",
}
LLM_CRITERIA = ("C1_structure", "C2_it_content", "C3_skills", "C4_projects", "C5_experience", "C6_certs_activities")
REQUIREMENT_CRITERION = "C8_jd_fit"
REQUIRED_FOR_TOTAL = (("C3_skills",), ("C4_projects", "C5_experience"), ("C8_jd_fit",))
COVERAGE_MIN = 0.80          # lock on dev before the test run
# Extracted CV text / PDF text-layer characters below this → content may have been lost. Chosen on the dev
# CVs without labels: about 0.75 x the lowest ratio of the gold CVSchemas (0.34), so gold is never flagged.
LOW_TEXT_RATIO = 0.25
MIN_QUOTE = 4
USAGE_SECTIONS = {"experience", "projects", "certifications", "activities", "awards"}
LISTING_SECTIONS = {"skills", "summary", "education"}
REQ_STATUSES = ("met", "mentioned_only", "missing", "unclear")
REQ_VALUE = {"met": 1.0, "mentioned_only": 0.5, "missing": 0.0}

P_RULES = """Bạn là chuyên gia đánh giá CV ngành CNTT, chấm theo rubric nội bộ của nhóm nghiên cứu.
Quy tắc:
1. Với mỗi tiêu chí được giao: status là "scored" hoặc "missing_in_cv". missing_in_cv chỉ khi CV không có nội dung cho tiêu chí đó; khi ấy score = 0 và evidence rỗng.
2. evidence: 1–3 trích dẫn. field là đường dẫn trong JSON CV (ví dụ "projects[0].details", "skills.hard_skills", "summary", "experience[1].description"). quote là câu chữ CHÉP NGUYÊN VĂN từ đúng field đó, 3–25 từ, không sửa, không dịch, không tóm tắt. Không trích từ JD hay từ tri thức tham khảo.
3. Mỗi điểm lớn hơn 0 phải có ít nhất một trích dẫn chứng minh. Không có trích dẫn thì không cho điểm đó.
4. requirements: xét từng yêu cầu của JD. met = CV cho thấy đã dùng trong dự án, kinh nghiệm hoặc chứng chỉ (trích từ đó); mentioned_only = chỉ có trong danh sách kỹ năng hoặc mục tiêu (trích từ đó); missing = không thấy (quote rỗng); unclear = có dấu hiệu nhưng không đủ để quyết định (ghi lý do ở note).
5. suggestion: một gợi ý cụ thể bằng tiếng Việt. Không đề nghị thêm kỹ năng, số liệu, công ty hay dự án mà CV không có; dùng chỗ trống [số liệu thật] khi cần.
6. Không chấm theo tên, giới tính, ảnh, quê quán, trường học hay thông tin cá nhân. C7 và C8 được tính bằng chương trình, không thuộc phần việc của bạn.
7. Chỉ trả về JSON đúng schema."""


# ---------- verification ----------

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                         "•": " ", "●": " ", " ": " "})
_PATH = re.compile(r"([A-Za-z_]+)|\[(\d+)\]|\.(\d+)")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text)).translate(_QUOTES).casefold()
    return re.sub(r"\s+", " ", text).strip(" .,;:-\"'")


def _flatten(node: Any) -> str:
    if isinstance(node, dict):
        return " ".join(_flatten(v) for v in node.values())
    if isinstance(node, list):
        return " ".join(_flatten(v) for v in node)
    return "" if node is None else str(node)


def resolve(cv: dict[str, Any], field: str) -> tuple[str | None, str | None]:
    """(section, text of the field) for a path like projects[1].details; text None when the path is wrong."""
    tokens = [m.group(1) or m.group(2) or m.group(3) for m in _PATH.finditer(str(field or ""))]
    if not tokens or tokens[0] not in cv:
        return None, None
    node: Any = cv
    for token in tokens:
        if isinstance(node, dict) and token in node:
            node = node[token]
        elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
            node = node[int(token)]
        else:
            return tokens[0], None
    return tokens[0], _flatten(node)


def locate(cv: dict[str, Any], quote: str) -> set[str]:
    """Sections whose text contains every part of the quote (parts split at an ellipsis)."""
    parts = [norm(p) for p in re.split(r"\.\.\.|…", quote) if len(norm(p)) >= MIN_QUOTE]
    if not parts:
        return set()
    return {section for section, value in cv.items()
            if all(part in norm(_flatten(value)) for part in parts)}


def check_quote(cv: dict[str, Any], field: str, quote: str) -> str:
    """'field' (in the field pointed to), 'section' (elsewhere in that section), 'other' (elsewhere in the CV), 'none'."""
    parts = [norm(p) for p in re.split(r"\.\.\.|…", quote) if len(norm(p)) >= MIN_QUOTE]
    if not parts:
        return "none"
    section, text = resolve(cv, field)
    if text is not None and all(part in norm(text) for part in parts):
        return "field"
    found = locate(cv, quote)
    if section in found:
        return "section"
    return "other" if found else "none"


def content_flags(document: dict[str, Any], cv: dict[str, Any]) -> list[str]:
    """Signals that the extracted CV may be missing content the PDF has."""
    flags = []
    characters = document.get("character_count") or 0
    if characters >= 800 and len(_flatten(cv)) < LOW_TEXT_RATIO * characters:
        flags.append("low_text_coverage")
    return flags


def verify_criterion(cv: dict[str, Any], item: dict[str, Any], criterion: str) -> dict[str, Any]:
    checked = []
    for evidence in item.get("evidence") or []:
        field, quote = str(evidence.get("field") or ""), str(evidence.get("quote") or "")
        level = check_quote(cv, field, quote)
        if criterion == "C1_structure" and level == "none" and resolve(cv, field)[1]:
            level = "field"  # structure evidence may name a section rather than quote it
        checked.append({"field": field, "quote": quote[:300], "check": level})
    valid = [e for e in checked if e["check"] in ("field", "section")]
    return {**item, "evidence_checked": checked, "valid_evidence": len(valid)}


def verify_requirement(cv: dict[str, Any], req: dict[str, Any], given: str) -> tuple[str, str]:
    """(verified status, reason) for one requirement."""
    quote = str(req.get("quote") or "")
    if given in ("missing", "unclear"):
        return given, ""
    found = locate(cv, quote)
    if not found:
        return "missing", "trích dẫn không có trong CV"
    skills = extract_skills(str(req.get("text") or ""))
    if skills and not any(skill in extract_skills(quote) for skill in skills):
        return "missing", "trích dẫn không nhắc tới yêu cầu"
    if given == "met" and not found & USAGE_SECTIONS:
        return "mentioned_only", "chỉ thấy trong danh sách kỹ năng hoặc mục tiêu"
    return given, ""


def c8_from_requirements(requirements: list[dict[str, Any]]) -> tuple[int | None, str]:
    must = [r for r in requirements if r["type"] == "must" and r["status"] in REQ_VALUE]
    nice = [r for r in requirements if r["type"] != "must" and r["status"] in REQ_VALUE]
    unclear = sum(1 for r in requirements if r["type"] == "must" and r["status"] == "unclear")
    if not must or unclear > len(must):
        return None, "Không đủ yêu cầu bắt buộc xác định được để tính mức phù hợp."
    share = sum(REQ_VALUE[r["status"]] for r in must) / len(must)
    nice_hit = any(r["status"] in ("met", "mentioned_only") for r in nice)
    has_nice = any(r["type"] != "must" for r in requirements)  # undecided nice-to-haves still count as existing
    score = 0 if share < 0.2 else 1 if share < 0.4 else 2 if share < 0.6 else 3 if share < 0.8 else \
        4 if (nice_hit or not has_nice) else 3
    met = sum(r["status"] == "met" for r in must)
    half = sum(r["status"] == "mentioned_only" for r in must)
    return score, (f"{met}/{len(must)} yêu cầu bắt buộc có bằng chứng sử dụng, {half} chỉ được liệt kê "
                   f"(tỉ lệ {share:.0%}); {unclear} chưa xác định.")


# ---------- prompt ----------

def p_schema(requirement_ids: list[str] | None) -> dict[str, Any]:
    evidence = {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["field", "quote"],
                                           "properties": {"field": {"type": "string"}, "quote": {"type": "string"}}}}
    item = {"type": "object", "additionalProperties": False,
            "required": ["status", "score", "evidence", "reason", "suggestion"],
            "properties": {"status": {"type": "string", "enum": ["scored", "missing_in_cv"]}, "score": {"type": "integer"},
                           "evidence": evidence, "reason": {"type": "string"}, "suggestion": {"type": "string"}}}
    requirement = {"type": "object", "additionalProperties": False,
                   "required": ["req_id", "text", "type", "status", "field", "quote", "note"],
                   "properties": {"req_id": {"type": "string"}, "text": {"type": "string"},
                                  "type": {"type": "string", "enum": ["must", "nice"]},
                                  "status": {"type": "string", "enum": list(REQ_STATUSES)},
                                  "field": {"type": "string"}, "quote": {"type": "string"}, "note": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False, "required": ["criteria", "requirements"],
            "properties": {"criteria": {"type": "object", "additionalProperties": False, "required": list(LLM_CRITERIA),
                                        "properties": {c: item for c in LLM_CRITERIA}},
                           "requirements": {"type": "array", "items": requirement}}}


def requirement_text(requirements: list[dict[str, str]] | None) -> str:
    if not requirements:
        return ("## Yêu cầu của JD\nTự tách JD thành các yêu cầu nguyên tử (mỗi công nghệ hoặc kỹ năng một dòng), "
                "đặt req_id R1, R2, ...; type = must cho yêu cầu bắt buộc, nice cho yêu cầu ưu tiên hoặc điểm cộng.")
    lines = [f"- {r['req_id']} [{r['type']}] {r['text']}" for r in requirements]
    return "## Yêu cầu của JD cần xét (giữ nguyên req_id, text và type)\n" + "\n".join(lines)


def _clean(raw: dict[str, Any], criteria: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    source = raw.get("criteria") if isinstance(raw.get("criteria"), dict) else raw
    out = {}
    for criterion in criteria:
        item = source.get(criterion)
        if not isinstance(item, dict) or "score" not in item:
            raise rs.ScoringError(f"Kết quả chấm điểm thiếu tiêu chí {criterion}.")
        try:
            score = max(0, min(4, int(round(float(item["score"])))))
        except (TypeError, ValueError) as exc:
            raise rs.ScoringError(f"Điểm của {criterion} không hợp lệ.") from exc
        status = "missing_in_cv" if item.get("status") == "missing_in_cv" else "scored"
        evidence = [e for e in item.get("evidence") or [] if isinstance(e, dict)][:3]
        out[criterion] = {"status": status, "score": 0 if status == "missing_in_cv" else score, "evidence": evidence,
                          "reason": str(item.get("reason") or "")[:600], "suggestion": str(item.get("suggestion") or "")[:600]}
    return out


# ---------- scoring ----------

def score(strategy: str, *, cv_schema: dict[str, Any], jd_text: str, document: dict[str, Any], call: rs.Caller,
          retrieve: rs.Retrieve | None = None, requirements: list[dict[str, str]] | None = None,
          rubric: dict[str, Any] | None = None, kb: list[dict[str, Any]] | None = None,
          progress: Callable[[str], None] = lambda message: None, model: str = rs.GROQ_MODEL) -> dict[str, Any]:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown P strategy {strategy}")
    verify, abstain = strategy != "p_no_verify", strategy != "p_no_abstain"
    rubric = rubric or rs.load_rubric()
    weights = {c["id"]: float(c["weight"]) for c in rubric["criteria"]}
    names = {c["id"]: c["name"] for c in rubric["criteria"]}
    cv, facts = rs.cv_payload(cv_schema), rs.pdf_facts(document, cv_schema)
    flags = content_flags(document, cv) if abstain else []
    started = time.perf_counter()
    usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}

    progress("P · đang truy xuất tri thức tham khảo...")
    context, retrieval = rs.rag_context(cv, jd_text, retrieve, kb)

    def ask(criteria: tuple[str, ...], extra: str = "", with_requirements: bool = True) -> dict[str, Any]:
        user = rs.build_user_message(facts, cv, jd_text, rs.rubric_text(rubric, criteria), context)
        if with_requirements:
            user += "\n\n" + requirement_text(requirements)
        if extra:
            user += "\n\n" + extra
        schema = p_schema(None)
        if not with_requirements:
            schema = {**schema, "required": ["criteria"], "properties": {"criteria": {
                **schema["properties"]["criteria"], "required": list(criteria),
                "properties": {c: schema["properties"]["criteria"]["properties"][c] for c in criteria}}}}
        raw, used = call([{"role": "system", "content": P_RULES}, {"role": "user", "content": user}], schema, 4000)
        usage["calls"] += 1
        usage["input_tokens"] += used.get("input_tokens", 0)
        usage["output_tokens"] += used.get("output_tokens", 0)
        return raw

    progress("P · đang chấm 6 tiêu chí và từng yêu cầu của JD...")
    raw = ask(LLM_CRITERIA)
    items = _clean(raw, LLM_CRITERIA)
    raw_requirements = [r for r in raw.get("requirements") or [] if isinstance(r, dict)]

    # Step 2: verify evidence; ask once more for scores left without valid evidence.
    stats = {"evidence_total": 0, "evidence_valid": 0, "rescored": [], "abstained": []}
    for criterion in LLM_CRITERIA:
        items[criterion] = verify_criterion(cv, items[criterion], criterion)
        stats["evidence_total"] += len(items[criterion]["evidence_checked"])
        stats["evidence_valid"] += items[criterion]["valid_evidence"]
    unsupported = tuple(c for c in LLM_CRITERIA if verify and items[c]["status"] == "scored"
                        and items[c]["score"] > 0 and items[c]["valid_evidence"] == 0)
    if unsupported:
        progress("P · đang chấm lại các tiêu chí thiếu bằng chứng hợp lệ...")
        bad = "; ".join(f"{c}: " + ", ".join(f"\"{e['quote'][:80]}\"" for e in items[c]["evidence_checked"]) for c in unsupported)
        retry = _clean(ask(unsupported, with_requirements=False, extra=(
            "## Chấm lại\nCác trích dẫn sau không tìm thấy nguyên văn trong đúng trường của CV: " + bad +
            "\nChấm lại riêng các tiêu chí này. Chỉ chép nguyên văn từ JSON CV; nếu không tìm được câu chữ chứng minh "
            "thì hạ điểm theo mô tả neo.")), unsupported)
        for criterion in unsupported:
            items[criterion] = {**verify_criterion(cv, retry[criterion], criterion), "rescored": True}
            stats["rescored"].append(criterion)

    criteria_out: dict[str, dict[str, Any]] = {}
    for criterion in LLM_CRITERIA:
        item = items[criterion]
        status = item["status"]
        if verify and abstain and status == "scored" and item["score"] > 0 and item["valid_evidence"] == 0:
            status = "needs_verification"
        if flags and (status == "missing_in_cv" or (status == "scored" and item["score"] == 0)):
            status = "needs_verification"
        if status == "needs_verification":
            stats["abstained"].append(criterion)
        evidence = "; ".join(e["quote"] for e in item["evidence_checked"] if e["check"] in ("field", "section")) \
            if verify else "; ".join(e["quote"] for e in item["evidence_checked"])
        criteria_out[criterion] = {"status": status, "score": None if status == "needs_verification" else item["score"],
                                   "evidence": evidence or item["reason"], "reason": item["reason"],
                                   "suggestion": item["suggestion"], "scored_by": "llm_verified" if verify else "llm",
                                   "evidence_checked": item["evidence_checked"], "rescored": bool(item.get("rescored"))}

    # Requirements and C8.
    given = {str(r.get("req_id")): r for r in raw_requirements}
    listed = requirements or [{"req_id": str(r.get("req_id") or f"R{i + 1}"), "type": "must" if r.get("type") == "must" else "nice",
                               "text": str(r.get("text") or "")} for i, r in enumerate(raw_requirements)]
    req_out = []
    for req in listed:
        answer = given.get(req["req_id"], {})
        claimed = answer.get("status") if answer.get("status") in REQ_STATUSES else "unclear"
        status, why = verify_requirement(cv, {**answer, "text": req["text"]}, claimed) if verify else (claimed, "")
        if flags and status == "missing":
            status, why = "unclear", "trích xuất có thể đã mất nội dung"
        req_out.append({"req_id": req["req_id"], "type": req["type"], "text": req["text"], "claimed": claimed,
                        "status": status, "quote": str(answer.get("quote") or "")[:300], "check_note": why})
    c8, c8_note = c8_from_requirements(req_out)
    if c8 is None and not abstain:
        c8 = 0
    criteria_out[REQUIREMENT_CRITERION] = {
        "status": "needs_verification" if c8 is None else "scored", "score": c8, "evidence": c8_note, "reason": c8_note,
        "suggestion": "Với yêu cầu bắt buộc còn thiếu, chỉ ghi vào CV khi bạn đã thực sự dùng; nếu chưa, làm một dự án nhỏ để có minh chứng."
        if c8 is not None and c8 < 4 else "", "scored_by": "requirements"}
    if c8 is None:
        stats["abstained"].append(REQUIREMENT_CRITERION)
    ats = rs.ats_from_pdf(facts)
    criteria_out[rs.ATS] = {"status": "scored", "score": ats["score"], "evidence": ats["evidence"],
                            "suggestion": ats["suggestion"], "scored_by": "pdf"}

    return aggregate(strategy, rubric, criteria_out, req_out, names, weights, flags=flags, stats=stats,
                     retrieval=retrieval, document=document, usage=usage, latency=time.perf_counter() - started,
                     model=model)


def aggregate(strategy: str, rubric: dict[str, Any], items: dict[str, dict[str, Any]], requirements: list[dict[str, Any]],
              names: dict[str, str], weights: dict[str, float], *, flags: list[str], stats: dict[str, Any],
              retrieval: dict[str, Any] | None, document: dict[str, Any], usage: dict[str, int], latency: float,
              model: str) -> dict[str, Any]:
    criteria = []
    for criterion in rubric["criteria"]:
        item = items[criterion["id"]]
        scored = item["score"] is not None
        criteria.append({"id": criterion["id"], "name": names[criterion["id"]], "weight": criterion["weight"],
                         "status": item["status"], "score": item["score"],
                         "weighted": round(criterion["weight"] * item["score"] / 4, 2) if scored else None,
                         "evidence": item["evidence"], "suggestion": item["suggestion"], "scored_by": item["scored_by"],
                         "initial_score": None, "evidence_checked": item.get("evidence_checked", []),
                         "rescored": item.get("rescored", False)})
    usable = [c for c in criteria if c["score"] is not None]
    weight_all = sum(weights.values())
    weight_ok = sum(c["weight"] for c in usable)
    q = round(100 * sum(c["weight"] * c["score"] for c in usable) / (4 * weight_ok), 1) if weight_ok else 0.0
    coverage = round(weight_ok / weight_all, 3)
    scored_ids = {c["id"] for c in usable}
    required_ok = all(any(c in scored_ids for c in group) for group in REQUIRED_FOR_TOTAL)
    shown = coverage >= COVERAGE_MIN and required_ok
    verdict = ("Tốt" if q >= 80 else "Khá" if q >= 65 else "Trung bình" if q >= 50 else "Cần cải thiện") if shown \
        else "Cần kiểm tra lại trích xuất"
    to_check = [f"{c['name']}: chưa đủ căn cứ để chấm" for c in criteria if c["status"] == "needs_verification"]
    strengths = [f"{c['name']} ({c['score']}/4): {c['evidence']}" for c in sorted(usable, key=lambda c: -c["weighted"])
                 if c["score"] >= 3 and c["evidence"]]
    improvements = [f"{c['name']} ({c['score']}/4): {c['suggestion']}"
                    for c in sorted(usable, key=lambda c: -(c["weight"] * (4 - c["score"]))) if c["score"] < 4 and c["suggestion"]]
    return {
        "result_type": "rubric_v2", "rubric_version": rubric["rubric_version"], "strategy": strategy,
        "method": f"{STRATEGIES[strategy]} · {model} · {rubric['rubric_version']}",
        "total_score": q, "total_shown": shown, "coverage": coverage, "verdict": verdict,
        "criteria": criteria, "requirements": requirements, "content_flags": flags,
        "verification": {"evidence_total": stats["evidence_total"], "evidence_valid": stats["evidence_valid"],
                         "rescored": stats["rescored"], "abstained": stats["abstained"]},
        "strengths": strengths[:4], "improvements": (to_check + improvements)[:6], "overall_comment": "",
        "retrieval": retrieval, "provider": "groq", "model": model, "calls": usage["calls"],
        "input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"],
        "latency_seconds": round(latency, 2), "extraction": document,
    }
