"""Durable store for user satisfaction ratings sent by the web app.

Render's free web service has no persistent disk, so the web forwards each rating to this API,
whose host keeps FEEDBACK_DIR on a volume (Oracle VM: /data/feedback). A record holds the rating,
an optional comment with contact data masked, and non-identifying result metadata. No CV, JD or
job id is stored. One JSON line per rating; a rating id can be recorded only once.
"""

from __future__ import annotations

import json
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from baseline_extraction.privacy import redact_text


class DuplicateFeedbackError(ValueError):
    pass


class FeedbackStore:
    def __init__(self, directory: str | Path) -> None:
        self.path = Path(directory) / "feedback.jsonl"
        self._lock = threading.Lock()
        self._ids: set[str] | None = None

    def _records(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
        return records

    def add(self, record: dict[str, Any]) -> dict[str, Any]:
        stored = {
            **record,
            "comment": redact_text(record.get("comment") or "").strip(),
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            if self._ids is None:
                self._ids = {item.get("id") for item in self._records()}
            if stored["id"] in self._ids:
                raise DuplicateFeedbackError("Kết quả này đã được đánh giá.")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(stored, ensure_ascii=False) + "\n")
            self._ids.add(stored["id"])
        return stored

    def records(self, limit: int = 5000) -> list[dict[str, Any]]:
        """Most recent ratings first, for the web admin page."""
        with self._lock:
            records = self._records()
        return list(reversed(records))[:limit]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            records = self._records()
        ratings = [int(item["rating"]) for item in records if isinstance(item.get("rating"), int)]
        distribution = Counter(ratings)
        return {
            "count": len(ratings),
            "mean_rating": round(sum(ratings) / len(ratings), 3) if ratings else None,
            "distribution": {str(stars): distribution.get(stars, 0) for stars in range(1, 6)},
            "with_comment": sum(1 for item in records if item.get("comment")),
        }
