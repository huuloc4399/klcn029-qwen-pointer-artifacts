FROM runpod/pytorch:1.0.3-cu1281-torch291-ubuntu2404

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/runpod-volume/huggingface \
    PADDLE_HOME=/runpod-volume/paddle \
    PRELOAD_MODEL=1

WORKDIR /app

COPY deployment/runpod_qwen/requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt

COPY deployment/runpod_qwen /app
COPY baseline_extraction/__init__.py /app/baseline_extraction/__init__.py
COPY baseline_extraction/privacy.py /app/baseline_extraction/privacy.py
COPY training/evaluation/__init__.py /app/training/evaluation/__init__.py
COPY training/__init__.py /app/training/__init__.py
COPY training/evaluation/frozen/cvpointer_output_parser_v1/pointer_parser.py /app/training/evaluation/pointer_parser.py
COPY training/evaluation/frozen/cvpointer_output_parser_v1/parser.py /app/training/evaluation/parser.py
COPY training/evaluation/frozen/cvpointer_output_parser_v1/schema.py /app/baseline_extraction/schema.py
COPY training/evaluation/frozen/cvpointer_output_parser_v1/FROZEN_MANIFEST.json /app/FROZEN_MANIFEST.json

CMD ["python", "-u", "handler.py"]
