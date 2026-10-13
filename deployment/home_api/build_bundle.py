"""Assemble the extraction API for a Windows laptop (deployment/home_api): the Space API bundle
plus the synthetic fidelity bundle. Called by setup_home.ps1; can also be run directly.

Usage (from the project root):
    python deployment/home_api/build_bundle.py --out E:/klcn029-home/api
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIDELITY_BUNDLE = ROOT / "training/colab/artifacts/gguf_fidelity_bundle_v1.zip"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "dist/home_api")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("build_space", ROOT / "deployment/hf_space_api/build_space.py")
    build_space = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_space)
    hashed = build_space.build(args.out)
    shutil.copy2(FIDELITY_BUNDLE, args.out / FIDELITY_BUNDLE.name)
    print(f"Built {args.out} ({len(hashed)} hashed runtime files + fidelity bundle)")


if __name__ == "__main__":
    main()
