"""End-to-end checks for upload, scoring, consent storage and withdrawal."""

from __future__ import annotations

import io
import json
import re
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


def feedback_context(body: str) -> str:
    """Signed context token from the rating form on a result page."""
    match = re.search(r'name="context" value="([^"]+)"', body)
    assert match, "result page has no rating form"
    return match.group(1)


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

    def test_local_feedback_is_stored_once(self):
        body = self._post(research=False).get_data(as_text=True)
        self.assertIn("Bạn hài lòng với kết quả này", body)
        context = feedback_context(body)
        stored = self.client.post("/feedback", data={"context": context, "rating": "4", "comment": "mail me: a@b.vn"},
                                  headers={"Accept": "application/json"})
        self.assertEqual(stored.status_code, 201)
        again = self.client.post("/feedback", data={"context": context, "rating": "2"}, headers={"Accept": "application/json"})
        self.assertEqual(again.get_json()["status"], "duplicate")
        lines = (self.tempdir / "feedback" / "feedback.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["rating"], 4)
        self.assertNotIn("a@b.vn", record["comment"])
        self.assertEqual(record["context"]["pipeline_mode"], "local_baseline")
        self.assertIn("total_score", record["context"])

    def test_feedback_rejects_bad_rating_and_forged_context(self):
        context = feedback_context(self._post(research=False).get_data(as_text=True))
        headers = {"Accept": "application/json"}
        self.assertEqual(self.client.post("/feedback", data={"context": context, "rating": "6"}, headers=headers).status_code, 400)
        self.assertEqual(self.client.post("/feedback", data={"context": context, "rating": ""}, headers=headers).status_code, 400)
        self.assertEqual(self.client.post("/feedback", data={"context": context[:-2] + "xx", "rating": "5"},
                                          headers=headers).status_code, 400)
        self.assertEqual(self.client.post("/feedback", data={"context": context, "rating": "5", "comment": "x" * 1001},
                                          headers=headers).status_code, 400)
        self.assertFalse((self.tempdir / "feedback" / "feedback.jsonl").exists())

    def test_feedback_without_javascript_renders_thank_you_page(self):
        context = feedback_context(self._post(research=False).get_data(as_text=True))
        response = self.client.post("/feedback", data={"context": context, "rating": "5"})
        self.assertEqual(response.status_code, 201)
        self.assertIn("Cảm ơn bạn đã đánh giá", response.get_data(as_text=True))

    def test_pdf_with_bytes_before_header_is_accepted(self):
        def upload(payload: bytes):
            return self.client.post("/evaluate", data={
                "cv_file": (io.BytesIO(payload), "candidate.pdf"), "jd_text": JD_TEXT,
                "language": "en", "consent_evaluation": "yes",
            }, content_type="multipart/form-data")

        self.assertEqual(upload(b"\n" + sample_pdf()).status_code, 200)
        rejected = upload(b"PK\x03\x04 not a pdf")
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("cấu trúc PDF", rejected.get_data(as_text=True))

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



class FakeSpaceClient:
    """Mimics deployment/hf_space_api: one in-flight status first, then a final payload."""

    def __init__(self, final, first=None):
        self.final = final
        self.first = first or {"status": "IN_PROGRESS", "delayTime": 10}
        self.submitted = []
        self.feedback = []
        self.polls = 0

    def submit(self, job_input, *, webhook_url=None):
        self.submitted.append(job_input)
        return {"id": "a" * 32, "status": "IN_QUEUE"}

    def status(self, job_id):
        self.polls += 1
        if self.polls == 1:
            return {"id": job_id, **self.first}
        return {"id": job_id, **self.final}

    def submit_feedback(self, record):
        if any(item["id"] == record["id"] for item in self.feedback):
            return False
        self.feedback.append(record)
        return True

    def list_feedback(self, limit=5000):
        return list(reversed(self.feedback))[:limit]

    def health(self):
        return {"model": "ready", "pending_jobs": 1, "job_seconds_estimate": 32,
                "gguf": {"backend": "llama-server"}}


class HFSpaceWebFlowTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = ROOT / "cv_evaluation_web" / "data" / ".qa" / uuid.uuid4().hex
        self.tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self):
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _app(self, final, research_enabled=False, first=None):
        self.remote = FakeSpaceClient(final, first)
        app = create_app({
            "TESTING": True,
            "DATA_DIR": str(self.tempdir),
            "PIPELINE_MODE": "hf_space",
            "REMOTE_CLIENT": self.remote,
            "RESEARCH_ENABLED": research_enabled,
            "CSRF_ENABLED": False,
        })
        return app.test_client()

    def _submit(self, client, research=True):
        data = {
            "cv_file": (io.BytesIO(sample_pdf()), "candidate.pdf"),
            "jd_text": JD_TEXT,
            "language": "en",
            "consent_evaluation": "yes",
        }
        if research:
            data["consent_research"] = "yes"
        return client.post("/evaluate", data=data, content_type="multipart/form-data")

    def test_research_disabled_hides_option_and_never_stores(self):
        client = self._app({"status": "COMPLETED", "output": {**REMOTE_OUTPUT, "method_label": "Qwen Pointer P0 (GGUF, CPU) + Parser v1"}})
        home = client.get("/").get_data(as_text=True)
        self.assertNotIn('name="consent_research"', home)
        self.assertIn("Oracle Cloud", home)
        token = self._submit(client, research=True).headers["Location"].rsplit("/", 1)[-1]
        self.assertEqual(client.get(f"/api/jobs/{token}").get_json()["status"], "IN_PROGRESS")
        status = client.get(f"/api/jobs/{token}").get_json()
        self.assertEqual(status["status"], "COMPLETED")
        body = client.get(status["result_url"]).get_data(as_text=True)
        self.assertIn("GGUF, CPU", body)
        self.assertEqual(list((self.tempdir / "submissions").glob("*/cv.pdf")), [])
        self.assertIn("source_text", self.remote.submitted[0])

    def test_infra_note_can_name_another_host(self):
        app = create_app({
            "TESTING": True, "DATA_DIR": str(self.tempdir), "PIPELINE_MODE": "hf_space",
            "REMOTE_CLIENT": FakeSpaceClient({}), "CSRF_ENABLED": False,
            "INFRA_NOTE": "Render vận hành web; máy tính của nhóm qua Cloudflare Tunnel vận hành model.",
        })
        body = app.test_client().get("/privacy").get_data(as_text=True)
        self.assertIn("Cloudflare Tunnel", body)
        self.assertNotIn("Oracle Cloud", body)

    def test_remote_failure_message_is_shown(self):
        client = self._app({"status": "FAILED", "error": "PDF có mật khẩu."})
        token = self._submit(client, research=False).headers["Location"].rsplit("/", 1)[-1]
        client.get(f"/api/jobs/{token}")
        status = client.get(f"/api/jobs/{token}").get_json()
        self.assertEqual(status, {"status": "FAILED", "message": "PDF có mật khẩu."})

    def test_queue_position_and_eta_are_shown(self):
        client = self._app({"status": "COMPLETED", "output": REMOTE_OUTPUT},
                           first={"status": "IN_QUEUE", "queuePosition": 2, "etaSeconds": 900, "estimateSeconds": 330})
        token = self._submit(client, research=False).headers["Location"].rsplit("/", 1)[-1]
        status = client.get(f"/api/jobs/{token}").get_json()
        self.assertEqual(status["queue_position"], 2)
        self.assertEqual(status["eta_seconds"], 900)
        self.assertIn("còn 2 CV trước bạn", status["message"])
        self.assertIn("12–18 phút", status["message"])

    def test_feedback_is_forwarded_once_without_cv_content(self):
        client = self._app({"status": "COMPLETED", "output": REMOTE_OUTPUT})
        token = self._submit(client, research=False).headers["Location"].rsplit("/", 1)[-1]
        client.get(f"/api/jobs/{token}")
        result_url = client.get(f"/api/jobs/{token}").get_json()["result_url"]
        context = feedback_context(client.get(result_url).get_data(as_text=True))
        form = {"context": context, "rating": "5", "comment": "Rất hữu ích, gọi 0912 345 678"}
        first = client.post("/feedback", data=form, headers={"Accept": "application/json"})
        self.assertEqual(first.status_code, 201, first.get_json())
        # Reloading the result page yields the same rating id, so a second rating is refused.
        second = client.post("/feedback", data={**form, "context": feedback_context(client.get(result_url).get_data(as_text=True))},
                             headers={"Accept": "application/json"})
        self.assertEqual(second.get_json()["status"], "duplicate")
        self.assertEqual(len(self.remote.feedback), 1)
        record = self.remote.feedback[0]
        self.assertEqual(record["rating"], 5)
        self.assertNotIn("0912", record["comment"])
        self.assertEqual(record["context"]["pipeline_mode"], "hf_space")
        self.assertEqual(record["context"]["generated_tokens"], 140)
        self.assertRegex(record["id"], r"^[0-9a-f]{32}$")
        self.assertNotIn("Backend developer", json.dumps(record, ensure_ascii=False))

    def test_rejected_extraction_fails_job(self):
        client = self._app({"status": "COMPLETED", "output": {"status": "rejected", "issues": []}})
        token = self._submit(client, research=False).headers["Location"].rsplit("/", 1)[-1]
        client.get(f"/api/jobs/{token}")
        self.assertEqual(client.get(f"/api/jobs/{token}").get_json()["status"], "FAILED")


ADMIN_KEY = "admin-key-for-tests-only"


class AdminPageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = ROOT / "cv_evaluation_web" / "data" / ".qa" / uuid.uuid4().hex
        self.tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self):
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _client(self, **config):
        app = create_app({"TESTING": True, "CSRF_ENABLED": False, "DATA_DIR": str(self.tempdir),
                          "ADMIN_KEY": ADMIN_KEY, **config})
        return app.test_client()

    def _rate(self, client, rating, comment):
        upload = client.post("/evaluate", data={
            "cv_file": (io.BytesIO(sample_pdf()), "candidate.pdf"), "jd_text": JD_TEXT,
            "language": "en", "consent_evaluation": "yes",
        }, content_type="multipart/form-data")
        context = feedback_context(upload.get_data(as_text=True))
        response = client.post("/feedback", data={"context": context, "rating": str(rating), "comment": comment},
                               headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 201)

    def test_admin_is_disabled_without_a_long_key(self):
        for key in ("", "short-key"):
            client = self._client(ADMIN_KEY=key)
            self.assertEqual(client.get("/admin").status_code, 404)
            self.assertEqual(client.get("/admin/login").status_code, 404)

    def test_login_required_and_wrong_key_rejected(self):
        client = self._client()
        self.assertEqual(client.get("/admin").headers["Location"], "/admin/login")
        self.assertEqual(client.get("/admin/feedback.jsonl").status_code, 303)
        wrong = client.post("/admin/login", data={"admin_key": "not-the-admin-key-123"})
        self.assertEqual(wrong.status_code, 400)
        self.assertEqual(client.get("/admin").status_code, 303)

    def test_login_attempts_are_rate_limited(self):
        client = self._client()
        codes = [client.post("/admin/login", data={"admin_key": f"wrong-key-attempt-{i:02d}"}).status_code for i in range(10)]
        blocked = client.post("/admin/login", data={"admin_key": ADMIN_KEY})
        self.assertEqual(set(codes), {400})
        self.assertIn("Quá nhiều lần đăng nhập", blocked.get_data(as_text=True))

    def test_dashboard_shows_local_ratings_escaped(self):
        client = self._client()
        self._rate(client, 5, "Rất hữu ích")
        self._rate(client, 2, "<script>alert(1)</script> chưa đúng")
        self.assertEqual(client.post("/admin/login", data={"admin_key": ADMIN_KEY}).status_code, 303)
        page = client.get("/admin")
        body = page.get_data(as_text=True)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["Cache-Control"], "no-store")
        self.assertIn("Đánh giá mức độ hài lòng", body)
        self.assertIn("3.5", body)  # mean of 5 and 2
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn('class="bar-chart"', body)
        filtered = client.get("/admin?stars=5").get_data(as_text=True)
        self.assertIn("Rất hữu ích", filtered)
        self.assertNotIn("&lt;script&gt;", filtered)
        download = client.get("/admin/feedback.jsonl")
        lines = download.get_data(as_text=True).splitlines()
        self.assertEqual([json.loads(line)["rating"] for line in lines], [5, 2])
        self.assertIn("attachment", download.headers["Content-Disposition"])
        client.post("/admin/logout")
        self.assertEqual(client.get("/admin").status_code, 303)

    def test_dashboard_reads_ratings_from_extraction_api(self):
        remote = FakeSpaceClient({"status": "COMPLETED", "output": REMOTE_OUTPUT})
        remote.feedback.append({"id": "e" * 32, "rating": 4, "comment": "Ổn",
                                "created_at": "2026-10-13T01:00:00+00:00",
                                "context": {"language": "vi", "total_score": 72.0, "document_route": "web_native_pdf_text"}})
        client = self._client(PIPELINE_MODE="hf_space", REMOTE_CLIENT=remote)
        client.post("/admin/login", data={"admin_key": ADMIN_KEY})
        body = client.get("/admin").get_data(as_text=True)
        self.assertIn("Máy chủ trích xuất sẵn sàng", body)
        self.assertIn("llama-server", body)
        self.assertIn("Ổn", body)
        self.assertIn("70–84", body)


class AdminReportTests(unittest.TestCase):
    def test_summary_and_chart_geometry(self):
        from datetime import date
        from services.admin_report import bar_chart, summarize

        records = [
            {"rating": 5, "comment": "a", "created_at": "2026-10-12T20:00:00+00:00", "context": {"language": "en", "total_score": 90}},
            {"rating": 3, "comment": "", "created_at": "2026-10-13T01:00:00+00:00", "context": {"language": "vi", "total_score": 40}},
        ]
        report = summarize(records, today=date(2026, 10, 13))
        self.assertEqual((report["count"], report["mean"], report["with_comment"]), (2, 4.0, 1))
        # 20:00 UTC on 12/10 is 03:00 on 13/10 in Vietnam, so both ratings fall on 13/10.
        self.assertEqual(report["days_with_ratings"][0]["count"], 2)
        self.assertEqual([row["count"] for row in report["distribution"]], [0, 0, 1, 0, 1])
        chart = bar_chart([("1", 0, ""), ("2", 7, "")])
        self.assertEqual([tick["value"] for tick in chart["ticks"]], [0, 2, 4, 6, 8])
        self.assertEqual(chart["bars"][0]["path"], "")
        self.assertTrue(chart["bars"][1]["path"].startswith("M"))


class ExtractionClientTests(unittest.TestCase):
    class Response:
        def __init__(self, status_code, body=None, content_type="application/json"):
            self.status_code = status_code
            self._body = body
            self.headers = {"Content-Type": content_type}

        def json(self):
            return self._body

        def raise_for_status(self):
            if self.status_code >= 400:
                import requests
                raise requests.HTTPError(str(self.status_code))

    def setUp(self):
        import services.extraction_client as module
        self.module = module
        self.client = module.ExtractionAPIClient("https://team-api.hf.space/", "key", hf_token="hf_x")
        self.calls = []
        self.original = (module.requests.post, module.requests.get)

    def tearDown(self):
        self.module.requests.post, self.module.requests.get = self.original

    def _respond(self, response):
        def fake(url, **kwargs):
            self.calls.append((url, kwargs))
            return response
        self.module.requests.post = self.module.requests.get = fake

    def test_submit_sends_both_keys_and_strips_request_id(self):
        self._respond(self.Response(202, {"id": "b" * 32, "status": "IN_QUEUE"}))
        self.client.submit({"request_id": "t", "language": "en", "source_text": "x"})
        url, kwargs = self.calls[0]
        self.assertEqual(url, "https://team-api.hf.space/v1/jobs")
        self.assertEqual(kwargs["headers"]["X-API-Key"], "key")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer hf_x")
        self.assertNotIn("request_id", kwargs["json"])

    def test_sleeping_space_html_is_a_friendly_error(self):
        self._respond(self.Response(200, None, content_type="text/html"))
        with self.assertRaises(self.module.ExtractionAPIError) as caught:
            self.client.submit({"language": "en", "source_text": "x"})
        self.assertIn("khởi động", str(caught.exception))

    def test_unknown_job_after_restart_becomes_failed(self):
        self._respond(self.Response(404, {"detail": "Job not found or expired"}))
        status = self.client.status("c" * 32)
        self.assertEqual(status["status"], "FAILED")

    def test_feedback_post_and_duplicate(self):
        self._respond(self.Response(201, {"id": "d" * 32, "status": "stored"}))
        self.assertTrue(self.client.submit_feedback({"id": "d" * 32, "rating": 5}))
        self.assertEqual(self.calls[0][0], "https://team-api.hf.space/v1/feedback")
        self._respond(self.Response(409, {"detail": "duplicate"}))
        self.assertFalse(self.client.submit_feedback({"id": "d" * 32, "rating": 5}))

    def test_requires_https_and_key(self):
        with self.assertRaises(ValueError):
            self.module.ExtractionAPIClient("http://insecure", "key")

if __name__ == "__main__":
    unittest.main()
