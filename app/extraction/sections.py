from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)

SECTION_PATTERNS: dict[str, list[str]] = {
    "summary": [
        r"summary",
        r"professional\s+summary",
        r"profile",
        r"objective",
        r"about\s+me",
        r"career\s+objective",
        r"personal\s+statement",
    ],
    "skills": [
        r"skills",
        r"technical\s+skills",
        r"core\s+competencies",
        r"competencies",
        r"technologies",
        r"tools\s+(?:and|&)\s+technologies",
        r"tech\s+stack",
    ],
    "experience": [
        r"experience",
        r"work\s+experience",
        r"professional\s+experience",
        r"employment\s+history",
        r"work\s+history",
        r"career\s+history",
    ],
    "education": [
        r"education",
        r"academic\s+background",
        r"academic\s+qualifications",
        r"educational\s+background",
    ],
    "certifications": [
        r"certifications?",
        r"licenses?\s+(?:and|&)\s+certifications?",
        r"professional\s+certifications?",
        r"accreditations?",
    ],
    "projects": [
        r"projects",
        r"personal\s+projects",
        r"portfolio",
        r"notable\s+projects",
        r"side\s+projects",
    ],
    "achievements": [
        r"achievements?",
        r"awards?\s+(?:and|&)\s+achievements?",
        r"honors?\s+(?:and|&)\s+awards?",
        r"accomplishments?",
    ],
    "languages": [
        r"languages",
        r"language\s+proficiency",
    ],
}

# Build a single compiled regex that matches any section heading
_all_patterns: list[str] = []
_pattern_to_section: dict[str, str] = {}
for section, patterns in SECTION_PATTERNS.items():
    for p in patterns:
        _all_patterns.append(p)
        _pattern_to_section[p] = section

# Match heading on its own line (case-insensitive), possibly followed by colon
HEADING_RE = re.compile(
    r"^[\s]*(?:" + "|".join(_all_patterns) + r")[\s]*:?[\s]*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class ResumeSection:
    name: str
    content: str
    start_line: int
    end_line: int


def detect_sections(text: str) -> dict[str, ResumeSection]:
    """Detect resume sections and return a mapping of section name -> content."""
    lines = text.split("\n")
    section_starts: list[tuple[int, str]] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Check if line matches a heading pattern
        if HEADING_RE.match(line):
            # Determine which section this maps to
            for pattern, section_name in _pattern_to_section.items():
                if re.match(
                    r"^[\s]*" + pattern + r"[\s]*:?[\s]*$",
                    line,
                    re.IGNORECASE,
                ):
                    section_starts.append((i, section_name))
                    break

    sections: dict[str, ResumeSection] = {}

    # If no sections detected, return the whole text as "unknown"
    if not section_starts:
        logger.warning("No section headings detected")
        sections["full_text"] = ResumeSection(
            name="full_text",
            content=text,
            start_line=0,
            end_line=len(lines) - 1,
        )
        return sections

    # Content before first section is the header / contact area
    first_section_line = section_starts[0][0]
    if first_section_line > 0:
        header_content = "\n".join(lines[:first_section_line]).strip()
        if header_content:
            sections["header"] = ResumeSection(
                name="header",
                content=header_content,
                start_line=0,
                end_line=first_section_line - 1,
            )

    # Extract content for each detected section
    for idx, (start_line, section_name) in enumerate(section_starts):
        if idx + 1 < len(section_starts):
            end_line = section_starts[idx + 1][0] - 1
        else:
            end_line = len(lines) - 1

        # Content starts after the heading line
        content = "\n".join(lines[start_line + 1 : end_line + 1]).strip()

        # If section already exists, append content
        if section_name in sections:
            sections[section_name].content += "\n\n" + content
            sections[section_name].end_line = end_line
        else:
            sections[section_name] = ResumeSection(
                name=section_name,
                content=content,
                start_line=start_line,
                end_line=end_line,
            )

    logger.info("Detected %d sections: %s", len(sections), list(sections.keys()))
    return sections
