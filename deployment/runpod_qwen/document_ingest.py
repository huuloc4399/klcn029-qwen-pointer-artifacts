"""PDF text/OCR routing for the serverless extraction worker."""

from __future__ import annotations

import base64
import io
from dataclasses import asdict, dataclass
from typing import Any

import pymupdf


MAX_PDF_BYTES = 6 * 1024 * 1024
MAX_PAGES = 12
OCR_DPI = 200


@dataclass(slots=True)
class IngestResult:
    text: str
    page_count: int
    native_text_pages: int
    ocr_pages: int
    character_count: int
    routes: list[str]
    ocr_quality_warning: bool

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("text", None)
        return payload


_OCR_ENGINES: dict[str, Any] = {}


def _ocr_engine(language: str):
    from paddleocr import PaddleOCR

    key = "vi" if language == "vi" else "en"
    if key not in _OCR_ENGINES:
        recognition = "latin_PP-OCRv5_mobile_rec" if key == "vi" else "en_PP-OCRv5_mobile_rec"
        _OCR_ENGINES[key] = PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name=recognition,
            device="cpu",
            enable_mkldnn=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    return _OCR_ENGINES[key]


def _ocr_page(page: pymupdf.Page, language: str) -> str:
    if language not in {"en", "vi"}:
        raise ValueError("Image-only PDF requires language='en' or language='vi'")
    import numpy as np
    from PIL import Image

    pixmap = page.get_pixmap(dpi=OCR_DPI, alpha=False)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    results = list(_ocr_engine(language).predict(np.asarray(image)))
    if len(results) != 1:
        raise RuntimeError("OCR returned an unexpected result count")
    data = results[0].json.get("res", results[0].json)
    return "\n".join(str(value).strip() for value in data.get("rec_texts", []) if str(value).strip())


def ingest_pdf_base64(value: str, language: str) -> IngestResult:
    try:
        pdf_bytes = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError("pdf_base64 is invalid") from exc
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("Uploaded bytes are not a PDF")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError("PDF exceeds the 6 MB serverless limit")
    document = pymupdf.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    try:
        if document.needs_pass:
            raise ValueError("Password-protected PDF is not supported")
        if document.page_count < 1 or document.page_count > MAX_PAGES:
            raise ValueError(f"PDF must contain 1-{MAX_PAGES} pages")
        texts: list[str] = []
        routes: list[str] = []
        native_pages = 0
        ocr_pages = 0
        for page in document:
            native = page.get_text("text", sort=True).strip()
            if len(native) >= 40:
                texts.append(native)
                routes.append("pdf_text")
                native_pages += 1
            else:
                ocr = _ocr_page(page, language)
                if not ocr:
                    raise ValueError("OCR did not detect text on a sparse PDF page")
                texts.append(ocr)
                routes.append("paddleocr_latin_vi" if language == "vi" else "paddleocr_en")
                ocr_pages += 1
        text = "\n".join(part for part in texts if part).strip()
        return IngestResult(
            text=text,
            page_count=document.page_count,
            native_text_pages=native_pages,
            ocr_pages=ocr_pages,
            character_count=len(text),
            routes=routes,
            ocr_quality_warning=language == "vi" and ocr_pages > 0,
        )
    finally:
        document.close()
