from __future__ import annotations

import re
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?"
    r"(?:\(?\d{2,4}\)?[-.\s]?)?"
    r"\d{3,4}[-.\s]?\d{3,4}"
)
URL_RE = re.compile(r"https?://[^\s,;)\"']+")
LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[^\s,;)\"']+", re.I)
GITHUB_RE = re.compile(r"https?://(?:www\.)?github\.com/[^\s,;)\"']+", re.I)


@dataclass
class ContactInfo:
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    urls: list[str] = field(default_factory=list)


def extract_contact_info(text: str) -> ContactInfo:
    info = ContactInfo()

    info.emails = list(set(EMAIL_RE.findall(text)))

    raw_phones = PHONE_RE.findall(text)
    # Filter out numbers that are too short or look like years
    phones = []
    for p in raw_phones:
        digits = re.sub(r"\D", "", p)
        if 7 <= len(digits) <= 15:
            phones.append(p.strip())
    info.phones = list(set(phones))

    urls = URL_RE.findall(text)
    info.urls = list(set(urls))

    linkedin_matches = LINKEDIN_RE.findall(text)
    if linkedin_matches:
        info.linkedin = linkedin_matches[0].rstrip("/")

    github_matches = GITHUB_RE.findall(text)
    if github_matches:
        info.github = github_matches[0].rstrip("/")

    # Portfolio: any URL that isn't LinkedIn or GitHub
    for url in urls:
        if "linkedin.com" not in url.lower() and "github.com" not in url.lower():
            info.portfolio = url.rstrip("/")
            break

    return info
