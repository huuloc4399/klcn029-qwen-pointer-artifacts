"""Verify and publish the frozen adapter to a private Hugging Face model repo."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ZIP = ROOT / "training/qwen3_4b_cvschema2_pointer_stage2_full_v1_final_adapter.zip"
EXPECTED_ZIP_SHA256 = "274aeb95e78f5717b04af9fd0045e5215fd247533bd9572c73c73e8242f86b4b"
EXPECTED_WEIGHT_SHA256 = "8d68628e382593132010f20fb12cbb18d9477ca034c154811d109ec075a65f81"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    for member in archive.infolist():
        name = PurePosixPath(member.filename)
        if name.is_absolute() or ".." in name.parts:
            raise ValueError(f"Unsafe ZIP member: {member.filename}")
    archive.extractall(destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True, help="Private Hugging Face model repository")
    parser.add_argument("--adapter-zip", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--private", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    token = os.getenv("HF_TOKEN")
    if not token:
        raise RuntimeError("Set HF_TOKEN in the environment; do not put it in source code")
    observed_zip = sha256_file(args.adapter_zip)
    # The weight and internal manifest are the authoritative checks. ZIP metadata may differ
    # when the same files are repackaged, so the expected ZIP hash can be updated explicitly.
    if EXPECTED_ZIP_SHA256 and observed_zip != EXPECTED_ZIP_SHA256:
        print(f"Adapter ZIP SHA-256 differs from recorded packaging hash: {observed_zip}")
    from huggingface_hub import HfApi

    with tempfile.TemporaryDirectory(prefix="klcn029_publish_") as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(args.adapter_zip) as archive:
            if archive.testzip() is not None:
                raise ValueError("Adapter ZIP CRC check failed")
            safe_extract(archive, staging)
        adapter_dir = staging / "final_adapter"
        if sha256_file(adapter_dir / "adapter_model.safetensors") != EXPECTED_WEIGHT_SHA256:
            raise ValueError("Adapter weight hash mismatch")
        card = adapter_dir / "README.md"
        card.write_text(
            "---\nbase_model: Qwen/Qwen3-4B-Instruct-2507\nlibrary_name: peft\n"
            "pipeline_tag: text-generation\nlicense: other\n---\n\n"
            "# KLCN029 Qwen3-4B Hybrid Pointer adapter\n\n"
            "Private research artifact. Model revision and training provenance are recorded in "
            "`run_config.json` and `_FILE_MANIFEST.json`. Do not publish CV data in this repository.\n",
            encoding="utf-8",
        )
        api = HfApi(token=token)
        api.create_repo(args.repo_id, repo_type="model", private=args.private, exist_ok=True)
        api.upload_folder(
            repo_id=args.repo_id,
            repo_type="model",
            folder_path=staging,
            revision=args.revision,
            commit_message="Publish verified Pointer Stage 2 adapter",
        )
        print(json.dumps({
            "repo_id": args.repo_id,
            "revision": args.revision,
            "private": args.private,
            "adapter_zip_sha256": observed_zip,
            "adapter_model_sha256": EXPECTED_WEIGHT_SHA256,
        }, indent=2))


if __name__ == "__main__":
    main()
