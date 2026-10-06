"""Small, testable client for a queue-based RunPod Serverless endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"})


class RunPodError(RuntimeError):
    """Raised when the remote endpoint cannot accept or describe a job."""


@dataclass(slots=True)
class RunPodClient:
    endpoint_id: str
    api_key: str
    timeout_seconds: float = 30.0
    base_url: str = "https://api.runpod.ai/v2"

    def __post_init__(self) -> None:
        self.endpoint_id = self.endpoint_id.strip()
        self.api_key = self.api_key.strip()
        if not self.endpoint_id or not self.api_key:
            raise ValueError("RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY are required")

    @property
    def endpoint_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.endpoint_id}"

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def submit(self, job_input: dict[str, Any], *, webhook_url: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "input": job_input,
            "policy": {"executionTimeout": 900_000, "ttl": 3_600_000},
        }
        if webhook_url:
            payload["webhook"] = webhook_url
        try:
            response = requests.post(
                f"{self.endpoint_url}/run",
                headers=self.headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RunPodError("Không thể gửi tác vụ đến dịch vụ trích xuất.") from exc
        job_id = body.get("id")
        if not isinstance(job_id, str) or not job_id.strip():
            raise RunPodError("RunPod không trả về mã tác vụ hợp lệ.")
        return body

    def status(self, job_id: str) -> dict[str, Any]:
        if not job_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in job_id):
            raise ValueError("Invalid RunPod job id")
        try:
            response = requests.get(
                f"{self.endpoint_url}/status/{job_id}",
                headers=self.headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RunPodError("Không thể kiểm tra trạng thái tác vụ trích xuất.") from exc
        if not isinstance(body, dict) or not isinstance(body.get("status"), str):
            raise RunPodError("RunPod trả về trạng thái không hợp lệ.")
        return body
