"""Exercise the public Render form through RunPod with a synthetic PDF."""

from __future__ import annotations

import argparse
import io
import re
import time

import pymupdf
import requests


JD = """Junior Backend Developer. Required skills include Python, FastAPI, PostgreSQL,
Docker, REST API and automated testing. Build reliable services and collaborate with a product team."""


def synthetic_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_textbox(
        pymupdf.Rect(60, 60, 530, 780),
        """SUMMARY
Backend developer focused on reliable API services.
SKILLS
Python, FastAPI, PostgreSQL, Git, REST API
EXPERIENCE
Backend Developer - Example Systems
2024 - Present
Built REST APIs for an internal inventory application.
PROJECTS
Inventory API
Role: Backend Developer
Tech: Python, FastAPI, PostgreSQL
Implemented endpoints and automated tests for inventory workflows.
EDUCATION
Bachelor of Software Engineering - Example University - 2023
""",
        fontsize=11,
    )
    data = document.tobytes()
    document.close()
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", help="Render URL, for example https://cv-insight.onrender.com")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    session = requests.Session()
    home = session.get(base_url, timeout=30)
    home.raise_for_status()
    csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', home.text)
    if not csrf_match:
        raise SystemExit("Could not find the CSRF token on the upload form")
    submitted = session.post(
        f"{base_url}/evaluate",
        data={
            "csrf_token": csrf_match.group(1),
            "jd_text": JD,
            "language": "en",
            "participant_code": "PUBLIC-SMOKE",
            "consent_evaluation": "yes",
        },
        files={"cv_file": ("synthetic-smoke.pdf", io.BytesIO(synthetic_pdf()), "application/pdf")},
        allow_redirects=False,
        timeout=60,
    )
    if submitted.status_code != 303 or "/processing/" not in submitted.headers.get("Location", ""):
        raise SystemExit(f"Upload failed: HTTP {submitted.status_code}: {submitted.text[:500]}")
    processing_url = requests.compat.urljoin(base_url, submitted.headers["Location"])
    token = processing_url.rstrip("/").rsplit("/", 1)[-1]
    deadline = time.monotonic() + args.timeout
    last_status = None
    while time.monotonic() < deadline:
        status_response = session.get(f"{base_url}/api/jobs/{token}", timeout=30)
        status_response.raise_for_status()
        payload = status_response.json()
        status = str(payload.get("status", "UNKNOWN")).upper()
        if status != last_status:
            print(f"Render job {token}: {status}")
            last_status = status
        if status == "COMPLETED":
            result_url = requests.compat.urljoin(base_url, payload["result_url"])
            result = session.get(result_url, timeout=30)
            result.raise_for_status()
            required = ["Pipeline đã xác minh", "Qwen/Qwen3-4B-Instruct-2507", "CV không được lưu"]
            missing = [value for value in required if value not in result.text]
            if missing:
                raise SystemExit(f"Result page is missing evidence: {missing}")
            print("Render + RunPod end-to-end smoke test: PASSED")
            return
        if status in {"FAILED", "TIMED_OUT", "CANCELLED", "NOT_FOUND"}:
            raise SystemExit(f"End-to-end job failed: {payload}")
        time.sleep(5)
    raise SystemExit(f"End-to-end smoke test exceeded {args.timeout} seconds")


if __name__ == "__main__":
    main()
