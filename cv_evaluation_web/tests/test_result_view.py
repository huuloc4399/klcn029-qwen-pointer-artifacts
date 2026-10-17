"""Result page view: two scores, the to-do list and counts from the CV; display only.

Run from cv_evaluation_web: python -m unittest tests/test_result_view.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services import result_view  # noqa: E402

WEIGHTS = {"C1_structure": 10, "C2_it_content": 10, "C3_skills": 15, "C4_projects": 15, "C5_experience": 10,
           "C6_certs_activities": 5, "C7_ats": 10, "C8_jd_fit": 25}


def result(scores, requirements=None):
    criteria = [{"id": c, "name": c, "weight": w, "score": scores.get(c),
                 "status": "needs_verification" if scores.get(c) is None else "scored",
                 "evidence": f"ev {c}", "suggestion": f"sg {c}"} for c, w in WEIGHTS.items()]
    return {"criteria": criteria, "requirements": requirements or [], "total_shown": True}


class ResultViewTests(unittest.TestCase):
    def test_gains_add_up_to_the_missing_points_and_rank_the_todos(self):
        scores = {"C1_structure": 3, "C2_it_content": 4, "C3_skills": 2, "C4_projects": 4, "C5_experience": 0,
                  "C6_certs_activities": 4, "C7_ats": 4, "C8_jd_fit": 2}
        view = result_view.build(result(scores))
        total = 100 * sum(WEIGHTS[c] * s for c, s in scores.items()) / (4 * 100)
        self.assertAlmostEqual(sum(t["gain"] for t in view["todos"]), 100 - total, places=1)
        self.assertEqual([t["id"] for t in view["todos"]], ["C8_jd_fit", "C5_experience", "C3_skills", "C1_structure"])
        self.assertEqual([t["severity"] for t in view["todos"]], ["important", "important", "important", "should"])
        self.assertTrue(next(t for t in view["todos"] if t["id"] == "C5_experience")["may_not_apply"])
        self.assertFalse(next(t for t in view["todos"] if t["id"] == "C3_skills")["may_not_apply"])

    def test_two_scores_and_requirement_counts(self):
        scores = {c: 4 for c in WEIGHTS} | {"C8_jd_fit": 2}
        reqs = [{"type": "must", "status": "met", "text": "Java"}, {"type": "must", "status": "missing", "text": "Docker"},
                {"type": "nice", "status": "missing", "text": "Kubernetes"}, {"type": "must", "status": "unclear", "text": "OOP"}]
        view = result_view.build(result(scores, reqs))
        self.assertEqual((view["cv_quality"], view["jd_fit"]), (100.0, 50.0))
        self.assertEqual(view["must_counts"], {"met": 1, "mentioned_only": 0, "missing": 1, "unclear": 1})
        self.assertEqual(view["nice_missing"], ["Kubernetes"])
        self.assertEqual(view["unclear"], ["OOP"])

    def test_undecided_criteria_are_listed_and_left_out_of_the_gains(self):
        scores = {c: 3 for c in WEIGHTS} | {"C4_projects": None}
        view = result_view.build(result(scores))
        self.assertEqual([i["id"] for i in view["needs_verification"]], ["C4_projects"])
        self.assertNotIn("C4_projects", [t["id"] for t in view["todos"]])
        self.assertEqual(result_view.verdict(64.9), "Trung bình")

    def test_counts_read_from_the_cv(self):
        cv = {"skills": {"hard_skills": ["Java", "Docker", "Figma"]},
              "projects": [{"name": "Shop", "technologies": ["Java"],
                            "details": "Built REST API serving 200 users\nDeployed with Docker on a VPS\nhttps://github.com/x/shop"}],
              "experience": []}
        counts = {c["label"]: (c["value"], c["total"]) for c in result_view.cv_counts(cv)}
        self.assertEqual(counts["Dòng mô tả dự án hoặc kinh nghiệm có số liệu"], (1, 2))
        self.assertEqual(counts["Kỹ năng xuất hiện trong dự án hoặc kinh nghiệm"], (2, 3))
        self.assertEqual(counts["Dự án có link sản phẩm hoặc mã nguồn"], (1, 1))


if __name__ == "__main__":
    unittest.main()
