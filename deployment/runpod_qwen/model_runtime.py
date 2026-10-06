"""Exact Qwen base + QLoRA adapter runtime used by the serverless handler."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
MODEL_REVISION = "1b4199c4f36b0cef378bfb12390c18780c18af4c"
EXPECTED_ADAPTER_SHA256 = "8d68628e382593132010f20fb12cbb18d9477ca034c154811d109ec075a65f81"
EXPECTED_CHAT_TEMPLATE_SHA256 = "40c21f34cf67d8c760ef72f8ad3ae5afad514299d4b06e91dd9a8d705af7b541"
MAX_INPUT_TOKENS = 5120
MAX_NEW_TOKENS = 768


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class QwenPointerRuntime:
    def __init__(self) -> None:
        import torch
        from huggingface_hub import snapshot_download
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA GPU is required for the production worker")
        artifact_repo = os.environ["ARTIFACT_REPO_ID"]
        artifact_revision = os.getenv("ARTIFACT_REVISION") or None
        hf_token = os.getenv("HF_TOKEN") or None
        artifact_root = Path(
            snapshot_download(
                repo_id=artifact_repo,
                revision=artifact_revision,
                token=hf_token,
                allow_patterns=["final_adapter/*"],
            )
        )
        adapter_dir = artifact_root / "final_adapter"
        adapter_weights = adapter_dir / "adapter_model.safetensors"
        if _sha256_file(adapter_weights) != EXPECTED_ADAPTER_SHA256:
            raise RuntimeError("Adapter weight hash mismatch")

        self.tokenizer = AutoTokenizer.from_pretrained(
            adapter_dir, use_fast=True, trust_remote_code=False
        )
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        chat_hash = hashlib.sha256(self.tokenizer.chat_template.encode("utf-8")).hexdigest()
        if chat_hash != EXPECTED_CHAT_TEMPLATE_SHA256:
            raise RuntimeError("Chat template hash mismatch")

        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        base = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            revision=MODEL_REVISION,
            quantization_config=quantization,
            device_map={"": 0},
            dtype=torch.float16,
            attn_implementation="sdpa",
            trust_remote_code=False,
            token=hf_token,
        )
        self.model = PeftModel.from_pretrained(base, adapter_dir, is_trainable=False)
        self.model.eval()
        self.model.config.use_cache = True
        self.torch = torch

    def generate(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        encoded = self.tokenizer(prompt, return_tensors="pt")
        input_tokens = int(encoded["input_ids"].shape[1])
        if input_tokens > MAX_INPUT_TOKENS:
            raise ValueError(f"Prompt has {input_tokens} tokens; maximum is {MAX_INPUT_TOKENS}")
        encoded = {key: value.to(self.model.device) for key, value in encoded.items()}
        self.torch.cuda.synchronize()
        started = time.perf_counter()
        with self.torch.inference_mode():
            generated = self.model.generate(
                **encoded,
                do_sample=False,
                max_new_tokens=MAX_NEW_TOKENS,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                use_cache=True,
            )
        self.torch.cuda.synchronize()
        runtime_seconds = time.perf_counter() - started
        new_ids = generated[0, input_tokens:]
        raw_output = self.tokenizer.decode(new_ids, skip_special_tokens=True).strip()
        return {
            "raw_output": raw_output,
            "input_tokens": input_tokens,
            "generated_tokens": int(new_ids.numel()),
            "runtime_seconds": round(runtime_seconds, 6),
        }


_RUNTIME: QwenPointerRuntime | None = None


def get_runtime() -> QwenPointerRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = QwenPointerRuntime()
    return _RUNTIME
