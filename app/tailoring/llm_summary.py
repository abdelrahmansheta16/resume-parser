"""LLM-enhanced professional summary generation using Claude API."""
from __future__ import annotations

from app.api.schemas import JobPosting, ParsedResume
from app.core.logging import get_logger
from app.models.config import config

logger = get_logger(__name__)


def generate_summary_with_llm(
    resume: ParsedResume,
    job: JobPosting,
    matched_skills: list[str],
) -> str:
    """Generate a tailored professional summary using Claude.

    Returns a 2-3 sentence summary highlighting the candidate's
    fit for the specific job.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    skills_str = ", ".join(resume.skills[:15])
    matched_str = ", ".join(matched_skills[:6])
    years = int(resume.total_years_experience) if resume.total_years_experience else "several"

    experience_summary = ""
    if resume.experience:
        latest = resume.experience[0]
        experience_summary = f"Most recent: {latest.job_title} at {latest.company}"

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        system=(
            "You write professional resume summaries. Rules:\n"
            "1. 2-3 sentences only.\n"
            "2. Only reference skills, experience, and accomplishments present in the resume.\n"
            "3. Never fabricate employers, titles, degrees, or metrics.\n"
            "4. Tailor the summary to highlight fit for the target job.\n"
            "5. Professional, concise tone."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Write a professional summary for {resume.candidate_name or 'the candidate'}.\n\n"
                f"Years of experience: {years}\n"
                f"All skills: {skills_str}\n"
                f"Skills matching this job: {matched_str}\n"
                f"{experience_summary}\n\n"
                f"Target job: {job.title} at {job.company}\n"
                f"Job description: {(job.description or '')[:300]}\n\n"
                f"Return ONLY the summary text, nothing else."
            ),
        }],
    )

    summary = message.content[0].text.strip()
    # Basic validation: should not be too long
    if len(summary) > 500:
        summary = summary[:497] + "..."
    return summary
