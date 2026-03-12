"""Tests for language detection module."""
import pytest

from app.parsing.language_detect import detect_language


class TestLanguageDetection:
    def test_english_text(self):
        text = "I am a software engineer with 5 years of experience in Python and JavaScript."
        assert detect_language(text) == "en"

    def test_arabic_text(self):
        text = "أنا مهندس برمجيات ولدي خبرة خمس سنوات في تطوير البرمجيات والتطبيقات"
        result = detect_language(text)
        assert result == "ar"

    def test_french_text(self):
        text = "Je suis un ingénieur logiciel avec cinq ans d'expérience en développement."
        result = detect_language(text)
        assert result == "fr"

    def test_empty_text_defaults_to_english(self):
        assert detect_language("") == "en"

    def test_unsupported_language_defaults_to_english(self):
        # Chinese text should default to English since not in SUPPORTED_LANGUAGES
        text = "我是一名软件工程师，拥有五年的开发经验"
        result = detect_language(text)
        assert result == "en"
