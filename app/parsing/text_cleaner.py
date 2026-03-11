import re

from app.core.logging import get_logger

logger = get_logger(__name__)


def clean_text(raw_text: str) -> str:
    """Clean extracted resume text while preserving section structure."""
    text = raw_text

    # Replace common broken characters from PDFs
    replacements = {
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2022": "-",
        "\uf0b7": "-",
        "\u00a0": " ",
        "\uf0a7": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Normalize whitespace within lines (preserve newlines)
    text = re.sub(r"[^\S\n]+", " ", text)

    # Collapse 3+ consecutive newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip trailing whitespace from each line
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # Strip leading/trailing whitespace from entire text
    text = text.strip()

    logger.debug("Text cleaned: %d -> %d chars", len(raw_text), len(text))
    return text
