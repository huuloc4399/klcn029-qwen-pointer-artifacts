"""Persistent, atomic state for asynchronous CV evaluation jobs."""

from __future__ import annotations

import json
import os
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class JobStore:
    def __init__(self, data_dir: str | Path) -> None:
        self.root = Path(data_dir).resolve() / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _directory(self, token: str) -> Path:
        if len(token) != 48 or any(char not in "0123456789abcdef" for char in token):
            raise ValueError("Invalid job token")
        target = (self.root / token).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Invalid job path")
        return target

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)

    def create(
        self,
        *,
        pdf_path: Path,
        jd_text: str,
        language: str,
        participant_code: str,
        research_consent: bool,
        document: dict[str, Any],
    ) -> str:
        token = secrets.token_hex(24)
        directory = self._directory(token)
        directory.mkdir(parents=False, exist_ok=False)
        try:
            shutil.copy2(pdf_path, directory / "cv.pdf")
            (directory / "jd.txt").write_text(jd_text, encoding="utf-8")
            self._write_json(
                directory / "job.json",
                {
                    "token": token,
                    "created_at": self._now(),
                    "updated_at": self._now(),
                    "status": "CREATED",
                    "remote_job_id": None,
                    "language": language,
                    "participant_code": participant_code,
                    "research_consent": research_consent,
                    "document": document,
                },
            )
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        return token

    def load(self, token: str) -> dict[str, Any] | None:
        path = self._directory(token) / "job.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def update(self, token: str, **changes: Any) -> dict[str, Any]:
        directory = self._directory(token)
        path = directory / "job.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.update(changes)
        payload["updated_at"] = self._now()
        self._write_json(path, payload)
        return payload

    def find_by_remote_id(self, remote_job_id: str) -> str | None:
        for path in self.root.glob("*/job.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if payload.get("remote_job_id") == remote_job_id:
                return str(payload.get("token"))
        return None

    def pdf_path(self, token: str) -> Path:
        return self._directory(token) / "cv.pdf"

    def jd_text(self, token: str) -> str:
        return (self._directory(token) / "jd.txt").read_text(encoding="utf-8")

    def result(self, token: str) -> dict[str, Any] | None:
        path = self._directory(token) / "result.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def complete(self, token: str, result: dict[str, Any]) -> None:
        directory = self._directory(token)
        self._write_json(directory / "result.json", result)
        (directory / "cv.pdf").unlink(missing_ok=True)
        (directory / "jd.txt").unlink(missing_ok=True)
        self.update(token, status="COMPLETED")

    def fail(self, token: str, message: str) -> None:
        directory = self._directory(token)
        (directory / "cv.pdf").unlink(missing_ok=True)
        (directory / "jd.txt").unlink(missing_ok=True)
        self.update(token, status="FAILED", error=message[:500])

    def delete(self, token: str) -> None:
        shutil.rmtree(self._directory(token), ignore_errors=True)

    def cleanup(self, *, pending_hours: int = 3, completed_hours: int = 24) -> None:
        now = datetime.now(timezone.utc)
        for path in self.root.glob("*/job.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                updated = datetime.fromisoformat(payload["updated_at"])
                age_limit = completed_hours if payload.get("status") in {"COMPLETED", "FAILED"} else pending_hours
                if updated < now - timedelta(hours=age_limit):
                    shutil.rmtree(path.parent, ignore_errors=True)
            except (OSError, ValueError, KeyError):
                continue
