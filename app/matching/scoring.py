from __future__ import annotations

import csv
import re

from rapidfuzz import fuzz

from app.api.schemas import MatchResult, ParsedJobDescription, ParsedResume
from app.core.logging import get_logger
from app.core.paths import TAXONOMIES_DIR
from app.matching.semantic_match import compute_semantic_similarity
from app.models.config import config

logger = get_logger(__name__)


def _load_title_taxonomy() -> dict[str, list[str]]:
    """Load job title aliases for matching."""
    path = TAXONOMIES_DIR / "job_titles.csv"
    mapping: dict[str, list[str]] = {}
    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                canonical = row["canonical"].strip().lower()
                aliases = [a.strip().lower() for a in row["aliases"].split(",")]
                mapping[canonical] = aliases
    except FileNotFoundError:
        pass
    return mapping


def compute_skill_match(resume: ParsedResume, jd: ParsedJobDescription) -> tuple[float, list[str], list[str]]:
    """Compute skill overlap score, matched skills, and missing skills."""
    # Use required_skills; fall back to preferred, then tools_and_technologies
    jd_skills = jd.required_skills
    if not jd_skills:
        jd_skills = jd.preferred_skills
    if not jd_skills:
        jd_skills = jd.tools_and_technologies

    resume_skills_lower = {s.lower() for s in resume.skills}
    target_lower = {s.lower(): s for s in jd_skills}

    matched = []
    missing = []

    for skill_lower, skill_original in target_lower.items():
        if skill_lower in resume_skills_lower:
            matched.append(skill_original)
        else:
            # Try fuzzy matching
            best_score = 0
            for rs in resume_skills_lower:
                score = fuzz.ratio(skill_lower, rs)
                if score > best_score:
                    best_score = score
            if best_score >= 80:
                matched.append(skill_original)
            else:
                missing.append(skill_original)

    total = len(target_lower)
    if total == 0:
        return 100.0, matched, missing

    score = (len(matched) / total) * 100
    return score, matched, missing


def compute_experience_match(resume: ParsedResume, jd: ParsedJobDescription) -> float:
    """Score based on years of experience alignment."""
    if jd.required_years_experience is None:
        return 75.0  # default if JD doesn't specify

    required = jd.required_years_experience
    actual = resume.total_years_experience

    if actual >= required:
        return 100.0
    elif actual >= required * 0.7:
        return 70.0 + (actual / required) * 30
    elif actual > 0:
        return (actual / required) * 70
    return 20.0  # minimum if there's any experience data


def compute_title_match(resume: ParsedResume, jd: ParsedJobDescription) -> float:
    """Score based on how well the candidate's most recent title matches the JD title."""
    if not jd.title:
        return 50.0

    jd_title_lower = jd.title.lower()
    title_taxonomy = _load_title_taxonomy()

    # Get candidate's most recent job title
    candidate_title = None
    if resume.experience:
        candidate_title = resume.experience[0].job_title
    if not candidate_title:
        return 30.0

    candidate_lower = candidate_title.lower()

    # Direct fuzzy match
    direct_score = fuzz.token_set_ratio(candidate_lower, jd_title_lower)
    if direct_score >= 80:
        return min(100.0, direct_score)

    # Taxonomy-based match
    for canonical, aliases in title_taxonomy.items():
        jd_match = canonical in jd_title_lower or any(a in jd_title_lower for a in aliases)
        cand_match = canonical in candidate_lower or any(a in candidate_lower for a in aliases)
        if jd_match and cand_match:
            return 85.0

    return max(30.0, direct_score)


def compute_education_match(resume: ParsedResume, jd: ParsedJobDescription) -> float:
    """Score based on education requirements."""
    if not jd.education_requirements:
        return 75.0

    level_order = {"high_school": 1, "associate": 2, "bachelor": 3, "master": 4, "doctorate": 5}

    # Determine required level from JD
    required_level = 3  # default bachelor
    jd_edu_text = " ".join(jd.education_requirements).lower()
    if "master" in jd_edu_text or "ms " in jd_edu_text or "m.s" in jd_edu_text:
        required_level = 4
    elif "phd" in jd_edu_text or "doctorate" in jd_edu_text:
        required_level = 5
    elif "bachelor" in jd_edu_text or "bs " in jd_edu_text or "b.s" in jd_edu_text:
        required_level = 3

    if not resume.education:
        return 30.0

    # Determine candidate's highest education level
    candidate_level = 0
    for edu in resume.education:
        if edu.degree:
            deg_lower = edu.degree.lower()
            if "doctor" in deg_lower or "phd" in deg_lower:
                candidate_level = max(candidate_level, 5)
            elif "master" in deg_lower:
                candidate_level = max(candidate_level, 4)
            elif "bachelor" in deg_lower:
                candidate_level = max(candidate_level, 3)
            elif "associate" in deg_lower:
                candidate_level = max(candidate_level, 2)
            else:
                candidate_level = max(candidate_level, 3)  # assume bachelor

    if candidate_level >= required_level:
        return 100.0
    elif candidate_level == required_level - 1:
        return 70.0
    return 40.0


def compute_keyword_relevance(resume: ParsedResume, jd: ParsedJobDescription) -> float:
    """Compute keyword overlap between resume text and JD."""
    if not resume.raw_text or not jd.raw_text:
        return 50.0

    # Extract significant words from JD
    jd_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", jd.raw_text.lower()))
    resume_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", resume.raw_text.lower()))

    # Remove common stop words
    stop_words = {
        "the", "and", "for", "with", "you", "your", "our", "are", "will",
        "have", "has", "this", "that", "from", "was", "were", "been", "being",
        "which", "who", "what", "when", "where", "how", "not", "but", "all",
        "can", "could", "would", "should", "may", "might", "shall", "must",
        "about", "also", "into", "more", "than", "other",
    }
    jd_words -= stop_words
    resume_words -= stop_words

    if not jd_words:
        return 50.0

    overlap = jd_words & resume_words
    score = (len(overlap) / len(jd_words)) * 100
    return min(100.0, score)


def generate_explanation(
    match: MatchResult,
    resume: ParsedResume,
    jd: ParsedJobDescription,
) -> list[str]:
    """Generate human-readable explanations for match scores."""
    explanations = []

    # Skill match explanation
    if match.matched_skills:
        explanations.append(
            f"Strong alignment in: {', '.join(match.matched_skills[:5])}"
        )
    if match.missing_skills:
        explanations.append(
            f"Missing required skills: {', '.join(match.missing_skills[:5])}"
        )

    # Experience explanation
    if jd.required_years_experience:
        if resume.total_years_experience >= jd.required_years_experience:
            explanations.append(
                f"Meets experience requirement ({resume.total_years_experience:.1f} years "
                f"vs {jd.required_years_experience:.0f}+ required)"
            )
        else:
            gap = jd.required_years_experience - resume.total_years_experience
            explanations.append(
                f"Experience gap of ~{gap:.1f} years "
                f"({resume.total_years_experience:.1f} vs {jd.required_years_experience:.0f}+ required)"
            )

    # Title match
    if resume.experience and resume.experience[0].job_title:
        explanations.append(
            f"Most recent role: {resume.experience[0].job_title}"
        )

    # Education
    if resume.education:
        edu = resume.education[0]
        edu_str = edu.degree or "Degree"
        if edu.field_of_study:
            edu_str += f" in {edu.field_of_study}"
        explanations.append(f"Education: {edu_str}")

    return explanations


def get_recommendation_label(score: float) -> str:
    if score >= 85:
        return "Strong Match"
    elif score >= 70:
        return "Good Match"
    elif score >= 55:
        return "Moderate Match"
    elif score >= 40:
        return "Weak Match"
    return "Poor Match"


def score_candidate(resume: ParsedResume, jd: ParsedJobDescription) -> MatchResult:
    """Score a single candidate against a job description."""
    weights = config.matching_weights

    skill_score, matched, missing = compute_skill_match(resume, jd)
    exp_score = compute_experience_match(resume, jd)
    title_score = compute_title_match(resume, jd)
    edu_score = compute_education_match(resume, jd)
    keyword_score = compute_keyword_relevance(resume, jd)

    # Semantic similarity
    resume_text = resume.summary or resume.raw_text or ""
    jd_text = jd.raw_text or ""
    semantic_score = compute_semantic_similarity(resume_text[:500], jd_text[:500])

    # Weighted total
    total = (
        skill_score * weights.skills
        + semantic_score * weights.semantic_similarity
        + exp_score * weights.experience
        + title_score * weights.title_relevance
        + edu_score * weights.education
    )

    match = MatchResult(
        candidate_name=resume.candidate_name,
        match_score=round(total, 1),
        matched_skills=matched,
        missing_skills=missing,
        experience_match_score=round(exp_score, 1),
        education_match_score=round(edu_score, 1),
        title_match_score=round(title_score, 1),
        semantic_similarity_score=round(semantic_score, 1),
        keyword_relevance_score=round(keyword_score, 1),
    )
    match.recommendation = get_recommendation_label(match.match_score)
    match.explanation = generate_explanation(match, resume, jd)

    logger.info(
        "Scored %s: %.1f (%s)",
        resume.candidate_name,
        match.match_score,
        match.recommendation,
    )
    return match
