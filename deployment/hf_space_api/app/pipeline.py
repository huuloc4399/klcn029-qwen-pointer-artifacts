"""Extraction pipeline from the Colab demo: route PDF -> Pointer prompt -> Qwen -> Parser v1 -> acceptance v2.

The output object keeps the RunPod worker contract consumed by cv_evaluation_web
(status/cv/evidence/parser/manifest), so the web app finalizes jobs the same way.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from baseline_extraction.privacy import redact_text
from prompting import build_messages
from training.evaluation.deployment_policy import (
    DEPLOYMENT_ACCEPTANCE_POLICY_VERSION,
    assess_pointer_result,
    normalized_cvschema_for_deployment,
)
from training.evaluation.pointer_parser import POINTER_PARSER_VERSION, parse_pointer_output

from .llm_runtime import MAX_NEW_TOKENS, MODEL_ID, MODEL_REVISION, ADAPTER_MODEL_SHA256
from .ocr import MAX_INPUT_CHARACTERS, DocumentError, OCREngines, route_pdf


API_VERSION = "klcn029_pointer_cpu_api_v1"
METHOD_LABEL = "Qwen Pointer P0 (GGUF, CPU) + Parser v1 + real-CV acceptance v2"
MAX_PDF_BYTES = 8 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
FROZEN_SOURCE_HASHES = {
    "training/evaluation/pointer_parser.py": "43df8c6971a7c30d37a593930ed3c6ab34605f3187173a88e374b2af9627940e",
    "training/evaluation/parser.py": "67950be62e4fd6abba5ec24fe87d32f8a27042086f4612f960129904c1cbb0e5",
    "baseline_extraction/schema.py": "15f30db15ae4e97a29ee49c16ce7459fa0c7df509015d56747e6a3c618ff0bdb",
}


class Runtime(Protocol):
    def generate(self, messages: list[dict[str, str]]) -> dict[str, Any]: ...


def verify_runtime_sources(root: Path = ROOT) -> dict[str, str]:
    """Refuse to serve if the frozen parser or any copied module differs from the build manifest."""
    expected = dict(FROZEN_SOURCE_HASHES)
    manifest_path = root / "RUNTIME_MANIFEST.json"
    if manifest_path.is_file():
        expected.update(json.loads(manifest_path.read_text(encoding="utf-8"))["files"])
    observed = {}
    for relative, digest in expected.items():
        actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        if actual != digest:
            raise RuntimeError(f"Runtime source hash mismatch: {relative}")
        observed[relative] = actual
    return observed


def _document_from_text(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    text = redact_text(payload["source_text"], first_page=True)
    if len(text) > MAX_INPUT_CHARACTERS:
        raise DocumentError(f"CV có {len(text)} ký tự, vượt giới hạn {MAX_INPUT_CHARACTERS}; hệ thống không cắt ngầm.")
    return text, {
        "route": "web_native_pdf_text",
        "language": payload.get("language", "auto"),
        "page_count": int(payload.get("page_count") or 0),
        "native_text_pages": int(payload.get("native_text_pages") or 0),
        "ocr_pages": 0,
        "character_count": len(text),
        "ocr_quality_warning": False,
    }


def _document_from_pdf(payload: dict[str, Any], engines: OCREngines) -> tuple[str, dict[str, Any]]:
    try:
        pdf_bytes = base64.b64decode(payload["pdf_base64"], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DocumentError("pdf_base64 không hợp lệ.") from exc
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise DocumentError("PDF vượt giới hạn 8 MB.")
    routed = route_pdf(pdf_bytes, payload.get("language", "auto"), engines)
    return routed.text, routed.public_dict()


def process_request(payload: dict[str, Any], runtime: Runtime, engines: OCREngines) -> dict[str, Any]:
    if payload.get("source_text"):
        source_text, document = _document_from_text(payload)
    else:
        source_text, document = _document_from_pdf(payload, engines)

    messages, normalized_source = build_messages(source_text)
    generation = runtime.generate(messages)
    parsed = parse_pointer_output(generation["raw_output"], normalized_source)
    decision = assess_pointer_result(parsed)
    cv_schema = normalized_cvschema_for_deployment(parsed, decision)
    manifest = {
        "worker_version": API_VERSION,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "adapter_model_sha256": ADAPTER_MODEL_SHA256,
        "gguf": getattr(runtime, "artifact", None),
        "parser_version": POINTER_PARSER_VERSION,
        "deployment_policy_version": DEPLOYMENT_ACCEPTANCE_POLICY_VERSION,
        "decoding": {"do_sample": False, "max_new_tokens": MAX_NEW_TOKENS},
        "source_sha256": hashlib.sha256(normalized_source.encode("utf-8")).hexdigest(),
        "document": document,
        "input_tokens": generation["input_tokens"],
        "generated_tokens": generation["generated_tokens"],
        "hit_max_new_tokens": generation.get("hit_max_new_tokens", False),
        "runtime_seconds": generation["runtime_seconds"],
    }
    parse_payload = parsed.to_dict()
    if not decision.accepted or cv_schema is None:
        return {
            "status": "rejected",
            "error": "Kết quả Qwen chưa vượt Parser v1 và chính sách triển khai.",
            "issues": parse_payload.get("issues", []),
            "deployment": decision.to_dict(),
            "manifest": manifest,
        }
    return {
        "status": "success",
        "method_label": METHOD_LABEL,
        "cv": cv_schema,
        "evidence": parsed.evidence,
        "parser": {
            "parser_version": parsed.parser_version,
            "status": parsed.status,
            "strict_json": parsed.strict_json,
            "recovery_steps": list(parsed.recovery_steps),
            "cvschema_valid": parsed.cvschema_valid,
            "skill_policy_valid": parsed.skill_policy_valid,
        },
        "deployment": decision.to_dict(),
        "manifest": manifest,
    }
