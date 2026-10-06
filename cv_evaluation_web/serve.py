"""Serve CV Insight with Waitress for local pilots and a small private host."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from waitress import serve

from app import create_app


if __name__ == "__main__":
    host = os.getenv("CV_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("CV_WEB_PORT", "8780"))
    print(f"CV Insight: http://{host}:{port}")
    serve(create_app(), host=host, port=port, threads=6)
