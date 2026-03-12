"""Cover letter generation — template-based with optional LLM enhancement."""
from __future__ import annotations

from app.api.schemas import JobMatchResult, JobPosting, ParsedResume
from app.core.logging import get_logger
from app.models.config import config

logger = get_logger(__name__)

COVER_LETTER_TEMPLATE = """Dear Hiring Manager,

I am writing to express my strong interest in the {role} position at {company}. With {years} years of professional experience and a proven track record in {top_skills}, I am confident in my ability to make a meaningful contribution to your team.

{why_paragraph}

{qualifications_paragraph}

I would welcome the opportunity to discuss how my background aligns with your team's needs. Thank you for considering my application. I look forward to the possibility of contributing to {company}'s continued success.

Sincerely,
{candidate_name}"""


def generate_cover_letter(
    resume: ParsedResume,
    job: JobPosting,
    match: JobMatchResult,
) -> str:
    """Generate a cover letter. Uses LLM if enabled, otherwise template."""
    if getattr(config, "llm_tailoring_enabled", False) and getattr(config, "anthropic_api_key", ""):
        try:
            return generate_cover_letter_llm(resume, job, match)
        except Exception as e:
            logger.warning("LLM cover letter failed, falling back to template: %s", e)

    return generate_cover_letter_template(resume, job, match)


def generate_cover_letter_template(
    resume: ParsedResume,
    job: JobPosting,
    match: JobMatchResult,
) -> str:
    """Generate a cover letter using templates."""
    candidate_name = resume.candidate_name or "Candidate"
    role = job.title or "the open position"
    company = job.company or "your organization"
    years = str(int(resume.total_years_experience)) if resume.total_years_experience else "several"

    matched = match.matched_skills[:4] if match.matched_skills else resume.skills[:4]
    top_skills = ", ".join(matched) if matched else "relevant technical skills"

    # Build "why" paragraph
    why_parts = []
    if job.description:
        why_parts.append(
            f"The {role} role at {company} particularly excites me because it aligns "
            f"closely with my expertise and career goals."
        )
    if match.matched_skills:
        why_parts.append(
            f"Your requirements in {', '.join(match.matched_skills[:3])} "
            f"match directly with my core competencies."
        )
    why_paragraph = " ".join(why_parts) if why_parts else (
        f"I am drawn to this opportunity because of {company}'s reputation "
        f"and the alignment with my professional experience."
    )

    # Build qualifications paragraph
    qual_parts = []
    if resume.experience:
        latest = resume.experience[0]
        if latest.job_title and latest.company:
            qual_parts.append(
                f"In my most recent role as {latest.job_title} at {latest.company}, "
                f"I developed deep expertise that directly relates to this position."
            )
        if latest.description:
            top_bullet = latest.description[0]
            if len(top_bullet) > 150:
                top_bullet = top_bullet[:147] + "..."
            qual_parts.append(f"Notably, I {top_bullet[0].lower()}{top_bullet[1:]}")

    if match.missing_skills:
        qual_parts.append(
            f"While I am eager to further develop skills in "
            f"{', '.join(match.missing_skills[:2])}, my strong foundation ensures a quick ramp-up."
        )
    qualifications_paragraph = " ".join(qual_parts) if qual_parts else (
        f"My background in {top_skills} has prepared me well for the challenges of this role."
    )

    return COVER_LETTER_TEMPLATE.format(
        role=role,
        company=company,
        years=years,
        top_skills=top_skills,
        candidate_name=candidate_name,
        why_paragraph=why_paragraph,
        qualifications_paragraph=qualifications_paragraph,
    )


def generate_cover_letter_llm(
    resume: ParsedResume,
    job: JobPosting,
    match: JobMatchResult,
) -> str:
    """Generate a cover letter using Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    skills_str = ", ".join(resume.skills[:10])
    experience_str = ""
    for exp in resume.experience[:3]:
        bullets = "; ".join((exp.description or [])[:3])
        experience_str += f"- {exp.job_title} at {exp.company}: {bullets}\n"

    matched_str = ", ".join(match.matched_skills[:5])
    missing_str = ", ".join(match.missing_skills[:3])

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        system=(
            "You write professional cover letters. Rules:\n"
            "1. Only reference skills, experience, and accomplishments present in the resume.\n"
            "2. Never fabricate employers, titles, degrees, or specific metrics.\n"
            "3. 4 paragraphs: greeting, why this role, qualifications, closing.\n"
            "4. Professional but genuine tone. No clichés.\n"
            "5. Under 350 words."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Write a cover letter for {resume.candidate_name or 'the candidate'} "
                f"applying to {job.title} at {job.company}.\n\n"
                f"Candidate skills: {skills_str}\n"
                f"Experience:\n{experience_str}\n"
                f"Matched skills for this job: {matched_str}\n"
                f"Skills to develop: {missing_str}\n"
                f"Job description: {(job.description or '')[:500]}"
            ),
        }],
    )

    return message.content[0].text
