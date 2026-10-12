# Hugging Face Space (Docker SDK, free "CPU basic": 2 vCPU, 16 GB RAM).
# Built from the bundle that deployment/hf_space_api/build_space.py assembles.

FROM python:3.11-slim-bookworm AS llama-build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake git \
    && rm -rf /var/lib/apt/lists/*
# Portable AVX2 build: the Space build machine is not the runtime machine, so no -march=native.
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON -DGGML_BLAS=OFF -DLLAMA_CURL=OFF"
RUN pip wheel --no-cache-dir --no-deps -w /wheels llama-cpp-python==0.3.36

FROM python:3.11-slim-bookworm
ARG WITH_OCR=1
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/user \
    HF_HOME=/tmp/hf \
    MODEL_CACHE_DIR=/tmp/models \
    PADDLE_PDX_CACHE_HOME=/tmp/paddlex \
    OMP_NUM_THREADS=2
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

COPY requirements.txt requirements.txt
RUN if [ "$WITH_OCR" = "1" ]; then \
        pip install -r requirements.txt && pip install --no-deps vietocr==0.3.13; \
    else \
        grep -E '^(fastapi|uvicorn|pydantic|huggingface_hub|requests|PyMuPDF|numpy|Pillow)==' requirements.txt > core.txt \
        && pip install -r core.txt; \
    fi
COPY --from=llama-build /wheels /wheels
RUN pip install /wheels/*.whl && rm -rf /wheels

COPY --chown=user . .
USER user
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
