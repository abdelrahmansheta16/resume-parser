from __future__ import annotations

import re

from app.api.schemas import ParsedResume
from app.core.logging import get_logger

logger = get_logger(__name__)


def normalize_name(name: str | None) -> str:
    """Normalize a name for comparison: lowercase, strip titles, collapse whitespace."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r"\b(mr|mrs|ms|dr|prof)\.?\s*", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def normalize_email(email: str | None) -> str:
    """Normalize email for comparison."""
    if not email:
        return ""
    return email.lower().strip()


def normalize_phone(phone: str | None) -> str:
    """Strip non-digit characters from phone for comparison."""
    if not phone:
        return ""
    return re.sub(r"\D", "", phone)


def get_skill_set(resume: ParsedResume) -> set[str]:
    """Get normalized skill set from a resume."""
    return {s.lower() for s in resume.skills}


def compute_fingerprint(resume: ParsedResume) -> dict[str, str | set[str]]:
    """Compute a fingerprint dict for a resume for dedup matching."""
    return {
        "name": normalize_name(resume.candidate_name),
        "email": normalize_email(resume.email),
        "phone": normalize_phone(resume.phone),
        "skills": get_skill_set(resume),
    }
