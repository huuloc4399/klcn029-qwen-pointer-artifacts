import json

import cv_evaluation_web.services.llm_matching as llm_matching
from cv_evaluation_web.services.llm_matching import (
    MATCHING_STRATEGIES,
    _cv_payload,
    _prompt,
    evaluate_with_strategy,
    retrieve_knowledge,
)


CV = {
    "personal_info": {"name": "PRIVATE", "email": "private@example.com"},
    "summary": "Backend developer",
    "skills": {"hard_skills": ["Python", "FastAPI"], "soft_skills": ["Communication"]},
    "experience": [], "projects": [], "education": [],
    "certifications": [], "activities": [], "awards": [],
}


def test_personal_info_is_not_sent_to_external_matching():
    payload = _cv_payload(CV)
    assert "personal_info" not in payload
    assert "private@example.com" not in str(payload)


def test_all_expected_strategies_are_named():
    assert set(MATCHING_STRATEGIES) == {"deterministic_b1", "zero_shot_m1", "few_shot_m2", "rag_m3"}


def test_few_shot_prompt_contains_examples():
    prompt, retrieved = _prompt("few_shot_m2", CV, "Need Python and Docker", 18)
    assert "Example A" in prompt and not retrieved


def test_rag_prompt_has_retrieval_log_with_provenance_status():
    prompt, retrieved = _prompt("rag_m3", CV, "Need Python and Docker", 18)
    assert retrieved and all(item["source_status"] == "internal_project_rubric" for item in retrieved)
    assert retrieved[0]["id"] in prompt


def test_retrieval_is_deterministic():
    assert retrieve_knowledge(CV, "Need Python") == retrieve_knowledge(CV, "Need Python")


def test_zero_shot_maps_strict_json_to_common_result_contract():
    llm_payload = {
        "impact_score": 20.0, "impact_notes": "grounded",
        "semantic_score": 25.0, "semantic_notes": "2/3",
        "tone_score": 10.0, "tone_notes": "active",
        "must_have_coverage": 0.6667,
        "matched_skills": ["Python", "FastAPI"], "missing_skills": ["Docker"],
        "unverified_skills": [], "action_verbs_found": ["Built"],
        "passive_phrases_found": [], "quantified_lines": 1,
        "strengths": ["Python evidence"], "improvements": ["Learn Docker"],
    }

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(llm_payload)}}]}

    captured = {}

    def fake_post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return FakeResponse()

    original = llm_matching.requests.post
    llm_matching.requests.post = fake_post
    try:
        output = evaluate_with_strategy(
            strategy="zero_shot_m1", cv_schema=CV, jd_text="Need Python FastAPI Docker " * 5,
            deterministic_result={
                "scores": {"ats": 18.0}, "score_notes": {"ats": "PDF evidence"},
                "cv_skills": ["Python", "FastAPI"], "jd_skills": ["Python", "FastAPI", "Docker"],
                "extraction": {"page_count": 1},
            },
            api_key="test-only-key",
        )
    finally:
        llm_matching.requests.post = original

    assert output["total_score"] == 73.0
    assert output["strategy"] == "zero_shot_m1" and output["matched_skills"] == ["Python", "FastAPI"]
    assert captured["json"]["response_format"]["json_schema"]["strict"] is True
    assert "personal_info" not in captured["json"]["messages"][1]["content"]
