FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY cv_evaluation_web/requirements.txt /app/cv_evaluation_web/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/cv_evaluation_web/requirements.txt

COPY cv_evaluation_web /app/cv_evaluation_web
RUN mkdir -p /app/baseline_extraction
COPY baseline_extraction/__init__.py /app/baseline_extraction/__init__.py
COPY baseline_extraction/privacy.py /app/baseline_extraction/privacy.py
COPY baseline_extraction/schema.py /app/baseline_extraction/schema.py

WORKDIR /app/cv_evaluation_web
# One process owns the SQLite database and atomic job files. Threads provide enough
# concurrency because GPU inference is remote and HTTP requests are short lived.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 8 --timeout 60 wsgi:application"]
