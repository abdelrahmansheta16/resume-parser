from __future__ import annotations

from app.api.schemas import ParsedResume
from app.core.logging import get_logger

logger = get_logger(__name__)


def anonymize_resume(resume: ParsedResume, candidate_id: int = 1) -> ParsedResume:
    """Strip identifying information from a parsed resume.

    Replaces name, contact info, and institution names with placeholders.
    """
    anon = resume.model_copy(deep=True)

    # Replace name with anonymous label
    anon.candidate_name = f"Candidate {chr(64 + min(candidate_id, 26))}"

    # Strip contact info
    anon.email = None
    anon.phone = None
    anon.linkedin = None
    anon.github = None
    anon.portfolio = None
    anon.location = None

    # Anonymize education institutions
    for edu in anon.education:
        edu.institution = "[University]"

    # Mark as anonymized
    anon.anonymized = True

    logger.info("Anonymized resume for candidate_id=%d", candidate_id)
    return anon
