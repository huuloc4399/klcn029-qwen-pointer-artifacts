"""Export satisfaction ratings (feedback.jsonl from the extraction API host) to an Excel report.

Sheets: "Tổng quan" (count, mean, median, share of 4-5 stars, distribution + chart),
"Theo nhóm" (by language, CV score band, document route, verdict, day) and "Danh sách" (one row
per rating, filterable). Summary cells are Excel formulas over "Danh sách", so filtering or
correcting rows there updates the report. Several files can be merged (e.g. laptop + Oracle);
a rating id that appears twice is kept once.

The workbook holds free-text comments from participants: keep it out of the repository.

Usage:
    python deployment/tools/export_feedback.py E:/klcn029-home/data/feedback/feedback.jsonl
    python deployment/tools/export_feedback.py laptop.jsonl oracle.jsonl -o feedback_report.xlsx
Requires openpyxl (pip install openpyxl).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo
except ImportError as exc:  # pragma: no cover - guidance for the operator
    raise SystemExit("Cần openpyxl: python -m pip install openpyxl") from exc


LIST_SHEET = "Danh sách"
COLUMNS = [
    ("Thời điểm", 19), ("Số sao", 8), ("Góp ý", 60), ("Ngôn ngữ", 10), ("Điểm CV", 9),
    ("Mức đánh giá", 16), ("Tuyến xử lý", 22), ("Chế độ pipeline", 15), ("Token sinh", 11),
    ("Giây chạy model", 15), ("Cảnh báo OCR", 13), ("Mã đánh giá", 34),
]
SCORE_BANDS = [("0–49", 0, 50), ("50–69", 50, 70), ("70–84", 70, 85), ("85–100", 85, 101)]
HEADER_FILL = PatternFill("solid", fgColor="E8F5EE")
BOLD = Font(bold=True)


def load_records(paths: list[Path]) -> tuple[list[dict[str, Any]], int]:
    records, seen, duplicates = [], set(), 0
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except ValueError as exc:
                raise SystemExit(f"{path}:{number} không phải JSON hợp lệ") from exc
            if record.get("id") in seen:
                duplicates += 1
                continue
            seen.add(record.get("id"))
            records.append(record)
    records.sort(key=lambda item: item.get("created_at") or item.get("received_at") or "")
    return records, duplicates


def local_time(value: str | None) -> datetime | None:
    if not value:
        return None
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone().replace(tzinfo=None)  # Excel has no time zones; show local time


def put_text(cell, value: Any) -> None:
    """Write user-supplied text as text: a comment starting with '=' must never become a formula."""
    cell.value = "" if value is None else str(value)
    cell.data_type = "s"


def header_row(sheet, row: int, labels: list[str]) -> None:
    for column, label in enumerate(labels, 1):
        cell = sheet.cell(row=row, column=column, value=label)
        cell.font = BOLD
        cell.fill = HEADER_FILL


def write_list(workbook: Workbook, records: list[dict[str, Any]]) -> int:
    sheet = workbook.create_sheet(LIST_SHEET)
    header_row(sheet, 1, [name for name, _ in COLUMNS])
    for column, (_, width) in enumerate(COLUMNS, 1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    for row, record in enumerate(records, 2):
        context = record.get("context") or {}
        stamp = local_time(record.get("created_at") or record.get("received_at"))
        sheet.cell(row=row, column=1, value=stamp).number_format = "yyyy-mm-dd hh:mm"
        sheet.cell(row=row, column=2, value=int(record["rating"]))
        put_text(sheet.cell(row=row, column=3), record.get("comment"))
        sheet.cell(row=row, column=3).alignment = Alignment(wrap_text=True, vertical="top")
        put_text(sheet.cell(row=row, column=4), context.get("language"))
        sheet.cell(row=row, column=5, value=context.get("total_score"))
        put_text(sheet.cell(row=row, column=6), context.get("verdict"))
        put_text(sheet.cell(row=row, column=7), context.get("document_route") or "web")
        put_text(sheet.cell(row=row, column=8), context.get("pipeline_mode"))
        sheet.cell(row=row, column=9, value=context.get("generated_tokens"))
        sheet.cell(row=row, column=10, value=context.get("model_runtime_seconds"))
        put_text(sheet.cell(row=row, column=11), "có" if context.get("ocr_quality_warning") else "")
        put_text(sheet.cell(row=row, column=12), record.get("id"))
    last = max(len(records) + 1, 2)
    if records:
        table = Table(displayName="DanhGia", ref=f"A1:{get_column_letter(len(COLUMNS))}{last}")
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium7", showRowStripes=True)
        sheet.add_table(table)
    sheet.freeze_panes = "A2"
    return last


def col(letter: str, last: int) -> str:
    return f"'{LIST_SHEET}'!${letter}$2:${letter}${last}"


def write_overview(sheet, last: int, sources: list[Path], duplicates: int) -> None:
    stars, comments, stamps = col("B", last), col("C", last), col("A", last)
    sheet["A1"] = "Báo cáo mức độ hài lòng – CV Insight (KLCN029)"
    sheet["A1"].font = Font(bold=True, size=14)
    metrics = [
        ("Số lượt đánh giá", f"=COUNT({stars})", "0"),
        ("Điểm hài lòng trung bình (1–5)", f'=IFERROR(AVERAGE({stars}),"")', "0.00"),
        ("Trung vị", f'=IFERROR(MEDIAN({stars}),"")', "0.0"),
        ("Tỷ lệ hài lòng (4–5 sao)", f'=IFERROR(COUNTIF({stars},">=4")/COUNT({stars}),"")', "0.0%"),
        ("Tỷ lệ không hài lòng (1–2 sao)", f'=IFERROR(COUNTIF({stars},"<=2")/COUNT({stars}),"")', "0.0%"),
        ("Số lượt có góp ý", f'=COUNTIF({comments},"?*")', "0"),
        ("Từ", f'=IF(COUNT({stamps}),MIN({stamps}),"")', "yyyy-mm-dd"),
        ("Đến", f'=IF(COUNT({stamps}),MAX({stamps}),"")', "yyyy-mm-dd"),
    ]
    for row, (label, formula, number_format) in enumerate(metrics, 3):
        sheet.cell(row=row, column=1, value=label).font = BOLD
        sheet.cell(row=row, column=2, value=formula).number_format = number_format

    start = 3 + len(metrics) + 2
    sheet.cell(row=start - 1, column=1, value="Phân bố số sao").font = BOLD
    header_row(sheet, start, ["Số sao", "Số lượt", "Tỷ lệ"])
    for offset, value in enumerate(range(1, 6), 1):
        row = start + offset
        sheet.cell(row=row, column=1, value=value)
        sheet.cell(row=row, column=2, value=f"=COUNTIF({stars},A{row})")
        sheet.cell(row=row, column=3, value=f"=IFERROR(B{row}/$B$3,0)").number_format = "0.0%"
    chart = BarChart()
    chart.title = "Phân bố số sao"
    chart.y_axis.title = "Số lượt"
    chart.x_axis.title = "Số sao"
    chart.legend = None
    chart.add_data(Reference(sheet, min_col=2, min_row=start, max_row=start + 5), titles_from_data=True)
    chart.set_categories(Reference(sheet, min_col=1, min_row=start + 1, max_row=start + 5))
    chart.height, chart.width = 7.5, 13
    sheet.add_chart(chart, "E3")

    note = start + 8
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    sheet.cell(row=note, column=1, value="Nguồn").font = BOLD
    put_text(sheet.cell(row=note, column=2), "; ".join(str(path) for path in sources))
    sheet.cell(row=note + 1, column=1, value="Tạo lúc").font = BOLD
    put_text(sheet.cell(row=note + 1, column=2), generated)
    sheet.cell(row=note + 2, column=1, value="Bản ghi trùng đã bỏ").font = BOLD
    sheet.cell(row=note + 2, column=2, value=duplicates)
    sheet.cell(row=note + 3, column=1, value="Lưu ý").font = BOLD
    put_text(sheet.cell(row=note + 3, column=2),
             "Đánh giá tự nguyện của người dùng thử nghiệm; không phải mẫu ngẫu nhiên. "
             "Tệp chứa góp ý tự do: không đưa lên kho mã nguồn.")
    sheet.column_dimensions["A"].width = 32
    sheet.column_dimensions["B"].width = 16
    sheet.column_dimensions["C"].width = 10


def write_groups(sheet, last: int, records: list[dict[str, Any]]) -> None:
    stars = col("B", last)
    row = 1

    def block(title: str, labels: list[str], count_formula, mean_formula) -> None:
        nonlocal row
        sheet.cell(row=row, column=1, value=title).font = Font(bold=True, size=12)
        header_row(sheet, row + 1, ["Nhóm", "Số lượt", "Điểm hài lòng TB", "Tỷ lệ 4–5 sao"])
        for index, label in enumerate(labels):
            current = row + 2 + index
            put_text(sheet.cell(row=current, column=1), label)
            sheet.cell(row=current, column=2, value=count_formula(label, current))
            sheet.cell(row=current, column=3, value=f'=IFERROR({mean_formula(label, current)},"")').number_format = "0.00"
        row += len(labels) + 3

    def by_text(letter: str):
        values = col(letter, last)
        return (lambda label, r: f"=COUNTIF({values},A{r})",
                lambda label, r: f"AVERAGEIF({values},A{r},{stars})",
                values)

    for title, letter in (("Theo ngôn ngữ CV", "D"), ("Theo tuyến xử lý PDF", "G"), ("Theo mức đánh giá CV", "F")):
        index = {"D": "language", "G": "document_route", "F": "verdict"}[letter]
        labels = sorted({str((item.get("context") or {}).get(index) or ("web" if letter == "G" else ""))
                         for item in records} - {""}) or ["(chưa có)"]
        count, mean, values = by_text(letter)
        start = row
        block(title, labels, count, mean)
        for offset in range(len(labels)):
            current = start + 2 + offset
            sheet.cell(row=current, column=4,
                       value=f'=IFERROR(COUNTIFS({values},A{current},{stars},">=4")/B{current},"")').number_format = "0.0%"

    scores = col("E", last)
    start = row
    block("Theo điểm CV (thang 100)", [band for band, _, _ in SCORE_BANDS],
          lambda label, r: '=COUNTIFS({0},">={1}",{0},"<{2}")'.format(scores, *bounds(label)),
          lambda label, r: 'AVERAGEIFS({3},{0},">={1}",{0},"<{2}")'.format(scores, *bounds(label), stars))
    for offset, (band, low, high) in enumerate(SCORE_BANDS):
        current = start + 2 + offset
        sheet.cell(row=current, column=4, value=(
            f'=IFERROR(COUNTIFS({scores},">={low}",{scores},"<{high}",{stars},">=4")/B{current},"")'
        )).number_format = "0.0%"

    stamps = col("A", last)
    days = sorted({stamp.date() for stamp in (local_time(item.get("created_at") or item.get("received_at"))
                                              for item in records) if stamp})
    sheet.cell(row=row, column=1, value="Theo ngày").font = Font(bold=True, size=12)
    header_row(sheet, row + 1, ["Ngày", "Số lượt", "Điểm hài lòng TB", "Tỷ lệ 4–5 sao"])
    for index, day in enumerate(days or [datetime.now().date()]):
        current = row + 2 + index
        sheet.cell(row=current, column=1, value=datetime.combine(day, datetime.min.time())).number_format = "yyyy-mm-dd"
        window = f'{stamps},">="&A{current},{stamps},"<"&(A{current}+1)'
        sheet.cell(row=current, column=2, value=f"=COUNTIFS({window})")
        sheet.cell(row=current, column=3, value=f'=IFERROR(AVERAGEIFS({stars},{window}),"")').number_format = "0.00"
        sheet.cell(row=current, column=4,
                   value=f'=IFERROR(COUNTIFS({window},{stars},">=4")/B{current},"")').number_format = "0.0%"
    for letter, width in (("A", 26), ("B", 10), ("C", 18), ("D", 14)):
        sheet.column_dimensions[letter].width = width


def bounds(label: str) -> tuple[int, int]:
    for band, low, high in SCORE_BANDS:
        if band == label:
            return low, high
    raise KeyError(label)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inputs", nargs="+", type=Path, help="feedback.jsonl files")
    parser.add_argument("-o", "--output", type=Path,
                        help="default: feedback_report_<date>.xlsx next to the first input")
    args = parser.parse_args()
    records, duplicates = load_records(args.inputs)
    output = args.output or args.inputs[0].with_name(f"feedback_report_{datetime.now():%Y%m%d}.xlsx")

    workbook = Workbook()
    overview = workbook.active
    overview.title = "Tổng quan"
    groups = workbook.create_sheet("Theo nhóm")
    last = write_list(workbook, records)
    write_overview(overview, last, args.inputs, duplicates)
    write_groups(groups, last, records)
    workbook.calculation.fullCalcOnLoad = True
    workbook.save(output)
    print(f"{len(records)} đánh giá ({duplicates} trùng đã bỏ) -> {output}")


if __name__ == "__main__":
    main()
