from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


def parse_docx(file_path: Path) -> str:
    from docx import Document

    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        raise ValueError(f"No text found in DOCX: {file_path.name}")
    logger.info("DOCX parsed successfully: %s", file_path.name)
    return "\n".join(paragraphs)
