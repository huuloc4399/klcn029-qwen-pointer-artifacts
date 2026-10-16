"""Rubric v2 strategies M1–M4: web flow with a fake Groq caller, privacy of the payload, fallbacks.

Run from the project root: PYTHONPATH=. python -m unittest cv_evaluation_web/tests/test_rubric_scoring.py -v
"""

from __future__ import annotations

import copy
import io
import json
import shutil
import sys
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cv_evaluation_web"))
sys.path.insert(0, str(ROOT / "cv_evaluation_web/tests"))
import test_web as base  # noqa: E402
from app import create_app  # noqa: E402
from services import rubric_scoring  # noqa: E402

RUBRIC = rubric_scoring.load_rubric()
LLM_CRITERIA = [c["id"] for c in RUBRIC["criteria"] if c["id"] != "C7_ats"]


class FakeGroq:
    """Answers every call with fixed scores for the criteria named in the requested schema."""

    def __init__(self, scores=None, fail=None, critic_scores=None):
        self.scores = scores or {"C1_structure": 3, "C2_it_content": 4, "C3_skills": 3, "C4_projects": 4,
                                 "C5_experience": 2, "C6_certs_activities": 0, "C8_jd_fit": 3}
        self.critic_scores = critic_scores
        self.fail = fail
        self.calls = []

    def __call__(self, messages, schema, max_tokens):
        self.calls.append({"messages": messages, "schema": schema})
        if self.fail:
            raise self.fail
        is_critic = "overall_comment" in schema["properties"]
        source = self.critic_scores if is_critic and self.critic_scores else self.scores
        answer = {cid: {"score": source[cid], "evidence": f"bằng chứng {cid}", "suggestion": f"gợi ý {cid}"}
                  for cid in schema["properties"] if cid != "overall_comment"}
        if is_critic:
            answer["overall_comment"] = "Ứng viên phù hợp một phần."
        return answer, {"input_tokens": 1000, "output_tokens": 200}


class RetrievingSpaceClient(base.FakeSpaceClient):
    def __init__(self, final, fail_retrieve=False):
        super().__init__(final)
        self.fail_retrieve = fail_retrieve
        self.queries = []

    def retrieve(self, query, top_k=3, roles=None):
        self.queries.append((query, top_k, roles))
        if self.fail_retrieve:
            raise RuntimeError("embedding down")
        kb = {row["id"]: row for row in rubric_scoring.load_kb()}
        ids = ["kb_backend_core"] if roles == ["backend", "frontend"] else ["kb_project_quality", "kb_impact_bullet"]
        return {"backend": "bge-m3 (test)", "results": [{**kb[i], "score": 0.8} for i in ids[:top_k]]}


def remote_output_with_contact():
    output = copy.deepcopy(base.REMOTE_OUTPUT)
    output["cv"]["summary"] = "Backend developer seeking a junior role. Contact me at dev.person@example.com."
    output["cv"]["personal_info"]["github_url"] = "https://github.com/secret-person"
    output["cv"]["projects"][0]["details"] += " Source: github.com/secret-person/booking-api"
    return output


class StrategyFlowTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = ROOT / "cv_evaluation_web" / "data" / ".qa" / uuid.uuid4().hex
        self.tempdir.mkdir(parents=True, exist_ok=False)
        self.addCleanup(shutil.rmtree, self.tempdir, ignore_errors=True)

    def client(self, groq=None, remote=None, groq_key=True):
        self.groq = groq or FakeGroq()
        self.remote = remote or RetrievingSpaceClient({"status": "COMPLETED", "output": remote_output_with_contact()})
        config = {"TESTING": True, "DATA_DIR": str(self.tempdir), "PIPELINE_MODE": "hf_space",
                  "REMOTE_CLIENT": self.remote, "RESEARCH_ENABLED": False, "CSRF_ENABLED": False}
        if groq_key:
            config["GROQ_CALLER"] = self.groq
        return create_app(config).test_client()

    def run_job(self, client, strategy, consent=True):
        data = {"cv_file": (io.BytesIO(base.sample_pdf()), "candidate.pdf"), "jd_text": base.JD_TEXT,
                "language": "en", "consent_evaluation": "yes", "strategy": strategy}
        if consent:
            data["consent_llm"] = "yes"
        response = client.post("/evaluate", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 303)
        token = response.headers["Location"].rstrip("/").split("/")[-1]
        statuses = []
        for _ in range(100):
            body = client.get(f"/api/jobs/{token}").get_json()
            statuses.append(body["status"])
            if body["status"] == "COMPLETED":
                return client.get(body["result_url"]).get_data(as_text=True), statuses
            time.sleep(0.02)
        self.fail(f"job did not finish: {statuses[-5:]}")

    def test_m1_scores_eight_criteria_with_pdf_based_ats_and_masked_payload(self):
        client = self.client()
        page, statuses = self.run_job(client, "m1_zero_shot")
        self.assertIn("SCORING", statuses)
        self.assertEqual(len(self.groq.calls), 1)
        self.assertIn("Chi tiết 8 tiêu chí", page)
        self.assertIn("chấm từ phân tích PDF", page)
        self.assertIn("M1 · Zero-shot", page)
        call = self.groq.calls[0]
        self.assertEqual(sorted(call["schema"]["properties"]), sorted(LLM_CRITERIA))
        sent = json.dumps(call["messages"], ensure_ascii=False)
        self.assertNotIn("dev.person@example.com", sent)
        self.assertNotIn("secret-person", sent)
        self.assertNotIn("personal_info", sent)
        self.assertIn("[LINK]", sent)  # the project still shows it has a repository link
        self.assertNotIn("hãy cho 3 hoặc 4", sent)
        # LLM: 3,4,3,4,2,0 and C8 3; C7 comes from the PDF facts: the fixture has 240 characters of
        # text, which the ATS rule scores 1/4. Weights 10,10,15,15,10,5,10,25.
        self.assertIn("Lớp chữ của PDF thiếu hoặc quá ít", page)
        expected = 10 * 3 / 4 + 10 + 15 * 3 / 4 + 15 + 10 * 2 / 4 + 0 + 10 * 1 / 4 + 25 * 3 / 4
        self.assertIn(f"<strong>{round(expected)}</strong>", page)

    def test_without_llm_consent_falls_back_to_rules_with_a_note(self):
        client = self.client()
        page, statuses = self.run_job(client, "m2_few_shot", consent=False)
        self.assertNotIn("SCORING", statuses)
        self.assertEqual(self.groq.calls, [])
        self.assertIn("chưa đồng ý gửi CV", page)
        self.assertIn("Chấm theo quy tắc trên máy chủ của nhóm", page)  # rubric v2 by rules, no Groq call

    def test_m3_uses_api_retrieval_and_falls_back_to_bm25(self):
        client = self.client()
        page, _ = self.run_job(client, "m3_rag")
        self.assertIn("bge-m3 (test)", page)
        self.assertIn("Yêu cầu thường gặp của JD backend", page)
        (jd_query, _, jd_roles), (cv_text_query, cv_k, cv_roles) = self.remote.queries
        self.assertIn("Kỹ năng trong CV", jd_query)
        self.assertEqual((jd_roles, cv_roles, cv_k), (["backend", "frontend"], ["all"], 2))
        self.assertIn("Built a REST API", cv_text_query)
        self.assertIn("Mô tả dự án đầy đủ", page)
        self.assertIn("Tri thức tham khảo nội bộ", self.groq.calls[0]["messages"][1]["content"])
        failing = RetrievingSpaceClient({"status": "COMPLETED", "output": base.REMOTE_OUTPUT}, fail_retrieve=True)
        page, _ = self.run_job(self.client(remote=failing), "m3_rag")
        self.assertIn("BM25 dự phòng", page)

    def test_m4_runs_three_agents_and_limits_the_critic_to_one_point(self):
        critic = {cid: 0 for cid in LLM_CRITERIA}  # tries to push every score to 0
        client = self.client(groq=FakeGroq(critic_scores=critic))
        page, _ = self.run_job(client, "m4_multi_agent")
        self.assertEqual(len(self.groq.calls), 3)
        self.assertEqual(sorted(self.groq.calls[0]["schema"]["properties"]), sorted(rubric_scoring.HR_CRITERIA))
        self.assertEqual(sorted(self.groq.calls[1]["schema"]["properties"]), sorted(rubric_scoring.TECH_CRITERIA))
        self.assertIn("phản biện đổi từ 4/4", page)  # C2 4 -> at most 3
        self.assertIn("Ứng viên phù hợp một phần.", page)

    def test_groq_failure_returns_rule_based_result_with_reason(self):
        failing = FakeGroq(fail=rubric_scoring.ScoringError("Dịch vụ Groq đang quá tải."))
        page, _ = self.run_job(self.client(groq=failing), "m1_zero_shot")
        self.assertIn("Chưa chấm được bằng M1 · Zero-shot", page)
        self.assertIn("Dịch vụ Groq đang quá tải.", page)
        self.assertIn("Chấm theo quy tắc trên máy chủ của nhóm", page)
        self.assertIn("Chi tiết 8 tiêu chí", page)

    def test_without_groq_key_only_rules_are_offered(self):
        client = self.client(groq_key=False)
        home = client.get("/").get_data(as_text=True)
        self.assertNotIn('name="strategy" value="m1_zero_shot"', home)
        self.assertNotIn("consent_llm", home)
        page, statuses = self.run_job(client, "m1_zero_shot")
        self.assertNotIn("SCORING", statuses)
        self.assertIn("Chấm theo quy tắc trên máy chủ của nhóm", page)


class ScoringUnitTests(unittest.TestCase):
    def facts(self, **changes):
        facts = {"page_count": 1, "pages_with_text_layer": 1, "characters": 2400, "needs_ocr": False,
                 "likely_multi_column": False, "sections_found": ["summary", "skills", "projects", "education"]}
        facts.update(changes)
        return facts

    def test_ats_from_pdf_follows_anchors(self):
        self.assertEqual(rubric_scoring.ats_from_pdf(self.facts())["score"], 4)
        self.assertEqual(rubric_scoring.ats_from_pdf(self.facts(page_count=3))["score"], 3)
        self.assertEqual(rubric_scoring.ats_from_pdf(self.facts(sections_found=["summary", "skills"]))["score"], 3)
        self.assertEqual(rubric_scoring.ats_from_pdf(self.facts(likely_multi_column=True))["score"], 2)
        self.assertEqual(rubric_scoring.ats_from_pdf(self.facts(characters=300))["score"], 1)
        self.assertEqual(rubric_scoring.ats_from_pdf(self.facts(needs_ocr=True, pages_with_text_layer=0))["score"], 0)

    def test_bm25_prefers_matching_chunks_and_respects_roles(self):
        kb = rubric_scoring.load_kb()
        top = rubric_scoring.lexical_retrieve("frontend React TypeScript responsive", kb, top_k=1)
        self.assertEqual(top[0]["id"], "kb_frontend_core")
        general = rubric_scoring.lexical_retrieve("frontend React TypeScript", kb, top_k=12, roles=["all"])
        self.assertNotIn("kb_frontend_core", [chunk["id"] for chunk in general])

    def test_groq_caller_retries_rate_limits_and_falls_back_to_json_object(self):
        class Response:
            def __init__(self, status, body=None, text="", headers=None):
                self.status_code, self._body, self.text, self.headers = status, body, text, headers or {}

            def json(self):
                return self._body

        ok = Response(200, {"choices": [{"message": {"content": '{"C1_structure": {"score": 3}}'}}],
                            "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
        replies = [Response(400, text="response_format json_schema not supported"),
                   Response(429, headers={"retry-after": "1"}), ok]
        sleeps = []
        with mock.patch.object(rubric_scoring.requests, "post", side_effect=replies) as post:
            parsed, usage = rubric_scoring.groq_caller("key", sleep=sleeps.append)([{"role": "user", "content": "x"}], {}, 10)
        self.assertEqual(parsed["C1_structure"]["score"], 3)
        self.assertEqual(usage, {"input_tokens": 10, "output_tokens": 5})
        self.assertEqual(post.call_args_list[1].kwargs["json"]["response_format"], {"type": "json_object"})
        self.assertEqual(len(sleeps), 1)
        with mock.patch.object(rubric_scoring.requests, "post", return_value=Response(429)):
            with self.assertRaises(rubric_scoring.ScoringError):
                rubric_scoring.groq_caller("key", sleep=lambda _: None)([], {}, 10)
        # A per-minute limit is waited out when the caller allows it; a daily quota fails at once.
        sleeps = []
        with mock.patch.object(rubric_scoring.requests, "post", side_effect=[Response(429, headers={"retry-after": "45"}), ok]):
            rubric_scoring.groq_caller("key", max_wait=90, sleep=sleeps.append)([], {}, 10)
        self.assertEqual(sleeps, [45.0])
        sleeps = []
        with mock.patch.object(rubric_scoring.requests, "post", return_value=Response(429, headers={"retry-after": "3600"})):
            with self.assertRaisesRegex(rubric_scoring.ScoringError, "hạn mức.*3600 giây"):
                rubric_scoring.groq_caller("key", max_wait=90, sleep=sleeps.append)([], {}, 10)
        self.assertEqual(sleeps, [])

    def test_scores_are_clamped_and_missing_criteria_rejected(self):
        cleaned = rubric_scoring._clean_scores({"C1_structure": {"score": 7, "evidence": "e", "suggestion": "s"}},
                                               ("C1_structure",))
        self.assertEqual(cleaned["C1_structure"]["score"], 4)
        with self.assertRaises(rubric_scoring.ScoringError):
            rubric_scoring._clean_scores({}, ("C1_structure",))


if __name__ == "__main__":
    unittest.main()
