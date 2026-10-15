"""Counterfactual format-shift inputs from the synthetic validation split (experiment v1).

Question: does fine-tuning make the model depend on surface conventions of the synthetic CVs
(fixed English section headings, one skill per line, every long text on one line) that real
CVs do not follow? Each selected validation CV is rendered in five variants whose labels stay
exactly the same, so any F1 drop between variants of the same CV is caused by the surface
change alone:

  original        unchanged synthetic text (control)
  headings        section headings renamed to real-CV synonyms (half of the CVs Vietnamese)
  grouped_skills  one-per-line skills regrouped as "Label: a, b, c" lines, soft skills on
                  their own "Soft skills: ..." line
  wrapped_text    summary / experience descriptions / project details wrapped over several
                  lines, as PDF text extraction returns them
  combined        all three changes

Only synthetic CC-BY-4.0 data is used; no real CV and no GOLD40 item is involved.
Build (from the project root):  python -m training.evaluation.format_shift
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
import textwrap
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "deployment/runpod_qwen"))
from prompting import build_messages, normalize_source_text  # noqa: E402

VERSION = "format_shift_v1"
VALIDATION = ROOT / "training/data/resume_parsing_vision_cvschema_v2/validation.jsonl"
OUT_DIR = ROOT / "training/data" / VERSION
PACKAGE = ROOT / "training/colab/artifacts" / f"{VERSION}_inputs.zip"
VARIANTS = ("original", "headings", "grouped_skills", "wrapped_text", "combined")
PER_TEMPLATE = {"sidebar": 7, "classic": 7, "two_column": 6}
SEED = 42

HEADINGS_EN = {
    "Summary": ["Objective", "Career Objective", "Profile", "About Me"],
    "Experience": ["Work Experience", "Employment History", "Professional Experience"],
    "Projects": ["Personal Projects", "Academic Projects", "Project Experience"],
    "Education": ["Academic Background", "Education & Training", "Qualifications"],
    "Skills": ["Technical Skills", "Core Competencies", "Skills & Tools"],
    "Languages": ["Language Proficiency", "Foreign Languages"],
    "Certificates": ["Certifications", "Licenses & Certifications"],
}
HEADINGS_VI = {
    "Summary": ["Mục tiêu nghề nghiệp", "Giới thiệu bản thân"],
    "Experience": ["Kinh nghiệm làm việc"],
    "Projects": ["Dự án", "Dự án cá nhân"],
    "Education": ["Học vấn"],
    "Skills": ["Kỹ năng"],
    "Languages": ["Ngoại ngữ"],
    "Certificates": ["Chứng chỉ"],
}
SECTION_HEADINGS = set(HEADINGS_EN) | {"Preferences", "Looking for", "Hobbies"}
SKILL_GROUP_LABELS = ["Technical", "Tools", "Technologies", "Other"]


def norm(value: Any) -> str:
    """Same normalization as training/evaluation/metrics.py."""
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def rng_for(cv_id: str, purpose: str) -> random.Random:
    return random.Random(f"{SEED}:{cv_id}:{purpose}")


def rename_headings(text: str, cv_id: str) -> tuple[str, int]:
    rng = rng_for(cv_id, "headings")
    vietnamese = rng.random() < 0.5
    table = HEADINGS_VI if vietnamese else HEADINGS_EN
    upper = not vietnamese and rng.random() < 0.5
    out, renamed = [], 0
    for line in text.split("\n"):
        if line.strip() in table:
            new = rng.choice(table[line.strip()])
            out.append(new.upper() if upper else new)
            renamed += 1
        else:
            out.append(line)
    return "\n".join(out), renamed


def group_skills(text: str, target: dict, cv_id: str) -> tuple[str, int]:
    """Replace the one-skill-per-line block under "Skills" with grouped comma lines."""
    rng = rng_for(cv_id, "skills")
    hard = {norm(s) for s in target["skills"]["hard_skills"]}
    soft = {norm(s) for s in target["skills"]["soft_skills"]}
    lines = text.split("\n")
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "Skills")
    except StopIteration:
        return text, 0
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() in SECTION_HEADINGS), len(lines))
    block = lines[start + 1:end]
    hard_lines = [line.strip() for line in block if norm(line) in hard]
    soft_lines = [line.strip() for line in block if norm(line) in soft]
    other = [line for line in block if norm(line) not in hard and norm(line) not in soft]
    if len(hard_lines) < 3:
        return text, 0
    grouped, index = [], 0
    labels = SKILL_GROUP_LABELS[:]
    rng.shuffle(labels)
    while index < len(hard_lines):
        size = rng.randint(3, 5)
        chunk = hard_lines[index:index + size]
        index += size
        label = labels[len(grouped) % len(labels)]
        grouped.append(f"{label}: {', '.join(chunk)}")
    if soft_lines:
        grouped.append(f"Soft skills: {', '.join(soft_lines)}")
    new_block = grouped + other
    return "\n".join(lines[:start + 1] + new_block + lines[end:]), len(hard_lines) + len(soft_lines)


def long_text_values(target: dict) -> set[str]:
    values = {target.get("summary") or ""}
    values |= {item.get("description") or "" for item in target.get("experience") or []}
    values |= {item.get("details") or "" for item in target.get("projects") or []}
    return {norm(value) for value in values if value}


def wrap_long_text(text: str, target: dict, cv_id: str) -> tuple[str, int]:
    rng = rng_for(cv_id, "wrap")
    targets = long_text_values(target)
    out, wrapped = [], 0
    for line in text.split("\n"):
        if len(line) > 90 and norm(line) in targets:
            # Break only at spaces: a break after "water-" would change the label text.
            out.extend(textwrap.wrap(line.strip(), width=rng.randint(60, 85),
                                     break_long_words=False, break_on_hyphens=False))
            wrapped += 1
        else:
            out.append(line)
    return "\n".join(out), wrapped


def render(variant: str, text: str, target: dict, cv_id: str) -> tuple[str, dict[str, int]]:
    changes = {"headings_renamed": 0, "skill_lines_grouped": 0, "long_lines_wrapped": 0}
    if variant in ("grouped_skills", "combined"):
        text, changes["skill_lines_grouped"] = group_skills(text, target, cv_id)
    if variant in ("headings", "combined"):
        text, changes["headings_renamed"] = rename_headings(text, cv_id)
    if variant in ("wrapped_text", "combined"):
        text, changes["long_lines_wrapped"] = wrap_long_text(text, target, cv_id)
    return text, changes


def target_leaves(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [leaf for item in value.values() for leaf in target_leaves(item)]
    if isinstance(value, list):
        return [leaf for item in value for leaf in target_leaves(item)]
    if value is None or value == "" or value == "[MASKED]":
        return []
    return [norm(value)]


def findable(target: dict, text: str) -> set[str]:
    """Label values that occur in the text (whitespace-insensitive), i.e. are extractable."""
    haystack = norm(text)
    return {leaf for leaf in target_leaves(target) if leaf in haystack}


def select(rows: list[dict]) -> list[dict]:
    rng = random.Random(SEED)
    chosen = []
    for template, count in PER_TEMPLATE.items():
        pool = sorted((r for r in rows if r["metadata"]["template_id"] == template), key=lambda r: r["sample_id"])
        chosen += rng.sample(pool, count)
    return sorted(chosen, key=lambda r: r["sample_id"])


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build() -> dict[str, Any]:
    rows = [json.loads(line) for line in VALIDATION.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = select(rows)
    inputs, targets, change_totals = [], [], Counter()
    for row in selected:
        cv_id, source, target = row["sample_id"], row["source_text"], row["target"]
        user = row["messages"][1]["content"]
        if not user.endswith(source):
            raise ValueError(f"{cv_id}: cannot isolate the Full JSON prompt prefix")
        system, prefix = row["messages"][0]["content"], user[: -len(source)]
        baseline = findable(target, source)
        targets.append({"cv_id": cv_id, "template_id": row["metadata"]["template_id"], "target": target})
        for variant in VARIANTS:
            text, changes = render(variant, source, target, cv_id)
            if variant != "original" and text == source:
                raise ValueError(f"{cv_id}: variant {variant} changed nothing")
            lost = baseline - findable(target, text)
            if lost:
                raise ValueError(f"{cv_id}/{variant}: perturbation removed label values {sorted(lost)[:3]}")
            pointer_messages, pointer_source = build_messages(text)
            change_totals.update({f"{variant}.{key}": value for key, value in changes.items()})
            inputs.append({
                "sample_id": f"{cv_id}__{variant}", "cv_id": cv_id, "variant": variant,
                "template_id": row["metadata"]["template_id"], "language": "en",
                "changes": changes,
                "source_text": text,
                "source_text_sha256": sha(text.encode("utf-8")),
                "fulljson_messages": [{"role": "system", "content": system},
                                      {"role": "user", "content": prefix + text}],
                "pointer_messages": pointer_messages,
                "pointer_source_text": pointer_source,
            })
    if normalize_source_text(inputs[0]["source_text"]) != inputs[0]["pointer_source_text"]:
        raise ValueError("pointer normalization mismatch")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs_path, targets_path = OUT_DIR / "inputs.jsonl", OUT_DIR / "targets.jsonl"
    inputs_path.write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in inputs), encoding="utf-8")
    targets_path.write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in targets), encoding="utf-8")
    manifest = {
        "version": VERSION, "seed": SEED, "variants": list(VARIANTS),
        "cv_count": len(selected), "record_count": len(inputs),
        "cv_ids": [r["sample_id"] for r in selected],
        "templates": dict(Counter(r["metadata"]["template_id"] for r in selected)),
        "change_totals": dict(sorted(change_totals.items())),
        "validation_sha256": sha(VALIDATION.read_bytes()),
        "inputs_sha256": sha(inputs_path.read_bytes()),
        "targets_sha256": sha(targets_path.read_bytes()),
        "labels_in_package": False,
        "label_invariance": "every label value findable in the original text is findable in each variant",
        "source": "synthetic validation split (sukhrobnurali/resume-parsing-vision, CC-BY-4.0); no real CVs",
    }
    (OUT_DIR / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PACKAGE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(PACKAGE, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("inputs.jsonl", "MANIFEST.json"):
            info = zipfile.ZipInfo(f"{VERSION}/{name}", (2026, 10, 13, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (OUT_DIR / name).read_bytes())
    manifest["package_sha256"] = sha(PACKAGE.read_bytes())
    return manifest


if __name__ == "__main__":
    result = build()
    print(json.dumps({key: result[key] for key in ("cv_count", "record_count", "templates", "change_totals",
                                                   "inputs_sha256", "package_sha256")}, ensure_ascii=False, indent=2))
