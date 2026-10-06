"""Contract tests that do not load the GPU model."""

from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WORKER))

runpod_stub = types.ModuleType("runpod")
runpod_stub.serverless = types.SimpleNamespace(progress_update=lambda *args, **kwargs: None, start=lambda *args, **kwargs: None)
sys.modules.setdefault("runpod", runpod_stub)

from handler import process_job  # noqa: E402
from prompting import build_messages, load_contract  # noqa: E402


SOURCE = """SUMMARY
Backend developer seeking a junior role.
SKILLS
Python
EXPERIENCE
Acme | Backend Developer | 2024 - Present
Built APIs for 120 users.
EDUCATION
Bachelor of Software Engineering
""".strip()


POINTER = {
    "personal_info": {"name": "[MASKED]", "email": "[MASKED]", "phone": "[MASKED]", "github_url": ""},
    "summary_span": [2, 2],
    "skills": {"hard_skills": ["Python"], "soft_skills": []},
    "experience": [{"company": "Acme", "job_title": "Backend Developer", "duration": "2024 - Present", "description_span": [7, 7]}],
    "projects": [],
    "education": [{"degree": "Bachelor of Software Engineering", "university": "", "gpa": None, "year_graduated": None}],
    "certifications": [],
    "activities": [],
    "awards": [],
}


class FakeRuntime:
    def generate(self, messages):
        self.messages = messages
        return {
            "raw_output": json.dumps(POINTER),
            "input_tokens": 300,
            "generated_tokens": 120,
            "runtime_seconds": 0.01,
        }


class WorkerContractTests(unittest.TestCase):
    def test_prompt_hashes_and_line_indexing(self):
        contract = load_contract()
        messages, normalized = build_messages(" First line \n\n Second line ")
        self.assertEqual(normalized, "First line\nSecond line")
        self.assertIn("[L0001] First line", messages[1]["content"])
        self.assertIn("[L0002] Second line", messages[1]["content"])
        self.assertEqual(contract["contract_version"], "cvpointer_prompt_v1")

    def test_end_to_end_worker_contract_with_fake_generation(self):
        runtime = FakeRuntime()
        result = process_job({"input": {"source_text": SOURCE, "language": "en", "page_count": 1, "native_text_pages": 1}}, runtime=runtime)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["cv"]["summary"], "Backend developer seeking a junior role.")
        self.assertEqual(result["cv"]["experience"][0]["description"], "Built APIs for 120 users.")
        self.assertEqual(result["manifest"]["parser_version"], "cvpointer_output_parser_v1")
        self.assertNotIn("raw_output", result)


if __name__ == "__main__":
    unittest.main()
