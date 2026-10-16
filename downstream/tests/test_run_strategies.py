"""Strategy runner: same inputs for every strategy, resumable runs, and the comparison with human labels.

Run from the project root: python -m unittest downstream/tests/test_run_strategies.py -v
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from downstream.eval import run_strategies as rs

CV = {
    "personal_info": {"name": "[MASKED]", "email": "[MASKED]", "phone": "[MASKED]", "github_url": "", "linkedin_url": ""},
    "summary": "Backend developer intern focused on Java and Spring Boot.",
    "skills": {"hard_skills": ["Java", "Spring Boot", "MySQL", "Git"], "soft_skills": ["Teamwork"]},
    "experience": [],
    "projects": [{"name": "Library API", "role": "Backend developer", "technologies": ["Java", "Spring Boot", "MySQL"],
                  "details": "Built a REST API for 200 users with Spring Boot and MySQL, deployed with Docker."}],
    "education": [{"degree": "Bachelor", "university": "HUIT", "gpa": None, "year_graduated": 2026}],
    "certifications": [], "activities": [], "awards": [],
}
DOCUMENT = {"page_count": 1, "native_text_pages": 1, "character_count": 700, "block_count": 20,
            "likely_multi_column": False, "needs_ocr": False}
JD = "Java Backend Intern. Yêu cầu: Java, Spring Boot, MySQL, REST API, Git."
REQUIREMENTS = [{"req_id": "JD1-M01", "type": "must", "text": "Java"},
                {"req_id": "JD1-M02", "type": "must", "text": "Spring Boot"},
                {"req_id": "JD1-M03", "type": "must", "text": "Docker"},
                {"req_id": "JD1-N01", "type": "nice", "text": "Kubernetes"}]
PAIRS = [{"pair_id": "T1", "cv_id": "CV1", "jd_id": "JD1", "split": "dev"},
         {"pair_id": "T2", "cv_id": "CV2", "jd_id": "JD1", "split": "dev"}]
CONFIG = {"model": "fake-model", "temperature": 0, "seed": 42, "retriever": "bm25", "split": "dev",
          "rubric_version": "rubric_v2_draft1"}


class FakeGroq:
    def __init__(self, score=3, fail_after=None, error=None):
        self.score, self.fail_after, self.error, self.calls = score, fail_after, error, 0

    def __call__(self, messages, schema, max_tokens):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise self.error
        if "criteria" in schema["properties"]:  # method P
            quote = {"field": "projects[0].details", "quote": "Built a REST API for 200 users"}
            items = {c: {"status": "scored", "score": self.score, "evidence": [quote], "reason": "r", "suggestion": "s"}
                     for c in schema["properties"]["criteria"]["required"]}
            reqs = [{"req_id": r["req_id"], "text": r["text"], "type": r["type"], "field": "projects[0].details",
                     "status": "met" if r["text"] == "Spring Boot" else "missing",
                     "quote": "with Spring Boot and MySQL" if r["text"] == "Spring Boot" else "", "note": ""}
                    for r in REQUIREMENTS]
            return {"criteria": items, "requirements": reqs}, {"input_tokens": 3000, "output_tokens": 600}
        answer = {cid: {"score": self.score, "evidence": "Built a REST API", "suggestion": "Thêm kết quả đo được."}
                  for cid in schema["properties"] if cid != "overall_comment"}
        if "overall_comment" in schema["properties"]:
            answer["overall_comment"] = "Phù hợp một phần."
        return answer, {"input_tokens": 1000, "output_tokens": 200}


def load_cv(source, cv_id):
    return None if (source, cv_id) == ("b0", "CV2") else CV


def label(pair_id, cv_id, scores, fit):
    criteria = {cid: {"status": "scored", "score": s} for cid, s in scores.items()}
    criteria["C6_certs_activities"] = {"status": "missing_in_cv", "score": 0}
    return {"pair_id": pair_id, "cv_id": cv_id, "jd_id": "JD1", "overall_fit": fit, "criteria": criteria, "requirements": {}}


class RunStrategiesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.rubric_scoring, _ = rs._web()

    def go(self, call, strategies=("baseline_rules", "m1_zero_shot", "m4_multi_agent"), inputs=("gold", "b0"),
           config=CONFIG, **kw):
        return rs.run(run_dir=self.tmp / "run", pairs=PAIRS, strategies=list(strategies), inputs=list(inputs),
                      repeats=1, config=config, call=call, retrieve=rs.bm25_retriever(self.rubric_scoring),
                      load_cv=load_cv, load_document=lambda cv: DOCUMENT, jd_text=lambda jd: JD,
                      requirements=lambda jd: REQUIREMENTS, log=lambda m: None, **kw)

    def predictions(self):
        return rs._read_jsonl(self.tmp / "run/predictions.jsonl")

    def test_every_strategy_gets_the_same_pairs_and_invalid_extraction_is_recorded(self):
        fake = FakeGroq()
        counts = self.go(fake)
        # 3 strategies x 2 inputs x 2 pairs; the b0 output of CV2 is invalid for every strategy.
        self.assertEqual(counts, {"ok": 9, "skipped": 0, "extraction_invalid": 3, "error": 0})
        self.assertEqual(fake.calls, (1 + 3) * 3)  # M1 one call and M4 three, on 3 valid pair inputs
        records = self.predictions()
        invalid = {(r["strategy"], r["input"], r["pair_id"]) for r in records if r["status"] == "extraction_invalid"}
        self.assertEqual(invalid, {(s, "b0", "T2") for s in ("baseline_rules", "m1_zero_shot", "m4_multi_agent")})
        m4 = next(r for r in records if r["strategy"] == "m4_multi_agent" and r["status"] == "ok")
        self.assertEqual(m4["calls"], 3)
        self.assertEqual(m4["criteria"]["C7_ats"]["scored_by"], "pdf")
        config = json.loads((self.tmp / "run/run_config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["pair_ids"], ["T1", "T2"])

    def test_resume_skips_done_work_and_refuses_changed_conditions(self):
        self.go(FakeGroq())
        again = FakeGroq()
        counts = self.go(again)
        self.assertEqual((counts["ok"], again.calls), (0, 0))
        with self.assertRaises(SystemExit):
            self.go(FakeGroq(), config={**CONFIG, "model": "other-model"})

    def test_quota_stops_the_run_and_the_rerun_retries_the_failed_pair(self):
        quota = self.rubric_scoring.ScoringError("Dịch vụ Groq đang quá tải hoặc vượt hạn mức miễn phí.")
        with self.assertRaises(rs.QuotaExhausted):
            self.go(FakeGroq(fail_after=1, error=quota), strategies=("m1_zero_shot",), inputs=("gold",))
        self.assertEqual([r["status"] for r in self.predictions()], ["ok", "error"])
        counts = self.go(FakeGroq(), strategies=("m1_zero_shot",), inputs=("gold",))
        self.assertEqual((counts["ok"], counts["skipped"]), (1, 1))

    def test_max_calls_stops_cleanly(self):
        fake = FakeGroq()
        self.go(fake, strategies=("m4_multi_agent",), inputs=("gold",), max_calls=3)
        self.assertEqual(fake.calls, 3)
        self.assertEqual(len(self.predictions()), 1)

    def test_baseline_runs_without_a_groq_key_but_llm_strategies_do_not(self):
        counts = self.go(None, strategies=("baseline_rules",), inputs=("gold",))
        self.assertEqual(counts["ok"], 2)
        with self.assertRaises(SystemExit):
            self.go(None, strategies=("m1_zero_shot",), inputs=("gold",))

    def test_report_compares_with_labels_and_the_reference(self):
        self.go(FakeGroq(score=3), strategies=("baseline_rules", "m1_zero_shot", "m3_rag"), inputs=("gold",))
        human = {"C1_structure": 3, "C2_it_content": 3, "C3_skills": 2, "C4_projects": 4, "C5_experience": 0,
                 "C7_ats": 4, "C8_jd_fit": 3}
        labels = self.tmp / "labels.jsonl"
        labels.write_text("".join(json.dumps(label(p["pair_id"], p["cv_id"], human, 4 if p["pair_id"] == "T1" else 2)) + "\n"
                                  for p in PAIRS), encoding="utf-8")
        out = rs.report(self.tmp / "run", labels, reference="m3_rag", reps=50)
        table = out["inputs"]["gold"]["strategies"]
        self.assertEqual(set(table), {"baseline_rules", "m1_zero_shot", "m3_rag"})
        m1 = table["m1_zero_shot"]
        self.assertEqual((m1["pairs_with_labels"], m1["compliance"]), (2, 1.0))
        # Fake LLM gives 3 everywhere; human C3 2, C4 4, C5 0 → absolute errors 1, 1, 3 (C6 missing_in_cv vs 3 → 3).
        self.assertAlmostEqual(m1["per_criterion_mae"]["C5_experience"], 3.0)
        self.assertEqual(m1["per_criterion_mae"]["C7_ats"], table["m3_rag"]["per_criterion_mae"]["C7_ats"])
        self.assertEqual(out["inputs"]["gold"]["reference"], "m3_rag")
        text = (self.tmp / "run/REPORT.md").read_text(encoding="utf-8")
        self.assertIn("Chênh lệch so với `m3_rag`", text)
        self.assertNotIn("Built a REST API", text)

    def test_method_p_and_keyword_requirements_reach_the_report(self):
        self.go(FakeGroq(score=3), strategies=("baseline_rules", "p_grounded"), inputs=("gold",))
        records = {r["strategy"]: r for r in self.predictions() if r["pair_id"] == "T1"}
        p = records["p_grounded"]
        self.assertEqual(p["calls"], 1)
        self.assertEqual(p["requirements"]["JD1-M02"]["status"], "met")
        self.assertEqual(p["criteria"]["C8_jd_fit"]["score"], 1)  # 1 of 3 must = 33%
        self.assertEqual(records["baseline_rules"]["requirements"]["JD1-M03"]["status"], "met")  # "deployed with Docker"
        human = {"C1_structure": 3, "C2_it_content": 3, "C3_skills": 3, "C4_projects": 3, "C5_experience": 0,
                 "C7_ats": 4, "C8_jd_fit": 1}
        rows = []
        for pair in PAIRS:
            row = label(pair["pair_id"], pair["cv_id"], human, 3)
            row["requirements"] = {"JD1-M01": {"status": "met"}, "JD1-M02": {"status": "met"},
                                   "JD1-M03": {"status": "met"}, "JD1-N01": {"status": "missing"}}
            rows.append(json.dumps(row))
        labels = self.tmp / "labels.jsonl"
        labels.write_text("".join(row + "\n" for row in rows), encoding="utf-8")
        out = rs.report(self.tmp / "run", labels, reference="baseline_rules", reps=20)
        table = out["inputs"]["gold"]["strategies"]
        self.assertEqual(table["p_grounded"]["requirements"]["n"], 8)
        self.assertEqual(table["p_grounded"]["requirements"]["agreement"], 0.5)  # the fake judges Java and Docker missing
        self.assertEqual(table["p_grounded"]["abstention"], 0.0)
        self.assertEqual(table["p_grounded"]["evidence_valid_rate"], 1.0)
        self.assertEqual(table["baseline_rules"]["requirements"]["agreement"], 1.0)

    def test_compliance_needs_evidence_for_llm_scores(self):
        criteria = [c["id"] for c in self.rubric_scoring.load_rubric()["criteria"]]
        pred = {"criteria": {c: {"score": 2, "scored_by": "llm", "evidence": "x"} for c in criteria}}
        self.assertTrue(rs.compliance(pred, criteria))
        pred["criteria"]["C4_projects"]["evidence"] = " "
        self.assertFalse(rs.compliance(pred, criteria))
        del pred["criteria"]["C4_projects"]
        self.assertFalse(rs.compliance(pred, criteria))

    def test_throttle_spaces_calls(self):
        now, waits = [0.0], []
        call = rs.throttled(lambda: "ok", 2.5, sleep=lambda s: (waits.append(s), now.__setitem__(0, now[0] + s)),
                            clock=lambda: now[0])
        call()
        now[0] += 1.0
        call()
        self.assertEqual(waits, [1.5])


if __name__ == "__main__":
    unittest.main()
