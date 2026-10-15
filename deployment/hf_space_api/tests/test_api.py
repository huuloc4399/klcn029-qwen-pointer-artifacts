"""Contract tests for the Space API without llama.cpp, OCR models or network.

The tests build the real Space bundle into a temporary folder and import the app from
there, so the copied frozen parser layout and RUNTIME_MANIFEST.json are exercised too.
Run from the project root: python -m unittest deployment/hf_space_api/tests/test_api.py -v
"""

from __future__ import annotations

import base64
import importlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "deployment/hf_space_api"))
import build_space  # noqa: E402

BUNDLE = Path(tempfile.mkdtemp(prefix="klcn029_space_")) / "bundle"
build_space.build(BUNDLE)
sys.path.insert(0, str(BUNDLE))
os.environ["KLCN029_API_AUTOSTART"] = "0"
os.environ["API_KEY"] = "test-key"

from fastapi.testclient import TestClient  # noqa: E402

main = importlib.import_module("app.main")
pipeline = importlib.import_module("app.pipeline")
retrieval = importlib.import_module("app.retrieval")
llm_runtime = importlib.import_module("app.llm_runtime")
from baseline_extraction.schema import CVSchema  # noqa: E402

EMPTY_POINTER = {
    "personal_info": {"name": "[MASKED]", "email": "[MASKED]", "phone": "[MASKED]", "github_url": ""},
    "summary_span": None,
    "skills": {"hard_skills": [], "soft_skills": []},
    "experience": [], "projects": [], "education": [],
    "certifications": [], "activities": [], "awards": [],
}
HEADERS = {"X-API-Key": "test-key"}


class FakeRuntime:
    artifact = {"filename": "fake.gguf", "sha256": "0" * 64}
    threads = 2

    def __init__(self, raw_output: str | None = None, gate: threading.Event | None = None) -> None:
        self.raw_output = raw_output or json.dumps(EMPTY_POINTER)
        self.gate = gate
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages):
        self.calls.append(messages)
        if self.gate is not None:
            self.gate.wait(5)
        return {"raw_output": self.raw_output, "input_tokens": 1000, "generated_tokens": 50,
                "hit_max_new_tokens": False, "runtime_seconds": 0.01}


def synthetic_sample() -> tuple[str, str]:
    """First synthetic validation CV and the frozen P0 pointer output recorded for it."""
    source = json.loads((ROOT / "training/data/resume_parsing_vision_cvschema_v2_pointer_v1/validation.jsonl")
                        .read_text(encoding="utf-8").splitlines()[0])
    result = json.loads((ROOT / "training/evaluation/results/pointer_stage2_validation_p0_v1/sample_results.jsonl")
                        .read_text(encoding="utf-8").splitlines()[0])
    assert source["sample_id"] == result["sample_id"]
    return source["source_text"], json.dumps(result["parsed_pointer"], ensure_ascii=False)


def text_pdf(lines: list[str]) -> bytes:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 16
    data = document.tobytes()
    document.close()
    return data


def wait_for(client: TestClient, job_id: str) -> dict:
    for _ in range(200):
        body = client.get(f"/v1/jobs/{job_id}", headers=HEADERS).json()
        if body["status"] in {"COMPLETED", "FAILED"}:
            return body
        time.sleep(0.02)
    raise AssertionError("job did not finish")


class SpaceApiTest(unittest.TestCase):
    def client(self, runtime=None, **kwargs) -> TestClient:
        app = main.create_app(lambda: runtime or FakeRuntime(), **kwargs)
        return TestClient(app)

    def test_bundle_sources_match_manifest(self):
        observed = pipeline.verify_runtime_sources(BUNDLE)
        self.assertIn("training/evaluation/pointer_parser.py", observed)
        self.assertIn("app/pipeline.py", observed)

    def test_tampered_bundle_is_rejected(self):
        tampered = BUNDLE.parent / "tampered"
        shutil.copytree(BUNDLE, tampered, dirs_exist_ok=True)
        target = tampered / "training/evaluation/deployment_policy.py"
        target.write_text(target.read_text(encoding="utf-8") + "\n# edit\n", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            pipeline.verify_runtime_sources(tampered)

    def test_retrieve_ranks_kb_chunks_and_requires_key(self):
        class BagOfWords:
            """Deterministic stand-in for bge-m3: word counts over a fixed vocabulary."""

            vocabulary = ["ats", "một", "cột", "frontend", "react", "backend", "rest", "sql", "dự", "án", "kết", "quả"]

            def __init__(self):
                self.calls = 0

            def embed(self, texts):
                self.calls += 1
                return [[text.lower().count(word) + 0.01 for word in self.vocabulary] for text in texts]

        embedder = BagOfWords()
        retriever = retrieval.Retriever(embedder)
        self.assertEqual(retriever.status, "idle")
        self.assertTrue((BUNDLE / "rag/kb_v1.jsonl").is_file())
        self.assertIn("rag/kb_v1.jsonl", pipeline.verify_runtime_sources(BUNDLE))
        with self.client(retriever=retriever) as client:
            self.assertEqual(client.post("/v1/retrieve", json={"query": "react"}).status_code, 401)
            body = client.post("/v1/retrieve", headers=HEADERS,
                               json={"query": "JD frontend React, cần CV một cột cho ATS", "top_k": 2}).json()
            self.assertEqual(len(body["results"]), 2)
            self.assertIn(body["results"][0]["id"], {"kb_frontend_core", "kb_ats_layout"})
            self.assertGreaterEqual(body["results"][0]["score"], body["results"][1]["score"])
            self.assertEqual(len(body["kb_sha256"]), 64)
            client.post("/v1/retrieve", headers=HEADERS, json={"query": "backend REST SQL"})
            self.assertEqual(embedder.calls, 3)  # KB embedded once (startup warm-up), then one call per query
            general = client.post("/v1/retrieve", headers=HEADERS,
                                  json={"query": "frontend React kết quả dự án", "top_k": 6, "roles": ["all"]}).json()
            self.assertTrue(all("all" in row["roles"] for row in general["results"]))
            self.assertEqual(client.post("/v1/retrieve", headers=HEADERS,
                                         json={"query": "react", "roles": ["devops"]}).status_code, 422)
            self.assertEqual(client.get("/health").json()["retrieval"], "ready")
            self.assertEqual(client.post("/v1/retrieve", headers=HEADERS, json={"query": "ab"}).status_code, 422)

    def test_retrieve_without_embedding_server_is_503(self):
        with self.client(retriever=retrieval.Retriever(None)) as client:
            response = client.post("/v1/retrieve", headers=HEADERS, json={"query": "backend REST"})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(client.get("/health").json()["retrieval"], "disabled")

    def test_requires_api_key(self):
        with self.client() as client:
            self.assertEqual(client.post("/v1/jobs", json={"source_text": "x"}).status_code, 401)
            self.assertEqual(client.get("/v1/jobs/" + "0" * 32).status_code, 401)
            self.assertEqual(client.get("/health").status_code, 200)

    def test_rejects_ambiguous_source(self):
        with self.client() as client:
            response = client.post("/v1/jobs", headers=HEADERS,
                                   json={"source_text": "a", "pdf_base64": "JVBERi0="})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(client.post("/v1/jobs", headers=HEADERS, json={}).status_code, 422)

    def test_text_job_returns_valid_cvschema_with_frozen_prompt(self):
        source_text, raw_output = synthetic_sample()
        runtime = FakeRuntime(raw_output)
        with self.client(runtime) as client:
            submitted = client.post("/v1/jobs", headers=HEADERS,
                                    json={"language": "en", "source_text": source_text, "page_count": 2})
            self.assertEqual(submitted.status_code, 202)
            body = wait_for(client, submitted.json()["id"])
        self.assertEqual(body["status"], "COMPLETED", body)
        output = body["output"]
        self.assertEqual(output["status"], "success", output)
        CVSchema.model_validate(output["cv"])
        self.assertTrue(output["evidence"])
        self.assertEqual(output["manifest"]["document"]["route"], "web_native_pdf_text")
        self.assertEqual(output["manifest"]["parser_version"], "cvpointer_output_parser_v1")
        system, user = runtime.calls[0]
        contract = json.loads((BUNDLE / "prompt_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(system["content"], contract["system_prompt"])
        self.assertTrue(user["content"].startswith(contract["user_prefix"]))
        self.assertIn("[L0001] ", user["content"])

    def test_pdf_job_uses_native_text_route(self):
        lines = ["Backend developer with three years of experience building APIs in Python and Go."] * 3
        pdf = base64.b64encode(text_pdf(["SUMMARY", *lines, "SKILLS", "Python, FastAPI, PostgreSQL"])).decode()
        with self.client() as client:
            job_id = client.post("/v1/jobs", headers=HEADERS, json={"language": "auto", "pdf_base64": pdf}).json()["id"]
            body = wait_for(client, job_id)
        self.assertEqual(body["status"], "COMPLETED", body)
        document = body["output"]["manifest"]["document"]
        self.assertEqual(document["route"], "api_pdf_router")
        self.assertEqual(document["language"], "en")
        self.assertEqual([page["route"] for page in document["routing_log"]], ["native_text"])

    def test_pdf_with_bytes_before_header_is_routed(self):
        lines = ["Backend developer with three years of experience building APIs in Python and Go."] * 3
        pdf = b"\n" + text_pdf(["SUMMARY", *lines, "SKILLS", "Python, FastAPI, PostgreSQL"])
        with self.client() as client:
            job_id = client.post("/v1/jobs", headers=HEADERS,
                                 json={"language": "en", "pdf_base64": base64.b64encode(pdf).decode()}).json()["id"]
            body = wait_for(client, job_id)
        self.assertEqual(body["status"], "COMPLETED", body)
        self.assertEqual(body["output"]["manifest"]["document"]["routing_log"][0]["route"], "native_text")

    def test_invalid_pdf_fails_with_user_message(self):
        with self.client() as client:
            job_id = client.post("/v1/jobs", headers=HEADERS,
                                 json={"pdf_base64": base64.b64encode(b"not a pdf").decode()}).json()["id"]
            body = wait_for(client, job_id)
        self.assertEqual(body["status"], "FAILED")
        self.assertIn("PDF", body["error"])

    def test_unparseable_output_is_rejected_not_failed(self):
        with self.client(FakeRuntime("not json")) as client:
            job_id = client.post("/v1/jobs", headers=HEADERS, json={"source_text": "SUMMARY\nHello"}).json()["id"]
            body = wait_for(client, job_id)
        self.assertEqual(body["output"]["status"], "rejected")
        self.assertNotIn("cv", body["output"])

    def test_queue_limit(self):
        gate = threading.Event()
        with self.client(FakeRuntime(gate=gate), max_pending=1) as client:
            codes = [client.post("/v1/jobs", headers=HEADERS, json={"source_text": f"CV {i}\nline"}).status_code
                     for i in range(4)]
            gate.set()
        self.assertIn(429, codes)

    def test_status_reports_queue_position_and_eta(self):
        gate = threading.Event()
        with self.client(FakeRuntime(gate=gate)) as client:
            ids = [client.post("/v1/jobs", headers=HEADERS, json={"source_text": f"CV {i}\nline"}).json()["id"]
                   for i in range(3)]
            for _ in range(100):
                first = client.get(f"/v1/jobs/{ids[0]}", headers=HEADERS).json()
                if first["status"] == "IN_PROGRESS":
                    break
                time.sleep(0.02)
            third = client.get(f"/v1/jobs/{ids[2]}", headers=HEADERS).json()
            gate.set()
            done = wait_for(client, ids[2])
        self.assertEqual(first["queuePosition"], 0)
        self.assertEqual(first["estimateSeconds"], 330)
        self.assertLessEqual(first["etaSeconds"], 330)
        self.assertEqual(third["status"], "IN_QUEUE")
        self.assertEqual(third["queuePosition"], 2)
        self.assertGreater(third["etaSeconds"], 2 * 330 - 10)
        self.assertNotIn("queuePosition", done)

    def test_feedback_is_stored_once_with_contact_masked(self):
        folder = Path(tempfile.mkdtemp(prefix="klcn029_feedback_"))
        record = {"id": "f" * 32, "rating": 4, "comment": "Hữu ích, liên hệ a.b@example.com",
                  "context": {"pipeline_mode": "hf_space", "language": "en", "total_score": 72.5}}
        with self.client(feedback_dir=folder) as client:
            self.assertEqual(client.post("/v1/feedback", json=record).status_code, 401)
            self.assertEqual(client.post("/v1/feedback", headers=HEADERS, json=record).status_code, 201)
            self.assertEqual(client.post("/v1/feedback", headers=HEADERS, json=record).status_code, 409)
            self.assertEqual(client.post("/v1/feedback", headers=HEADERS,
                                         json={**record, "id": "e" * 32, "rating": 6}).status_code, 422)
            self.assertEqual(client.post("/v1/feedback", headers=HEADERS,
                                         json={**record, "id": "e" * 32, "context": {"cv_text": "x"}}).status_code, 422)
            summary = client.get("/v1/feedback/summary", headers=HEADERS).json()
            self.assertEqual(client.get("/v1/feedback").status_code, 401)
            listed = client.get("/v1/feedback", headers=HEADERS).json()
            self.assertEqual(listed["count"], 1)
            self.assertEqual(listed["records"][0]["id"], "f" * 32)
        self.assertEqual(summary["count"], 1)
        self.assertEqual(summary["distribution"]["4"], 1)
        stored = json.loads((folder / "feedback.jsonl").read_text(encoding="utf-8"))
        self.assertNotIn("example.com", stored["comment"])
        self.assertEqual(stored["context"]["total_score"], 72.5)

    def test_model_load_failure_is_reported(self):
        def broken():
            raise RuntimeError("Missing Space variables: GGUF_SHA256")

        app = main.create_app(broken)
        with TestClient(app) as client:
            for _ in range(100):
                if client.get("/health").json()["model"] == "error":
                    break
                time.sleep(0.02)
            self.assertEqual(client.get("/health").json()["model"], "error")
            self.assertEqual(client.post("/v1/jobs", headers=HEADERS, json={"source_text": "a\nb"}).status_code, 503)

    def test_llama_server_runtime_uses_greedy_frozen_decoding(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        model_path = Path(tempfile.mkdtemp(prefix="klcn029_gguf_")) / "model.gguf"
        model_path.write_bytes(b"gguf")
        seen: dict[str, dict] = {}
        token_count = {"n": 1200}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, body):
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._send({"status": "ok"} if self.path == "/health" else {"model_path": str(model_path)})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen[self.path] = body
                if self.path == "/tokenize":
                    self._send({"tokens": list(range(token_count["n"]))})
                else:
                    self._send({"content": " {\"a\": 1} ", "tokens_predicted": 42, "stop_type": "limit"})

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            runtime = llm_runtime.LlamaServerRuntime(url, model_path, {"sha256": "0" * 64})
            result = runtime.generate([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}])
            self.assertEqual(result["raw_output"], '{"a": 1}')
            self.assertEqual((result["input_tokens"], result["generated_tokens"]), (1200, 42))
            self.assertTrue(result["hit_max_new_tokens"])
            request = seen["/completion"]
            self.assertEqual(request["prompt"], list(range(1200)))
            self.assertEqual((request["temperature"], request["top_k"], request["repeat_penalty"]), (0.0, 1, 1.0))
            self.assertEqual(request["n_predict"], llm_runtime.MAX_NEW_TOKENS)
            self.assertEqual(request["stop"], ["<|im_end|>"])
            self.assertTrue(seen["/tokenize"]["content"].endswith("<|im_start|>assistant\n"))
            token_count["n"] = llm_runtime.MAX_INPUT_TOKENS + 1
            with self.assertRaises(llm_runtime.PromptTooLongError):
                runtime.generate([{"role": "user", "content": "U"}])
            with self.assertRaises(RuntimeError):
                llm_runtime.LlamaServerRuntime(url, model_path.with_name("other.gguf"), {})
        finally:
            server.shutdown()

    def test_llama_server_runtime_rejects_other_program_on_port(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class Impostor(BaseHTTPRequestHandler):
            """Another local app holding the port: answers 200 with HTML, never llama-server JSON."""

            def log_message(self, *args):
                pass

            def do_GET(self):
                data = b"<html>OK</html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Impostor)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with self.assertRaises(RuntimeError) as caught:
                llm_runtime.LlamaServerRuntime(f"http://127.0.0.1:{server.server_address[1]}",
                                               Path("model.gguf"), {}, startup_timeout=1)
            self.assertIn("status ok", str(caught.exception))
        finally:
            server.shutdown()

    def test_chatml_render(self):
        rendered = llm_runtime.render_chatml([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}])
        self.assertEqual(rendered, "<|im_start|>system\nS<|im_end|>\n<|im_start|>user\nU<|im_end|>\n<|im_start|>assistant\n")


if __name__ == "__main__":
    unittest.main()
