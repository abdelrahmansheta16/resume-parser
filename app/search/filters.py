from __future__ import annotations

from app.api.schemas import ParsedResume, SearchFilters, SearchResult
from app.core.logging import get_logger

logger = get_logger(__name__)

EDUCATION_LEVELS = {
    "high school": 0,
    "associate": 1,
    "bachelor": 2,
    "master": 3,
    "doctorate": 4,
    "phd": 4,
}


def _get_education_level(resume: ParsedResume) -> int:
    """Get the highest education level from a resume."""
    best = -1
    for edu in resume.education:
        if edu.degree:
            degree_lower = edu.degree.lower()
            for level_name, level_val in EDUCATION_LEVELS.items():
                if level_name in degree_lower:
                    best = max(best, level_val)
    return best


def _matches_location(resume: ParsedResume, location_filter: str) -> bool:
    """Check if resume location matches filter (case-insensitive substring)."""
    if not resume.location:
        return False
    return location_filter.lower() in resume.location.lower()


def _matches_job_title(resume: ParsedResume, keywords: list[str]) -> bool:
    """Check if any experience job title contains any of the keywords."""
    for exp in resume.experience:
        if exp.job_title:
            title_lower = exp.job_title.lower()
            for kw in keywords:
                if kw.lower() in title_lower:
                    return True
    return False


def apply_filters(resumes: list[ParsedResume], filters: SearchFilters) -> SearchResult:
    """Apply search filters to a list of parsed resumes."""
    filtered = []

    for resume in resumes:
        # Skills ALL: candidate must have all specified skills
        if filters.skills:
            resume_skills_lower = {s.lower() for s in resume.skills}
            required = {s.lower() for s in filters.skills}
            if not required.issubset(resume_skills_lower):
                continue

        # Skills ANY: candidate must have at least one
        if filters.skills_any:
            resume_skills_lower = {s.lower() for s in resume.skills}
            any_skills = {s.lower() for s in filters.skills_any}
            if not resume_skills_lower & any_skills:
                continue

        # Min years experience
        if filters.min_years_experience is not None:
            if resume.total_years_experience < filters.min_years_experience:
                continue

        # Max years experience
        if filters.max_years_experience is not None:
            if resume.total_years_experience > filters.max_years_experience:
                continue

        # Education level
        if filters.education_level:
            required_level = EDUCATION_LEVELS.get(filters.education_level.lower(), -1)
            candidate_level = _get_education_level(resume)
            if candidate_level < required_level:
                continue

        # Location
        if filters.location:
            if not _matches_location(resume, filters.location):
                continue

        # Job title keywords
        if filters.job_title_keywords:
            if not _matches_job_title(resume, filters.job_title_keywords):
                continue

        filtered.append(resume)

    result = SearchResult(
        total=len(resumes),
        filtered=len(filtered),
        candidates=filtered,
    )
    logger.info("Search filters: %d/%d candidates match", len(filtered), len(resumes))
    return result
