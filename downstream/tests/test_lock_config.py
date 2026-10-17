"""Pre-registered COVERAGE_MIN rule.

Run from the project root: python -m unittest downstream/tests/test_lock_config.py -v
"""

from __future__ import annotations

import unittest

from downstream.eval import lock_config


def result(coverage, inp="gold", c8=2):
    criteria = {"C3_skills": {"score": 2}, "C4_projects": {"score": 3}, "C8_jd_fit": {"score": c8}}
    return {"strategy": "p_grounded", "status": "ok", "input": inp, "repeat": 1, "coverage": coverage,
            "criteria": criteria}


class CoverageRuleTests(unittest.TestCase):
    def test_highest_threshold_with_enough_totals_shown(self):
        records = [result(0.95)] * 6 + [result(0.82, "b0")] * 2 + [result(0.72, "b0")] * 2
        out = lock_config.coverage_rule(records, expected=10)
        self.assertEqual(out["candidates"][0.80]["pooled"], 0.8)
        self.assertEqual(out["candidates"][0.85]["pooled"], 0.6)
        self.assertEqual(out["chosen"], 0.80)

    def test_missing_required_criterion_hides_the_total(self):
        self.assertFalse(lock_config.shown(result(1.0, c8=None), 0.5))

    def test_too_few_results_chooses_nothing(self):
        out = lock_config.coverage_rule([result(0.9)] * 5, expected=10)
        self.assertIsNone(out["chosen"])

    def test_no_threshold_reaching_the_share_takes_the_lowest(self):
        out = lock_config.coverage_rule([result(0.4)] * 10, expected=10)
        self.assertEqual(out["chosen"], 0.50)


if __name__ == "__main__":
    unittest.main()
