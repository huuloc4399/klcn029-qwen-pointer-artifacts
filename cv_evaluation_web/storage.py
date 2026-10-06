"""Private storage for opt-in research submissions."""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


POLICY_VERSION = "research-consent-v1-2026-10-06"


class SubmissionStore:
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir).resolve()
        self.submissions_dir = self.data_dir / "submissions"
        self.db_path = self.data_dir / "submissions.sqlite3"
        self.submissions_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS submissions (
                    submission_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    language TEXT NOT NULL,
                    participant_code TEXT NOT NULL,
                    consent_policy_version TEXT NOT NULL,
                    withdrawal_hash TEXT NOT NULL UNIQUE,
                    directory_name TEXT NOT NULL UNIQUE,
                    page_count INTEGER NOT NULL,
                    total_score REAL NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_submissions_sha ON submissions(source_sha256)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS request_events (
                    identifier_hash TEXT NOT NULL,
                    created_epoch INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_request_events ON request_events(identifier_hash, created_epoch)"
            )

    def allow_request(self, identifier_hash: str, *, maximum: int, window_seconds: int) -> bool:
        """Apply a persistent fixed-window limit without storing source IPs."""

        import time

        now = int(time.time())
        cutoff = now - window_seconds
        with self._connection() as connection:
            connection.execute("DELETE FROM request_events WHERE created_epoch < ?", (cutoff,))
            count = connection.execute(
                "SELECT COUNT(*) AS count FROM request_events WHERE identifier_hash = ? AND created_epoch >= ?",
                (identifier_hash, cutoff),
            ).fetchone()["count"]
            if int(count) >= maximum:
                return False
            connection.execute(
                "INSERT INTO request_events(identifier_hash, created_epoch) VALUES (?, ?)",
                (identifier_hash, now),
            )
        return True

    def save_opt_in(
        self,
        *,
        pdf_path: Path,
        language: str,
        participant_code: str,
        jd_text: str,
        extraction: dict,
        evaluation: dict,
    ) -> dict[str, str]:
        submission_id = secrets.token_hex(12)
        withdrawal_code = secrets.token_urlsafe(18)
        withdrawal_hash = hashlib.sha256(withdrawal_code.encode("utf-8")).hexdigest()
        created_at = datetime.now(timezone.utc).isoformat()
        source_sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        target_dir = (self.submissions_dir / submission_id).resolve()
        if not target_dir.is_relative_to(self.submissions_dir):
            raise RuntimeError("Invalid submission path")
        target_dir.mkdir(parents=False, exist_ok=False)
        try:
            shutil.copy2(pdf_path, target_dir / "cv.pdf")
            (target_dir / "jd.txt").write_text(jd_text, encoding="utf-8")
            metadata = {
                "submission_id": submission_id,
                "created_at": created_at,
                "source_sha256": source_sha256,
                "language": language,
                "participant_code": participant_code,
                "consent_policy_version": POLICY_VERSION,
                "extraction": extraction,
                "evaluation": evaluation,
            }
            (target_dir / "submission.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO submissions (
                        submission_id, created_at, source_sha256, language,
                        participant_code, consent_policy_version, withdrawal_hash,
                        directory_name, page_count, total_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        submission_id, created_at, source_sha256, language,
                        participant_code, POLICY_VERSION, withdrawal_hash,
                        submission_id, int(extraction["page_count"]), float(evaluation["total_score"]),
                    ),
                )
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise
        return {"submission_id": submission_id, "withdrawal_code": withdrawal_code}

    def withdraw(self, withdrawal_code: str) -> bool:
        code_hash = hashlib.sha256(withdrawal_code.strip().encode("utf-8")).hexdigest()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT submission_id, directory_name FROM submissions WHERE withdrawal_hash = ?", (code_hash,)
            ).fetchone()
            if row is None:
                return False
            target = (self.submissions_dir / row["directory_name"]).resolve()
            if target.is_relative_to(self.submissions_dir):
                shutil.rmtree(target, ignore_errors=True)
            connection.execute("DELETE FROM submissions WHERE submission_id = ?", (row["submission_id"],))
        return True

    def public_stats(self) -> dict[str, int]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS submissions, COUNT(DISTINCT source_sha256) AS distinct_cvs FROM submissions"
            ).fetchone()
        return {"submissions": int(row["submissions"]), "distinct_cvs": int(row["distinct_cvs"])}
