"""llama.cpp runtime for the merged Qwen3-4B + Pointer Stage 2 GGUF.

The Colab pipeline runs the base model in bitsandbytes NF4 with the LoRA adapter on a GPU.
Free CPU hosting cannot do that, so the adapter is merged into the base model and exported
to GGUF (see training/colab/Qwen3_Pointer_GGUF_Export_Colab.ipynb). Prompt, decoding and
parser stay identical; quantization can still change outputs, which the export notebook
measures before a GGUF is published.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any


MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
MODEL_REVISION = "1b4199c4f36b0cef378bfb12390c18780c18af4c"
ADAPTER_MODEL_SHA256 = "8d68628e382593132010f20fb12cbb18d9477ca034c154811d109ec075a65f81"
MAX_INPUT_TOKENS = 5120
MAX_NEW_TOKENS = 768
CONTEXT_TOKENS = 6144
END_OF_TURN = "<|im_end|>"


class PromptTooLongError(ValueError):
    """The indexed CV does not fit the frozen input budget; it is never truncated."""


def render_chatml(messages: list[dict[str, str]]) -> str:
    """Qwen3-Instruct-2507 chat template with add_generation_prompt=True.

    The export notebook asserts this string equals tokenizer.apply_chat_template()
    for the validation prompts before the GGUF is uploaded.
    """
    rendered = "".join(f"<|im_start|>{m['role']}\n{m['content']}{END_OF_TURN}\n" for m in messages)
    return rendered + "<|im_start|>assistant\n"


def available_cpus() -> int:
    """CPU quota of the container; os.cpu_count() reports host cores on Spaces."""
    override = os.getenv("LLAMA_THREADS", "").strip()
    if override:
        return max(1, int(override))
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()[:2]
        if quota != "max":
            return max(1, int(int(quota) / int(period)))
    except (OSError, ValueError):
        pass
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except AttributeError:
        return max(1, os.cpu_count() or 1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_gguf() -> tuple[Path, dict[str, str]]:
    """Fetch the pinned GGUF from the private artifact repo and verify its hash."""
    from huggingface_hub import hf_hub_download

    repo_id = os.getenv("GGUF_REPO_ID", "").strip()
    filename = os.getenv("GGUF_FILENAME", "").strip()
    revision = os.getenv("GGUF_REVISION", "").strip()
    expected = os.getenv("GGUF_SHA256", "").strip().lower()
    missing = [name for name, value in (("GGUF_REPO_ID", repo_id), ("GGUF_FILENAME", filename),
                                        ("GGUF_REVISION", revision), ("GGUF_SHA256", expected)) if not value]
    if missing:
        raise RuntimeError("Missing Space variables: " + ", ".join(missing))
    path = Path(hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        revision=revision,
        token=os.getenv("HF_TOKEN") or None,
    ))
    observed = sha256_file(path)
    if observed != expected:
        raise RuntimeError(f"GGUF hash mismatch: expected {expected}, observed {observed}")
    return path, {"repo_id": repo_id, "filename": filename, "revision": revision, "sha256": observed}


class LlamaPointerRuntime:
    def __init__(self, model_path: Path, artifact: dict[str, str]) -> None:
        from llama_cpp import Llama

        self.threads = available_cpus()
        self.artifact = artifact
        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=CONTEXT_TOKENS,
            n_batch=512,
            n_threads=self.threads,
            n_threads_batch=self.threads,
            seed=42,
            use_mmap=True,
            verbose=False,
        )

    def generate(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        prompt = render_chatml(messages)
        tokens = self.llm.tokenize(prompt.encode("utf-8"), add_bos=False, special=True)
        if len(tokens) > MAX_INPUT_TOKENS:
            raise PromptTooLongError(
                f"CV dài {len(tokens)} token, vượt giới hạn {MAX_INPUT_TOKENS}; hệ thống không cắt ngầm."
            )
        started = time.perf_counter()
        # Greedy decoding as in Colab (do_sample=False). llama.cpp defaults to a 1.1 repeat
        # penalty, which would change greedy outputs, so every penalty is disabled explicitly.
        # The shared system prompt + schema prefix is reused from the previous call's KV cache.
        completion = self.llm.create_completion(
            prompt=tokens,
            max_tokens=MAX_NEW_TOKENS,
            temperature=0.0,
            top_k=1,
            top_p=1.0,
            min_p=0.0,
            repeat_penalty=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            stop=[END_OF_TURN],
        )
        runtime_seconds = time.perf_counter() - started
        choice = completion["choices"][0]
        return {
            "raw_output": choice["text"].strip(),
            "input_tokens": len(tokens),
            "generated_tokens": int(completion["usage"]["completion_tokens"]),
            "hit_max_new_tokens": choice.get("finish_reason") == "length",
            "runtime_seconds": round(runtime_seconds, 3),
        }


class LlamaServerRuntime:
    """Same prompt and greedy decoding through a local llama-server process.

    Used on Windows hosts (deployment/home_api): llama-cpp-python has no current prebuilt
    Windows wheel, so the official llama.cpp release binary of the pinned commit serves the
    GGUF (CPU or CUDA). The server must have loaded exactly the verified GGUF file.
    """

    def __init__(self, base_url: str, model_path: Path, artifact: dict[str, str], *,
                 startup_timeout: float = 600.0) -> None:
        import requests

        self._session = requests.Session()
        self.base_url = base_url.rstrip("/")
        self.threads = available_cpus()
        deadline = time.monotonic() + startup_timeout
        # Require llama-server's {"status": "ok"} body, not just HTTP 200: another program on the
        # same port can answer 200 too.
        while not self._healthy():
            if time.monotonic() > deadline:
                raise RuntimeError(f"llama-server at {self.base_url} did not report status ok")
            time.sleep(2)
        try:
            props = self._session.get(f"{self.base_url}/props", timeout=10).json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError(
                f"{self.base_url}/props did not return llama-server JSON; is another program using this port?"
            ) from exc
        served = props.get("model_path") if isinstance(props, dict) else None
        if not served or Path(served).resolve() != Path(model_path).resolve():
            raise RuntimeError(f"llama-server serves {served!r}, not the verified GGUF {model_path}")
        self.artifact = {**artifact, "backend": "llama-server"}

    def _healthy(self) -> bool:
        import requests

        try:
            response = self._session.get(f"{self.base_url}/health", timeout=10)
            body = response.json()
        except (requests.RequestException, ValueError):
            return False
        return response.status_code == 200 and isinstance(body, dict) and body.get("status") == "ok"

    def _post(self, route: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        response = self._session.post(f"{self.base_url}{route}", json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def generate(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        prompt = render_chatml(messages)
        tokens = self._post("/tokenize", {"content": prompt, "add_special": False, "parse_special": True},
                            timeout=60)["tokens"]
        if len(tokens) > MAX_INPUT_TOKENS:
            raise PromptTooLongError(
                f"CV dài {len(tokens)} token, vượt giới hạn {MAX_INPUT_TOKENS}; hệ thống không cắt ngầm."
            )
        started = time.perf_counter()
        # Greedy decoding with every penalty disabled, as in LlamaPointerRuntime.
        completion = self._post("/completion", {
            "prompt": tokens,
            "n_predict": MAX_NEW_TOKENS,
            "temperature": 0.0,
            "top_k": 1,
            "top_p": 1.0,
            "min_p": 0.0,
            "repeat_penalty": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "seed": 42,
            "stop": [END_OF_TURN],
            "cache_prompt": True,
        }, timeout=1800)
        runtime_seconds = time.perf_counter() - started
        return {
            "raw_output": completion["content"].strip(),
            "input_tokens": len(tokens),
            "generated_tokens": int(completion["tokens_predicted"]),
            "hit_max_new_tokens": completion.get("stop_type") == "limit",
            "runtime_seconds": round(runtime_seconds, 3),
        }


def load_runtime() -> LlamaPointerRuntime | LlamaServerRuntime:
    path, artifact = download_gguf()
    server_url = os.getenv("LLAMA_SERVER_URL", "").strip()
    if server_url:
        return LlamaServerRuntime(server_url, path, artifact)
    return LlamaPointerRuntime(path, artifact)
