from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_LANGUAGES = {"en", "ar", "fr"}


def detect_language(text: str) -> str:
    """Detect language of text. Returns ISO 639-1 code, default 'en'."""
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0  # deterministic
        lang = detect(text[:2000])
        if lang in SUPPORTED_LANGUAGES:
            logger.info("Detected language: %s", lang)
            return lang
    except ImportError:
        logger.warning("langdetect not installed — defaulting to English")
    except Exception as e:
        logger.warning("Language detection failed: %s", e)
    return "en"
