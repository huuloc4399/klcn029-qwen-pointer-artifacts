"""Smoke-test a deployed RunPod endpoint with synthetic, non-personal CV text."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from baseline_extraction.schema import CVSchema


SYNTHETIC_CV = """SUMMARY
Backend developer focused on reliable API services.
SKILLS
Python
FastAPI
PostgreSQL
EXPERIENCE
Example Systems | Backend Developer | 2024 - Present
Built REST APIs for an internal inventory application.
PROJECTS
Inventory API
Role: Backend Developer
Tech: Python, FastAPI, PostgreSQL
Implemented endpoints and automated tests for inventory workflows.
EDUCATION
Bachelor of Software Engineering | Example University | 2023
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint-id", default=os.getenv("RUNPOD_ENDPOINT_ID"))
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    api_key = os.getenv("RUNPOD_API_KEY", "").strip()
    if not args.endpoint_id or not api_key:
        raise SystemExit("Set RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY; do not paste keys into source code")

    base = f"https://api.runpod.ai/v2/{args.endpoint_id}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    submitted = requests.post(
        f"{base}/run",
        headers=headers,
        json={
            "input": {
                "language": "en",
                "source_text": SYNTHETIC_CV,
                "page_count": 1,
                "native_text_pages": 1,
            },
            "policy": {"executionTimeout": args.timeout * 1000, "ttl": 3_600_000},
        },
        timeout=30,
    )
    submitted.raise_for_status()
    job_id = submitted.json()["id"]
    deadline = time.monotonic() + args.timeout
    last_status = None
    while time.monotonic() < deadline:
        response = requests.get(f"{base}/status/{job_id}", headers=headers, timeout=30)
        response.raise_for_status()
        payload = response.json()
        status = str(payload.get("status", "UNKNOWN")).upper()
        if status != last_status:
            print(f"RunPod job {job_id}: {status}")
            last_status = status
        if status == "COMPLETED":
            output = payload.get("output") or {}
            if output.get("status") != "success":
                raise SystemExit(json.dumps(output, ensure_ascii=False, indent=2))
            try:
                CVSchema.model_validate(output.get("cv"))
            except ValidationError as exc:
                raise SystemExit(f"RunPod returned invalid CVSchema 2.0: {exc}") from exc
            print(json.dumps({
                "smoke": "passed",
                "model": (output.get("manifest") or {}).get("model_id"),
                "parser": (output.get("parser") or {}).get("parser_version"),
                "generated_tokens": (output.get("manifest") or {}).get("generated_tokens"),
                "runtime_seconds": (output.get("manifest") or {}).get("runtime_seconds"),
            }, ensure_ascii=False, indent=2))
            return
        if status in {"FAILED", "TIMED_OUT", "CANCELLED"}:
            raise SystemExit(json.dumps(payload, ensure_ascii=False, indent=2))
        time.sleep(5)
    raise SystemExit(f"RunPod smoke test exceeded {args.timeout} seconds")


if __name__ == "__main__":
    main()
