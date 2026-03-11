from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.parsing.ocr_parser import is_garbage_text

logger = get_logger(__name__)


def parse_pdf_pdfplumber(file_path: Path) -> str:
    import pdfplumber

    text_parts: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def parse_pdf_pymupdf(file_path: Path) -> str:
    import fitz

    text_parts: list[str] = []
    with fitz.open(file_path) as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def parse_pdf(file_path: Path) -> tuple:
    """Parse PDF with pdfplumber -> PyMuPDF -> OCR fallback.

    Returns (text, parse_method).
    """
    # Attempt 1: pdfplumber
    try:
        text = parse_pdf_pdfplumber(file_path)
        if text.strip() and not is_garbage_text(text):
            logger.info("PDF parsed with pdfplumber: %s", file_path.name)
            return text, "pdfplumber"
    except Exception as e:
        logger.warning("pdfplumber failed for %s: %s", file_path.name, e)

    # Attempt 2: PyMuPDF
    try:
        text = parse_pdf_pymupdf(file_path)
        if text.strip() and not is_garbage_text(text):
            logger.info("PDF parsed with PyMuPDF: %s", file_path.name)
            return text, "pymupdf"
    except Exception as e:
        logger.warning("PyMuPDF failed for %s: %s", file_path.name, e)

    # Attempt 3: OCR
    from app.models.config import config
    if config.ocr_enabled:
        try:
            from app.parsing.ocr_parser import parse_pdf_ocr
            text = parse_pdf_ocr(file_path)
            if text.strip():
                logger.info("PDF parsed with OCR: %s", file_path.name)
                return text, "ocr"
        except Exception as e:
            logger.warning("OCR failed for %s: %s", file_path.name, e)

    raise ValueError(f"Could not extract text from PDF: {file_path.name}")
