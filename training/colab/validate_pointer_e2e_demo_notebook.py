"""Static gates for the operator-assisted Pointer end-to-end Colab notebook."""

from __future__ import annotations

import ast
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
NOTEBOOK = HERE / "Qwen3_Pointer_EndToEnd_CV_JD_Demo_Colab.ipynb"


def main() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code_cells = ["".join(cell.get("source", [])) for cell in notebook["cells"] if cell["cell_type"] == "code"]
    joined = "\n".join(code_cells)
    required = [
        "qwen3_4b_cvschema2_pointer_stage2_full_v1",
        "cvpointer_output_parser_v1",
        "398ce7961eac9b3ccd1661116f9287bf2b0b6b20",
        "8d68628e382593132010f20fb12cbb18d9477ca034c154811d109ec075a65f81",
        "MAX_INPUT_TOKENS = 5120",
        "MAX_NEW_TOKENS = 768",
        '"PyMuPDF==1.26.7"',
        "import pymupdf",
        "do_sample=False",
        "parse_pointer_output(raw_output, normalized_source)",
        "assess_pointer_result(parse_result)",
        "real_cv_soft_skills_v2_2026-10-07",
        "deployment_acceptance.json",
        "MATCHING_STRATEGY",
        "EXTERNAL_MATCHING_CONSENT",
        "evaluate_with_strategy",
        "qwen/qwen3.8-27b",
        "deterministic matching baseline v1",
        "RESEARCH_CONSENT",
        "CONSENT_VERSION",
        "consent.json",
        "submission_index.jsonl",
        '"pipeline_status": "success"',
        "WITHDRAWAL_CODE_TO_DELETE",
    ]
    missing = [value for value in required if value not in joined]
    if missing:
        raise AssertionError(f"Notebook thiếu contract: {missing}")
    forbidden = ["gradio", "share=True", "ngrok", "cloudflared", "localtunnel"]
    hits = [value for value in forbidden if value.casefold() in joined.casefold()]
    if hits:
        raise AssertionError(f"Notebook mở public web/tunnel không phù hợp Colab free: {hits}")
    for index, source in enumerate(code_cells):
        python_lines = [line for line in source.splitlines() if not line.lstrip().startswith(("%", "!"))]
        ast.parse("\n".join(python_lines), filename=f"cell_{index}")
    print({"notebook": str(NOTEBOOK), "cells": len(notebook["cells"]), "status": "valid"})


if __name__ == "__main__":
    main()
