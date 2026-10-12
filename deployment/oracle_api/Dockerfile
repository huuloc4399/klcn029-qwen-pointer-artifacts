# Extraction API on an Oracle Cloud Always Free Ampere A1 VM (aarch64, 2 OCPU, 12 GB RAM).
# Same app as deployment/hf_space_api; only the CPU target, the Paddle index and the cache
# location differ. Built on the VM itself by docker compose (deployment/oracle_api/docker-compose.yml).

FROM python:3.11-slim-bookworm AS llama-build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake git \
    && rm -rf /var/lib/apt/lists/*
# The image is built on the machine that runs it (Ampere Altra / Neoverse-N1), so native
# tuning picks up NEON + dotprod. Rebuild if the image is moved to another CPU.
ENV CMAKE_ARGS="-DGGML_NATIVE=ON -DGGML_BLAS=OFF -DLLAMA_CURL=OFF"
RUN pip wheel --no-cache-dir --no-deps -w /wheels llama-cpp-python==0.3.36

FROM python:3.11-slim-bookworm
ARG WITH_OCR=1
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/user \
    HF_HOME=/data/hf \
    MODEL_CACHE_DIR=/data/models \
    PADDLE_PDX_CACHE_HOME=/data/paddlex \
    OMP_NUM_THREADS=2
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user && mkdir -p /data && chown user:user /data
WORKDIR /home/user/app

COPY requirements.txt requirements.txt
# PyPI has no linux aarch64 wheel for paddlepaddle 3.3.1; Paddle's own CPU index does.
RUN if [ "$WITH_OCR" = "1" ]; then \
        pip install --extra-index-url https://www.paddlepaddle.org.cn/packages/stable/cpu/ -r requirements.txt \
        && pip install --no-deps vietocr==0.3.13; \
    else \
        grep -E '^(fastapi|uvicorn|pydantic|huggingface_hub|requests|PyMuPDF|numpy|Pillow)==' requirements.txt > core.txt \
        && pip install -r core.txt; \
    fi
COPY --from=llama-build /wheels /wheels
RUN pip install /wheels/*.whl && rm -rf /wheels

COPY --chown=user . .
USER user
# GGUF (~2.5 GB), VietOCR and Paddle weights persist here across restarts.
VOLUME ["/data"]
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
