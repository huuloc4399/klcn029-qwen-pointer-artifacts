"""PDF text/OCR router ported from the Colab demo (cell "Upload một CV PDF và chạy bộ định tuyến OCR").

Routing per page is unchanged: OCR only when the page has visible ink (dark-pixel ratio >= 2%)
and fewer than 80 native characters; otherwise keep the PDF text layer; near-blank pages are
skipped. English pages use PaddleOCR; Vietnamese pages use the Paddle detector + VietOCR
Seq2Seq recognizer with a PaddleOCR fallback for contact lines. The Colab notebook ran
VietOCR on the GPU; here it runs on CPU.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf

from baseline_extraction.privacy import redact_text


MAX_PDF_PAGES = 12
MAX_INPUT_CHARACTERS = 30_000
NATIVE_TEXT_THRESHOLD = 80
DARK_PIXEL_THRESHOLD = 0.02
DPI = 200
VIETOCR_WEIGHT_URL = os.getenv("VIETOCR_WEIGHT_URL", "https://vocr.vn/data/vietocr/vgg_seq2seq.pth")
VIETOCR_WEIGHT_SHA256 = "0921503a41375a0584268e23ef3d414ea478a8fe8777865c7745d38f2d0bc5db"
VIETOCR_WEIGHT_BYTES = 89_575_371
MODEL_CACHE_DIR = Path(os.getenv("MODEL_CACHE_DIR", "/tmp/models"))
VIETNAMESE_CHARS = set("ăâđêôơưĂÂĐÊÔƠƯạảãàáặẳẵằắậẩẫầấẹẻẽèéệểễềếịỉĩìíọỏõòóộổỗồốợởỡờớụủũùúựửữừứỵỷỹỳý")
VIETOCR_CONFIG = {
    "backbone": "vgg19_bn",
    "cnn": {
        "hidden": 256,
        "ks": [[2, 2], [2, 2], [2, 1], [2, 1], [1, 1]],
        "ss": [[2, 2], [2, 2], [2, 1], [2, 1], [1, 1]],
        "pretrained": False,
    },
    "dataset": {"image_height": 32, "image_max_width": 512, "image_min_width": 32},
    "device": "cpu",
    "predictor": {"beamsearch": False},
    "quiet": True,
    "seq_modeling": "seq2seq",
    "transformer": {
        "decoder_embedded": 256,
        "decoder_hidden": 256,
        "dropout": 0.1,
        "encoder_hidden": 256,
        "img_channel": 256,
    },
    "vocab": (
        "aAàÀảẢãÃáÁạẠăĂằẰẳẲẵẴắẮặẶâÂầẦẩẨẫẪấẤậẬbBcCdDđĐeEèÈẻẺẽẼéÉẹẸêÊềỀểỂễỄếẾệỆfFgGhHiIìÌỉỈĩĨíÍịỊ"
        "jJkKlLmMnNoOòÒỏỎõÕóÓọỌôÔồỒổỔỗỖốỐộỘơƠờỜởỞỡỠớỚợỢpPqQrRsStTuUùÙủỦũŨúÚụỤưƯừỪửỬữỮứỨựỰvVwWxXyY"
        "ỳỲỷỶỹỸýÝỵỴzZ0123456789!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ "
    ),
}


class DocumentError(ValueError):
    """User-facing problem with the uploaded PDF."""


@dataclass(slots=True)
class RoutedDocument:
    text: str
    language: str
    page_count: int
    routing_log: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ocr_pages(self) -> int:
        return sum(item["route"].startswith("ocr_") for item in self.routing_log)

    @property
    def native_text_pages(self) -> int:
        return sum(item["route"] == "native_text" for item in self.routing_log)

    def public_dict(self) -> dict[str, Any]:
        return {
            "route": "api_pdf_router",
            "language": self.language,
            "page_count": self.page_count,
            "native_text_pages": self.native_text_pages,
            "ocr_pages": self.ocr_pages,
            "character_count": len(self.text),
            "ocr_quality_warning": self.language == "vi" and self.ocr_pages > 0,
            "routing_log": self.routing_log,
        }


def detect_language(text: str) -> str:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        raise DocumentError("PDF không có lớp chữ để tự nhận diện ngôn ngữ. Hãy chọn Tiếng Việt hoặc English.")
    return "vi" if any(char in VIETNAMESE_CHARS for char in letters) else "en"


def dark_pixel_ratio(image) -> float:
    import numpy as np

    gray = np.asarray(image.convert("L"))
    return float((gray < 230).mean())


def render_page(page: pymupdf.Page):
    from PIL import Image

    pixmap = page.get_pixmap(dpi=DPI, alpha=False)
    return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def crop_polygon(image, polygon, padding: int = 4):
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    box = (
        max(0, int(min(xs)) - padding),
        max(0, int(min(ys)) - padding),
        min(image.width, int(max(xs)) + padding + 1),
        min(image.height, int(max(ys)) + padding + 1),
    )
    return image.crop(box).convert("RGB")


def is_contact_line(value: str) -> bool:
    lowered = value.casefold()
    has_phone = bool(re.search(r"(?<!\d)(?:\+?84|0)[\d\s().-]{7,18}(?!\d)", value))
    return has_phone or any(marker in lowered for marker in ("@", "gmail", "github.com/", "linkedin.com/", "facebook.com/"))


class OCREngines:
    """Lazily built OCR models, reused across requests (the API processes one job at a time)."""

    def __init__(self) -> None:
        self._paddle: dict[str, Any] = {}
        self._vietocr = None
        self._lock = threading.Lock()

    def paddle(self, language: str):
        with self._lock:
            if language not in self._paddle:
                try:
                    from paddleocr import PaddleOCR
                except ImportError as exc:
                    raise DocumentError("Máy chủ này chưa bật OCR; hãy dùng PDF có lớp chữ.") from exc
                recognizer = "en_PP-OCRv5_mobile_rec" if language == "en" else "latin_PP-OCRv5_mobile_rec"
                self._paddle[language] = PaddleOCR(
                    text_detection_model_name="PP-OCRv5_mobile_det",
                    text_recognition_model_name=recognizer,
                    device="cpu",
                    enable_mkldnn=False,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                )
            return self._paddle[language]

    def vietocr(self):
        with self._lock:
            if self._vietocr is None:
                from vietocr.tool.config import Cfg
                from vietocr.tool.predictor import Predictor

                config = Cfg(dict(VIETOCR_CONFIG))
                config["weights"] = str(ensure_vietocr_weight())
                self._vietocr = Predictor(config)
            return self._vietocr


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_vietocr_weight() -> Path:
    path = MODEL_CACHE_DIR / "vietocr" / "vgg_seq2seq.pth"
    if path.is_file() and path.stat().st_size == VIETOCR_WEIGHT_BYTES and _sha256_file(path) == VIETOCR_WEIGHT_SHA256:
        return path
    import requests

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".pth.tmp")
    with requests.get(VIETOCR_WEIGHT_URL, stream=True, timeout=120) as response:
        response.raise_for_status()
        with temporary.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    handle.write(chunk)
    if temporary.stat().st_size != VIETOCR_WEIGHT_BYTES or _sha256_file(temporary) != VIETOCR_WEIGHT_SHA256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("VietOCR checkpoint hash or size mismatch")
    os.replace(temporary, path)
    return path


def ocr_page(image, language: str, engines: OCREngines) -> tuple[str, dict[str, Any]]:
    import numpy as np

    started = time.perf_counter()
    results = list(engines.paddle(language).predict(np.asarray(image)))
    if len(results) != 1:
        raise RuntimeError(f"OCR returned {len(results)} results for one page")
    data = results[0].json.get("res", results[0].json)
    paddle_lines = [str(value).strip() for value in data.get("rec_texts", [])]
    scores = [float(value) for value in data.get("rec_scores", [])]
    polygons = data.get("rec_polys", [])
    fallback_lines = 0
    if language == "vi" and polygons:
        crops = [crop_polygon(image, polygon) for polygon in polygons]
        viet_lines = engines.vietocr().predict_batch(crops)
        lines = []
        for paddle_line, viet_line in zip(paddle_lines, viet_lines):
            if is_contact_line(paddle_line):
                lines.append(paddle_line)
                fallback_lines += 1
            else:
                lines.append(str(viet_line).strip())
    else:
        lines = paddle_lines
    return "\n".join(line for line in lines if line), {
        "detected_lines": len(lines),
        "mean_paddle_confidence": round(sum(scores) / len(scores), 4) if scores else None,
        "contact_fallback_lines": fallback_lines,
        "runtime_seconds": round(time.perf_counter() - started, 3),
    }


def route_pdf(pdf_bytes: bytes, language: str, engines: OCREngines) -> RoutedDocument:
    # Same rule as PDF readers: the header may follow a few stray bytes within the first 1 KB.
    if b"%PDF-" not in pdf_bytes[:1024]:
        raise DocumentError("Tệp gửi lên không phải PDF.")
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise DocumentError("Không mở được PDF.") from exc
    pages = []
    try:
        if document.needs_pass:
            raise DocumentError("PDF có mật khẩu.")
        if not 1 <= document.page_count <= MAX_PDF_PAGES:
            raise DocumentError(f"PDF phải có từ 1 đến {MAX_PDF_PAGES} trang.")
        for number, page in enumerate(document, 1):
            image = render_page(page)
            pages.append({
                "page": number,
                "native_text": page.get_text("text", sort=True).strip(),
                "image": image,
                "dark_pixel_ratio": dark_pixel_ratio(image),
            })
    finally:
        document.close()

    resolved = language
    if resolved == "auto":
        resolved = detect_language("\n".join(page["native_text"] for page in pages))
    if resolved not in {"vi", "en"}:
        raise DocumentError("Ngôn ngữ không hợp lệ.")

    routing_log, parts = [], []
    for page in pages:
        native_characters = len(" ".join(page["native_text"].split()))
        if page["dark_pixel_ratio"] >= DARK_PIXEL_THRESHOLD and native_characters < NATIVE_TEXT_THRESHOLD:
            text, details = ocr_page(page["image"], resolved, engines)
            route = f"ocr_{resolved}"
        elif native_characters:
            text, route = page["native_text"], "native_text"
            details = {"detected_lines": None, "mean_paddle_confidence": None, "contact_fallback_lines": 0, "runtime_seconds": 0.0}
        else:
            text, route = "", "skip_near_blank"
            details = {"detected_lines": 0, "mean_paddle_confidence": None, "contact_fallback_lines": 0, "runtime_seconds": 0.0}
        routing_log.append({
            "page": page["page"],
            "native_characters": native_characters,
            "dark_pixel_ratio": round(page["dark_pixel_ratio"], 4),
            "route": route,
            **details,
        })
        redacted = redact_text(text, first_page=page["page"] == 1).strip()
        if redacted:
            parts.append(redacted)

    source_text = "\n\n".join(parts)
    if not source_text:
        raise DocumentError("Không trích được nội dung từ CV.")
    if len(source_text) > MAX_INPUT_CHARACTERS:
        raise DocumentError(f"CV có {len(source_text)} ký tự, vượt giới hạn {MAX_INPUT_CHARACTERS}; hệ thống không cắt ngầm.")
    return RoutedDocument(text=source_text, language=resolved, page_count=len(pages), routing_log=routing_log)
