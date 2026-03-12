from __future__ import annotations

from app.api.schemas import ConfidenceScore, ParsedResume
from app.core.logging import get_logger

logger = get_logger(__name__)

# Weights for overall confidence
WEIGHTS = {
    "name": 0.2,
    "skills": 0.3,
    "education": 0.25,
    "experience": 0.25,
}

REVIEW_THRESHOLD = 0.6


def compute_confidence(resume: ParsedResume) -> ConfidenceScore:
    """Compute field-level confidence scores for a parsed resume."""
    # Name confidence
    name_conf = 1.0 if resume.candidate_name else 0.0

    # Skills confidence: ratio of skills found to expected density
    text_len = len(resume.raw_text) if resume.raw_text else 500
    expected_skills = max(text_len / 200, 1)
    skills_conf = min(len(resume.skills) / expected_skills, 1.0)

    # Education confidence
    edu_conf = 0.0
    if resume.education:
        edu_scores = []
        for edu in resume.education:
            score = 0.0
            if edu.degree:
                score += 0.5
            if edu.institution:
                score += 0.3
            if edu.graduation_date:
                score += 0.2
            edu_scores.append(score)
        edu_conf = max(edu_scores) if edu_scores else 0.0

    # Experience confidence
    exp_conf = 0.0
    if resume.experience:
        exp_scores = []
        for exp in resume.experience:
            score = 0.0
            if exp.job_title:
                score += 0.35
            if exp.company:
                score += 0.25
            if exp.start_date:
                score += 0.2
            if exp.description:
                score += 0.2
            exp_scores.append(score)
        exp_conf = sum(exp_scores) / len(exp_scores) if exp_scores else 0.0

    overall = (
        WEIGHTS["name"] * name_conf
        + WEIGHTS["skills"] * skills_conf
        + WEIGHTS["education"] * edu_conf
        + WEIGHTS["experience"] * exp_conf
    )

    conf = ConfidenceScore(
        name_confidence=round(name_conf, 2),
        skills_confidence=round(skills_conf, 2),
        education_confidence=round(edu_conf, 2),
        experience_confidence=round(exp_conf, 2),
        overall=round(overall, 2),
    )
    logger.debug("Confidence for '%s': overall=%.2f", resume.candidate_name, overall)
    return conf


def needs_review(confidence: ConfidenceScore) -> bool:
    """Check if a resume should be flagged for human review."""
    return confidence.overall < REVIEW_THRESHOLD
