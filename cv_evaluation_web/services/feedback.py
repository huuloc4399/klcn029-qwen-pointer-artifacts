"""Satisfaction ratings (1–5 stars + optional comment) collected under each result.

The result page carries a signed context token, so a rating can only be sent for a result the
server produced, and the stored metadata (score, language, route, model time) cannot be forged.
No CV or JD content is ever part of a rating. With the free deployment the web forwards ratings
to the extraction API, whose host has persistent storage; other modes keep them locally.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from pathlib import Path
from typing import Any

from baseline_extraction.privacy import redact_text


FEEDBACK_SALT = "result-feedback-v1"
FEEDBACK_MAX_AGE_SECONDS = 7 * 24 * 3600
COMMENT_LIMIT = 1000
RATING_LABELS = {1: "Rất không hài lòng", 2: "Chưa hài lòng", 3: "Bình thường", 4: "Hài lòng", 5: "Rất hài lòng"}


def feedback_id_for_job(secret: bytes, token: str) -> str:
    """Stable id per async result, so reloading the result page cannot rate it twice."""
    return hmac.new(secret, f"feedback:{token}".encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def result_context(result: dict[str, Any], pipeline: dict[str, Any] | None, *,
                   language: str, pipeline_mode: str) -> dict[str, Any]:
    """Non-identifying facts about the rated result (matches the API's FeedbackContext)."""
    pipeline = pipeline or {}
    context = {
        "pipeline_mode": pipeline_mode,
        "language": language,
        "total_score": round(float(result["total_score"]), 2),
        "verdict": str(result.get("verdict", ""))[:60] or None,
        "method": str(result.get("method", ""))[:200] or None,
        "document_route": pipeline.get("document_route"),
        "ocr_quality_warning": pipeline.get("ocr_quality_warning"),
        "generated_tokens": pipeline.get("generated_tokens"),
        "model_runtime_seconds": pipeline.get("model_runtime_seconds"),
    }
    return {key: value for key, value in context.items() if value is not None}


def clean_comment(comment: str) -> str:
    return redact_text(comment.strip()).strip()


class LocalFeedbackStore:
    """JSON-lines store for modes whose web host keeps its disk (local, RunPod with a disk)."""

    def __init__(self, data_dir: str | Path) -> None:
        self.path = Path(data_dir).resolve() / "feedback" / "feedback.jsonl"
        self._lock = threading.Lock()

    def add(self, record: dict[str, Any]) -> bool:
        """Append the rating; False when this result was already rated."""
        with self._lock:
            if self.path.is_file():
                for line in self.path.read_text(encoding="utf-8").splitlines():
                    try:
                        if json.loads(line).get("id") == record["id"]:
                            return False
                    except ValueError:
                        continue
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True

    def records(self) -> list[dict[str, Any]]:
        """Most recent ratings first (admin page)."""
        with self._lock:
            if not self.path.is_file():
                return []
            lines = self.path.read_text(encoding="utf-8").splitlines()
        records = []
        for line in lines:
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
        return list(reversed(records))
