"""Keep the JD collection consistent: manifest, rewritten JD texts and JD gold (module A).

    python -m downstream.data.jd_catalog check        # manifest <-> .txt <-> gold, fills sha256
    python -m downstream.data.jd_catalog init-gold    # empty JDSchema files to fill in by hand

Layout (see downstream/data/jd_v1/README.md):
    downstream/data/jd_v1/jd_manifest.csv   one row per JD
    downstream/data/jd_v1/JD001.txt         JD rewritten by the team
    downstream/data/jd_gold_v1/JD001.json   requirements in JDSchema, labelled by two people
"""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from baseline_extraction.schema import JDSchema

ROOT = Path(__file__).resolve().parents[2]
JD_DIR = ROOT / "downstream/data/jd_v1"
GOLD_DIR = ROOT / "downstream/data/jd_gold_v1"
MANIFEST_COLUMNS = ["jd_id", "role", "level", "language", "job_title", "source_name", "source_url",
                    "access_date", "rewritten", "collected_by", "notes", "sha256"]
ROLES = {"backend", "frontend"}
LEVELS = {"intern", "fresher", "junior"}
LANGUAGES = {"vi", "en"}
JD_ID = re.compile(r"^JD\d{3}$")


def read_manifest(path: Path) -> list[dict[str, str]]:
    """Rows of the manifest. Accepts what Excel writes back: a BOM and ';' as separator."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"{path.name}: không phải UTF-8; trong Excel chọn Save As → 'CSV UTF-8 (Comma delimited)'") from None
    header = text.split("\n", 1)[0]
    delimiter = ";" if header.count(";") > header.count(",") else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    if reader.fieldnames != MANIFEST_COLUMNS:
        raise ValueError(f"{path.name}: columns must be {MANIFEST_COLUMNS}, found {reader.fieldnames}")
    return [{k: (v or "").strip() for k, v in row.items()} for row in reader if any((v or "").strip() for v in row.values())]


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    try:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    except PermissionError:
        raise RuntimeError(f"không ghi được {path.name}: tệp đang mở trong Excel hoặc chương trình khác; đóng tệp rồi chạy lại") from None


def iso_date(value: str) -> str | None:
    """YYYY-MM-DD from the formats Excel may save: 2026-10-14, 14/10/2026, 14-10-2026."""
    for pattern in (r"(\d{4})-(\d{1,2})-(\d{1,2})", r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})"):
        match = re.fullmatch(pattern, value)
        if match:
            parts = match.groups()
            year, month, day = (parts if len(parts[0]) == 4 else parts[::-1])
            try:
                return date(int(year), int(month), int(day)).isoformat()
            except ValueError:
                return None
    return None


def text_sha256(path: Path) -> str:
    """Hash of the text with normalized line endings, so Windows/Git checkouts agree."""
    return hashlib.sha256(path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")).hexdigest()


def posting_key(url: str) -> str:
    """Comparable form of a posting link: no query string, fragment, scheme or trailing slash."""
    return re.sub(r"^https?://(www\.)?", "", url.split("#")[0].split("?")[0].strip().lower()).rstrip("/")


def duplicate_errors(rows: list[dict[str, str]], jd_dir: Path, threshold: float = 0.85) -> list[str]:
    """Same posting link, or original texts that are nearly identical (the same JD saved twice)."""
    errors = []
    by_url: dict[str, list[str]] = {}
    for row in rows:
        if row["source_url"]:
            by_url.setdefault(posting_key(row["source_url"]), []).append(row["jd_id"])
    errors += [f"{', '.join(ids)}: cùng một tin tuyển dụng ({url})" for url, ids in by_url.items() if len(ids) > 1]
    texts = {}
    for row in rows:
        raw, rewritten = jd_dir / "raw" / f"{row['jd_id']}.txt", jd_dir / f"{row['jd_id']}.txt"
        source = raw if raw.is_file() else rewritten
        if source.is_file():
            texts[row["jd_id"]] = " ".join(source.read_text(encoding="utf-8").casefold().split())
    ids = sorted(texts)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ratio = difflib.SequenceMatcher(None, texts[a], texts[b], autojunk=False).ratio()
            if ratio >= threshold:
                errors.append(f"{a}, {b}: nội dung giống nhau {ratio:.0%}, có thể là cùng một JD")
    return errors


def check(jd_dir: Path = JD_DIR, gold_dir: Path = GOLD_DIR, *, write_hashes: bool = True) -> tuple[list[str], list[str]]:
    """Return (errors, notes). Missing gold is a note until pairs are built; bad gold is an error."""
    errors, notes = [], []
    manifest_path = jd_dir / "jd_manifest.csv"
    rows = read_manifest(manifest_path)
    ids = [r["jd_id"] for r in rows]
    for jd_id, n in Counter(ids).items():
        if n > 1:
            errors.append(f"{jd_id}: xuất hiện {n} lần trong manifest")
    texts = {p.stem for p in jd_dir.glob("*.txt")}
    for extra in sorted(texts - set(ids)):
        errors.append(f"{extra}.txt: chưa có dòng trong jd_manifest.csv")
    errors += duplicate_errors(rows, jd_dir)
    changed = False  # set when a hash is filled or a date is normalized
    for row in rows:
        jd_id = row["jd_id"]
        if not JD_ID.match(jd_id):
            errors.append(f"{jd_id or '(trống)'}: jd_id phải có dạng JD001")
            continue
        for field, allowed in (("role", ROLES), ("level", LEVELS), ("language", LANGUAGES)):
            if row[field] not in allowed:
                errors.append(f"{jd_id}: {field} '{row[field]}' phải thuộc {sorted(allowed)}")
        for field in ("job_title", "source_name", "source_url", "collected_by"):
            if not row[field]:
                errors.append(f"{jd_id}: thiếu {field}")
        normalized = iso_date(row["access_date"])
        if normalized is None:
            errors.append(f"{jd_id}: access_date '{row['access_date']}' phải có dạng YYYY-MM-DD")
        elif normalized != row["access_date"]:
            row["access_date"], changed = normalized, True
        if row["rewritten"] != "yes":
            errors.append(f"{jd_id}: rewritten phải là yes (JD đã viết lại bằng lời của nhóm)")
        text = jd_dir / f"{jd_id}.txt"
        if not text.is_file():
            errors.append(f"{jd_id}: thiếu tệp {text.name}")
        else:
            digest = text_sha256(text)
            if row["sha256"] != digest:
                if row["sha256"] and not write_hashes:
                    errors.append(f"{jd_id}: nội dung {text.name} đã đổi so với sha256 trong manifest")
                row["sha256"], changed = digest, True
        gold = gold_dir / f"{jd_id}.json"
        if not gold.is_file():
            notes.append(f"{jd_id}: chưa có JD gold ({gold.relative_to(ROOT) if gold.is_relative_to(ROOT) else gold})")
            continue
        try:
            jd = JDSchema.model_validate(json.loads(gold.read_text(encoding="utf-8")))
        except (ValidationError, json.JSONDecodeError) as error:
            errors.append(f"{jd_id}: JD gold không đúng JDSchema: {str(error).splitlines()[0]}")
            continue
        if not jd.requirements.must_have:
            notes.append(f"{jd_id}: JD gold chưa có yêu cầu must_have")
        units = jd.requirements.must_have + jd.requirements.nice_to_have
        duplicates = [u for u, n in Counter(u.casefold() for u in units).items() if n > 1]
        if duplicates:
            errors.append(f"{jd_id}: yêu cầu bị lặp: {duplicates}")
    if changed and write_hashes:
        try:
            write_manifest(manifest_path, rows)
            notes.append("đã cập nhật sha256 và chuẩn hóa ngày trong jd_manifest.csv")
        except RuntimeError as error:
            errors.append(str(error))
    counts = Counter((r["role"], r["language"]) for r in rows)
    notes.append("phân bố: " + ", ".join(f"{role}/{lang}={counts[(role, lang)]}"
                                          for role in sorted(ROLES) for lang in sorted(LANGUAGES))
                 + f" · tổng {len(rows)} JD (mục tiêu 12: 8 backend, 4 frontend)")
    return errors, notes


def init_gold(jd_dir: Path = JD_DIR, gold_dir: Path = GOLD_DIR) -> list[Path]:
    """Create an empty JDSchema file for every JD that has none; never overwrite."""
    gold_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for row in read_manifest(jd_dir / "jd_manifest.csv"):
        path = gold_dir / f"{row['jd_id']}.json"
        if path.exists() or not JD_ID.match(row["jd_id"]):
            continue
        skeleton = {"job_title": row["job_title"],
                    "requirements": {"must_have": [], "nice_to_have": [], "min_experience_years": None, "education": ""},
                    "responsibilities": [], "seniority_level": row["level"]}
        path.write_text(json.dumps(skeleton, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        created.append(path)
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the JD collection or create empty JD gold files.")
    parser.add_argument("command", choices=("check", "init-gold"))
    parser.add_argument("--jd-dir", type=Path, default=JD_DIR)
    parser.add_argument("--gold-dir", type=Path, default=GOLD_DIR)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        return run(args)
    except (ValueError, RuntimeError) as error:
        print(f"LỖI  {error}")
        return 1


def run(args) -> int:
    if args.command == "init-gold":
        created = init_gold(args.jd_dir, args.gold_dir)
        print(f"Đã tạo {len(created)} tệp JD gold rỗng" + "".join(f"\n  {p.name}" for p in created))
        return 0
    errors, notes = check(args.jd_dir, args.gold_dir)
    for line in errors:
        print(f"LỖI  {line}")
    for line in notes:
        print(f"     {line}")
    print("OK" if not errors else f"{len(errors)} lỗi")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
