"""Frozen prompt construction shared by RunPod inference and tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


CONTRACT_PATH = Path(__file__).resolve().parent / "prompt_contract.json"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_contract() -> dict:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    for field in ("system_prompt", "user_prefix"):
        if _sha256(contract[field]) != contract[f"{field}_sha256"]:
            raise RuntimeError(f"Prompt contract hash mismatch: {field}")
    return contract


def normalize_source_text(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("source_text must be a string")
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        raise ValueError("source_text has no non-empty lines")
    return "\n".join(lines)


def build_messages(source_text: str) -> tuple[list[dict[str, str]], str]:
    source_text = normalize_source_text(source_text)
    contract = load_contract()
    indexed = "\n".join(
        contract["line_format"].format(line_number=index, text=line)
        for index, line in enumerate(source_text.splitlines(), 1)
    )
    messages = [
        {"role": "system", "content": contract["system_prompt"]},
        {"role": "user", "content": f"{contract['user_prefix']}\n\n{indexed}"},
    ]
    return messages, source_text
