from __future__ import annotations

import re
from dataclasses import dataclass, field

from dateutil import parser as dateparser

from app.core.logging import get_logger

logger = get_logger(__name__)

DATE_RANGE_RE = re.compile(
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"[\s,]*\d{4}|"
    r"\d{1,2}/\d{4}|"
    r"\d{4})"
    r"\s*[-–—to]+\s*"
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"[\s,]*\d{4}|"
    r"\d{1,2}/\d{4}|"
    r"\d{4}|"
    r"[Pp]resent|[Cc]urrent|[Nn]ow)",
    re.IGNORECASE,
)

TITLE_INDICATORS = [
    "engineer",
    "developer",
    "architect",
    "manager",
    "analyst",
    "scientist",
    "designer",
    "consultant",
    "lead",
    "director",
    "coordinator",
    "administrator",
    "specialist",
    "intern",
    "associate",
    "senior",
    "junior",
    "principal",
    "staff",
    "head",
    "vp",
    "chief",
]


@dataclass
class ExperienceEntry:
    job_title: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration_months: int | None = None
    description: list[str] = field(default_factory=list)


def parse_date(date_str: str):
    """Try to parse a date string into year-month."""
    if not date_str:
        return None
    normalized = date_str.strip()
    if normalized.lower() in ("present", "current", "now"):
        from datetime import datetime
        return datetime.now()
    try:
        return dateparser.parse(normalized, fuzzy=True)
    except (ValueError, OverflowError):
        return None


def compute_duration_months(start_str: str | None, end_str: str | None) -> int | None:
    if not start_str:
        return None
    start = parse_date(start_str)
    end = parse_date(end_str)
    if start and end:
        diff = (end.year - start.year) * 12 + (end.month - start.month)
        return max(diff, 0)
    return None


def _looks_like_title(line: str) -> bool:
    """Heuristic: check if a line looks like a job title."""
    lower = line.lower().strip()
    return any(indicator in lower for indicator in TITLE_INDICATORS)


def _looks_like_company(line: str) -> bool:
    """Heuristic: check if a line looks like a company name."""
    indicators = [
        "inc", "llc", "ltd", "corp", "company", "co.", "group",
        "solutions", "technologies", "tech", "labs", "software",
        "analytics", "consulting", "services",
    ]
    lower = line.lower().strip()
    return any(indicator in lower for indicator in indicators)


def extract_experience(text: str) -> list[ExperienceEntry]:
    """Extract work experience entries from text."""
    entries: list[ExperienceEntry] = []
    lines = text.split("\n")

    current: ExperienceEntry | None = None
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Check for date range
        date_match = DATE_RANGE_RE.search(line)

        if date_match:
            # If we already have a current entry being built (title/company found
            # before the date line), just attach the date to it instead of creating
            # a new entry.
            if current and (current.job_title or current.company) and current.start_date is None:
                current.start_date = date_match.group(1).strip()
                current.end_date = date_match.group(2).strip()
                current.duration_months = compute_duration_months(
                    current.start_date, current.end_date
                )
            else:
                # This line starts a new experience entry
                if current:
                    entries.append(current)
                current = ExperienceEntry()
                current.start_date = date_match.group(1).strip()
                current.end_date = date_match.group(2).strip()
                current.duration_months = compute_duration_months(
                    current.start_date, current.end_date
                )

                # Remove date from line to parse title/company
                remaining = line[: date_match.start()].strip().rstrip("|,-–—")
                if not remaining and i > 0:
                    remaining = lines[i - 1].strip() if i > 0 else ""

                # Try to split title and company
                # Common patterns: "Title | Company" or "Title at Company" or "Title, Company"
                for sep in ["|", " at ", " - ", ", "]:
                    if sep in remaining:
                        parts = remaining.split(sep, 1)
                        current.job_title = parts[0].strip()
                        current.company = parts[1].strip()
                        break
                else:
                    if _looks_like_title(remaining):
                        current.job_title = remaining
                    elif _looks_like_company(remaining):
                        current.company = remaining
                    else:
                        current.job_title = remaining

        elif _looks_like_title(line) and not current:
            # Title line without date yet
            current = ExperienceEntry()
            current.job_title = line.rstrip("|,-–—").strip()

        elif _looks_like_title(line) and current and current.description:
            # New role detected (title without date)
            entries.append(current)
            current = ExperienceEntry()
            current.job_title = line.rstrip("|,-–—").strip()

        elif current:
            # Check if this is company info
            if current.company is None and not line.startswith("-") and _looks_like_company(line):
                current.company = line.rstrip(",.|").strip()
            elif current.job_title is None and _looks_like_title(line):
                current.job_title = line.rstrip("|,-–—").strip()
            elif line.startswith("-") or line.startswith("*"):
                current.description.append(line.lstrip("-* ").strip())
            else:
                # Could be continuation of description
                if current.description:
                    current.description.append(line)
                elif current.company is None:
                    current.company = line.rstrip(",.|").strip()

        i += 1

    if current:
        entries.append(current)

    logger.info("Extracted %d experience entries", len(entries))
    return entries


def estimate_total_years(entries: list[ExperienceEntry]) -> float:
    """Estimate total years of experience from entries."""
    total_months = 0
    for entry in entries:
        if entry.duration_months:
            total_months += entry.duration_months
        elif entry.start_date:
            # Try to estimate
            months = compute_duration_months(entry.start_date, entry.end_date)
            if months:
                total_months += months
    return round(total_months / 12, 1)
