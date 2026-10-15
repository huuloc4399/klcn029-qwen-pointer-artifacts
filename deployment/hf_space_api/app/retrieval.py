"""Knowledge-base retrieval for the RAG scoring strategy (M3) of the web demo.

The KB (rag/kb_v1.jsonl, copied from downstream/rag/) is embedded with bge-m3 served by a second
llama-server started with --embedding (deployment/home_api/start_home.ps1), and queries are
ranked by cosine similarity. No CV text is stored; the web sends only a short query built from
the JD and the CV's skills.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from pathlib import Path
from typing import Any, Protocol

import requests


ROOT = Path(__file__).resolve().parents[1]
# In the built bundle the KB sits next to app/; in the repository it lives in downstream/rag/.
KB_PATH = next((path for path in (ROOT / "rag/kb_v1.jsonl", ROOT.parents[1] / "downstream/rag/kb_v1.jsonl")
                if path.is_file()), ROOT / "rag/kb_v1.jsonl")
EMBED_BACKEND = "bge-m3 (GGUF Q8_0, llama-server --embedding)"
# Official ggml-org conversion of BAAI/bge-m3 (MIT), pinned by revision and SHA-256.
EMBED_GGUF_DEFAULTS = {
    "EMBED_GGUF_REPO_ID": "ggml-org/bge-m3-Q8_0-GGUF",
    "EMBED_GGUF_FILENAME": "bge-m3-q8_0.gguf",
    "EMBED_GGUF_REVISION": "9eba04c5d75ba5a1595e45de734d36bef4e5cb98",
    "EMBED_GGUF_SHA256": "aa473d51f451a22f0fcf39ba3330c14bed38a385712b1113440f69df4047a173",
}
MAX_QUERY_CHARACTERS = 4000


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def load_kb(path: Path = KB_PATH) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows or len({row["id"] for row in rows}) != len(rows):
        raise RuntimeError(f"Knowledge base {path.name} is empty or has duplicate ids")
    return rows


def download_embedding_gguf() -> tuple[Path, dict[str, str]]:
    """Fetch the pinned bge-m3 GGUF (public repo) and verify its hash; env vars override the pin."""
    from huggingface_hub import hf_hub_download

    from .llm_runtime import sha256_file

    pin = {key: os.getenv(key, default).strip() for key, default in EMBED_GGUF_DEFAULTS.items()}
    path = Path(hf_hub_download(repo_id=pin["EMBED_GGUF_REPO_ID"], filename=pin["EMBED_GGUF_FILENAME"],
                                revision=pin["EMBED_GGUF_REVISION"]))
    observed = sha256_file(path)
    if observed != pin["EMBED_GGUF_SHA256"].lower():
        raise RuntimeError(f"Embedding GGUF hash mismatch: expected {pin['EMBED_GGUF_SHA256']}, observed {observed}")
    return path, {"repo_id": pin["EMBED_GGUF_REPO_ID"], "filename": pin["EMBED_GGUF_FILENAME"],
                  "revision": pin["EMBED_GGUF_REVISION"], "sha256": observed}


class LlamaServerEmbedder:
    """OpenAI-compatible /v1/embeddings of a llama-server started with --embedding."""

    # The first call after a cold start pages the GGUF in from disk (slow on an external HDD).
    def __init__(self, base_url: str, timeout_seconds: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = requests.post(f"{self.base_url}/v1/embeddings", json={"input": texts, "model": "bge-m3"},
                                 timeout=self.timeout_seconds)
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        if len(data) != len(texts):
            raise RuntimeError("Embedding server returned a different number of vectors")
        return [item["embedding"] for item in data]


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise RuntimeError("Embedding server returned a zero vector")
    return [value / norm for value in vector]


class Retriever:
    """Cosine top-k over the KB; document vectors are computed once, on the first query."""

    def __init__(self, embedder: Embedder | None, kb: list[dict[str, Any]] | None = None) -> None:
        self.embedder = embedder
        self.kb = kb if kb is not None else load_kb()
        self.kb_sha256 = hashlib.sha256(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in self.kb).encode("utf-8")
        ).hexdigest()
        self._vectors: list[list[float]] | None = None
        self._lock = threading.Lock()
        self.error: str | None = None

    @property
    def status(self) -> str:
        if self.embedder is None:
            return "disabled"
        if self.error:
            return "error"
        return "ready" if self._vectors is not None else "idle"

    def _document_vectors(self) -> list[list[float]]:
        with self._lock:
            if self._vectors is None:
                texts = [f"{row['title']}\n{row['text']}" for row in self.kb]
                self._vectors = [_normalize(vector) for vector in self.embedder.embed(texts)]
            return self._vectors

    def warm(self) -> None:
        """Embed the KB in the background at startup so the first user query does not pay for it."""
        if self.embedder is None:
            return
        try:
            self._document_vectors()
        except (requests.RequestException, KeyError, ValueError, RuntimeError) as exc:
            self.error = str(exc)[:200]

    def retrieve(self, query: str, top_k: int = 3, roles: list[str] | None = None) -> list[dict[str, Any]]:
        """Top-k chunks by cosine similarity; roles keeps chunks tagged with any of those roles."""
        if self.embedder is None:
            raise RuntimeError("Embedding server is not configured (EMBED_SERVER_URL)")
        try:
            vectors = self._document_vectors()
            query_vector = _normalize(self.embedder.embed([query[:MAX_QUERY_CHARACTERS]])[0])
            self.error = None
        except (requests.RequestException, KeyError, ValueError, RuntimeError) as exc:
            self.error = str(exc)[:200]
            raise RuntimeError("Máy chủ embedding chưa sẵn sàng.") from exc
        scored = sorted(((sum(a * b for a, b in zip(query_vector, vector)), row)
                         for vector, row in zip(vectors, self.kb)
                         if not roles or set(roles) & set(row.get("roles", []))), key=lambda item: -item[0])
        return [{"id": row["id"], "title": row["title"], "text": row["text"], "criteria": row.get("criteria", []),
                 "roles": row.get("roles", []), "score": round(score, 4)} for score, row in scored[:top_k]]


def retriever_from_env() -> Retriever:
    url = os.getenv("EMBED_SERVER_URL", "").strip()
    return Retriever(LlamaServerEmbedder(url) if url else None)
