from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


def generate_pdf_from_docx(docx_path: Path) -> Path:
    """Convert a DOCX file to PDF.

    Tries docx2pdf first (uses LibreOffice/Word), falls back to reportlab.
    Returns the path to the generated PDF.
    """
    pdf_path = docx_path.with_suffix(".pdf")

    # Attempt 1: docx2pdf (high-fidelity, requires LibreOffice or Word)
    try:
        from docx2pdf import convert

        convert(str(docx_path), str(pdf_path))
        if pdf_path.exists():
            logger.info("Generated PDF via docx2pdf: %s", pdf_path)
            return pdf_path
    except (Exception, SystemExit) as e:
        logger.debug("docx2pdf unavailable or failed: %s", e)

    # Attempt 2: reportlab fallback — read DOCX paragraphs and render to PDF
    try:
        return _reportlab_fallback(docx_path, pdf_path)
    except Exception as e:
        logger.warning("reportlab fallback failed: %s", e)
        raise RuntimeError(f"Could not generate PDF from {docx_path}: {e}") from e


def _reportlab_fallback(docx_path: Path, pdf_path: Path) -> Path:
    """Render DOCX content to PDF using reportlab."""
    from docx import Document
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    doc = Document(str(docx_path))
    styles = getSampleStyleSheet()

    # Custom styles matching ATS DOCX format
    heading0_style = ParagraphStyle(
        "Heading0",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        alignment=1,  # center
        spaceAfter=6,
    )
    heading1_style = ParagraphStyle(
        "Heading1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=14,
    )
    contact_style = ParagraphStyle(
        "Contact",
        parent=body_style,
        fontSize=10,
        alignment=1,  # center
        spaceAfter=8,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=body_style,
        leftIndent=18,
        bulletIndent=6,
        bulletFontName="Helvetica",
        bulletFontSize=11,
    )
    bold_style = ParagraphStyle(
        "Bold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    italic_style = ParagraphStyle(
        "Italic",
        parent=body_style,
        fontName="Helvetica-Oblique",
        fontSize=10,
    )

    pdf_doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
    )

    story = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            story.append(Spacer(1, 4))
            continue

        # Escape XML special chars for reportlab
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        style_name = para.style.name if para.style else ""

        if "Heading" in style_name:
            level = 0
            if style_name == "Heading 1":
                level = 1
            story.append(Paragraph(text, heading0_style if level == 0 else heading1_style))
        elif "List Bullet" in style_name:
            story.append(Paragraph(f"\u2022 {text}", bullet_style))
        elif para.runs and para.runs[0].bold:
            story.append(Paragraph(text, bold_style))
        elif para.runs and para.runs[0].italic:
            story.append(Paragraph(text, italic_style))
        elif para.alignment and para.alignment == 1:  # center
            story.append(Paragraph(text, contact_style))
        else:
            story.append(Paragraph(text, body_style))

    pdf_doc.build(story)
    logger.info("Generated PDF via reportlab: %s", pdf_path)
    return pdf_path
