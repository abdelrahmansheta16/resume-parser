from __future__ import annotations

import re

from app.core.logging import get_logger

logger = get_logger(__name__)

# Location patterns
LOCATION_RE = re.compile(
    r"(?:(?:Location|Address|Based in)[:\s]+)?"
    r"([A-Z][a-zA-Z\s]+,\s*(?:[A-Z]{2}|[A-Z][a-zA-Z\s]+))",
)


def extract_name_from_header(header_text: str) -> str | None:
    """Extract candidate name from the header section.

    Heuristic: the first non-empty line in the header that is not an email,
    phone, URL, or known label is likely the name.
    """
    lines = header_text.strip().split("\n")
    skip_patterns = [
        re.compile(r"@"),  # email
        re.compile(r"\d{3,}"),  # phone-like
        re.compile(r"https?://"),  # url
        re.compile(r"^(email|phone|location|address|linkedin|github|portfolio)", re.I),
    ]

    for line in lines:
        line = line.strip()
        if not line or len(line) < 2:
            continue
        # Skip lines matching skip patterns
        if any(p.search(line) for p in skip_patterns):
            continue
        # Name should be mostly alphabetic with spaces
        alpha_ratio = sum(c.isalpha() or c.isspace() for c in line) / max(
            len(line), 1
        )
        if alpha_ratio > 0.8 and len(line.split()) <= 5:
            # Strip common prefixes
            name = re.sub(r"^(name[:\s]+)", "", line, flags=re.I).strip()
            if name:
                return name
    return None


def extract_name_with_spacy(text: str) -> str | None:
    """Use spaCy NER to find PERSON entities."""
    try:
        import spacy

        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model not found — skipping NER name extraction")
            return None

        # Only process the first ~500 chars for name detection
        doc = nlp(text[:500])
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                return ent.text
    except ImportError:
        logger.warning("spaCy not installed — skipping NER name extraction")
    return None


def extract_location(text: str) -> str | None:
    """Extract location from text."""
    match = LOCATION_RE.search(text)
    if match:
        return match.group(1).strip()

    # Fallback: look for common city, state patterns in first few lines
    for line in text.split("\n")[:10]:
        # Match "City, ST" or "City, State"
        m = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*[A-Z]{2})\b", line)
        if m:
            return m.group(1)
    return None
