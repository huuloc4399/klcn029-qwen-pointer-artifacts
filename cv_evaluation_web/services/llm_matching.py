"""Experimental Groq matching strategies sharing the deterministic result contract."""

from __future__ import annotations

import copy
import json
import re
import time
import unicodedata
from typing import Any

import requests
from pydantic import BaseModel, ConfigDict, Field


GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MATCHING_MODEL = "qwen/qwen3.8-27b"
MATCHING_STRATEGIES = {
    "deterministic_b1": "B1 · Deterministic baseline",
    "zero_shot_m1": "M1 · Zero-shot (Groq Qwen 3.8 27B)",
    "few_shot_m2": "M2 · Few-shot (Groq Qwen 3.8 27B)",
    "rag_m3": "M3 · RAG thử nghiệm (Groq Qwen 3.8 27B)",
}


class MatchingLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    impact_score: float = Field(ge=0, le=30)
    impact_notes: str
    semantic_score: float = Field(ge=0, le=35)
    semantic_notes: str
    tone_score: float = Field(ge=0, le=15)
    tone_notes: str
    must_have_coverage: float = Field(ge=0, le=1)
    matched_skills: list[str]
    missing_skills: list[str]
    unverified_skills: list[str]
    action_verbs_found: list[str]
    passive_phrases_found: list[str]
    quantified_lines: int = Field(ge=0)
    strengths: list[str]
    improvements: list[str]


KNOWLEDGE_DOCS = (
    {
        "id": "project_rubric_skill_evidence_v1",
        "source_status": "internal_project_rubric",
        "text": (
            "Only count a JD skill as matched when the CV explicitly states the skill or an approved alias. "
            "A skill listed without experience or project evidence may be reported as unverified. Never invent experience."
        ),
    },
    {
        "id": "project_rubric_impact_v1",
        "source_status": "internal_project_rubric",
        "text": (
            "Impact evidence combines a concrete action, its context and an observable result. Quantified results are stronger, "
            "but absence of a number alone does not prove that an achievement is false."
        ),
    },
    {
        "id": "project_rubric_tone_v1",
        "source_status": "internal_project_rubric",
        "text": (
            "Prefer specific action verbs and direct descriptions of contribution. Flag passive phrases such as responsible for, "
            "participated in, helped with or worked on when a more precise action is available."
        ),
    },
    {
        "id": "project_rubric_ats_v1",
        "source_status": "internal_project_rubric",
        "text": (
            "ATS layout evidence must come from the PDF analysis. An LLM receiving structured CV text must not infer fonts, columns, "
            "icons or reading order. The ATS score supplied by the deterministic PDF analyzer is fixed."
        ),
    },
)


FEW_SHOT_EXAMPLES = """
Example A: CV explicitly states Python and FastAPI in a project; JD requires Python, FastAPI and Docker.
Expected: matched_skills=["Python","FastAPI"], missing_skills=["Docker"], must_have_coverage=0.6667.
Do not claim Docker experience or recommend adding it unless the candidate truly has it.

Example B: CV lists AWS in Skills but no experience/project mentions AWS; JD requires AWS.
Expected: AWS can be matched lexically and must also appear in unverified_skills. The improvement should ask for truthful evidence or removal.
""".strip()


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#.]{3,}", _fold(value)))


def retrieve_knowledge(cv_schema: dict[str, Any], jd_text: str, top_k: int = 3) -> list[dict[str, str]]:
    skills = cv_schema.get("skills") or {}
    query = jd_text + " " + " ".join(skills.get("hard_skills", []) + skills.get("soft_skills", []))
    query_tokens = _tokens(query)
    ranked = []
    for position, document in enumerate(KNOWLEDGE_DOCS):
        overlap = len(query_tokens & _tokens(document["text"]))
        ranked.append((-overlap, position, document))
    return [copy.deepcopy(item[2]) for item in sorted(ranked)[:top_k]]


def _cv_payload(cv_schema: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "summary", "skills", "experience", "projects", "education",
        "certifications", "activities", "awards",
    )
    return {key: copy.deepcopy(cv_schema.get(key)) for key in allowed}


def _prompt(strategy: str, cv_schema: dict[str, Any], jd_text: str, fixed_ats: float) -> tuple[str, list[dict[str, str]]]:
    retrieved: list[dict[str, str]] = []
    strategy_context = "No examples or retrieved knowledge are provided. Evaluate zero-shot."
    if strategy == "few_shot_m2":
        strategy_context = "Use these formatting and evidence examples:\n" + FEW_SHOT_EXAMPLES
    elif strategy == "rag_m3":
        retrieved = retrieve_knowledge(cv_schema, jd_text)
        strategy_context = "Use the retrieved internal project rubric below. Do not present it as an external academic quotation:\n" + json.dumps(retrieved, ensure_ascii=False)

    prompt = f"""You are an evidence-grounded CV-to-JD matching engine.
Strategy: {strategy}
{strategy_context}

The PDF analyzer already fixed ATS score at {fixed_ats}/20. Do not rescore layout.
Score only Impact (0-30), Semantic match (0-35), and Tone (0-15).
Use only facts explicitly present in CVSchema and JD. Never invent skills, years, metrics or achievements.
Keep improvements truthful: recommend adding a missing skill only if the candidate actually has it; otherwise recommend learning it.

=== CVSchema 2.0 without personal contact fields ===
{json.dumps(_cv_payload(cv_schema), ensure_ascii=False)}

=== JOB DESCRIPTION ===
{jd_text}

Return data matching the required JSON schema. matched_skills and missing_skills must be grounded in the JD.
"""
    return prompt, retrieved


def evaluate_with_strategy(
    *,
    strategy: str,
    cv_schema: dict[str, Any],
    jd_text: str,
    deterministic_result: dict[str, Any],
    api_key: str,
    timeout_seconds: int = 90,
) -> dict[str, Any]:
    if strategy not in {"zero_shot_m1", "few_shot_m2", "rag_m3"}:
        raise ValueError(f"Unsupported LLM matching strategy: {strategy}")
    if not api_key.strip():
        raise ValueError("GROQ_API_KEY is required for M1, M2 and M3")

    fixed_ats = float(deterministic_result["scores"]["ats"])
    prompt, retrieved = _prompt(strategy, cv_schema, jd_text, fixed_ats)
    schema = MatchingLLMOutput.model_json_schema()
    started = time.perf_counter()
    response = requests.post(
        GROQ_CHAT_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": GROQ_MATCHING_MODEL,
            "messages": [
                {"role": "system", "content": "Return only evidence-grounded structured matching data."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "reasoning_effort": "none",
            "max_tokens": 1600,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "cv_jd_matching", "strict": True, "schema": schema},
            },
        },
        timeout=timeout_seconds,
    )
    if response.status_code >= 400:
        detail = response.text[:800]
        raise RuntimeError(f"Groq matching HTTP {response.status_code}: {detail}")
    body = response.json()
    raw = body["choices"][0]["message"]["content"]
    parsed = MatchingLLMOutput.model_validate_json(raw)
    latency = time.perf_counter() - started
    total = round(fixed_ats + parsed.impact_score + parsed.semantic_score + parsed.tone_score, 1)
    verdict = "Rất phù hợp" if total >= 85 else "Phù hợp" if total >= 70 else "Cần bổ sung" if total >= 50 else "Cần cải thiện nhiều"

    return {
        "total_score": total,
        "verdict": verdict,
        "scores": {
            "ats": fixed_ats,
            "impact": round(parsed.impact_score, 1),
            "semantic": round(parsed.semantic_score, 1),
            "tone": round(parsed.tone_score, 1),
        },
        "score_notes": {
            "ats": deterministic_result["score_notes"]["ats"],
            "impact": parsed.impact_notes,
            "semantic": parsed.semantic_notes,
            "tone": parsed.tone_notes,
        },
        "cv_skills": deterministic_result["cv_skills"],
        "jd_skills": deterministic_result["jd_skills"],
        "matched_skills": parsed.matched_skills,
        "missing_skills": parsed.missing_skills,
        "unverified_skills": parsed.unverified_skills,
        "must_have_coverage": round(parsed.must_have_coverage, 4),
        "action_verbs_found": parsed.action_verbs_found,
        "passive_phrases_found": parsed.passive_phrases_found,
        "quantified_lines": parsed.quantified_lines,
        "strengths": parsed.strengths[:5],
        "improvements": parsed.improvements[:5],
        "extraction": deterministic_result["extraction"],
        "method": MATCHING_STRATEGIES[strategy],
        "strategy": strategy,
        "provider": "groq",
        "model": GROQ_MATCHING_MODEL,
        "latency_seconds": round(latency, 3),
        "retrieved_sources": [
            {"id": item["id"], "source_status": item["source_status"]} for item in retrieved
        ],
    }
