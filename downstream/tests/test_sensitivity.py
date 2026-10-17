"""Rubric sensitivity analysis.

Run from the project root: python -m unittest downstream/tests/test_sensitivity.py -v
"""

from __future__ import annotations

import random
import unittest

from downstream.eval import run_strategies, sensitivity


def req(status, kind="must"):
    return {"type": kind, "status": status}


class SensitivityTests(unittest.TestCase):
    def test_c8_rule_matches_the_rubric_code(self):
        band = run_strategies._grounded().c8_from_requirements
        rng = random.Random(1)
        for _ in range(300):
            reqs = [req(rng.choice(["met", "mentioned_only", "missing", "unclear"]), rng.choice(["must", "must", "nice"]))
                    for _ in range(rng.randint(1, 9))]
            self.assertEqual(sensitivity.c8_band(reqs), band(reqs)[0], reqs)

    def test_c8_variants_move_the_band(self):
        reqs = [req("met"), req("mentioned_only"), req("missing"), req("missing")]  # 1.5 / 4 = 0.375
        self.assertEqual(sensitivity.c8_band(reqs), 1)
        self.assertEqual(sensitivity.c8_band(reqs, half=1.0), 2)  # 2 / 4 = 0.5

    def test_dirichlet_keeps_the_total_and_centres_on_the_rubric(self):
        weights = {"a": 10.0, "b": 30.0}
        rng = random.Random(0)
        draws = [sensitivity._dirichlet(rng, weights, 50.0) for _ in range(2000)]
        self.assertAlmostEqual(sum(draws[0].values()), 40.0)
        self.assertAlmostEqual(sum(d["b"] for d in draws) / len(draws), 30.0, delta=0.6)

    def test_weight_sensitivity_reports_rank_stability(self):
        weights = {"C1": 1.0, "C8_jd_fit": 3.0}

        def rec(pid, cv, c1, c8, fit):
            return {"pair_id": pid, "cv_id": cv, "overall_fit": fit,
                    "criteria": {"C1": {"status": "scored", "score": c1}, "C8_jd_fit": {"status": "scored", "score": c8}}}
        records = [rec("P1", "A", 1, 4, 5), rec("P2", "A", 3, 1, 2), rec("P3", "B", 2, 3, 4), rec("P4", "C", 4, 0, 1)]
        out = sensitivity.weight_sensitivity(records, weights, draws=200)
        self.assertEqual(out["named"]["rubric"]["spearman_with_rubric_total"], 1.0)
        self.assertGreater(out["named"]["rubric"]["spearman_with_fit"], out["named"]["no_c8"]["spearman_with_fit"])


if __name__ == "__main__":
    unittest.main()
