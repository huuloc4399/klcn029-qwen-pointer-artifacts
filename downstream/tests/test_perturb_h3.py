"""H3 summary: abstentions, zero scores and score drops per variant kind.

Run from the project root: python -m unittest downstream/tests/test_perturb_h3.py -v
"""

from __future__ import annotations

import unittest

from downstream.eval import perturb_h3

ROWS = [{"pair_id": f"P1-{kind}", "source_pair": "P1", "intended_fit": kind, "affected": "C4_projects"}
        for kind in perturb_h3.KINDS]


def record(strategy, kind, total, c4, reqs=None):
    return {"strategy": strategy, "input": "gold", "pair_id": f"P1-{kind}", "repeat": 1, "status": "ok",
            "total_score": total, "criteria": {"C4_projects": {"score": c4}},
            "requirements": {k: {"status": v} for k, v in (reqs or {}).items()}}


class H3SummaryTests(unittest.TestCase):
    def test_p_abstains_on_misread_and_scores_zero_on_missing(self):
        records = [
            record("p_grounded", "orig", 70.0, 3, {"R1": "met", "R2": "missing"}),
            record("p_grounded", "misread", 66.0, None, {"R1": "unclear", "R2": "missing"}),
            record("p_grounded", "missing", 55.0, 0, {"R1": "missing", "R2": "missing"}),
            record("m3_rag", "orig", 70.0, 3),
            record("m3_rag", "misread", 55.0, 0),
            record("m3_rag", "missing", 55.0, 0),
        ]
        summary = perturb_h3.summarize(records, ROWS)
        p, m3 = summary["p_grounded"], summary["m3_rag"]
        self.assertEqual((p["misread"]["abstained"], p["missing"]["scored_zero"]), (1, 1))
        self.assertEqual((p["misread"]["mean_drop"], p["missing"]["mean_drop"]), (4.0, 15.0))
        self.assertEqual((p["misread"]["requirements_unclear"], p["missing"]["requirements_missing"]), (1, 1))
        self.assertEqual(m3["misread"]["mean_drop"], m3["missing"]["mean_drop"])
        self.assertEqual(list(summary), ["m3_rag", "p_grounded"])
        self.assertIn("đọc lỗi", perturb_h3.markdown(summary, "t"))


if __name__ == "__main__":
    unittest.main()
