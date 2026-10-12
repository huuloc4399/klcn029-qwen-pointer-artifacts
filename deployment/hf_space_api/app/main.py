"""FastAPI service exposing the Colab extraction pipeline as an asynchronous job API.

POST /v1/jobs        submit {language, source_text | pdf_base64}; returns {id, status}
GET  /v1/jobs/{id}   RunPod-compatible status with output when COMPLETED
GET  /health         public liveness and model state (no CV data)

Every /v1 route requires the X-API-Key header to equal the API_KEY Space secret.
"""

from __future__ import annotations

import hmac
import logging
import os
import re
import threading
from contextlib import asynccontextmanager
from typing import Any, Callable, Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from .jobs import JobQueue, QueueFullError
from .ocr import OCREngines
from .pipeline import API_VERSION, Runtime, process_request, verify_runtime_sources


LOGGER = logging.getLogger("klcn029.api")
JOB_ID = re.compile(r"^[0-9a-f]{32}$")


class JobRequest(BaseModel):
    language: Literal["auto", "en", "vi"] = "auto"
    source_text: str | None = Field(default=None, max_length=60_000)
    pdf_base64: str | None = Field(default=None, max_length=11_500_000)
    page_count: int | None = Field(default=None, ge=0, le=12)
    native_text_pages: int | None = Field(default=None, ge=0, le=12)
    request_id: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def exactly_one_source(self) -> "JobRequest":
        if bool(self.source_text and self.source_text.strip()) == bool(self.pdf_base64):
            raise ValueError("Provide exactly one of source_text or pdf_base64")
        return self


class ModelState:
    def __init__(self) -> None:
        self.status = "loading"
        self.error: str | None = None
        self.runtime: Runtime | None = None


def create_app(runtime_factory: Callable[[], Runtime] | None = None, *,
               verify_sources: bool = True, max_pending: int | None = None) -> FastAPI:
    if verify_sources:
        verify_runtime_sources()
    state = ModelState()
    engines = OCREngines()
    jobs = JobQueue(
        lambda payload: process_request(payload, state.runtime, engines),
        max_pending=max_pending or int(os.getenv("MAX_PENDING_JOBS", "8")),
        ttl_seconds=int(os.getenv("JOB_TTL_SECONDS", "3600")),
    )

    def load_model() -> None:
        try:
            if runtime_factory is None:
                from .llm_runtime import load_runtime
                state.runtime = load_runtime()
            else:
                state.runtime = runtime_factory()
            state.status = "ready"
            jobs.start()
            LOGGER.info("Model ready")
        except Exception as exc:  # surfaced through /health; jobs fail fast
            LOGGER.exception("Model load failed")
            state.status, state.error = "error", str(exc)[:300]
            jobs.fail_all_pending("Model trích xuất không khởi động được trên máy chủ.")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Load in the background so /health answers while the GGUF downloads (Spaces
        # mark a container unhealthy if the port stays closed during a long startup).
        threading.Thread(target=load_model, name="model-loader", daemon=True).start()
        yield

    app = FastAPI(title="KLCN029 CV extraction API", version=API_VERSION,
                  docs_url=None, redoc_url=None, lifespan=lifespan)

    def require_key(x_api_key: str = Header(default="")) -> None:
        expected = os.getenv("API_KEY", "")
        if not expected:
            raise HTTPException(status_code=503, detail="API_KEY is not configured on the server")
        if not hmac.compare_digest(x_api_key.encode(), expected.encode()):
            raise HTTPException(status_code=401, detail="Invalid API key")

    @app.get("/")
    def root() -> dict[str, Any]:
        return {"service": "klcn029-cv-extraction-api", "health": "/health"}

    @app.get("/health")
    def health() -> dict[str, Any]:
        runtime = state.runtime
        return {
            "status": "ok",
            "api_version": API_VERSION,
            "model": state.status,
            "model_error": state.error,
            "pending_jobs": jobs.pending,
            "threads": getattr(runtime, "threads", None),
            "gguf": getattr(runtime, "artifact", None),
        }

    @app.post("/v1/jobs", status_code=202, dependencies=[Depends(require_key)])
    def submit(request: JobRequest) -> dict[str, Any]:
        if state.status == "error":
            raise HTTPException(status_code=503, detail="Model trích xuất không khởi động được trên máy chủ.")
        try:
            job = jobs.submit(request.model_dump(exclude_none=True))
        except QueueFullError as exc:
            return JSONResponse(status_code=429, content={"detail": str(exc)})
        return {"id": job.id, "status": job.status, "model": state.status}

    @app.get("/v1/jobs/{job_id}", dependencies=[Depends(require_key)])
    def status(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id) if JOB_ID.match(job_id) else None
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found or expired")
        return job.public()

    return app


def _default_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return create_app()


app = _default_app() if os.getenv("KLCN029_API_AUTOSTART", "1") == "1" else None
