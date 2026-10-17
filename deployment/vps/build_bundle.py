"""Assemble the VPS bundle: extraction API (the Space bundle with an x86 Dockerfile), the web app and
the Compose, Caddy and setup files. Copy the archive to the VPS and run docker compose there.

Usage (from the project root):
    python deployment/vps/build_bundle.py               # -> dist/vps_bundle and dist/vps_bundle.tar.gz
    scp dist/vps_bundle.tar.gz root@<ip>:~
    ssh root@<ip> "mkdir -p ~/klcn029 && tar -xzf ~/vps_bundle.tar.gz -C ~/klcn029"

Never in the bundle: hidden files and folders (.env, .secrets/), cv_evaluation_web/data (local jobs,
submissions, feedback), caches; a final check refuses to write the archive if a key file slipped in.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TOP_FILES = ["docker-compose.yml", "Caddyfile", ".env.example", "setup_vps.sh"]
WEB_FILES = {  # bundle path -> source; mirrors what cv_evaluation_web/Dockerfile copies from the repo root
    "baseline_extraction/__init__.py": ROOT / "baseline_extraction/__init__.py",
    "baseline_extraction/privacy.py": ROOT / "baseline_extraction/privacy.py",
    "baseline_extraction/schema.py": ROOT / "baseline_extraction/schema.py",
    "downstream/rubric/rubric_v2.json": ROOT / "downstream/rubric/rubric_v2.json",
    "downstream/rag/kb_v1.jsonl": ROOT / "downstream/rag/kb_v1.jsonl",
}
WEB_SKIP = {"data", "__pycache__", "tests", ".pytest_cache"}
WEB_SKIP_SUFFIXES = {".pyc", ".sqlite3", ".db", ".log", ".bat", ".ps1"}
TEXT_SUFFIXES = {".py", ".html", ".css", ".js", ".txt", ".json", ".jsonl", ".md", ".sh", ".yml", ".yaml"}
FORBIDDEN = (".env", ".apikey", ".hftoken", ".secrets")


def load_space_builder():
    spec = importlib.util.spec_from_file_location("build_space", ROOT / "deployment/hf_space_api/build_space.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lf(source: Path, target: Path) -> None:
    """Text files go out with LF endings: a Windows checkout may hold CRLF, which bash and Caddy reject."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8"))


def copy_web(out: Path) -> int:
    source_root = ROOT / "cv_evaluation_web"
    count = 0
    for path in sorted(source_root.rglob("*")):
        relative = path.relative_to(source_root)
        hidden = any(part.startswith(".") for part in relative.parts)  # .secrets/, .env, editor folders
        if not path.is_file() or hidden or WEB_SKIP & set(relative.parts) or path.suffix in WEB_SKIP_SUFFIXES:
            continue
        target = out / "web/cv_evaluation_web" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.name == "Dockerfile" or path.suffix in TEXT_SUFFIXES:
            _lf(path, target)
        else:
            shutil.copy2(path, target)
        count += 1
    for target, source in WEB_FILES.items():
        (out / "web" / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, out / "web" / target)
        count += 1
    return count


def build(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    load_space_builder().build(out / "api")
    _lf(HERE / "Dockerfile.api", out / "api/Dockerfile")
    _lf(ROOT / "deployment/oracle_api/.dockerignore", out / "api/.dockerignore")
    web_files = copy_web(out)
    for name in TOP_FILES:
        _lf(HERE / name, out / name)
    leaked = [p for p in out.rglob("*") if p.name in FORBIDDEN or ".secrets" in p.parts
              or (p.name.startswith(".env.") and p.name != ".env.example")]
    if leaked:
        shutil.rmtree(out)  # never leave copied keys behind
        raise SystemExit(f"Refusing to bundle secrets: {[str(p.relative_to(out)) for p in leaked]}")
    archive = out.with_suffix(".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(out.rglob("*")):
            if path.is_file():
                tar.add(path, arcname=path.relative_to(out).as_posix())
    print(f"Built {out} (API bundle, {web_files} web files, Compose/Caddy/setup) and {archive}")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "dist/vps_bundle")
    build(parser.parse_args().out)


if __name__ == "__main__":
    main()
