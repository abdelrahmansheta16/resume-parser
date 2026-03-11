from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from app.core.logging import get_logger
from app.parsing.docx_parser import parse_docx
from app.parsing.pdf_parser import parse_pdf
from app.parsing.text_cleaner import clean_text

logger = get_logger(__name__)


@dataclass
class ParsedDocument:
    filename: str
    file_type: str
    raw_text: str
    cleaned_text: str
    processing_time_ms: float
    success: bool
    error: str | None = None
    metadata: dict = field(default_factory=dict)


def detect_file_type(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    type_map = {".pdf": "pdf", ".docx": "docx", ".doc": "docx", ".txt": "txt"}
    if suffix not in type_map:
        raise ValueError(f"Unsupported file type: {suffix}")
    return type_map[suffix]


def load_and_parse(file_path: Path) -> ParsedDocument:
    """Load a file, extract text, and return a ParsedDocument."""
    start = time.time()
    file_path = Path(file_path)

    if not file_path.exists():
        return ParsedDocument(
            filename=file_path.name,
            file_type="unknown",
            raw_text="",
            cleaned_text="",
            processing_time_ms=0,
            success=False,
            error=f"File not found: {file_path}",
        )

    try:
        file_type = detect_file_type(file_path)
    except ValueError as e:
        return ParsedDocument(
            filename=file_path.name,
            file_type="unknown",
            raw_text="",
            cleaned_text="",
            processing_time_ms=(time.time() - start) * 1000,
            success=False,
            error=str(e),
        )

    try:
        parse_method = "direct"
        if file_type == "pdf":
            raw_text, parse_method = parse_pdf(file_path)
        elif file_type == "docx":
            raw_text = parse_docx(file_path)
            parse_method = "python-docx"
        else:
            raw_text = file_path.read_text(encoding="utf-8", errors="replace")
            parse_method = "text"

        cleaned = clean_text(raw_text)
        elapsed = (time.time() - start) * 1000

        logger.info(
            "Parsed %s (%s/%s) in %.1fms — %d chars",
            file_path.name,
            file_type,
            parse_method,
            elapsed,
            len(cleaned),
        )
        return ParsedDocument(
            filename=file_path.name,
            file_type=file_type,
            raw_text=raw_text,
            cleaned_text=cleaned,
            processing_time_ms=elapsed,
            success=True,
            metadata={
                "file_size_bytes": file_path.stat().st_size,
                "parse_method": parse_method,
            },
        )
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error("Failed to parse %s: %s", file_path.name, e)
        return ParsedDocument(
            filename=file_path.name,
            file_type=file_type,
            raw_text="",
            cleaned_text="",
            processing_time_ms=elapsed,
            success=False,
            error=str(e),
        )


def load_from_bytes(file_bytes: bytes, filename: str) -> ParsedDocument:
    """Load from uploaded bytes by writing to a temp file."""
    import tempfile

    suffix = Path(filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)
    try:
        result = load_and_parse(tmp_path)
        result.filename = filename
        return result
    finally:
        tmp_path.unlink(missing_ok=True)
