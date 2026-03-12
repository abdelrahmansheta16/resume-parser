"""LLM-enhanced bullet point rewriting using Claude API."""
from __future__ import annotations

import re

from app.api.schemas import JobPosting, ParsedResume
from app.core.logging import get_logger
from app.models.config import config

logger = get_logger(__name__)


def rewrite_bullets_with_llm(
    bullets: list[str],
    job: JobPosting,
    resume: ParsedResume,
) -> list[str]:
    """Rewrite experience bullets to better match the target job using Claude.

    Maintains guardrails: no fabricated content, same length output.
    """
    if not bullets:
        return bullets

    import anthropic

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    skills_str = ", ".join(resume.skills[:15])
    bullets_text = "\n".join(f"{i+1}. {b}" for i, b in enumerate(bullets))
    jd_text = (job.description or "")[:500]
    req_skills = ", ".join(job.required_skills[:10]) if job.required_skills else ""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=(
            "You are an ATS resume optimizer. Rewrite each bullet point to better "
            "highlight relevance to the target job description.\n\n"
            "STRICT RULES:\n"
            "1. Never add employers, job titles, tools, technologies, dates, or skills "
            "not present in the candidate's resume skills list.\n"
            "2. Keep each bullet under 120 characters.\n"
            "3. Start each bullet with a strong action verb.\n"
            "4. Preserve any quantified metrics from the original.\n"
            "5. Return exactly the same number of bullets, numbered 1-N.\n"
            "6. If you cannot improve a bullet without breaking the rules, return it unchanged."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Candidate's skills: {skills_str}\n\n"
                f"Target job: {job.title} at {job.company}\n"
                f"Required skills: {req_skills}\n"
                f"Job description: {jd_text}\n\n"
                f"Bullets to rewrite:\n{bullets_text}\n\n"
                f"Return ONLY the numbered rewritten bullets, nothing else."
            ),
        }],
    )

    raw_response = message.content[0].text
    rewritten = _parse_numbered_bullets(raw_response, len(bullets))

    # Validate each bullet
    validated = _validate_rewritten_bullets(rewritten, bullets, resume)
    return validated


def _parse_numbered_bullets(text: str, expected_count: int) -> list[str]:
    """Parse numbered bullet points from LLM response."""
    lines = text.strip().split("\n")
    bullets = []
    for line in lines:
        line = line.strip()
        # Remove numbering like "1.", "1)", "- 1."
        cleaned = re.sub(r"^[\d]+[.)]\s*", "", line).strip()
        cleaned = re.sub(r"^[-•]\s*", "", cleaned).strip()
        if cleaned:
            bullets.append(cleaned)

    # If count doesn't match, pad or truncate
    while len(bullets) < expected_count:
        bullets.append("")
    return bullets[:expected_count]


def _validate_rewritten_bullets(
    rewritten: list[str],
    originals: list[str],
    resume: ParsedResume,
) -> list[str]:
    """Validate rewritten bullets against source resume.

    Falls back to original bullet if validation fails.
    """
    resume_text = " ".join([
        " ".join(resume.skills),
        " ".join(e.company or "" for e in resume.experience),
        " ".join(b for e in resume.experience for b in (e.description or [])),
        resume.summary or "",
    ]).lower()

    # Known tools/technologies from the resume
    resume_skills_lower = {s.lower() for s in resume.skills}

    validated = []
    for rewritten_bullet, original in zip(rewritten, originals):
        if not rewritten_bullet:
            validated.append(original)
            continue

        # Check: no new tool/technology names introduced
        # Extract capitalized words that might be tech names
        words_in_rewritten = set(re.findall(r"\b[A-Z][a-zA-Z+#.]+\b", rewritten_bullet))
        words_in_original = set(re.findall(r"\b[A-Z][a-zA-Z+#.]+\b", original))
        new_words = words_in_rewritten - words_in_original

        for word in new_words:
            if word.lower() not in resume_text and word.lower() not in resume_skills_lower:
                logger.debug("Rejected rewritten bullet (new term '%s'): %s", word, rewritten_bullet)
                validated.append(original)
                break
        else:
            validated.append(rewritten_bullet)

    return validated
