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


def requirement_rules():
    """The JD requirement rules the model prompts use (cv_evaluation_web/services/requirement_rules.py)."""
    web = str(ROOT / "cv_evaluation_web")
    if web not in sys.path:
        sys.path.insert(0, web)
    from services import requirement_rules as rules
    return rules
NAVY = RGBColor(0x17, 0x36, 0x5D)
# Bump when the guide's rules change; raters quote it so the coordinator knows which rules they used.
GUIDE_VERSION = "2026-10-17 (sau vòng chấm thử; quy tắc yêu cầu JD dùng chung với prompt model)"


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

    def checklist(items: list[str]) -> None:
        """Numbered (1), (2)… restarting for each list, so the level rules can cite them."""
        for number, item in enumerate(items, 1):
            doc.add_paragraph(f"({number}) {item}", style="List Bullet")

    heading(f"Hướng dẫn chấm cặp CV–JD · {round_name} · Người chấm {rater}", 15)
    doc.add_paragraph(f"Số cặp: {meta['pair_count']} · Số CV: {len(cv_ids)} · Rubric: {meta['rubric_version']} · "
                      f"Hướng dẫn bản {GUIDE_VERSION} · Hạn nộp: {deadline} · Liên hệ khi file lỗi: {coordinator}")

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
        "mentioned_only (chỉ liệt kê ở mục kỹ năng/mục tiêu), missing (không có, hoặc CV có thứ khác thay cho yêu cầu), "
        "unclear (chỉ có dấu hiệu, chưa đủ để khẳng định; ghi lý do ở ghi_chu). Xem quy tắc ngay dưới đây. Với met và "
        "mentioned_only, chép nguyên văn đoạn CV vào trich_dan.",
        "Sheet TIEU_CHI: chấm 0–4 cho 8 tiêu chí theo mô tả ở sheet RUBRIC. Chấm C8 (phù hợp JD) sau cùng, dựa vào bước 2.",
        "Sheet TONG_THE: chọn muc_phu_hop 1–5, viết tối đa 3 gợi ý sửa CV quan trọng nhất (mỗi gợi ý chọn một tiêu chí), "
        "ghi số phút đã dùng cho cặp.",
        "Kiểm tra cột kiem_tra hiện OK ở mọi dòng của cặp. Sheet TIEN_DO cho biết cặp đã xong chưa.",
    ])

    rules = requirement_rules()
    heading(f"Quy tắc xét yêu cầu JD (bản {rules.VERSION})", 11.5)
    doc.add_paragraph(
        "Danh sách dưới đây là đúng văn bản đưa vào prompt của mọi phương pháp chấm tự động, để người và máy theo cùng "
        "một quy tắc. Có thắc mắc về một quy tắc thì hỏi điều phối viên, không tự diễn giải khác.")
    bullets(list(rules.RULES))

    heading("Thao tác khi chấm yêu cầu", 11.5)
    bullets([
        "Trước khi chọn missing: dùng Ctrl+F trong PDF tìm tên công nghệ, cả tên viết tắt và cách viết khác (TS, "
        "TypeScript; Postgres, PostgreSQL; JS, JavaScript). Ở vòng chấm thử, phần lớn các ca một người chọn met còn "
        "người kia chọn missing là do bỏ sót khi đọc.",
        "Ghi chú bắt buộc ở ghi_chu: mọi dòng unclear (CV có gì, vì sao chưa đủ); dòng missing mà Ctrl+F vẫn thấy từ "
        "khóa (vì sao không tính, ví dụ 'chỉ có CSS' hoặc 'dùng MySQL thay vì PostgreSQL'); và mọi dòng đổi trạng thái khi "
        "rà lại (đổi từ gì, vì sao).",
        "Với met và mentioned_only: chép nguyên văn đoạn CV vào trich_dan. Với missing: để trống muc_bang_chung và trich_dan.",
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
        "Mức 0 vì CV không có mục hoặc nội dung cho tiêu chí (không có kinh nghiệm, không có chứng chỉ…) → luôn dùng "
        "missing_in_cv, kể cả C5 với JD junior. Chỉ dùng scored với điểm 0 khi CV có nội dung nhưng yếu đến mức 0 "
        "(ví dụ C8 dưới 20%).",
        "C8: tính tỉ lệ = (số met + 0,5 × số mentioned_only) / số yêu cầu bắt buộc, không tính các dòng unclear. Làm đúng "
        "theo khoảng: dưới 0,2 → 0; 0,2 đến dưới 0,4 → 1; 0,4 đến dưới 0,6 → 2; 0,6 đến dưới 0,8 → 3; từ 0,8 → 4 "
        "(cần thêm vài yêu cầu ưu tiên). Ví dụ 0,59 → 2.",
    ])

    heading("Cách chọn mức điểm (bổ sung sau vòng chấm thử)", 11.5)
    doc.add_paragraph(
        "Ở vòng chấm thử, mức 4 được dùng cho phần lớn CV ở C1, C2, C3 và C7. Khi gần như CV nào cũng được 4, điểm "
        "không còn phân biệt được CV tốt với CV trung bình. Các quy tắc dưới đây không đổi mô tả mức trong sheet "
        "RUBRIC; chúng chỉ nói cách kiểm tra từng điều kiện.")
    bullets([
        "Chấm từ dưới lên: đọc mô tả mức 2; CV thỏa hết điều kiện của mức 2 thì xét mức 3, rồi mức 4. Dừng ở mức cao "
        "nhất mà CV thỏa mọi điều kiện. Thiếu một điều kiện là chưa đạt mức đó.",
        "Mức 4 nghĩa là theo tiêu chí này CV gần như không còn gì để sửa. Khi cho 4, ghi ở ly_do vì sao CV đạt từng "
        "điều kiện của mức 4.",
        "Thấy mình sắp cho 4 ở một tiêu chí cho hầu hết CV: dừng lại, đọc lại mô tả mức 4 và các danh sách kiểm tra dưới đây.",
    ])

    heading("C1 · Cấu trúc và hình thức (chỉ xem cách trình bày, không xem nội dung chuyên môn hay máy đọc)", 11)
    checklist([
        "Có đủ các mục chính không: mục tiêu hoặc giới thiệu, kỹ năng, dự án hoặc kinh nghiệm, học vấn?",
        "Định dạng có nhất quán không: cách ghi ngày tháng, gạch đầu dòng, cỡ và kiểu chữ giữa các mục?",
        "Đếm lỗi chính tả và lỗi khoảng trắng hoặc dòng tràn sang trang mới.",
        "Độ dài 1–2 trang, không dày đặc chữ?",
        "Thông tin quan trọng với vị trí (kỹ năng, dự án hoặc kinh nghiệm CNTT) có đặt trước thông tin ít liên quan "
        "(sở thích, thông tin phụ) không?",
    ])
    bullets([
        "Mức 4: đạt cả (1)–(5) và không có lỗi chính tả nào. Mức 3: đạt (1), (2), (4) và chỉ có lỗi nhỏ (vài lỗi chính tả, "
        "khoảng trắng, một dòng tràn trang). Mức 2: đủ mục nhưng (2) hoặc (4) không đạt. Mức 1 và 0 theo sheet RUBRIC.",
        "Ghi vào ly_do kết quả từng câu, ví dụ: 'đủ mục; ngày tháng lúc ghi 03/2025 lúc ghi Mar 2025; 2 lỗi chính tả → 2'.",
    ])

    heading("C2 · Nội dung chuyên môn CNTT (chấm độc lập với JD)", 11)
    checklist([
        "Mục tiêu hoặc giới thiệu có nêu một hướng cụ thể (Backend, Frontend, Mobile…) không?",
        "Dự án và kinh nghiệm có cùng hướng đó không?",
        "Dự án hoặc kinh nghiệm có ít nhất một dấu hiệu chiều sâu kỹ thuật: thiết kế (CSDL, API, kiến trúc), kiểm thử "
        "(unit test, integration test) hoặc triển khai (deploy, Docker, CI/CD)? Chỉ ghi ở mục kỹ năng thì không tính.",
    ])
    bullets([
        "Mức 4: đạt cả (1)–(3). Mức 3: đạt (1) và (2). Mức 2: có nội dung CNTT nhưng không đạt (1), hoặc dự án lệch hướng đã nêu.",
    ])

    heading("C3 · Kỹ năng chuyên môn và bổ trợ", 11)
    checklist([
        "Lấy tối đa 5 kỹ năng chuyên môn chính (đầu danh sách, hoặc những kỹ năng CV nhấn mạnh). Đếm bao nhiêu kỹ năng "
        "xuất hiện trong dự án, kinh nghiệm hoặc chứng chỉ.",
        "Danh sách kỹ năng có được nhóm rõ không (ngôn ngữ, framework, CSDL, công cụ…)?",
        "Có kỹ năng bổ trợ không? Có ngữ cảnh cụ thể không: vai trò trong nhóm ('trưởng nhóm 4 người'), thuyết trình đồ "
        "án, chứng chỉ ngoại ngữ có điểm?",
    ])
    bullets([
        "Mức 4: ít nhất 4/5 kỹ năng có minh chứng, danh sách được nhóm, và kỹ năng bổ trợ có ngữ cảnh. Mức 3: ít nhất 3/5 "
        "có minh chứng và có kỹ năng bổ trợ (chưa cần ngữ cảnh). Mức 2: dưới 3/5 có minh chứng, hoặc không có kỹ năng bổ trợ.",
        "Ghi số đếm vào ly_do, ví dụ: '3/5 có minh chứng (Java, Spring Boot, MySQL); soft skill chỉ liệt kê → 3'.",
    ])

    heading("C7 · Khả năng đáp ứng ATS (máy đọc được): kiểm tra bắt buộc", 11)
    checklist([
        "Mở PDF, nhấn Ctrl+A rồi Ctrl+C, dán vào Notepad (không dán vào công cụ online). Có chép ra được chữ không? "
        "Không, hoặc gần như không → 0.",
        "Chữ dán ra có đúng thứ tự đọc không, hay các mục bị trộn, cột trái và cột phải xen nhau từng dòng? Bị trộn ở "
        "nhiều chỗ, hoặc thông tin quan trọng (kỹ năng, liên hệ, ngày tháng) chỉ nằm trong hình hay biểu tượng → 1.",
        "Đếm các vấn đề còn lại: (a) bố cục hai cột; (b) thanh, sao hay vòng tròn đo kỹ năng bằng đồ họa; (c) tiêu đề "
        "mục lạ, không phải Mục tiêu, Kỹ năng, Kinh nghiệm, Dự án, Học vấn hay tương đương tiếng Anh; (d) ngày tháng "
        "không nhất quán; (e) biểu tượng thay chữ (icon điện thoại không kèm số).",
    ])
    bullets([
        "Mức 4: chép đúng thứ tự và không có vấn đề nào ở (3). Mức 3: chỉ có hai cột đơn giản mà chữ dán ra vẫn đúng "
        "thứ tự, hoặc chỉ một lỗi nhỏ. Mức 2: còn một vấn đề rõ (thanh đồ họa kỹ năng, tiêu đề lạ, hai cột làm thứ tự "
        "dán ra bị xáo một phần). Mức 1: nhiều vấn đề, hoặc theo (2).",
        "Ghi vào ly_do kết quả (1)–(3), ví dụ: 'chép được; thứ tự đúng; có thanh đồ họa kỹ năng → 2'.",
    ])

    heading("6. Trích dẫn")
    bullets([
        "Chép nguyên văn từ PDF, tối đa khoảng 25 từ, không sửa chính tả; chọn mục chứa đoạn đó ở muc_bang_chung.",
        "Trích một đoạn liền mạch; không nối nhiều chỗ bằng '...'. Kỹ năng xuất hiện ở nhiều nơi thì trích chỗ mạnh nhất "
        "(dự án hoặc kinh nghiệm trước, mục kỹ năng sau).",
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
    stem = f"{ {'dev': 'pilot', None: 'full', 'test': 'main'}.get(split, split)}_rater_{rater}"
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
