---
title: KLCN029 CV Extraction API
emoji: 📄
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Qwen3-4B Pointer CV extraction (CPU, GGUF) for KLCN029
---

# KLCN029 CV extraction API

Asynchronous API that packages the team's Colab pipeline: PDF text/OCR routing,
Qwen3-4B + Pointer Stage 2 (merged, GGUF, llama.cpp on CPU), frozen Parser v1 and
real-CV acceptance v2. It returns CVSchema 2.0 with evidence; scoring runs in the web app.

- `GET /health` — model state and queue length.
- `POST /v1/jobs` — header `X-API-Key`; body `{"language": "auto|en|vi", "source_text": "..."}`
  or `{"language": "...", "pdf_base64": "..."}`.
- `GET /v1/jobs/{id}` — header `X-API-Key`; RunPod-compatible status with `output`.

CV content is processed in memory and is not written to disk. Jobs expire after one hour.
Source and deployment guide: `deployment/DEPLOY_FREE_HF_RENDER.md` in the project repository.
