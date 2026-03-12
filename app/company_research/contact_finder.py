from __future__ import annotations

import re
from urllib.parse import urlparse

from app.core.logging import get_logger

logger = get_logger(__name__)

# Only extract public recruiting-related contacts
_RECRUITING_EMAIL_PATTERNS = [
    r"careers@[\w.-]+\.\w+",
    r"jobs@[\w.-]+\.\w+",
    r"hr@[\w.-]+\.\w+",
    r"recruiting@[\w.-]+\.\w+",
    r"recruitment@[\w.-]+\.\w+",
    r"talent@[\w.-]+\.\w+",
    r"hiring@[\w.-]+\.\w+",
    r"apply@[\w.-]+\.\w+",
]


def extract_public_contacts(
    text: str,
    company_domain: str | None = None,
) -> list[dict[str, str]]:
    """Extract only public recruiting contacts from text.

    This function ONLY extracts:
    - Public recruiting email addresses (careers@, jobs@, hr@, etc.)
    - Web application form URLs
    - Listed recruiter names on job postings

    Does NOT scrape:
    - Employee directories
    - Social network profiles
    - Personal email addresses
    """
    contacts: list[dict[str, str]] = []
    seen: set[str] = set()

    # 1. Public recruiting emails
    for pattern in _RECRUITING_EMAIL_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            email = match.group(0).lower()
            if email not in seen:
                contacts.append({
                    "role": "recruiting",
                    "channel_type": "email",
                    "value": email,
                })
                seen.add(email)

    # 2. Application form URLs
    url_pattern = r'https?://[^\s<>"\']+(?:apply|careers|jobs|hiring)[^\s<>"\']*'
    for match in re.finditer(url_pattern, text, re.IGNORECASE):
        url = match.group(0).rstrip(".,;)")
        if url not in seen:
            contacts.append({
                "role": "application_form",
                "channel_type": "url",
                "value": url,
            })
            seen.add(url)

    # 3. Named recruiters mentioned in job posting text
    recruiter_patterns = [
        r"(?:contact|reach out to|email|send.*to)\s+([A-Z][a-z]+ [A-Z][a-z]+)",
        r"(?:recruiter|hiring manager|talent acquisition):\s*([A-Z][a-z]+ [A-Z][a-z]+)",
    ]
    for pattern in recruiter_patterns:
        for match in re.finditer(pattern, text):
            name = match.group(1)
            if name not in seen and len(name) > 3:
                contacts.append({
                    "role": "recruiter",
                    "channel_type": "name",
                    "value": name,
                })
                seen.add(name)

    logger.debug("Found %d public contacts", len(contacts))
    return contacts
