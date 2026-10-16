"""Method P: evidence verification, the second ask, abstention and coverage, and the ablations.

Run from cv_evaluation_web with the repo root on the path:
PYTHONPATH=".;.." python -m unittest tests/test_grounded_scoring.py -v
"""

from __future__ import annotations

import copy
import unittest

from services import grounded_scoring as gs
from services import rubric_scoring as rs
from services.rule_rubric import requirement_statuses

CV = {
    "personal_info": {"name": "[MASKED]", "email": "[MASKED]", "phone": "[MASKED]", "github_url": "", "linkedin_url": ""},
    "summary": "Backend developer intern focused on Java and Spring Boot.",
    "skills": {"hard_skills": ["Java", "Spring Boot", "MySQL", "Docker", "Git"], "soft_skills": ["Teamwork"]},
    "experience": [],
    "projects": [{"name": "Library API", "role": "Backend developer", "technologies": ["Java", "Spring Boot", "MySQL"],
                  "details": "Built a REST API for 200 users with Spring Boot and MySQL, and wrote unit tests with JUnit."}],
    "education": [{"degree": "Bachelor", "university": "HUIT", "gpa": None, "year_graduated": 2026}],
    "certifications": ["TOEIC 750 (2025)"], "activities": [], "awards": [],
}
DOCUMENT = {"page_count": 1, "native_text_pages": 1, "character_count": 700, "block_count": 20,
            "likely_multi_column": False, "needs_ocr": False}
JD = "Java Backend Intern. Yêu cầu: Java, Spring Boot, Docker. Ưu tiên: Kubernetes."
REQUIREMENTS = [{"req_id": "J-M01", "type": "must", "text": "Java"},
                {"req_id": "J-M02", "type": "must", "text": "Spring Boot"},
                {"req_id": "J-M03", "type": "must", "text": "Docker"},
                {"req_id": "J-N01", "type": "nice", "text": "Kubernetes"}]
GOOD = {"field": "projects[0].details", "quote": "Built a REST API for 200 users with Spring Boot"}
FAKE = {"field": "projects[0].details", "quote": "Led a team of 10 engineers to migrate to microservices"}


def criteria(**overrides):
    base = {c: {"status": "scored", "score": 3, "evidence": [GOOD], "reason": "r", "suggestion": "s"} for c in gs.LLM_CRITERIA}
    base["C1_structure"]["evidence"] = [{"field": "projects", "quote": ""}]
    base["C6_certs_activities"] = {"status": "scored", "score": 2, "reason": "r", "suggestion": "s",
                                   "evidence": [{"field": "certifications[0]", "quote": "TOEIC 750"}]}
    for key, value in overrides.items():
        base[key] = {**base[key], **value}
    return base


def requirements(**statuses):
    defaults = {"J-M01": ("met", "projects[0].technologies", "Java"),
                "J-M02": ("met", "projects[0].details", "with Spring Boot and MySQL"),
                "J-M03": ("met", "skills.hard_skills", "Docker"),
                "J-N01": ("missing", "", "")}
    defaults.update(statuses)
    return [{"req_id": rid, "text": "", "type": "must" if "-M" in rid else "nice", "status": st, "field": f, "quote": q,
             "note": ""} for rid, (st, f, q) in defaults.items()]


class FakeP:
    """Returns the queued answers in order (the last one repeats); records the schemas asked for."""

    def __init__(self, *answers):
        self.answers, self.schemas = list(answers), []

    def __call__(self, messages, schema, max_tokens):
        self.schemas.append(schema)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return copy.deepcopy(answer), {"input_tokens": 3000, "output_tokens": 600}


def run(strategy, call, document=DOCUMENT, cv=CV, reqs=REQUIREMENTS):
    return gs.score(strategy, cv_schema=cv, jd_text=JD, document=document, call=call, requirements=reqs)


def by_id(result):
    return {c["id"]: c for c in result["criteria"]}


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.cv = rs.cv_payload(CV)

    def test_quote_levels(self):
        self.assertEqual(gs.check_quote(self.cv, "projects[0].details", "built a REST api  for 200 users"), "field")
        self.assertEqual(gs.check_quote(self.cv, "projects[0].name", "Built a REST API"), "section")
        self.assertEqual(gs.check_quote(self.cv, "summary", "Built a REST API"), "other")
        self.assertEqual(gs.check_quote(self.cv, "projects[0].details", FAKE["quote"]), "none")
        self.assertEqual(gs.check_quote(self.cv, "projects[0].details", "Built a REST API … unit tests with JUnit"), "field")
        self.assertEqual(gs.check_quote(self.cv, "projects[0].details", "x"), "none")  # too short to prove anything
        # Seen on dev pairs: lists quoted with commas, one-word skills, sentence-final dots.
        self.assertEqual(gs.check_quote(self.cv, "skills.hard_skills", "Java, Spring Boot, MySQL"), "field")
        self.assertEqual(gs.check_quote(self.cv, "skills.hard_skills", "Git"), "field")
        self.assertEqual(gs.check_quote(self.cv, "projects[0].details", "unit tests with JUnit."), "field")
        self.assertEqual(gs.check_quote(self.cv, "skills.hard_skills", "Jav"), "none")  # whole words only

    def test_word_boundaries(self):
        cv = {"skills": {"hard_skills": ["JavaScript", "C#", ".NET"]}}
        self.assertEqual(gs.check_quote(cv, "skills", "Java"), "none")
        self.assertEqual(gs.check_quote(cv, "skills", "C#, .NET"), "field")

    def test_requirement_checks(self):
        met = {"text": "Spring Boot", "quote": "with Spring Boot and MySQL"}
        self.assertEqual(gs.verify_requirement(self.cv, met, "met")[0], "met")
        listed = {"text": "Docker", "quote": "Docker"}
        self.assertEqual(gs.verify_requirement(self.cv, listed, "met")[0], "mentioned_only")
        invented = {"text": "Kubernetes", "quote": "Deployed on Kubernetes"}
        self.assertEqual(gs.verify_requirement(self.cv, invented, "met")[0], "missing")
        off_topic = {"text": "Docker", "quote": "Built a REST API for 200 users"}
        self.assertEqual(gs.verify_requirement(self.cv, off_topic, "met")[0], "missing")
        self.assertEqual(gs.verify_requirement(self.cv, {"text": "Git", "quote": ""}, "unclear")[0], "unclear")
        # Direct implication from the rater guide: a Spring Boot project shows Java and a REST API.
        implied = {"text": "Java", "quote": "with Spring Boot and MySQL"}
        self.assertEqual(gs.verify_requirement(self.cv, implied, "met")[0], "met")
        self.assertEqual(gs.verify_requirement(self.cv, {"text": "REST API", "quote": "Spring Boot"}, "met")[0],
                         "met")  # Spring Boot is also in the project, where it implies a REST API
        loose = {"text": "Kubernetes", "quote": "Docker"}  # a related tool is not the required one
        self.assertEqual(gs.verify_requirement(self.cv, loose, "met")[0], "missing")

    def test_concept_requirements_need_their_own_words(self):
        """Outside the skill dictionary code can only check words: a related technology is not the concept."""
        cv = {"skills": {"hard_skills": ["HTML", "CSS", "Java", "Docker"], "soft_skills": []},
              "projects": [{"name": "Shop", "details": "Built responsive layouts with Flexbox and media queries for "
                                                         "mobile screens. Designed the database for a web application."}],
              "activities": ["Trưởng nhóm, làm việc nhóm 5 người"]}
        def check(text, quote, given="met"):
            return gs.verify_requirement(cv, {"text": text, "quote": quote}, given)[0]
        responsive = "Responsive web design"
        self.assertEqual(check(responsive, "CSS", "mentioned_only"), "unclear")
        generic_only = "Designed the database for a web application"
        self.assertEqual(check(responsive, generic_only), "unclear")
        self.assertEqual(check(responsive, "Built responsive layouts with Flexbox"), "met")
        self.assertEqual(check(responsive, "media queries for mobile screens"), "met")  # another wording of it
        self.assertEqual(check("OOP", "Java", "mentioned_only"), "unclear")
        self.assertEqual(check("Linux", "Docker", "mentioned_only"), "unclear")
        self.assertEqual(check("HTML5/CSS3", "HTML", "mentioned_only"), "mentioned_only")  # version numbers ignored
        self.assertEqual(check("Teamwork", "làm việc nhóm 5 người"), "met")  # Vietnamese wording
        self.assertEqual(check("Design patterns", "Designed the database"), "unclear")
        # The ablation accepts any located quote, as P did before the check.
        self.assertEqual(gs.verify_requirement(cv, {"text": responsive, "quote": "CSS"}, "mentioned_only", False)[0],
                         "mentioned_only")

    def test_c8_bands(self):
        reqs = lambda *s: [{"type": t, "status": st} for t, st in s]  # noqa: E731
        must4 = [("must", "met")] * 4
        self.assertEqual(gs.c8_from_requirements(reqs(*must4, ("must", "missing"), ("nice", "met")))[0], 4)
        self.assertEqual(gs.c8_from_requirements(reqs(*must4, ("must", "missing"), ("nice", "missing")))[0], 3)
        self.assertEqual(gs.c8_from_requirements(reqs(("must", "mentioned_only"), ("must", "missing")))[0], 1)  # 25%
        self.assertIsNone(gs.c8_from_requirements(reqs(("must", "unclear"), ("must", "unclear"), ("must", "met")))[0])

    def test_keyword_requirement_statuses(self):
        out = {r["req_id"]: r["status"] for r in requirement_statuses(CV, REQUIREMENTS + [
            {"req_id": "J-M04", "type": "must", "text": "Unit testing"}])}
        self.assertEqual(out, {"J-M01": "met", "J-M02": "met", "J-M03": "mentioned_only", "J-N01": "missing",
                               "J-M04": "met"})

    def test_keyword_concepts_ignore_generic_words(self):
        cv = {"skills": {"hard_skills": ["CSS"]},
              "projects": [{"name": "A", "details": "Designed the database for a web application"}]}
        responsive = [{"req_id": "R", "type": "must", "text": "Responsive web design"}]

        def status(c):
            return requirement_statuses(c, responsive)[0]["status"]
        self.assertEqual(status(cv), "missing")
        cv["projects"][0]["details"] = "Built responsive layouts with Flexbox"
        self.assertEqual(status(cv), "met")


class ScoringTests(unittest.TestCase):
    def test_valid_evidence_is_scored_in_one_call(self):
        fake = FakeP({"criteria": criteria(), "requirements": requirements()})
        result = run("p_grounded", fake)
        items = by_id(result)
        self.assertEqual(result["calls"], 1)
        self.assertTrue(all(c["status"] == "scored" for c in result["criteria"]))
        # 2 must met + Docker only listed = 2.5 / 3 = 83%, no nice met → 3.
        self.assertEqual(items["C8_jd_fit"]["score"], 3)
        self.assertEqual({r["req_id"]: r["status"] for r in result["requirements"]}["J-M03"], "mentioned_only")
        self.assertTrue(result["total_shown"])
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(items["C7_ats"]["scored_by"], "pdf")
        schema = fake.schemas[0]
        self.assertEqual(schema["properties"]["criteria"]["required"], list(gs.LLM_CRITERIA))

    def test_unsupported_score_is_asked_again_then_abstained(self):
        bad = {"criteria": criteria(C4_projects={"evidence": [FAKE]}), "requirements": requirements()}
        still_bad = {"criteria": {"C4_projects": {"status": "scored", "score": 4, "evidence": [FAKE], "reason": "", "suggestion": ""}}}
        fake = FakeP(bad, still_bad)
        result = run("p_grounded", fake)
        c4 = by_id(result)["C4_projects"]
        self.assertEqual((c4["status"], c4["score"], c4["rescored"]), ("needs_verification", None, True))
        self.assertEqual(result["calls"], 2)
        self.assertEqual(fake.schemas[1]["properties"]["criteria"]["required"], ["C4_projects"])
        self.assertNotIn("requirements", fake.schemas[1]["properties"])
        self.assertEqual(result["coverage"], 0.85)
        self.assertTrue(result["total_shown"])  # C5 still covers the "C4 or C5" requirement
        self.assertIn("C4_projects", result["verification"]["abstained"])
        self.assertTrue(any("chưa đủ căn cứ" in line for line in result["improvements"]))

    def test_second_ask_can_fix_the_quote(self):
        bad = {"criteria": criteria(C4_projects={"evidence": [FAKE]}), "requirements": requirements()}
        fixed = {"criteria": {"C4_projects": {"status": "scored", "score": 3, "evidence": [GOOD], "reason": "", "suggestion": ""}}}
        c4 = by_id(run("p_grounded", FakeP(bad, fixed)))["C4_projects"]
        self.assertEqual((c4["status"], c4["score"], c4["rescored"]), ("scored", 3, True))

    def test_ablation_without_verification_keeps_the_llm_scores(self):
        bad = {"criteria": criteria(C4_projects={"score": 4, "evidence": [FAKE]}),
               "requirements": requirements(**{"J-N01": ("met", "projects[0].details", "Deployed on Kubernetes")})}
        result = run("p_no_verify", FakeP(bad))
        self.assertEqual(result["calls"], 1)
        self.assertEqual(by_id(result)["C4_projects"]["score"], 4)
        self.assertEqual({r["req_id"]: r["status"] for r in result["requirements"]}["J-N01"], "met")

    def test_lost_content_turns_missing_into_needs_verification(self):
        answer = {"criteria": criteria(C5_experience={"status": "missing_in_cv", "score": 0, "evidence": []}),
                  "requirements": requirements(**{"J-M03": ("missing", "", "")})}
        lost = {**DOCUMENT, "character_count": 9000}  # the PDF holds far more text than the extracted CV
        result = run("p_grounded", FakeP(answer), document=lost)
        self.assertEqual(result["content_flags"], ["low_text_coverage"])
        self.assertEqual(by_id(result)["C5_experience"]["status"], "needs_verification")
        self.assertEqual({r["req_id"]: r["status"] for r in result["requirements"]}["J-M03"], "unclear")
        kept = run("p_no_abstain", FakeP(answer), document=lost)
        self.assertEqual((by_id(kept)["C5_experience"]["status"], by_id(kept)["C5_experience"]["score"]), ("missing_in_cv", 0))
        same = run("p_grounded", FakeP(answer))
        self.assertEqual(by_id(same)["C5_experience"]["status"], "missing_in_cv")

    def test_total_hidden_when_c8_cannot_be_decided(self):
        unclear = {rid: ("unclear", "", "") for rid in ("J-M01", "J-M02", "J-M03")}
        result = run("p_grounded", FakeP({"criteria": criteria(), "requirements": requirements(**unclear)}))
        self.assertEqual(by_id(result)["C8_jd_fit"]["status"], "needs_verification")
        self.assertFalse(result["total_shown"])
        self.assertEqual(result["verdict"], "Cần kiểm tra lại trích xuất")
        self.assertEqual(result["coverage"], 0.75)

    def test_requirements_listed_by_the_llm_when_the_jd_has_no_gold(self):
        listed = [{"req_id": "R1", "text": "Java", "type": "must", "status": "met", "field": "projects[0].technologies",
                   "quote": "Java", "note": ""},
                  {"req_id": "R2", "text": "Docker", "type": "must", "status": "missing", "field": "", "quote": "", "note": ""}]
        result = run("p_grounded", FakeP({"criteria": criteria(), "requirements": listed}), reqs=None)
        self.assertEqual([(r["req_id"], r["status"]) for r in result["requirements"]], [("R1", "met"), ("R2", "missing")])
        self.assertEqual(by_id(result)["C8_jd_fit"]["score"], 2)  # 1 of 2 must = 50%


if __name__ == "__main__":
    unittest.main()
