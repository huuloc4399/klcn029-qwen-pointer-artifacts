"""Smoke-test the deployed extraction API with one synthetic CV (no real CV leaves the machine).

Env: EXTRACTION_API_URL (https://<user>-<space>.hf.space), EXTRACTION_API_KEY,
     EXTRACTION_HF_TOKEN (only for a private Space).
Usage: python deployment/hf_space_api/smoke_api.py [--pdf path/to/synthetic.pdf]
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "training/colab/artifacts/gguf_fidelity_bundle_v1.zip"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, help="send a PDF instead of the synthetic text sample")
    parser.add_argument("--timeout-minutes", type=float, default=20)
    args = parser.parse_args()
    base_url = os.environ["EXTRACTION_API_URL"].rstrip("/")
    headers = {"X-API-Key": os.environ["EXTRACTION_API_KEY"]}
    if os.environ.get("EXTRACTION_HF_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['EXTRACTION_HF_TOKEN']}"

    health = requests.get(f"{base_url}/health", headers=headers, timeout=60)
    print("health:", health.status_code, health.text[:300])
    if args.pdf:
        payload = {"language": "auto", "pdf_base64": base64.b64encode(args.pdf.read_bytes()).decode()}
    else:
        with zipfile.ZipFile(BUNDLE) as bundle:
            sample = json.loads(bundle.read("fidelity_set.jsonl").decode("utf-8").splitlines()[0])
        payload = {"language": "en", "source_text": sample["source_text"], "page_count": 1, "native_text_pages": 1}

    started = time.time()
    submitted = requests.post(f"{base_url}/v1/jobs", headers=headers, json=payload, timeout=60)
    print("submit:", submitted.status_code, submitted.text[:300])
    submitted.raise_for_status()
    job_id = submitted.json()["id"]
    while time.time() - started < args.timeout_minutes * 60:
        time.sleep(10)
        body = requests.get(f"{base_url}/v1/jobs/{job_id}", headers=headers, timeout=60).json()
        print(f"{time.time() - started:6.0f}s", body["status"])
        if body["status"] in {"COMPLETED", "FAILED"}:
            break
    output = body.get("output") or {}
    manifest = output.get("manifest") or {}
    summary = {
        "job_status": body["status"],
        "extraction_status": output.get("status"),
        "error": body.get("error") or output.get("error"),
        "input_tokens": manifest.get("input_tokens"),
        "generated_tokens": manifest.get("generated_tokens"),
        "model_seconds": manifest.get("runtime_seconds"),
        "queue_ms": body.get("delayTime"),
        "execution_ms": body.get("executionTime"),
        "hard_skills": (output.get("cv") or {}).get("skills", {}).get("hard_skills", [])[:8],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if body["status"] != "COMPLETED" or output.get("status") != "success":
        sys.exit("smoke: FAILED")
    print("smoke: passed")


if __name__ == "__main__":
    main()
