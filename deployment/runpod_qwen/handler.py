"""RunPod Serverless handler for the frozen P0 extraction baseline."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import runpod

import baseline_extraction.schema as schema_module
import training.evaluation.parser as parser_module
import training.evaluation.pointer_parser as pointer_parser_module
from baseline_extraction.privacy import redact_text
from training.evaluation.pointer_parser import POINTER_PARSER_VERSION, parse_pointer_output

from document_ingest import ingest_pdf_base64
from model_runtime import (
    EXPECTED_ADAPTER_SHA256,
    MAX_NEW_TOKENS,
    MODEL_ID,
    MODEL_REVISION,
    get_runtime,
)
from prompting import build_messages


WORKER_VERSION = "qwen_pointer_runpod_worker_v1"
FROZEN_SOURCE_HASHES = {
    "pointer_parser": "43df8c6971a7c30d37a593930ed3c6ab34605f3187173a88e374b2af9627940e",
    "parser": "67950be62e4fd6abba5ec24fe87d32f8a27042086f4612f960129904c1cbb0e5",
    "schema": "15f30db15ae4e97a29ee49c16ce7459fa0c7df509015d56747e6a3c618ff0bdb",
}


def _sha256_path(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_frozen_runtime() -> None:
    observed = {
        "pointer_parser": _sha256_path(pointer_parser_module.__file__),
        "parser": _sha256_path(parser_module.__file__),
        "schema": _sha256_path(schema_module.__file__),
    }
    if observed != FROZEN_SOURCE_HASHES:
        raise RuntimeError(f"Frozen parser source mismatch: {observed}")


verify_frozen_runtime()


def _request_source(job_input: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    language = str(job_input.get("language", "auto")).lower()
    source_text = job_input.get("source_text")
    if isinstance(source_text, str) and source_text.strip():
        return source_text, {
            "route": "render_native_pdf_text",
            "page_count": int(job_input.get("page_count", 0)),
            "native_text_pages": int(job_input.get("native_text_pages", 0)),
            "ocr_pages": 0,
            "character_count": len(source_text),
            "ocr_quality_warning": False,
        }
    pdf_base64 = job_input.get("pdf_base64")
    if isinstance(pdf_base64, str) and pdf_base64:
        ingested = ingest_pdf_base64(pdf_base64, language)
        return ingested.text, {"route": "runpod_pdf_router", **ingested.public_dict()}
    raise ValueError("Provide source_text or pdf_base64")


def process_job(job: dict[str, Any], *, runtime=None) -> dict[str, Any]:
    job_input = job.get("input")
    if not isinstance(job_input, dict):
        raise ValueError("input must be an object")
    source_text, document = _request_source(job_input)
    source_text = redact_text(source_text, first_page=True)
    messages, normalized_source = build_messages(source_text)
    model_runtime = runtime or get_runtime()
    generation = model_runtime.generate(messages)
    parsed = parse_pointer_output(generation["raw_output"], normalized_source)
    manifest = {
        "worker_version": WORKER_VERSION,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "adapter_model_sha256": EXPECTED_ADAPTER_SHA256,
        "parser_version": POINTER_PARSER_VERSION,
        "decoding": {"do_sample": False, "max_new_tokens": MAX_NEW_TOKENS},
        "source_sha256": hashlib.sha256(normalized_source.encode("utf-8")).hexdigest(),
        "document": document,
        "input_tokens": generation["input_tokens"],
        "generated_tokens": generation["generated_tokens"],
        "runtime_seconds": generation["runtime_seconds"],
    }
    if parsed.status != "success":
        return {
            "status": parsed.status,
            "error": "Model output did not pass the frozen parser contract",
            "parser": parsed.to_dict(),
            "manifest": manifest,
        }
    return {
        "status": "success",
        "cv": parsed.reconstructed_cvschema,
        "evidence": parsed.evidence,
        "parser": {
            "parser_version": parsed.parser_version,
            "strict_json": parsed.strict_json,
            "recovery_steps": list(parsed.recovery_steps),
            "cvschema_valid": parsed.cvschema_valid,
            "skill_policy_valid": parsed.skill_policy_valid,
        },
        "manifest": manifest,
    }


def handler(job: dict[str, Any]) -> dict[str, Any]:
    runpod.serverless.progress_update(job, "Đang trích xuất CV bằng Qwen Pointer P0")
    return process_job(job)


if __name__ == "__main__":
    if os.getenv("PRELOAD_MODEL", "1") == "1" and "--test_input" not in os.sys.argv:
        get_runtime()
    runpod.serverless.start({"handler": handler})
