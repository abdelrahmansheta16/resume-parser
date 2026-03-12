"""Tests for OCR parsing module."""
from app.parsing.ocr_parser import is_garbage_text


class TestGarbageTextDetection:
    def test_empty_text_is_garbage(self):
        assert is_garbage_text("") is True
        assert is_garbage_text("   ") is True

    def test_normal_text_is_not_garbage(self):
        assert is_garbage_text("John Doe is a software engineer") is False

    def test_mostly_symbols_is_garbage(self):
        assert is_garbage_text("@#$%^&*()!@#$%^&*()!@#$%") is True

    def test_mixed_text_below_threshold(self):
        # 20% alpha = garbage
        assert is_garbage_text("##!!abc##!!##!!##!!##") is True

    def test_mixed_text_above_threshold(self):
        # Mostly alphabetic = not garbage
        assert is_garbage_text("Hello World 123") is False

    def test_numbers_only_is_garbage(self):
        assert is_garbage_text("123456789012345678901234567890") is True
