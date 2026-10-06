"""Export the frozen Pointer prompt without packaging the training dataset."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "training/data/resume_parsing_vision_cvschema_v2_pointer_v1/train.jsonl"
OUTPUT = Path(__file__).resolve().parent / "prompt_contract.json"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> None:
    first = json.loads(SOURCE.read_text(encoding="utf-8").splitlines()[0])
    system_prompt = first["messages"][0]["content"]
    user_prefix = first["messages"][1]["content"].split("\n\n[L0001]", 1)[0]
    payload = {
        "contract_version": "cvpointer_prompt_v1",
        "system_prompt": system_prompt,
        "system_prompt_sha256": digest(system_prompt),
        "user_prefix": user_prefix,
        "user_prefix_sha256": digest(user_prefix),
        "line_format": "[L{line_number:04d}] {text}",
        "source": "resume_parsing_vision_cvschema_v2_pointer_v1/train.jsonl:first-record",
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
