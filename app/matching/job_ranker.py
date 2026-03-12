from __future__ import annotations

from collections import Counter

from app.api.schemas import JobMatchResult, JobPosting, ParsedJobDescription, ParsedResume
from app.core.logging import get_logger
from app.matching.scoring import (
    compute_education_match,
    compute_experience_match,
    compute_skill_match,
    compute_title_match,
    generate_explanation,
    get_recommendation_label,
)
from app.matching.semantic_match import compute_semantic_similarity
from app.models.config import config

logger = get_logger(__name__)


def job_to_jd(job: JobPosting) -> ParsedJobDescription:
    """Convert a JobPosting into a ParsedJobDescription for scoring reuse."""
    return ParsedJobDescription(
        title=job.title,
        required_skills=job.required_skills,
        preferred_skills=job.preferred_skills,
        required_years_experience=job.required_years_experience,
        education_requirements=job.education_requirements,
        raw_text=job.description or job.raw_text or "",
    )


def score_job_for_candidate(candidate: ParsedResume, job: JobPosting) -> JobMatchResult:
    """Score a single job posting against a candidate's resume."""
    jd = job_to_jd(job)
    weights = config.matching_weights

    skill_score, matched, missing = compute_skill_match(candidate, jd)
    exp_score = compute_experience_match(candidate, jd)
    title_score = compute_title_match(candidate, jd)
    edu_score = compute_education_match(candidate, jd)

    # Semantic similarity
    candidate_text = candidate.summary or candidate.raw_text or ""
    job_text = jd.raw_text or ""
    semantic_score = compute_semantic_similarity(candidate_text[:500], job_text[:500])

    total = (
        skill_score * weights.skills
        + semantic_score * weights.semantic_similarity
        + exp_score * weights.experience
        + title_score * weights.title_relevance
        + edu_score * weights.education
    )

    from app.api.schemas import MatchResult
    match = MatchResult(
        candidate_name=candidate.candidate_name,
        match_score=round(total, 1),
        matched_skills=matched,
        missing_skills=missing,
        experience_match_score=round(exp_score, 1),
        education_match_score=round(edu_score, 1),
        title_match_score=round(title_score, 1),
        semantic_similarity_score=round(semantic_score, 1),
    )
    explanation = generate_explanation(match, candidate, jd)

    return JobMatchResult(
        job=job,
        match_score=round(total, 1),
        recommendation=get_recommendation_label(total),
        skill_score=round(skill_score, 1),
        semantic_score=round(semantic_score, 1),
        experience_score=round(exp_score, 1),
        title_score=round(title_score, 1),
        education_score=round(edu_score, 1),
        matched_skills=matched,
        missing_skills=missing,
        explanation=explanation,
    )


def rank_jobs_for_candidate(
    candidate: ParsedResume,
    jobs: list[JobPosting],
    top_n: int = 50,
    max_per_company: int = 3,
) -> list[JobMatchResult]:
    """Rank job postings for a candidate with diversity and quality constraints.

    Returns the top_n jobs sorted by match score, with:
    - Max `max_per_company` jobs per company
    - Quality filter: skip jobs without apply_url or empty description
    """
    # Score all jobs
    scored: list[JobMatchResult] = []
    for job in jobs:
        # Quality filter
        if not job.description and not job.raw_text:
            continue
        result = score_job_for_candidate(candidate, job)
        scored.append(result)

    # Sort by score descending
    scored.sort(key=lambda x: x.match_score, reverse=True)

    # Apply diversity constraint
    company_counts: Counter = Counter()
    diverse: list[JobMatchResult] = []

    for result in scored:
        company = result.job.company.lower().strip() if result.job.company else "unknown"
        if company_counts[company] >= max_per_company:
            continue
        company_counts[company] += 1
        diverse.append(result)
        if len(diverse) >= top_n:
            break

    logger.info(
        "Ranked %d jobs for '%s': top score=%.1f, bottom score=%.1f",
        len(diverse),
        candidate.candidate_name,
        diverse[0].match_score if diverse else 0,
        diverse[-1].match_score if diverse else 0,
    )
    return diverse
