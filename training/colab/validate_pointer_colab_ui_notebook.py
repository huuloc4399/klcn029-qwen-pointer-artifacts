"""Static validation for the Colab ipywidgets UI notebook."""

from __future__ import annotations

import ast
import json
from pathlib import Path


NOTEBOOK = Path(__file__).with_name("Qwen3_Pointer_Colab_UI_Demo.ipynb")


def main() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    sources = ["".join(cell.get("source", [])) for cell in notebook["cells"] if cell["cell_type"] == "code"]
    joined = "\n".join(sources)
    required = [
        "widgets.FileUpload", "widgets.Textarea", "Đánh giá CV", "score-card",
        "OCR_PIPELINE_SOURCE", "EXTRACTION_PIPELINE_SOURCE", "EVALUATION_PIPELINE_SOURCE",
        "cvpointer_output_parser_v1", "RESEARCH_CONSENT", "files.download",
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
    print({"notebook": str(NOTEBOOK), "cells": len(notebook["cells"]), "status": "valid"})


if __name__ == "__main__":
    main()
