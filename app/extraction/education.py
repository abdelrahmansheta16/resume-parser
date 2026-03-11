from __future__ import annotations

import csv
import re
from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.paths import TAXONOMIES_DIR

logger = get_logger(__name__)

GPA_RE = re.compile(r"(?:GPA|gpa)[:\s]*(\d\.\d+)(?:/(\d\.\d+))?")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@dataclass
class EducationEntry:
    degree: str | None = None
    field_of_study: str | None = None
    institution: str | None = None
    graduation_date: str | None = None
    gpa: str | None = None


def load_degree_taxonomy(path=None) -> dict[str, tuple[str, str]]:
    """Load degree aliases -> (canonical, level) mapping."""
    path = path or TAXONOMIES_DIR / "degrees.csv"
    mapping: dict[str, tuple[str, str]] = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            canonical = row["canonical"].strip()
            level = row["level"].strip()
            aliases = [a.strip().lower() for a in row["aliases"].split(",")]
            for alias in aliases:
                mapping[alias] = (canonical, level)
            mapping[canonical.lower()] = (canonical, level)
    return mapping


DEGREE_PATTERNS = [
    re.compile(
        r"((?:bachelor|master|doctor|associate|phd|ph\.d|m\.s|b\.s|b\.a|m\.a|mba|m\.b\.a|b\.sc|m\.sc|b\.e|m\.e|b\.tech|m\.tech)"
        r"[a-z.\s]*(?:of\s+[a-z]+)?(?:\s+in\s+[a-zA-Z\s&,]+)?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"((?:BS|BA|MS|MA|MBA|PhD|BE|ME|BTech|MTech|BBA|BSc|MSc|JD|MD)"
        r"(?:\s+in\s+[a-zA-Z\s&,]+)?)",
    ),
]


def extract_education(text: str) -> list[EducationEntry]:
    """Extract education entries from text."""
    degree_taxonomy = load_degree_taxonomy()
    entries: list[EducationEntry] = []
    lines = text.split("\n")

    current_entry: EducationEntry | None = None
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Check for degree pattern
        degree_found = False
        for pattern in DEGREE_PATTERNS:
            m = pattern.search(line)
            if m:
                if current_entry:
                    entries.append(current_entry)
                current_entry = EducationEntry()
                degree_text = m.group(1).strip()

                # Try to split degree and field
                if " in " in degree_text.lower():
                    parts = re.split(r"\s+in\s+", degree_text, maxsplit=1, flags=re.I)
                    raw_degree = parts[0].strip()
                    current_entry.field_of_study = parts[1].strip().rstrip(",.")
                else:
                    raw_degree = degree_text

                # Normalize degree using taxonomy
                lookup = raw_degree.lower().strip(".")
                if lookup in degree_taxonomy:
                    current_entry.degree = degree_taxonomy[lookup][0]
                else:
                    current_entry.degree = raw_degree

                # Check for institution on same or next line
                remaining = line[m.end() :].strip()
                if not remaining and i + 1 < len(lines):
                    remaining = lines[i + 1].strip()
                    i += 1
                if remaining:
                    current_entry.institution = remaining.rstrip(",.")

                degree_found = True
                break

        if not degree_found and current_entry:
            # Check for graduation date
            year_match = YEAR_RE.search(line)
            gpa_match = GPA_RE.search(line)

            if gpa_match:
                gpa_val = gpa_match.group(1)
                if gpa_match.group(2):
                    gpa_val += "/" + gpa_match.group(2)
                current_entry.gpa = gpa_val

            if year_match:
                current_entry.graduation_date = year_match.group()

            # If line looks like an institution (contains "University", "College", etc.)
            if current_entry.institution is None and re.search(
                r"(university|college|institute|school|academy)", line, re.I
            ):
                current_entry.institution = line.rstrip(",.")

        i += 1

    if current_entry:
        entries.append(current_entry)

    logger.info("Extracted %d education entries", len(entries))
    return entries
