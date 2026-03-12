from __future__ import annotations

import re
from pathlib import Path

from app.api.schemas import JobPosting, ParsedResume
from app.core.logging import get_logger

logger = get_logger(__name__)


def compute_keyword_coverage(resume_text: str, job: JobPosting) -> float:
    """Compute what fraction of JD keywords appear in the resume text."""
    jd_text = job.description or job.raw_text or ""
    if not jd_text or not resume_text:
        return 0.0

    # Extract significant words from JD
    stop_words = {
        "the", "and", "for", "with", "you", "your", "our", "are", "will",
        "have", "has", "this", "that", "from", "was", "were", "been", "being",
        "which", "who", "what", "when", "where", "how", "not", "but", "all",
        "can", "could", "would", "should", "may", "might", "shall", "must",
        "about", "also", "into", "more", "than", "other", "able", "work",
    }
    jd_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", jd_text.lower())) - stop_words
    resume_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", resume_text.lower())) - stop_words

    if not jd_words:
        return 0.0

    coverage = len(jd_words & resume_words) / len(jd_words)
    return round(min(1.0, coverage), 4)


def ats_self_check(docx_path: Path, original_resume: ParsedResume, job: JobPosting) -> dict:
    """Re-parse a generated DOCX through the parser and check field survival.

    Returns a dict with:
    - ats_score: 0-100
    - keyword_coverage: 0.0-1.0
    - field_checks: dict of field -> pass/fail
    """
    from app.parsing.file_loader import load_and_parse
    from app.extraction.resume_structurer import structure_resume

    doc = load_and_parse(docx_path)
    if not doc.success:
        logger.warning("ATS self-check: failed to re-parse %s", docx_path)
        return {"ats_score": 0, "keyword_coverage": 0, "field_checks": {}}

    reparsed = structure_resume(doc.cleaned_text)

    # Field survival checks
    checks = {}
    checks["name_survived"] = bool(reparsed.candidate_name)
    checks["email_survived"] = bool(reparsed.email) if original_resume.email else True
    checks["skills_survived"] = len(reparsed.skills) >= max(1, len(original_resume.skills) // 2)
    checks["experience_survived"] = len(reparsed.experience) >= 1 if original_resume.experience else True
    checks["education_survived"] = len(reparsed.education) >= 1 if original_resume.education else True

    pass_count = sum(1 for v in checks.values() if v)
    field_score = (pass_count / len(checks)) * 100 if checks else 0

    # Keyword coverage
    coverage = compute_keyword_coverage(doc.cleaned_text, job)

    # Combined ATS score
    ats_score = round(field_score * 0.6 + coverage * 100 * 0.4, 1)

    logger.info("ATS self-check: score=%.1f, coverage=%.1f%%, fields=%d/%d",
                ats_score, coverage * 100, pass_count, len(checks))

    return {
        "ats_score": ats_score,
        "keyword_coverage": coverage,
        "field_checks": checks,
    }
