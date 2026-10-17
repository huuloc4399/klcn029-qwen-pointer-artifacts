"""Save what Groq reports about the scoring model on the day of a run, as evidence for the report.

Calls GET https://api.groq.com/openai/v1/models/<model> with GROQ_API_KEY and writes the raw answer
with the access time to downstream/results/<run_id>/model_snapshot.json (one entry per call, appended,
so a run spread over several days keeps one entry per day). The key is never written.

    python -m downstream.eval.model_snapshot --run-id test_v1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from downstream.eval import run_strategies

MODELS_URL = "https://api.groq.com/openai/v1/models/{model}"


def snapshot(model: str, api_key: str, get=requests.get) -> dict:
    response = get(MODELS_URL.format(model=model), headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    try:
        body = response.json()
    except ValueError:
        body = {"text": response.text[:2000]}
    return {"accessed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model": model,
            "http_status": response.status_code, "response": body}


def main() -> int:
    parser = argparse.ArgumentParser(description="Record Groq's model metadata on the day of a run.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", default=None, help="defaults to the model in the run's run_config.json")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise SystemExit("GROQ_API_KEY is not set.")
    run_dir = run_strategies.RESULTS / args.run_id
    model = args.model
    if model is None:
        config = run_dir / "run_config.json"
        if not config.is_file():
            raise SystemExit(f"{config} not found; pass --model.")
        model = json.loads(config.read_text(encoding="utf-8"))["conditions"]["model"]
    entry = snapshot(model, key)
    path = run_dir / "model_snapshot.json"
    entries = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    entries.append(entry)
    run_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    return 0 if entry["http_status"] == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
