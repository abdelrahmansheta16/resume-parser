from __future__ import annotations

from rapidfuzz import fuzz

from app.api.schemas import JobPosting, ParsedResume
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_evidence_map(resume: ParsedResume, job: JobPosting) -> dict[str, list[str]]:
    """Map each job requirement to evidence from the resume.

    Returns a dict: {requirement_string -> [evidence_snippets_from_resume]}
    """
    evidence: dict[str, list[str]] = {}

    # Collect all resume evidence snippets
    snippets: list[str] = []
    if resume.summary:
        snippets.append(resume.summary)
    for exp in resume.experience:
        if exp.job_title and exp.company:
            snippets.append(f"{exp.job_title} at {exp.company}")
        for bullet in exp.description:
            snippets.append(bullet)
    for proj in resume.projects:
        snippets.append(proj)

    # Map required skills to evidence
    all_requirements = list(job.required_skills) + list(job.preferred_skills) + list(job.requirements)

    for req in all_requirements:
        req_lower = req.lower()
        matched_snippets = []
        for snippet in snippets:
            # Check if the requirement keyword appears in the snippet
            if req_lower in snippet.lower():
                matched_snippets.append(snippet)
            elif fuzz.partial_ratio(req_lower, snippet.lower()) > 75:
                matched_snippets.append(snippet)

        evidence[req] = matched_snippets[:3]  # top 3 evidence snippets per requirement

    logger.debug("Evidence map: %d requirements, %d with evidence",
                 len(evidence), sum(1 for v in evidence.values() if v))
    return evidence
