"""JD collection checks: manifest, rewritten texts and JD gold.

Run from the project root: python -m unittest downstream/tests/test_jd_catalog.py -v
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from downstream.data import jd_catalog
from downstream.data.jd_catalog import MANIFEST_COLUMNS

ROW = {"jd_id": "JD001", "role": "backend", "level": "intern", "language": "vi", "job_title": "Backend Intern",
       "source_name": "ITviec", "source_url": "https://example.com/job/1", "access_date": "2026-10-14",
       "rewritten": "yes", "collected_by": "Loc", "notes": "", "sha256": ""}


class JdCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.jd, self.gold = self.tmp / "jd_v1", self.tmp / "jd_gold_v1"
        self.jd.mkdir()

    def write(self, rows):
        jd_catalog.write_manifest(self.jd / "jd_manifest.csv", rows)

    def check(self, **kwargs):
        return jd_catalog.check(self.jd, self.gold, **kwargs)

    def test_valid_collection_fills_hash_and_reports_missing_gold(self):
        self.write([dict(ROW)])
        (self.jd / "JD001.txt").write_text("Vị trí: Backend Intern\nYêu cầu bắt buộc:\n- Java\n", encoding="utf-8")
        errors, notes = self.check()
        self.assertEqual(errors, [])
        self.assertTrue(any("chưa có JD gold" in n for n in notes))
        saved = jd_catalog.read_manifest(self.jd / "jd_manifest.csv")[0]
        self.assertEqual(len(saved["sha256"]), 64)
        # An edited text no longer matches the recorded hash.
        (self.jd / "JD001.txt").write_text("Vị trí: khác\n", encoding="utf-8")
        errors, _ = self.check(write_hashes=False)
        self.assertTrue(any("đã đổi" in e for e in errors))

    def test_manifest_errors(self):
        bad = dict(ROW, jd_id="JD1", role="devops")
        self.write([dict(ROW), dict(ROW, rewritten="no", access_date="hôm qua"), bad])
        (self.jd / "JD002.txt").write_text("x", encoding="utf-8")
        errors, _ = self.check()
        text = "\n".join(errors)
        for expected in ("xuất hiện 2 lần", "JD002.txt: chưa có dòng", "dạng JD001", "rewritten phải là yes",
                         "access_date", "thiếu tệp JD001.txt"):
            self.assertIn(expected, text)

    def test_init_gold_creates_skeleton_once_and_check_validates_it(self):
        self.write([dict(ROW)])
        (self.jd / "JD001.txt").write_text("x", encoding="utf-8")
        created = jd_catalog.init_gold(self.jd, self.gold)
        self.assertEqual([p.name for p in created], ["JD001.json"])
        self.assertEqual(jd_catalog.init_gold(self.jd, self.gold), [])
        errors, notes = self.check()
        self.assertEqual(errors, [])
        self.assertTrue(any("chưa có yêu cầu must_have" in n for n in notes))
        gold = json.loads((self.gold / "JD001.json").read_text(encoding="utf-8"))
        gold["requirements"]["must_have"] = ["Java", "java"]
        gold["extra"] = 1
        (self.gold / "JD001.json").write_text(json.dumps(gold), encoding="utf-8")
        errors, _ = self.check()
        self.assertTrue(any("JDSchema" in e for e in errors))
        del gold["extra"]
        (self.gold / "JD001.json").write_text(json.dumps(gold), encoding="utf-8")
        errors, _ = self.check()
        self.assertTrue(any("bị lặp" in e for e in errors))

    def test_excel_saved_manifest_is_accepted_and_normalized(self):
        # Excel with Vietnamese regional settings: BOM, ';' separator, dd/mm/yyyy dates.
        values = dict(ROW, access_date="14/10/2026")
        line = ";".join(values[c] for c in MANIFEST_COLUMNS)
        (self.jd / "jd_manifest.csv").write_text("﻿" + ";".join(MANIFEST_COLUMNS) + "\n" + line + "\n", encoding="utf-8")
        (self.jd / "JD001.txt").write_text("x", encoding="utf-8")
        errors, _ = self.check()
        self.assertEqual(errors, [])
        saved = (self.jd / "jd_manifest.csv").read_text(encoding="utf-8")
        self.assertTrue(saved.startswith("jd_id,role,"))
        self.assertEqual(jd_catalog.read_manifest(self.jd / "jd_manifest.csv")[0]["access_date"], "2026-10-14")
        self.assertEqual(jd_catalog.iso_date("31/02/2026"), None)

    def test_ansi_manifest_gets_a_clear_message(self):
        (self.jd / "jd_manifest.csv").write_bytes(",".join(MANIFEST_COLUMNS).encode() + b"\nJD001,backend,intern,vi,L\xe1p tr\xecnh\n")
        with self.assertRaisesRegex(ValueError, "CSV UTF-8"):
            self.check()

    def test_duplicates_by_link_and_by_text(self):
        same_post = "https://www.topcv.vn/viec-lam/backend/123.html"
        self.write([dict(ROW, source_url=same_post + "?ta_source=a&u_sr_id=x"),
                    dict(ROW, jd_id="JD002", source_url="http://topcv.vn/viec-lam/backend/123.html/"),
                    dict(ROW, jd_id="JD003", source_url="https://example.com/other")])
        body = "Yêu cầu: Java, Spring Boot, REST API, MySQL, Git. Mô tả: phát triển API cho hệ thống."
        (self.jd / "raw").mkdir()
        for jd_id, text in (("JD001", body), ("JD002", "khác hẳn"), ("JD003", body + " Ưu tiên Docker.")):
            (self.jd / f"{jd_id}.txt").write_text("viết lại", encoding="utf-8")
            (self.jd / "raw" / f"{jd_id}.txt").write_text(text, encoding="utf-8")
        errors, _ = self.check()
        self.assertTrue(any("JD001, JD002: cùng một tin" in e for e in errors))
        self.assertTrue(any(e.startswith("JD001, JD003: nội dung giống nhau") for e in errors))
        self.assertFalse(any(e.startswith("JD001, JD002: nội dung") for e in errors))

    def test_manifest_columns_are_fixed(self):
        (self.jd / "jd_manifest.csv").write_text("jd_id,role\nJD001,backend\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "columns must be"):
            self.check()
        self.assertEqual(MANIFEST_COLUMNS[0], "jd_id")


if __name__ == "__main__":
    unittest.main()
