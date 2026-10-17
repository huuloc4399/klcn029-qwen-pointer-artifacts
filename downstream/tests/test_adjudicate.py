"""Adjudication rounds and FINAL labels.

Run from the project root: python -m unittest downstream/tests/test_adjudicate.py -v
"""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from downstream.eval import adjudicate, iaa


def criterion(score, status="scored"):
    return {"status": status, "score": score, "evidence_section": "projects", "quote": "q", "reason": "r",
            "confidence": "", "note": ""}


def requirement(status, kind="must", text="Java"):
    return {"type": kind, "text": text, "status": status, "evidence_section": "", "quote": "", "note": ""}


def record(pair_id="P1", cv_id="CV1", jd_id="JD1", scores=None, reqs=None, fit=3):
    scores = scores or {"C1_structure": 2, "C2_it_content": 3, "C8_jd_fit": 2}
    return {"pair_id": pair_id, "cv_id": cv_id, "jd_id": jd_id, "rater_id": "A", "rubric_version": "v",
            "overall_fit": fit, "comment": "", "criteria": {c: criterion(s) for c, s in scores.items()},
            "requirements": reqs or {"R1": requirement("met"), "R2": requirement("missing")}}


def decision(pair_id, item, value, note="n"):
    return {"pair_id": pair_id, "item": item, "decision": value, "adjudicator_note": note}


class AdjudicateTests(unittest.TestCase):
    def test_round2_lists_requirement_mismatches_left_by_round1(self):
        a = record(reqs={"R1": requirement("met"), "R2": requirement("mentioned_only"), "R3": requirement("met")})
        b = record(reqs={"R1": requirement("mentioned_only"), "R2": requirement("missing"), "R3": requirement("missing")})
        round1 = [{**decision("P1", "R9 · X", ""), "kind": "yêu cầu: met so với missing"}]
        rows = adjudicate.round2_rows([(a, b)], round1)
        self.assertEqual([r["item"].split(" · ")[0] for r in rows], ["R1", "R2", "R9"])  # R3 is round 1's
        self.assertTrue(rows[-1]["kind"].endswith("(vòng 1 chưa có quyết định)"))

    def test_final_merges_agreement_means_and_decisions(self):
        a = record(scores={"C1_structure": 2, "C2_it_content": 4, "C8_jd_fit": 2}, fit=3)
        b = record(scores={"C1_structure": 3, "C2_it_content": 2, "C8_jd_fit": 2}, fit=4,
                   reqs={"R1": requirement("mentioned_only"), "R2": requirement("missing")})
        b["criteria"]["C5_experience"] = criterion(0)
        a["criteria"]["C5_experience"] = criterion(0, "missing_in_cv")
        decisions = {("P1", "C2_it_content"): decision("P1", "C2_it_content", "2"),
                     ("P1", "R1"): decision("P1", "R1 · Java", "met")}
        records, errors, _ = adjudicate.final_records([(a, b)], decisions)
        self.assertEqual(errors, [])
        final = records[0]
        self.assertEqual(final["criteria"]["C1_structure"]["score"], 2.5)  # 1 apart → mean
        self.assertEqual(final["criteria"]["C2_it_content"]["score"], 2)  # decided
        c5 = final["criteria"]["C5_experience"]
        self.assertEqual((c5["status"], c5["score"]), ("missing_in_cv", 0))
        self.assertEqual(final["requirements"]["R1"]["status"], "met")
        self.assertEqual(final["overall_fit"], 3.5)
        self.assertEqual(final["final_source"]["C1_structure"], "mean")
        self.assertEqual(final["final_source"]["R2"], "agreed")

    def test_final_refuses_holes(self):
        a, b = record(scores={"C1_structure": 0, "C8_jd_fit": 2}), record(scores={"C1_structure": 3, "C8_jd_fit": 2})
        b["requirements"]["R1"] = requirement("mentioned_only")
        b["overall_fit"] = 5
        _, errors, _ = adjudicate.final_records([(a, b)], {})
        self.assertEqual(len(errors), 3)  # C1 three apart, R1, overall fit two apart

    def test_warnings_for_cv_consistency_and_c8_band(self):
        a1, a2 = record("P1"), record("P2", jd_id="JD2")
        b1, b2 = copy.deepcopy(a1), copy.deepcopy(a2)
        a2["criteria"]["C1_structure"]["score"] = b2["criteria"]["C1_structure"]["score"] = 4
        _, errors, warnings = adjudicate.final_records([(a1, b1), (a2, b2)], {}, adjudicate._c8_band())
        self.assertEqual(errors, [])
        self.assertTrue(any("CV1 C1_structure" in w for w in warnings))
        # 1 of 2 must requirements met → 50% → band 2, as labelled: no C8 warning.
        self.assertFalse(any("C8" in w for w in warnings))

    def test_decision_values_are_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "d.csv"
            adjudicate.write_csv(path, [{"pair_id": "P1", "item": "C1_structure", "decision": "5"},
                                        {"pair_id": "P1", "item": "R1 · Java", "decision": "met "},
                                        {"pair_id": "P1", "item": "overall_fit", "decision": "2"},
                                        {"pair_id": "P1", "item": "R2 · Git", "decision": "mention_only"}])
            decisions, errors, notes = adjudicate.read_decisions([path])
        self.assertEqual(len(errors), 1)
        self.assertEqual(set(decisions), {("P1", "R1"), ("P1", "overall_fit"), ("P1", "R2")})
        self.assertEqual(decisions[("P1", "R2")]["decision"], "mentioned_only")
        self.assertEqual(len(notes), 1)

    def test_half_point_scale_for_kappa(self):
        self.assertEqual(iaa.score_levels([1, 2], [3]), iaa.SCORES)
        self.assertEqual(iaa.score_levels([1, 2.5]), iaa.HALF_SCORES)
        self.assertAlmostEqual(iaa.kappa([2.5, 1, 3], [2.5, 1, 3], iaa.HALF_SCORES, weighted=True), 1.0)


if __name__ == "__main__":
    unittest.main()
