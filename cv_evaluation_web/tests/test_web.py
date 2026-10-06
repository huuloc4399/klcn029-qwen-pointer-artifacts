"""End-to-end checks for upload, scoring, consent storage and withdrawal."""

from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cv_evaluation_web"))
from app import create_app  # noqa: E402


JD_TEXT = """
Junior Backend Developer. Required skills: Python, FastAPI, PostgreSQL, Docker and REST API.
Responsibilities include building APIs, writing unit tests and collaborating with the product team.
""".strip()


REMOTE_OUTPUT = {
    "status": "success",
    "cv": {
        "personal_info": {"name": "[MASKED]", "email": "[MASKED]", "phone": "[MASKED]", "github_url": ""},
        "summary": "Backend developer seeking a junior role.",
        "skills": {"hard_skills": ["Python", "FastAPI", "PostgreSQL", "REST API"], "soft_skills": []},
        "experience": [],
        "projects": [{
            "name": "REST API",
            "role": "Backend developer",
            "technologies": ["Python", "FastAPI", "PostgreSQL"],
            "details": "Built a REST API with FastAPI and PostgreSQL for 120 users. Improved response time by 30 percent.",
        }],
        "education": [{"degree": "Bachelor of Software Engineering", "university": "", "gpa": None, "year_graduated": None}],
        "certifications": [],
        "activities": [],
        "awards": [],
    },
    "evidence": {"summary": {"span": [2, 2], "text": "Backend developer seeking a junior role."}},
    "parser": {"parser_version": "cvpointer_output_parser_v1", "strict_json": True, "cvschema_valid": True},
    "manifest": {
        "model_id": "Qwen/Qwen3-4B-Instruct-2507",
        "worker_version": "qwen_pointer_runpod_worker_v1",
        "input_tokens": 310,
        "generated_tokens": 140,
        "runtime_seconds": 0.12,
        "document": {
            "route": "render_native_pdf_text",
            "page_count": 1,
            "native_text_pages": 1,
            "character_count": 240,
            "ocr_pages": 0,
        },
    },
}


class FakeRunPodClient:
    def __init__(self):
        self.submitted = []

    def submit(self, job_input, *, webhook_url=None):
        self.submitted.append({"input": job_input, "webhook": webhook_url})
        return {"id": "remote_job_01", "status": "IN_QUEUE"}

    def status(self, job_id):
        assert job_id == "remote_job_01"
        return {"id": job_id, "status": "COMPLETED", "output": REMOTE_OUTPUT}


def sample_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    text = """SUMMARY
Backend developer seeking a junior role.
SKILLS
Python, FastAPI, PostgreSQL, Git, REST API
PROJECTS
Built a REST API with FastAPI and PostgreSQL for 120 users.
Improved response time by 30 percent.
EDUCATION
Bachelor of Software Engineering
"""
    page.insert_textbox(pymupdf.Rect(60, 60, 530, 780), text, fontsize=11)
    payload = document.tobytes()
    document.close()
    return payload


class WebFlowTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = ROOT / "cv_evaluation_web" / "data" / ".qa" / uuid.uuid4().hex
        self.tempdir.mkdir(parents=True, exist_ok=False)
        app = create_app({"TESTING": True, "CSRF_ENABLED": False, "DATA_DIR": str(self.tempdir), "MAX_CONTENT_LENGTH": 2 * 1024 * 1024})
        self.client = app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _post(self, *, research: bool):
        data = {
            "cv_file": (io.BytesIO(sample_pdf()), "candidate.pdf"),
            "jd_text": JD_TEXT,
            "language": "en",
            "participant_code": "PILOT-01",
            "consent_evaluation": "yes",
        }
        if research:
            data["consent_research"] = "yes"
        return self.client.post("/evaluate", data=data, content_type="multipart/form-data")

    def test_home_and_health(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Đánh giá CV", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/api/health").get_json()["status"], "ok")

    def test_no_research_consent_does_not_store_pdf(self):
        response = self._post(research=False)
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("CV không được lưu", body)
        self.assertEqual(list((self.tempdir / "submissions").glob("*/cv.pdf")), [])

    def test_opt_in_stores_and_withdrawal_deletes(self):
        response = self._post(research=True)
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Cảm ơn bạn đã đóng góp", body)
        stored = list((self.tempdir / "submissions").glob("*/cv.pdf"))
        self.assertEqual(len(stored), 1)
        database = self.tempdir / "submissions.sqlite3"
        self.assertTrue(database.is_file())

        # Obtain the one-time code from the rendered <code> element.
        start = body.index("<code>") + len("<code>")
        end = body.index("</code>", start)
        code = body[start:end].strip()
        withdrawn = self.client.post("/withdraw", data={"withdrawal_code": code})
        self.assertIn("đã được xóa", withdrawn.get_data(as_text=True))
        self.assertEqual(list((self.tempdir / "submissions").glob("*/cv.pdf")), [])

    def test_rejects_missing_consent_and_short_jd(self):
        response = self.client.post(
            "/evaluate",
            data={"cv_file": (io.BytesIO(sample_pdf()), "candidate.pdf"), "jd_text": "Short", "language": "en"},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        body = response.get_data(as_text=True)
        self.assertIn("đồng ý xử lý tạm thời", body)
        self.assertIn("ít nhất 80 ký tự", body)

    def test_csrf_is_required_when_enabled(self):
        csrf_dir = self.tempdir / "csrf"
        app = create_app({
            "TESTING": True,
            "CSRF_ENABLED": True,
            "DATA_DIR": str(csrf_dir),
            "SECRET_KEY": "test-only-secret",
        })
        client = app.test_client()
        response = client.post(
            "/evaluate",
            data={"cv_file": (io.BytesIO(sample_pdf()), "candidate.pdf"), "jd_text": JD_TEXT},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)

    def test_rate_limit_blocks_second_valid_upload(self):
        limited_dir = self.tempdir / "rate"
        app = create_app({
            "TESTING": True,
            "CSRF_ENABLED": False,
            "DATA_DIR": str(limited_dir),
            "RATE_LIMIT_PER_HOUR": 1,
        })
        client = app.test_client()

        def submit():
            return client.post(
                "/evaluate",
                data={
                    "cv_file": (io.BytesIO(sample_pdf()), "candidate.pdf"),
                    "jd_text": JD_TEXT,
                    "language": "en",
                    "consent_evaluation": "yes",
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(submit().status_code, 200)
        self.assertEqual(submit().status_code, 429)


class RunPodWebFlowTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = ROOT / "cv_evaluation_web" / "data" / ".qa" / uuid.uuid4().hex
        self.tempdir.mkdir(parents=True, exist_ok=False)
        self.remote = FakeRunPodClient()
        app = create_app({
            "TESTING": True,
            "DATA_DIR": str(self.tempdir),
            "PIPELINE_MODE": "runpod",
            "RUNPOD_CLIENT": self.remote,
            "RUNPOD_WEBHOOK_SECRET": "",
            "CSRF_ENABLED": False,
        })
        self.client = app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _submit(self, research=False):
        data = {
            "cv_file": (io.BytesIO(sample_pdf()), "candidate.pdf"),
            "jd_text": JD_TEXT,
            "language": "en",
            "participant_code": "ASYNC-01",
            "consent_evaluation": "yes",
        }
        if research:
            data["consent_research"] = "yes"
        return self.client.post("/evaluate", data=data, content_type="multipart/form-data")

    def test_async_qwen_flow_completes_and_deletes_opt_out_pdf(self):
        submitted = self._submit(research=False)
        self.assertEqual(submitted.status_code, 303)
        processing_url = submitted.headers["Location"]
        token = processing_url.rsplit("/", 1)[-1]
        status = self.client.get(f"/api/jobs/{token}").get_json()
        self.assertEqual(status["status"], "COMPLETED")
        result = self.client.get(status["result_url"])
        body = result.get_data(as_text=True)
        self.assertIn("Qwen Pointer P0", body)
        self.assertIn("310 token đầu vào", body)
        self.assertIn("CV không được lưu", body)
        self.assertFalse((self.tempdir / "jobs" / token / "cv.pdf").exists())
        self.assertEqual(len(self.remote.submitted), 1)

    def test_async_qwen_flow_stores_only_after_opt_in_completion(self):
        submitted = self._submit(research=True)
        token = submitted.headers["Location"].rsplit("/", 1)[-1]
        self.assertEqual(list((self.tempdir / "submissions").glob("*/cv.pdf")), [])
        status = self.client.get(f"/api/jobs/{token}").get_json()
        self.assertEqual(status["status"], "COMPLETED")
        self.assertEqual(len(list((self.tempdir / "submissions").glob("*/cv.pdf"))), 1)
        repeated = self.client.get(f"/api/jobs/{token}").get_json()
        self.assertEqual(repeated["status"], "COMPLETED")
        self.assertEqual(len(list((self.tempdir / "submissions").glob("*/cv.pdf"))), 1)


if __name__ == "__main__":
    unittest.main()
