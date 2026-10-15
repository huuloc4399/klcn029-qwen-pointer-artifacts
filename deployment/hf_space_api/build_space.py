"""Assemble the Hugging Face Space bundle for the extraction API and optionally push it.

The bundle mirrors the RunPod worker layout: frozen Parser v1 files are copied into the
package paths they were benchmarked under, and every copied file is hashed into
RUNTIME_MANIFEST.json, which the API verifies at startup.

Usage (from the project root):
    python deployment/hf_space_api/build_space.py                      # build dist/hf_space_api
    python deployment/hf_space_api/build_space.py --push USER/SPACE    # build + upload (HF_TOKEN env, write)
    python deployment/hf_space_api/build_space.py --push USER/SPACE --configure
        # also sets Space variables GGUF_* from env and secrets API_KEY / SPACE_HF_TOKEN from env
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FROZEN = ROOT / "training/evaluation/frozen/cvpointer_output_parser_v1"
COPIES = {
    "Dockerfile": HERE / "Dockerfile",
    "requirements.txt": HERE / "requirements.txt",
    "README.md": HERE / "space_card.md",
    "prompting.py": ROOT / "deployment/runpod_qwen/prompting.py",
    "fidelity_check.py": HERE / "fidelity/fidelity_check.py",
    "prompt_contract.json": ROOT / "deployment/runpod_qwen/prompt_contract.json",
    "baseline_extraction/__init__.py": ROOT / "baseline_extraction/__init__.py",
    "baseline_extraction/privacy.py": ROOT / "baseline_extraction/privacy.py",
    "baseline_extraction/schema.py": FROZEN / "schema.py",
    "training/__init__.py": ROOT / "training/__init__.py",
    "training/evaluation/__init__.py": ROOT / "training/evaluation/__init__.py",
    "training/evaluation/parser.py": FROZEN / "parser.py",
    "training/evaluation/pointer_parser.py": FROZEN / "pointer_parser.py",
    "training/evaluation/deployment_policy.py": ROOT / "training/evaluation/deployment_policy.py",
    "rag/kb_v1.jsonl": ROOT / "downstream/rag/kb_v1.jsonl",
}
SPACE_VARIABLES = ("GGUF_REPO_ID", "GGUF_FILENAME", "GGUF_REVISION", "GGUF_SHA256")
SPACE_SECRETS = {"API_KEY": "API_KEY", "HF_TOKEN": "SPACE_HF_TOKEN"}  # Space secret <- local env var


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(out: Path) -> dict[str, str]:
    if out.exists():
        shutil.rmtree(out)
    (out / "app").mkdir(parents=True)
    for source in sorted((HERE / "app").glob("*.py")):
        shutil.copy2(source, out / "app" / source.name)
    for target, source in COPIES.items():
        destination = out / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    hashed = {
        str(path.relative_to(out)).replace("\\", "/"): sha256(path)
        for path in sorted(out.rglob("*.py")) + [out / "prompt_contract.json", out / "rag/kb_v1.jsonl"]
    }
    (out / "RUNTIME_MANIFEST.json").write_text(
        json.dumps({"bundle": "klcn029_hf_space_api_v1", "files": hashed}, indent=2) + "\n", encoding="utf-8"
    )
    return hashed


def push(out: Path, repo_id: str, configure: bool) -> None:
    from huggingface_hub import HfApi

    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("Set HF_TOKEN (write access) to push the Space.")
    api = HfApi(token=token)
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", private=True, exist_ok=True)
    if configure:
        for name in SPACE_VARIABLES:
            if os.environ.get(name):
                api.add_space_variable(repo_id, name, os.environ[name])
        for secret, env_name in SPACE_SECRETS.items():
            if os.environ.get(env_name):
                api.add_space_secret(repo_id, secret, os.environ[env_name])
    commit = api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=str(out),
                               commit_message="Deploy KLCN029 extraction API bundle", delete_patterns=["*"])
    print(f"Pushed {repo_id}: {commit.oid if hasattr(commit, 'oid') else commit}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "dist/hf_space_api")
    parser.add_argument("--push", metavar="USER/SPACE")
    parser.add_argument("--configure", action="store_true", help="set Space variables/secrets from env")
    args = parser.parse_args()
    files = build(args.out)
    print(f"Built {args.out} ({len(files)} hashed files)")
    if args.push:
        push(args.out, args.push, args.configure)


if __name__ == "__main__":
    main()
