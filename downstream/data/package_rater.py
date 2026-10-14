"""Zip everything one rater needs: the locked workbook, the CV PDFs of their pairs and a guide.

The package holds real CVs, so it is written under downstream/data/labels_v1/packages/
(gitignored) and must only travel through the team's private channel. It deliberately leaves
out pairs.csv (split, intended fit, CV track), JD gold files, CVSchema gold and model outputs.

    python -m downstream.data.package_rater --rater A --split dev     # pilot round
    python -m downstream.data.package_rater --rater B --split dev
    python -m downstream.data.package_rater --rater A                 # full round, all 48 pairs
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor

from downstream.data import build_rating_workbook as builder

ROOT = Path(__file__).resolve().parents[2]
PAIRS = ROOT / "downstream/data/pairs_v1/pairs.csv"
JD_GOLD = ROOT / "downstream/data/jd_gold_v1"
JD_TEXT = ROOT / "downstream/data/jd_v1"
CV_MANIFEST = ROOT / "baseline_extraction/data/manifest.csv"
OUT_DIR = ROOT / "downstream/data/labels_v1/packages"
NAVY = RGBColor(0x17, 0x36, 0x5D)


def cv_pdf_paths(cv_ids: set[str], manifest: Path = CV_MANIFEST) -> dict[str, Path]:
    with manifest.open(encoding="utf-8-sig", newline="") as handle:
        rows = {r["id"]: ROOT / r["path"] for r in csv.DictReader(handle)}
    missing = sorted(c for c in cv_ids if c not in rows or not rows[c].is_file())
    if missing:
        raise FileNotFoundError(f"no PDF for {missing}")
    return {c: rows[c] for c in cv_ids}


def guide(path: Path, *, rater: str, round_name: str, workbook_name: str, meta: dict, cv_ids: list[str],
          deadline: str, coordinator: str) -> None:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name, style.font.size = "Arial", Pt(10.5)

    def heading(text: str, size: float = 13) -> None:
        run = doc.add_paragraph().add_run(text)
        run.bold, run.font.size, run.font.color.rgb = True, Pt(size), NAVY

    def bullets(items: list[str]) -> None:
        for item in items:
            doc.add_paragraph(item, style="List Bullet")

    def steps(items: list[str]) -> None:
        for item in items:
            doc.add_paragraph(item, style="List Number")

    heading(f"Hướng dẫn chấm cặp CV–JD · {round_name} · Người chấm {rater}", 15)
    doc.add_paragraph(f"Số cặp: {meta['pair_count']} · Số CV: {len(cv_ids)} · Rubric: {meta['rubric_version']} · "
                      f"Hạn nộp: {deadline} · Liên hệ khi file lỗi: {coordinator}")

    heading("1. Mục đích")
    doc.add_paragraph(
        "Bạn đánh giá mức phù hợp giữa từng CV và một mô tả công việc (JD) theo rubric 8 tiêu chí. Kết quả là "
        "nhãn tham chiếu của con người để so sánh với điểm do hệ thống chấm. Hai người chấm độc lập cùng các cặp; "
        "chỗ khác nhau sẽ được phân xử sau.")

    heading("2. Trong gói có gì")
    bullets([
        f"{workbook_name}: file Excel để chấm. Chỉ sửa ở các cột trắng; cột xám đã khóa.",
        f"CV_PDF/: {len(cv_ids)} CV đặt tên theo mã (ví dụ EN002.pdf). Mã trong file Excel trùng với tên tệp.",
        "Nội dung JD nằm ngay trong sheet JD của file Excel.",
        "Tệp này (00_DOC_TRUOC.docx).",
    ])

    heading("3. Quy tắc bắt buộc")
    bullets([
        "Chấm độc lập: không trao đổi điểm hay cách chấm với người chấm khác cho tới khi cả hai đã nộp.",
        "Không dùng ChatGPT, Claude hay công cụ AI nào để đọc CV hoặc gợi ý điểm, và không xem kết quả của mô hình.",
        "CV là dữ liệu thật của sinh viên: chỉ mở trên máy của bạn, không gửi lên nhóm chat chung, mạng xã hội "
        "hay công cụ online. Xóa gói khỏi máy sau khi nhóm xác nhận đã nhận file chấm.",
        "Không chấm theo tên, giới tính, ảnh, quê quán, trường học hay thông tin cá nhân.",
        "Không thêm, xóa, đổi thứ tự dòng; không đổi tên sheet, tên cột hay tên file.",
        "Mở bằng Microsoft Excel (hoặc LibreOffice). Không mở bằng Google Sheets vì có thể mất danh sách thả xuống.",
    ])

    heading("4. Cách chấm một cặp")
    steps([
        "Sheet CAP_CV_JD: lấy cặp tiếp theo theo cột thu_tu. Mở CV_PDF/<cv_id>.pdf và đọc JD ở sheet JD.",
        "Sheet YEU_CAU_JD: với mỗi yêu cầu của JD, chọn trang_thai: met (có dùng trong dự án, kinh nghiệm, chứng chỉ), "
        "mentioned_only (chỉ liệt kê ở mục kỹ năng/mục tiêu), missing (không thấy), unclear (không đủ để quyết định, "
        "ghi lý do ở ghi_chu). Với met và mentioned_only, chép nguyên văn đoạn CV vào trich_dan.",
        "Sheet TIEU_CHI: chấm 0–4 cho 8 tiêu chí theo mô tả ở sheet RUBRIC. Chấm C8 (phù hợp JD) sau cùng, dựa vào bước 2.",
        "Sheet TONG_THE: chọn muc_phu_hop 1–5, viết tối đa 3 gợi ý sửa CV quan trọng nhất (mỗi gợi ý chọn một tiêu chí), "
        "ghi số phút đã dùng cho cặp.",
        "Kiểm tra cột kiem_tra hiện OK ở mọi dòng của cặp. Sheet TIEN_DO cho biết cặp đã xong chưa.",
    ])

    heading("Một số trường hợp khó ở YEU_CAU_JD", 11.5)
    bullets([
        "Bỏ qua mức độ: JD ghi 'thành thạo Java', CV ghi 'Java' trong mục kỹ năng → mentioned_only như bình thường. "
        "Mức độ thành thạo được phản ánh ở tiêu chí C3.",
        "CV nêu một khả năng khác cùng lĩnh vực → missing và ghi lý do ở ghi_chu. Ví dụ JD cần giao tiếp tiếng Anh "
        "(viết và nói), CV chỉ ghi đọc hiểu tài liệu kỹ thuật.",
        "Yêu cầu có lựa chọn thay thế ('Jest hoặc Jasmine', 'React hoặc Vue') → CV có một trong các lựa chọn là đủ.",
        "Kỹ năng chỉ suy ra gián tiếp (CV có Spring Boot nhưng không ghi Java) → unclear và ghi lý do; không tự suy ra là met.",
    ])

    heading("5. Chấm tiêu chí")
    bullets([
        "scored: chấm 0–4 theo mô tả neo. Điểm từ 1 trở lên phải có trích dẫn.",
        "missing_in_cv: PDF đọc được nhưng CV không có nội dung cho tiêu chí đó. Điểm bắt buộc là 0.",
        "not_applicable: tiêu chí không áp dụng cho vị trí. Bỏ trống điểm, ghi lý do.",
        "unreadable: không đọc chắc được phần liên quan (mờ, vỡ font, mất trang). Bỏ trống điểm, ghi lý do.",
        "C1 (trình bày) và C7 (ATS): chọn muc_bang_chung = toan_bo_cv và mô tả ngắn điều quan sát được. Với C7, thử bôi đen "
        "và sao chép chữ trong PDF.",
        "C5 (kinh nghiệm) với JD intern/fresher: nếu không có kinh nghiệm nhưng có dự án đạt mức 3 ở C4, cho tối đa 2 điểm "
        "và ghi 'dự án thay thế' ở ly_do.",
    ])

    heading("6. Trích dẫn")
    bullets([
        "Chép nguyên văn từ PDF, tối đa khoảng 25 từ, không sửa chính tả; chọn mục chứa đoạn đó ở muc_bang_chung.",
        "Mục trong CV có tên khác danh sách thì chọn mục tương ứng: Ngoại ngữ → skills (chứng chỉ có điểm như TOEIC, "
        "IELTS → certifications); Mục tiêu, Giới thiệu → summary; Thực tập, Công việc → experience; Đồ án → projects; "
        "Giải thưởng, Thành tích → awards; Hoạt động, CLB, Tình nguyện → activities. Chỉ dùng toan_bo_cv cho C1 và C7.",
        "Chỉ chấm theo nội dung CV; không mở link GitHub, portfolio hay demo. Link chỉ tính như một dòng chữ trong CV "
        "(với C4, link repo hoặc demo của dự án vẫn là 'sản phẩm kiểm chứng được').",
        "Link GitHub với yêu cầu Git: link gắn với một dự án cụ thể → met (projects); chỉ có link hồ sơ ở phần liên hệ → "
        "mentioned_only (personal_info); Git/GitHub chỉ ghi trong mục kỹ năng → mentioned_only (skills).",
        "Ví dụ: tiêu chí C4, điểm 3, muc_bang_chung = projects, trich_dan = 'Built REST API for booking with Spring Boot "
        "and MySQL, role: backend developer', ly_do = 'Có vai trò, công nghệ, đầu việc; chưa có kết quả đo được'.",
        "Không chắc giữa hai mức điểm: chọn mức thấp hơn khi thiếu bằng chứng, và ghi điều phân vân vào ghi_chu. "
        "Ghi chú này rất có ích cho buổi chỉnh rubric.",
    ])

    heading("7. Thời gian và nộp bài")
    bullets([
        "Khoảng 10–12 phút mỗi cặp; cặp đầu tiên lâu hơn. Có thể chia nhiều buổi, nhớ lưu file thường xuyên (Ctrl+S).",
        f"Hạn nộp: {deadline}. Gửi lại đúng file {workbook_name} qua kênh riêng của nhóm cho {coordinator}.",
        "Không cần làm hết trong một lần; file chấm dở vẫn kiểm tra được.",
    ])

    heading("Thông tin truy vết", 10)
    doc.add_paragraph(f"layout {meta['layout_version']} · rubric_sha256 {meta['rubric_sha256'][:16]} · "
                      f"pairs_sha256 {meta['pairs_sha256'][:16]} · jd_gold_sha256 {meta['jd_gold_sha256'][:16]} · "
                      f"split {meta['split']} · tạo lúc {meta['created_at']}")
    doc.save(path)


def package(rater: str, *, split: str | None = None, pairs: Path = PAIRS, jd_gold: Path = JD_GOLD,
            jd_text: Path = JD_TEXT, out_dir: Path = OUT_DIR, deadline: str = "do điều phối viên thông báo",
            coordinator: str = "điều phối viên của nhóm", pdf_paths=cv_pdf_paths, guide_only: bool = False) -> Path:
    """Write the rater's zip; with guide_only, write only <stem>_00_DOC_TRUOC.docx (rule changes in the guide)."""
    round_name = "Vòng chấm thử" if split == "dev" else "Vòng chính" if split in (None, "test") else f"Tập {split}"
    stem = f"{'pilot' if split == 'dev' else 'full' if split is None else split}_rater_{rater}"
    workbook_name = f"{stem}.xlsx"
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        meta = builder.build(pairs, jd_gold, rater, work / workbook_name, jd_text_dir=jd_text, lock=True, split=split)
        with pairs.open(encoding="utf-8-sig", newline="") as handle:
            cv_ids = sorted({r["cv_id"] for r in csv.DictReader(handle) if split is None or r.get("split") == split})
        guide(work / "00_DOC_TRUOC.docx", rater=rater, round_name=round_name, workbook_name=workbook_name, meta=meta,
              cv_ids=cv_ids, deadline=deadline, coordinator=coordinator)
        out_dir.mkdir(parents=True, exist_ok=True)
        if guide_only:
            target = out_dir / f"{stem}_00_DOC_TRUOC.docx"
            target.write_bytes((work / "00_DOC_TRUOC.docx").read_bytes())
            return target
        pdfs = pdf_paths(set(cv_ids))
        target = out_dir / f"{stem}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(work / "00_DOC_TRUOC.docx", f"{stem}/00_DOC_TRUOC.docx")
            archive.write(work / workbook_name, f"{stem}/{workbook_name}")
            for cv in cv_ids:
                archive.write(pdfs[cv], f"{stem}/CV_PDF/{cv}.pdf")
    record = {"package": target.name, "rater": rater, "split": split or "all", "pairs": meta["pair_count"], "cvs": len(cv_ids),
              "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
              "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    with (out_dir / "PACKAGES_LOG.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(record, ensure_ascii=False) + "\n")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Build one rater's package.")
    parser.add_argument("--rater", required=True)
    parser.add_argument("--split", help="dev for the pilot round; omit for all pairs")
    parser.add_argument("--deadline", default="do điều phối viên thông báo")
    parser.add_argument("--coordinator", default="điều phối viên của nhóm")
    parser.add_argument("--guide-only", action="store_true",
                        help="only write the guide .docx; use when just the rules in the guide changed")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    target = package(args.rater, split=args.split, deadline=args.deadline, coordinator=args.coordinator,
                     guide_only=args.guide_only)
    print(f"{target.relative_to(ROOT)} ({target.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
