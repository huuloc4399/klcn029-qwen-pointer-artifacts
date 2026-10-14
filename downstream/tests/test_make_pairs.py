"""Pair design rules on synthetic CVs and JDs (no real data needed).

Run from the project root: python -m unittest downstream/tests/test_make_pairs.py -v
"""

from __future__ import annotations

import unittest
from collections import Counter

from downstream.data import make_pairs as mp


def synthetic():
    tracks, terms = {}, {}
    plan = [("backend", "en", {"java", "spring boot"})] * 6 + [("backend", "vi", {"php", "mysql"})] * 6 \
        + [("fullstack", "en", {"react", "node.js"})] * 3 + [("frontend", "vi", {"react", "html/css"})] * 2 \
        + [("mobile", "en", {"flutter", "java"})] * 4 + [("data_ai", "vi", {"python"})] * 3
    for i, (track, language, skills) in enumerate(plan):
        cv = f"{language.upper()}{i:03d}"
        tracks[cv], terms[cv] = {"track": track, "language": language}, skills
    jds = {
        "JD001": {"role": "backend", "language": "en", "must": ["Java", "Spring Boot", "Git"], "nice": []},
        "JD002": {"role": "backend", "language": "vi", "must": ["PHP", "MySQL"], "nice": []},
        "JD003": {"role": "backend", "language": "en", "must": ["Go"] * 1 + [f"x{i}" for i in range(21)], "nice": []},
        "JD004": {"role": "backend", "language": "vi", "must": ["Node.js", "REST API"], "nice": []},
        "JD005": {"role": "frontend", "language": "en", "must": ["React", "HTML/CSS", "Git"], "nice": []},
        "JD006": {"role": "frontend", "language": "vi", "must": ["Vue", "HTML/CSS"], "nice": []},
        "JD007": {"role": "frontend", "language": "en", "must": ["Angular"], "nice": []},
        "JD008": {"role": "frontend", "language": "en", "must": ["React"], "nice": []},
    }
    return tracks, terms, jds


class MakePairsTests(unittest.TestCase):
    def test_selection_split_and_assignment_rules(self):
        tracks, terms, jds = synthetic()
        cvs = mp.select_cvs(tracks, seed=1)
        self.assertEqual(len(cvs), mp.CV_COUNT - 3)  # 21 in-scope CVs, fewer than 24: keep all
        self.assertFalse(any(tracks[c]["track"] == "data_ai" for c in cvs))
        dev = mp.split_dev(cvs, tracks, seed=1)
        self.assertEqual(len(dev), mp.DEV_CV_COUNT)
        pairs = mp.assign(cvs, tracks, terms, jds, seed=1)
        per_cv = Counter(p["cv_id"] for p in pairs)
        self.assertEqual(set(per_cv.values()), {2})
        for cv in cvs:
            roles = sorted(jds[p["jd_id"]]["role"] for p in pairs if p["cv_id"] == cv)
            self.assertEqual(roles, ["backend", "frontend"], cv)  # one JD per track, whatever the CV
        load = Counter(p["jd_id"] for p in pairs)
        for jd_id, jd in jds.items():
            self.assertLessEqual(load[jd_id], mp.jd_capacity(len(jd["must"]) + len(jd["nice"])))
            self.assertGreaterEqual(load[jd_id], mp.MIN_USE, jd_id)
        # Same-track picks follow the skills: Java CVs land on the Java JD, PHP CVs on the PHP JD.
        same = {p["cv_id"]: p["jd_id"] for p in pairs if p["intended_fit"] == "same_track" and tracks[p["cv_id"]]["track"] == "backend"}
        self.assertGreater(sum(1 for cv, jd in same.items() if (jd == "JD001") == ("java" in terms[cv])), len(same) // 2)
        self.assertEqual(mp.assign(cvs, tracks, terms, jds, seed=1), pairs)

    def test_overrides_from_excel_and_their_errors(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cv_track_overrides.csv"
            self.assertEqual(mp.read_overrides(path, {"EN001"}), {})  # no file: nothing to override
            # Excel with Vietnamese settings: BOM and ';'.
            path.write_text("﻿cv_id;track;ly_do\nen001;Backend;Mục tiêu ghi Java backend\n\n", encoding="utf-8")
            self.assertEqual(mp.read_overrides(path, {"EN001"}), {"EN001": {"track": "backend", "ly_do": "Mục tiêu ghi Java backend"}})
            path.write_text("cv_id,track,ly_do\nEN001,devops,\nEN001,backend,x\nEN999,backend,x\n", encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                mp.read_overrides(path, {"EN001"})
            for expected in ("track 'devops'", "cần ghi ly_do", "EN001 xuất hiện hơn một lần", "'EN999' không phải CV GOLD40"):
                self.assertIn(expected, str(caught.exception))
            path.write_text("cv_id,nhan\nEN001,backend\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cột phải là"):
                mp.read_overrides(path, {"EN001"})

    def test_override_brings_a_cv_into_scope(self):
        tracks, _, _ = synthetic()
        moved = next(cv for cv, t in tracks.items() if t["track"] == "data_ai")
        tracks[moved]["track"] = "backend"  # what build() does with an override row
        self.assertIn(moved, mp.select_cvs(tracks, seed=1))

    def test_capacity_and_overlap(self):
        self.assertEqual([mp.jd_capacity(n) for n in (10, 16, 25)], [7, 5, 2])
        self.assertEqual(mp.overlap({"java", "c#"}, ["Java core", "JavaScript", "C# and .NET"]), 2)


if __name__ == "__main__":
    unittest.main()
