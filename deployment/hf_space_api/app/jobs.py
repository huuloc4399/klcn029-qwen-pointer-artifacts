"""In-memory job queue with one CPU worker.

CPU inference takes minutes, so requests are asynchronous: submit returns a job id and the
web app polls. Jobs live only in memory (no CV is written to disk) and expire after a TTL.
The status payload mirrors RunPod's /status shape that cv_evaluation_web already handles.
"""

from __future__ import annotations

import itertools
import logging
import queue
import statistics
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable


LOGGER = logging.getLogger("klcn029.jobs")
TERMINAL = {"COMPLETED", "FAILED"}


class QueueFullError(RuntimeError):
    pass


@dataclass(slots=True)
class Job:
    id: str
    payload: dict[str, Any] | None
    order: int = 0
    status: str = "IN_QUEUE"
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    output: dict[str, Any] | None = None
    error: str | None = None

    def public(self) -> dict[str, Any]:
        now = time.time()
        body: dict[str, Any] = {
            "id": self.id,
            "status": self.status,
            "delayTime": int(((self.started or now) - self.created) * 1000),
        }
        if self.started is not None:
            body["executionTime"] = int(((self.finished or now) - self.started) * 1000)
        if self.output is not None:
            body["output"] = self.output
        if self.error is not None:
            body["error"] = self.error
        return body


class JobQueue:
    def __init__(self, process: Callable[[dict[str, Any]], dict[str, Any]], *,
                 max_pending: int = 8, ttl_seconds: int = 3600, default_job_seconds: float = 330.0) -> None:
        self._process = process
        self._max_pending = max_pending
        self._ttl = ttl_seconds
        self._jobs: dict[str, Job] = {}
        self._pending: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._order = itertools.count(1)
        # Until real jobs finish, estimates use the per-CV time measured by the GGUF fidelity run.
        self._default_job_seconds = default_job_seconds
        self._recent_seconds: deque[float] = deque(maxlen=10)

    def start(self) -> None:
        if self._worker is None:
            self._worker = threading.Thread(target=self._run, name="extraction-worker", daemon=True)
            self._worker.start()

    @property
    def pending(self) -> int:
        return self._pending.qsize()

    def estimate_seconds(self) -> float:
        """Median duration of recent completed jobs (robust to one long OCR CV)."""
        with self._lock:
            recent = list(self._recent_seconds)
        return statistics.median(recent) if recent else self._default_job_seconds

    def public(self, job: Job) -> dict[str, Any]:
        """Status payload plus queue position and a rough ETA while the job is not finished.

        queuePosition counts jobs that run before this one (the running job included), so a
        waiting job with queuePosition 2 has one job in progress and one more queued ahead.
        Only counts are exposed, never anything about other users' CVs.
        """
        estimate = self.estimate_seconds()
        now = time.time()
        with self._lock:
            body = job.public()
            if job.status in TERMINAL:
                return body
            running = [other for other in self._jobs.values() if other.status == "IN_PROGRESS"]
            running_left = sum(max(estimate - (now - (other.started or now)), 0.0) for other in running)
            if job.status == "IN_PROGRESS":
                position, eta = 0, max(estimate - (now - (job.started or now)), 0.0)
            else:
                queued_ahead = sum(1 for other in self._jobs.values()
                                   if other.status == "IN_QUEUE" and other.payload is not None and other.order < job.order)
                position = len(running) + queued_ahead
                eta = running_left + (queued_ahead + 1) * estimate
        body.update({"queuePosition": position, "etaSeconds": int(round(eta)), "estimateSeconds": int(round(estimate))})
        return body

    def submit(self, payload: dict[str, Any]) -> Job:
        self._expire()
        with self._lock:
            if self._pending.qsize() >= self._max_pending:
                raise QueueFullError("Hàng đợi đang đầy; hãy thử lại sau vài phút.")
            job = Job(id=uuid.uuid4().hex, payload=payload, order=next(self._order))
            self._jobs[job.id] = job
        self._pending.put(job.id)
        return job

    def get(self, job_id: str) -> Job | None:
        self._expire()
        with self._lock:
            return self._jobs.get(job_id)

    def fail_all_pending(self, message: str) -> None:
        while True:
            try:
                job_id = self._pending.get_nowait()
            except queue.Empty:
                return
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    job.status, job.error, job.payload, job.finished = "FAILED", message, None, time.time()

    def _expire(self) -> None:
        cutoff = time.time() - self._ttl
        with self._lock:
            for job_id in [key for key, job in self._jobs.items() if job.created < cutoff]:
                del self._jobs[job_id]

    def _run(self) -> None:
        while True:
            job_id = self._pending.get()
            with self._lock:
                job = self._jobs.get(job_id)
                if job is None or job.payload is None:
                    continue
                payload, job.payload = job.payload, None
                job.status, job.started = "IN_PROGRESS", time.time()
            try:
                output = self._process(payload)
                with self._lock:
                    job.output, job.status = output, "COMPLETED"
                    self._recent_seconds.append(time.time() - job.started)
            except ValueError as exc:
                # ValueError subclasses carry user-facing messages (bad PDF, prompt too long).
                with self._lock:
                    job.error, job.status = str(exc), "FAILED"
            except Exception:
                LOGGER.exception("Extraction job %s failed", job_id)
                with self._lock:
                    job.error, job.status = "Lỗi nội bộ khi trích xuất CV.", "FAILED"
            finally:
                job.finished = time.time()
