from __future__ import annotations

import re

from app.api.schemas import ExperienceSchema, JobPosting, ParsedResume, TailoredResume
from app.core.logging import get_logger
from app.models.config import config
from app.tailoring.evidence_mapper import build_evidence_map

logger = get_logger(__name__)


def _generate_tailored_summary(resume: ParsedResume, job: JobPosting, matched_skills: list[str]) -> str:
    """Generate a job-specific professional summary."""
    name = resume.candidate_name or "Experienced professional"
    years = resume.total_years_experience
    title = resume.experience[0].job_title if resume.experience else "professional"

    # Pick top matched skills (up to 4)
    top_skills = matched_skills[:4] if matched_skills else resume.skills[:4]
    skills_str = ", ".join(top_skills[:-1]) + f", and {top_skills[-1]}" if len(top_skills) > 1 else (top_skills[0] if top_skills else "various technologies")

    summary = (
        f"{name} is a {title} with {years:.0f}+ years of experience specializing in {skills_str}. "
    )

    # Add evidence-based accomplishment if available
    if resume.experience and resume.experience[0].description:
        top_bullet = resume.experience[0].description[0]
        # Truncate if too long
        if len(top_bullet) > 100:
            top_bullet = top_bullet[:97] + "..."
        summary += f"Proven track record including: {top_bullet}"

    return summary.strip()


def _reorder_skills(resume: ParsedResume, job: JobPosting) -> list[str]:
    """Reorder skills: matched required first, then matched preferred, then remaining."""
    resume_skills_set = {s.lower(): s for s in resume.skills}
    ordered: list[str] = []
    seen: set[str] = set()

    # Required skills that candidate has
    for skill in job.required_skills:
        if skill.lower() in resume_skills_set and skill.lower() not in seen:
            ordered.append(resume_skills_set[skill.lower()])
            seen.add(skill.lower())

    # Preferred skills that candidate has
    for skill in job.preferred_skills:
        if skill.lower() in resume_skills_set and skill.lower() not in seen:
            ordered.append(resume_skills_set[skill.lower()])
            seen.add(skill.lower())

    # Remaining skills
    for skill in resume.skills:
        if skill.lower() not in seen:
            ordered.append(skill)
            seen.add(skill.lower())

    return ordered


def _prioritize_bullets(bullets: list[str], job: JobPosting) -> list[str]:
    """Reorder experience bullets to put most relevant first.

    Uses keyword matching to score each bullet against job requirements.
    """
    if not bullets:
        return []

    jd_keywords = set()
    for skill in job.required_skills + job.preferred_skills:
        jd_keywords.update(skill.lower().split())
    for req in job.requirements:
        jd_keywords.update(re.findall(r"\b[a-zA-Z]{3,}\b", req.lower()))

    # Score each bullet
    scored = []
    for bullet in bullets:
        bullet_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", bullet.lower()))
        overlap = len(jd_keywords & bullet_words)
        scored.append((overlap, bullet))

    # Sort by relevance (higher overlap first), stable sort preserves original order for ties
    scored.sort(key=lambda x: x[0], reverse=True)
    return [bullet for _, bullet in scored]


def tailor_resume(resume: ParsedResume, job: JobPosting, matched_skills: list[str] | None = None) -> TailoredResume:
    """Generate a tailored resume for a specific job posting.

    Guardrails:
    - No new employers, titles, degrees, or dates
    - No new tools/skills not present in source CV
    - All content must be verifiable from the original resume
    """
    if matched_skills is None:
        from app.matching.scoring import compute_skill_match
        from app.matching.job_ranker import job_to_jd
        _, matched_skills, _ = compute_skill_match(resume, job_to_jd(job))

    # Check if LLM enhancement is available
    llm_enabled = (
        getattr(config, "llm_tailoring_enabled", False)
        and getattr(config, "anthropic_api_key", "")
    )

    # 1. Tailored summary
    summary = _generate_tailored_summary(resume, job, matched_skills)
    if llm_enabled:
        try:
            from app.tailoring.llm_summary import generate_summary_with_llm
            summary = generate_summary_with_llm(resume, job, matched_skills)
            logger.info("Used LLM for summary generation")
        except Exception as e:
            logger.warning("LLM summary failed, using deterministic: %s", e)

    # 2. Reordered skills
    skills = _reorder_skills(resume, job)

    # 3. Prioritized experience bullets (with optional LLM rewriting)
    tailored_experience = []
    for exp in resume.experience:
        prioritized = _prioritize_bullets(exp.description, job)

        if llm_enabled and prioritized:
            try:
                from app.tailoring.llm_rewriter import rewrite_bullets_with_llm
                prioritized = rewrite_bullets_with_llm(prioritized, job, resume)
                logger.info("Used LLM to rewrite %d bullets for %s", len(prioritized), exp.company)
            except Exception as e:
                logger.warning("LLM bullet rewrite failed for %s: %s", exp.company, e)

        tailored_exp = ExperienceSchema(
            job_title=exp.job_title,
            company=exp.company,
            start_date=exp.start_date,
            end_date=exp.end_date,
            duration_months=exp.duration_months,
            description=prioritized,
        )
        tailored_experience.append(tailored_exp)

    return TailoredResume(
        job_id=job.job_id,
        tailored_summary=summary,
        tailored_skills=skills,
        tailored_experience=tailored_experience,
    )
