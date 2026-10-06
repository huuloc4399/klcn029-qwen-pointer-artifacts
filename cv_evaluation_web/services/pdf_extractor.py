"""Safe, lightweight PDF inspection used by the web baseline.

This module deliberately uses the native PDF text layer. The production OCR
router will be connected later; a sparse text layer is surfaced to the user
instead of silently inventing content.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf


class PDFExtractionError(ValueError):
    """Raised when an uploaded file cannot be processed safely."""


@dataclass(slots=True)
class DocumentAnalysis:
    text: str
    page_count: int
    native_text_pages: int
    character_count: int
    block_count: int
    likely_multi_column: bool
    needs_ocr: bool

    def public_dict(self) -> dict:
        data = asdict(self)
        data.pop("text", None)
        return data


def _looks_multi_column(page: pymupdf.Page, blocks: list[tuple]) -> bool:
    """Conservative layout signal; it is diagnostic, not a hard rejection."""
    width = max(float(page.rect.width), 1.0)
    meaningful = [b for b in blocks if len(b) >= 5 and str(b[4]).strip()]
    if len(meaningful) < 6:
        return False
    left = [b for b in meaningful if float(b[0]) < width * 0.42 and float(b[2]) < width * 0.68]
    right = [b for b in meaningful if float(b[0]) > width * 0.42]
    if len(left) < 2 or len(right) < 2:
        return False
    for l_block in left:
        for r_block in right:
            vertical_overlap = min(float(l_block[3]), float(r_block[3])) - max(float(l_block[1]), float(r_block[1]))
            if vertical_overlap > 12:
                return True
    return False


def extract_pdf(path: str | Path, *, max_pages: int = 12) -> DocumentAnalysis:
    source = Path(path)
    try:
        header = source.read_bytes()[:5]
    except OSError as exc:
        raise PDFExtractionError("Không thể đọc tệp đã tải lên.") from exc
    if header != b"%PDF-":
        raise PDFExtractionError("Tệp không có cấu trúc PDF hợp lệ.")

    try:
        document = pymupdf.open(source)
    except Exception as exc:  # PyMuPDF exposes several parser exceptions.
        raise PDFExtractionError("Không thể mở PDF. Tệp có thể bị hỏng hoặc được mã hóa.") from exc

    try:
        if document.needs_pass:
            raise PDFExtractionError("PDF có mật khẩu. Hãy tải lên bản không khóa.")
        if document.page_count < 1:
            raise PDFExtractionError("PDF không có trang nội dung.")
        if document.page_count > max_pages:
            raise PDFExtractionError(f"PDF vượt quá giới hạn {max_pages} trang.")

        page_texts: list[str] = []
        native_pages = 0
        block_count = 0
        multi_column = False
        for page in document:
            text = page.get_text("text", sort=True).strip()
            blocks = page.get_text("blocks", sort=True)
            page_texts.append(text)
            if len(text) >= 40:
                native_pages += 1
            block_count += len(blocks)
            multi_column = multi_column or _looks_multi_column(page, blocks)

        full_text = "\n\n".join(part for part in page_texts if part).strip()
        needs_ocr = native_pages < document.page_count or len(full_text) < 120
        return DocumentAnalysis(
            text=full_text,
            page_count=document.page_count,
            native_text_pages=native_pages,
            character_count=len(full_text),
            block_count=block_count,
            likely_multi_column=multi_column,
            needs_ocr=needs_ocr,
        )
    finally:
        document.close()
