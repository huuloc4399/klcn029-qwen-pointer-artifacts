"""Assemble the Oracle Cloud bundle: the Space API bundle plus the ARM Dockerfile, Compose,
Caddy and VM scripts. Copy the output folder to the VM and run docker compose there.

Usage (from the project root):
    python deployment/oracle_api/build_bundle.py            # -> dist/oracle_api(.tar.gz)
    scp dist/oracle_api.tar.gz ubuntu@<public-ip>:~
    ssh ubuntu@<public-ip> "mkdir -p ~/klcn029-api && tar -xzf ~/oracle_api.tar.gz -C ~/klcn029-api"
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OVERLAY = ["Dockerfile", ".dockerignore", "docker-compose.yml", "Caddyfile", ".env.example",
           "setup_vm.sh", "fidelity_check.py"]
FIDELITY_BUNDLE = ROOT / "training/colab/artifacts/gguf_fidelity_bundle_v1.zip"


def load_space_builder():
    spec = importlib.util.spec_from_file_location("build_space", ROOT / "deployment/hf_space_api/build_space.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "dist/oracle_api")
    args = parser.parse_args()
    hashed = load_space_builder().build(args.out)
    for name in OVERLAY:
        # Written with LF endings: a Windows checkout may hold CRLF, which bash and Caddy reject.
        text = (HERE / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        (args.out / name).write_bytes(text.encode("utf-8"))
    shutil.copy2(FIDELITY_BUNDLE, args.out / FIDELITY_BUNDLE.name)
    # One archive for first deploy and updates alike: extracting over ~/klcn029-api keeps .env.
    archive = args.out.with_suffix(".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(args.out.rglob("*")):
            if path.is_file():
                tar.add(path, arcname=path.relative_to(args.out).as_posix())
    print(f"Built {args.out} ({len(hashed)} hashed runtime files + Oracle overlay) and {archive}")


if __name__ == "__main__":
    main()
