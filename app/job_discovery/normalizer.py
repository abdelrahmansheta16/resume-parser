from __future__ import annotations

import re

from app.api.schemas import JobPosting
from app.core.logging import get_logger
from app.matching.jd_parser import parse_job_description

logger = get_logger(__name__)


def _extract_skills_from_text(text: str) -> list[str]:
    """Extract skills from raw text using the skill taxonomy."""
    from app.extraction.skills import extract_skills_from_text
    return extract_skills_from_text(text)


def enrich_job_posting(job: JobPosting, use_llm: bool = False) -> JobPosting:
    """Enrich a job posting by parsing its description into structured fields.

    Uses the JD parser and skill taxonomy to extract skills, requirements, etc.
    By default uses the fast rule-based parser. Set use_llm=True for single-job
    deep parsing (not recommended for bulk enrichment).
    """
    if not job.description:
        return job

    text = job.description
    if job.raw_text and len(job.raw_text) > len(job.description):
        text = job.raw_text

    # Strip HTML tags from text
    clean_text = re.sub(r"<[^>]+>", " ", text)
    clean_text = re.sub(r"&\w+;", " ", clean_text)

    # For bulk normalization, force rule-based parsing (fast)
    # to avoid 100s of LLM API calls
    from app.models.config import config
    original_llm_setting = config.llm_parsing_enabled
    if not use_llm:
        config.llm_parsing_enabled = False
    try:
        parsed = parse_job_description(clean_text)
    finally:
        config.llm_parsing_enabled = original_llm_setting

    # Only fill in fields that aren't already populated
    if not job.required_skills and parsed.required_skills:
        job.required_skills = parsed.required_skills
    if not job.preferred_skills and parsed.preferred_skills:
        job.preferred_skills = parsed.preferred_skills
    if job.required_years_experience is None and parsed.required_years_experience is not None:
        job.required_years_experience = parsed.required_years_experience
    if not job.education_requirements and parsed.education_requirements:
        job.education_requirements = parsed.education_requirements

    # If JD parser didn't find skills, extract from raw text using taxonomy
    if not job.required_skills:
        extracted = _extract_skills_from_text(clean_text)
        if extracted:
            job.required_skills = extracted

    return job


def normalize_jobs(jobs: list[JobPosting]) -> list[JobPosting]:
    """Normalize and enrich a list of job postings."""
    normalized = []
    for job in jobs:
        # Skip jobs with empty titles
        if not job.title or not job.title.strip():
            continue
        # Enrich with parsed requirements
        enriched = enrich_job_posting(job)
        normalized.append(enriched)

    logger.info("Normalized %d jobs (from %d raw)", len(normalized), len(jobs))
    return normalized
