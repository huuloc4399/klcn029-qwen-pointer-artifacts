"""Static validation for the Colab ipywidgets UI notebook."""

from __future__ import annotations

import ast
import hashlib
import json
import secrets
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


NOTEBOOK = Path(__file__).with_name("Qwen3_Pointer_Colab_UI_Demo.ipynb")


@contextmanager
def writable_tempdir():
    path = NOTEBOOK.parent / f".pointer_ui_validation_{secrets.token_hex(8)}"
    path.mkdir()
    try:
        yield str(path)
    finally:
        resolved = path.resolve()
        if resolved.parent != NOTEBOOK.parent.resolve():
            raise RuntimeError(f"Refusing to remove unexpected validation path: {resolved}")
        shutil.rmtree(resolved)


def main() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    sources = ["".join(cell.get("source", [])) for cell in notebook["cells"] if cell["cell_type"] == "code"]
    joined = "\n".join(sources)
    required = [
        "widgets.FileUpload", "widgets.Textarea", "Đánh giá CV", "score-card",
        "OCR_PIPELINE_SOURCE", "EXTRACTION_PIPELINE_SOURCE", "EVALUATION_PIPELINE_SOURCE",
        "cvpointer_output_parser_v1", "RESEARCH_CONSENT", "files.download",
        "CONSENT_VERSION", "consent.json", "submission_index.jsonl", "withdrawal_code",
    ]
    missing = [item for item in required if item not in joined]
    if missing:
        raise AssertionError(f"UI notebook thiếu thành phần: {missing}")
    forbidden = ["gradio", "share=True", "ngrok", "cloudflared", "localtunnel"]
    hits = [item for item in forbidden if item.casefold() in joined.casefold()]
    if hits:
        raise AssertionError(f"UI notebook mở public service: {hits}")
    for index, value in enumerate(sources):
        python = "\n".join(line for line in value.splitlines() if not line.lstrip().startswith(("%", "!")))
        ast.parse(python, filename=f"cell_{index}")

    ui_source = next(value for value in sources if "def _save_failed_research_submission" in value)
    ui_tree = ast.parse(ui_source)
    storage_function = next(
        node for node in ui_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_save_failed_research_submission"
    )
    function_module = ast.Module(body=[storage_function], type_ignores=[])
    ast.fix_missing_locations(function_module)
    with writable_tempdir() as temporary:
        namespace = {
            "Path": Path,
            "RESULT_ROOT": Path(temporary) / "research",
            "CONSENT_VERSION": "test-consent-v1",
            "datetime": datetime,
            "timezone": timezone,
            "hashlib": hashlib,
            "json": json,
        }
        exec(compile(function_module, "storage_function", "exec"), namespace, namespace)
        pdf_bytes = b"%PDF-1.4\nsynthetic-test-only"
        receipt = namespace["_save_failed_research_submission"](
            "test.pdf", pdf_bytes, "JD " * 40, "P001", "vi", RuntimeError("synthetic"), 2,
        )
        target = Path(receipt["drive_path"])
        assert (target / "cv.pdf").read_bytes() == pdf_bytes
        assert all((target / name).is_file() for name in ("jd.txt", "consent.json", "failure.json", "receipt.json"))
        stored_receipt = json.loads((target / "receipt.json").read_text(encoding="utf-8"))
        assert receipt["withdrawal_code"] not in json.dumps(stored_receipt)
        assert stored_receipt["withdrawal_hash"] == hashlib.sha256(receipt["withdrawal_code"].encode()).hexdigest()
        index = (namespace["RESULT_ROOT"] / "submission_index.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(index) == 1 and json.loads(index[0])["pipeline_status"] == "failed"

    evaluation_source = next(
        ast.literal_eval(node.value)
        for node in ui_tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "EVALUATION_PIPELINE_SOURCE" for target in node.targets)
    )
    consent_tail = evaluation_source.split("research_receipt = None", 1)[1].split("bundle_path =", 1)[0]
    consent_tail = "research_receipt = None" + consent_tail
    with writable_tempdir() as temporary:
        temporary_path = Path(temporary)
        pdf_path = temporary_path / "input.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nsuccess-test-only")
        local_output = temporary_path / "result"
        local_output.mkdir()
        (local_output / "manifest.json").write_text("{}", encoding="utf-8")
        namespace = {
            "RESEARCH_CONSENT": True,
            "RESULT_ROOT": temporary_path / "research",
            "PDF_PATH": pdf_path,
            "JD_TEXT": "JD " * 40,
            "PARTICIPANT_CODE": "P002",
            "CONSENT_VERSION": "test-consent-v1",
            "original_name": "success.pdf",
            "pdf_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            "resolved_language": "en",
            "pages": [1, 2],
            "parse_result": SimpleNamespace(status="success"),
            "evaluation": {"total_score": 75.0},
            "local_output": local_output,
            "datetime": datetime,
            "timezone": timezone,
            "hashlib": hashlib,
            "json": json,
            "shutil": shutil,
        }
        exec(consent_tail, namespace, namespace)
        receipt = namespace["research_receipt"]
        target = Path(receipt["drive_path"])
        assert all((target / name).exists() for name in ("cv.pdf", "jd.txt", "consent.json", "receipt.json", "result"))
        stored_receipt = json.loads((target / "receipt.json").read_text(encoding="utf-8"))
        assert receipt["withdrawal_code"] not in json.dumps(stored_receipt)
        index = (namespace["RESULT_ROOT"] / "submission_index.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(index) == 1 and json.loads(index[0])["pipeline_status"] == "success"
    print({"notebook": str(NOTEBOOK), "cells": len(notebook["cells"]), "status": "valid"})


if __name__ == "__main__":
    main()
