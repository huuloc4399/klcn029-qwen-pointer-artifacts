"""Model snapshot keeps Groq's answer and never the key.

Run from the project root: python -m unittest downstream/tests/test_model_snapshot.py -v
"""

from __future__ import annotations

import json
import unittest

from downstream.eval import model_snapshot


class FakeResponse:
    status_code = 200

    def json(self):
        return {"id": "qwen/qwen3.8-27b", "active": True, "context_window": 131072}


class SnapshotTests(unittest.TestCase):
    def test_snapshot_records_the_answer_and_time_but_not_the_key(self):
        seen = {}

        def get(url, headers, timeout):
            seen["url"] = url
            return FakeResponse()

        entry = model_snapshot.snapshot("qwen/qwen3.8-27b", "secret-key", get=get)
        self.assertEqual(seen["url"], "https://api.groq.com/openai/v1/models/qwen/qwen3.8-27b")
        self.assertEqual(entry["response"]["context_window"], 131072)
        self.assertIn("accessed_at", entry)
        self.assertNotIn("secret-key", json.dumps(entry))


if __name__ == "__main__":
    unittest.main()
