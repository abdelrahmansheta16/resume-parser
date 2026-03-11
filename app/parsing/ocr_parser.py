from __future__ import annotations

import io
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


def is_garbage_text(text: str) -> bool:
    """Check if extracted text is mostly non-alphabetic (likely garbage from image PDF)."""
    if not text.strip():
        return True
    alpha_count = sum(c.isalpha() for c in text)
    ratio = alpha_count / max(len(text), 1)
    return ratio < 0.3


def parse_pdf_ocr(file_path: Path) -> str:
    """Extract text from image-based PDF using Tesseract OCR."""
    import fitz
    from PIL import Image
    import pytesseract

    text_parts: list[str] = []
    with fitz.open(file_path) as doc:
        for page_num, page in enumerate(doc):
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            page_text = pytesseract.image_to_string(img)
            if page_text.strip():
                text_parts.append(page_text)
            logger.debug("OCR page %d: %d chars", page_num + 1, len(page_text))

    result = "\n".join(text_parts)
    logger.info("OCR extracted %d chars from %s", len(result), file_path.name)
    return result
