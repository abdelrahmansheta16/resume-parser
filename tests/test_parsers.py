import tempfile
from pathlib import Path

from app.parsing.file_loader import load_and_parse, load_from_bytes, detect_file_type
from app.parsing.text_cleaner import clean_text


def test_detect_file_type():
    assert detect_file_type(Path("resume.pdf")) == "pdf"
    assert detect_file_type(Path("resume.docx")) == "docx"
    assert detect_file_type(Path("resume.txt")) == "txt"


def test_detect_file_type_unsupported():
    import pytest
    with pytest.raises(ValueError):
        detect_file_type(Path("resume.xyz"))


def test_clean_text_basic():
    raw = "Hello   world\n\n\n\nNew section\n  trailing  "
    cleaned = clean_text(raw)
    assert "   " not in cleaned
    assert "\n\n\n" not in cleaned
    assert cleaned.endswith("trailing")


def test_clean_text_unicode():
    raw = "He\u2019s a developer \u2013 good"
    cleaned = clean_text(raw)
    assert "'" in cleaned
    assert "-" in cleaned


def test_load_txt_file(sample_resume_text, tmp_path):
    """Test loading a .txt resume file."""
    txt_file = tmp_path / "resume.txt"
    txt_file.write_text(sample_resume_text)
    doc = load_and_parse(txt_file)
    assert doc.success
    assert doc.file_type == "txt"
    assert len(doc.cleaned_text) > 100
    assert doc.processing_time_ms >= 0


def test_load_nonexistent_file():
    doc = load_and_parse(Path("/nonexistent/file.pdf"))
    assert not doc.success
    assert "not found" in doc.error.lower()


def test_load_from_bytes(sample_resume_text):
    content = sample_resume_text.encode("utf-8")
    doc = load_from_bytes(content, "test_resume.txt")
    assert doc.success
    assert doc.filename == "test_resume.txt"
    assert len(doc.cleaned_text) > 100
