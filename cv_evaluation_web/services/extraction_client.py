"""Client for the team's extraction API (deployment/hf_space_api), hosted on the Oracle Always
Free VM (deployment/oracle_api) or on a Hugging Face Space.

The API (deployment/hf_space_api) returns RunPod-compatible job payloads, so the web app
finalizes results with the same code path. Messages are user-facing Vietnamese text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from services.runpod_client import RemoteJobError


class ExtractionAPIError(RemoteJobError):
    """The Space is asleep, rebuilding, misconfigured or overloaded."""


@dataclass(slots=True)
class ExtractionAPIClient:
    base_url: str
    api_key: str
    hf_token: str = ""  # only needed when the Space is private
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        self.base_url = self.base_url.strip().rstrip("/")
        self.api_key = self.api_key.strip()
        self.hf_token = self.hf_token.strip()
        if not self.base_url.startswith("https://") or not self.api_key:
            raise ValueError("EXTRACTION_API_URL (https) and EXTRACTION_API_KEY are required")

    @property
    def headers(self) -> dict[str, str]:
        headers = {"X-API-Key": self.api_key, "Accept": "application/json"}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        return headers

    def _json(self, response: requests.Response) -> dict[str, Any]:
        if response.status_code in {401, 403}:
            raise ExtractionAPIError("Web chưa được cấu hình đúng khóa của máy chủ trích xuất.")
        if response.status_code in {502, 503, 504} or "application/json" not in response.headers.get("Content-Type", ""):
            # A sleeping or rebuilding Space answers with an HTML placeholder page.
            raise ExtractionAPIError(
                "Máy chủ trích xuất đang khởi động (sau thời gian không dùng có thể mất 3–5 phút). Hãy thử lại sau."
            )
        if response.status_code == 429:
            raise ExtractionAPIError("Máy chủ trích xuất đang bận với nhiều CV. Hãy thử lại sau vài phút.")
        try:
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ExtractionAPIError("Máy chủ trích xuất trả về phản hồi không hợp lệ.") from exc
        if not isinstance(body, dict):
            raise ExtractionAPIError("Máy chủ trích xuất trả về phản hồi không hợp lệ.")
        return body

    def submit(self, job_input: dict[str, Any], *, webhook_url: str | None = None) -> dict[str, Any]:
        del webhook_url  # the Space API is polled; it never calls back into the web app
        payload = {key: value for key, value in job_input.items() if key != "request_id"}
        try:
            response = requests.post(f"{self.base_url}/v1/jobs", headers=self.headers, json=payload,
                                     timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ExtractionAPIError("Không kết nối được máy chủ trích xuất.") from exc
        body = self._json(response)
        if not isinstance(body.get("id"), str) or not body["id"]:
            raise ExtractionAPIError("Máy chủ trích xuất không trả về mã tác vụ hợp lệ.")
        return body

    def status(self, job_id: str) -> dict[str, Any]:
        if not job_id or any(char not in "0123456789abcdef" for char in job_id):
            raise ValueError("Invalid extraction job id")
        try:
            response = requests.get(f"{self.base_url}/v1/jobs/{job_id}", headers=self.headers,
                                    timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ExtractionAPIError("Không kết nối được máy chủ trích xuất.") from exc
        if response.status_code == 404:
            # Jobs live in the Space's memory; a restart or the one-hour TTL drops them.
            return {"id": job_id, "status": "FAILED",
                    "error": "Máy chủ trích xuất đã khởi động lại hoặc tác vụ đã hết hạn. Hãy gửi lại CV."}
        body = self._json(response)
        if not isinstance(body.get("status"), str):
            raise ExtractionAPIError("Máy chủ trích xuất trả về trạng thái không hợp lệ.")
        return body

    def list_feedback(self, limit: int = 5000) -> list[dict[str, Any]]:
        """Stored ratings, most recent first (admin page)."""
        try:
            response = requests.get(f"{self.base_url}/v1/feedback", headers=self.headers,
                                    params={"limit": limit}, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ExtractionAPIError("Không kết nối được máy chủ trích xuất để đọc đánh giá.") from exc
        records = self._json(response).get("records")
        if not isinstance(records, list):
            raise ExtractionAPIError("Máy chủ trích xuất trả về danh sách đánh giá không hợp lệ.")
        return [record for record in records if isinstance(record, dict)]

    def health(self) -> dict[str, Any]:
        try:
            response = requests.get(f"{self.base_url}/health", headers=self.headers, timeout=10)
        except requests.RequestException as exc:
            raise ExtractionAPIError("Không kết nối được máy chủ trích xuất.") from exc
        return self._json(response)

    def retrieve(self, query: str, top_k: int = 3, roles: list[str] | None = None) -> dict[str, Any]:
        """Knowledge-base chunks for the RAG strategy (bge-m3 on the API host), optionally by role tag."""
        payload: dict[str, Any] = {"query": query[:4000], "top_k": top_k}
        if roles:
            payload["roles"] = roles
        try:
            response = requests.post(f"{self.base_url}/v1/retrieve", headers=self.headers,
                                     json=payload, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ExtractionAPIError("Không kết nối được máy chủ embedding.") from exc
        body = self._json(response)
        if not isinstance(body.get("results"), list):
            raise ExtractionAPIError("Máy chủ embedding trả về kết quả không hợp lệ.")
        return body

    def submit_feedback(self, record: dict[str, Any]) -> bool:
        """Store one rating on the API host; False when this result was already rated."""
        try:
            response = requests.post(f"{self.base_url}/v1/feedback", headers=self.headers, json=record,
                                     timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ExtractionAPIError("Chưa gửi được đánh giá đến máy chủ. Hãy thử lại sau.") from exc
        if response.status_code == 409:
            return False
        self._json(response)
        return True
