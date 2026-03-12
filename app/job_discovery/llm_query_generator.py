"""LLM-based job search query generation using LangChain + Claude."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel

from app.api.schemas import CandidateProfile
from app.core.logging import get_logger
from app.models.config import config

logger = get_logger(__name__)

SYSTEM_PROMPT = """\
You are an expert job search strategist. Given a candidate's profile, generate \
5-10 diverse job search queries optimized for job board APIs (Jooble, Adzuna, Indeed, etc.).

Rules:
1. Keep each query concise: 2-4 words (e.g., "Smart Contract Auditor", "DeFi Engineer").
2. Include a mix of:
   - Exact role titles matching the candidate's experience
   - Broader roles they'd qualify for
   - Niche specializations based on their unique skills
3. Consider their seniority level and years of experience.
4. If target titles are provided, include them but also add complementary queries.
5. Prioritize queries that would return relevant results on job boards.
6. Do NOT include location in the queries (locations are handled separately).
7. Do NOT include generic terms like "developer" alone — be specific.
"""

MAX_QUERIES = 10


class SearchQueries(BaseModel):
    """Structured output for LLM query generation."""
    queries: List[str]


def generate_queries_with_llm(profile: CandidateProfile) -> list[str] | None:
    """Generate job search queries using LangChain + Claude.

    Returns a list of search queries on success, or None if generation fails.
    """
    from langchain_anthropic import ChatAnthropic

    if not config.anthropic_api_key:
        logger.warning("No Anthropic API key configured for LLM query generation")
        return None

    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=config.anthropic_api_key,
        max_tokens=1024,
        temperature=0.3,
    )

    structured_llm = llm.with_structured_output(SearchQueries)

    # Build a concise profile summary for the LLM
    resume = profile.resume
    skills_str = ", ".join(resume.skills[:15])

    experience_lines = []
    for exp in resume.experience[:4]:
        title = exp.job_title or "Unknown"
        company = exp.company or "Unknown"
        experience_lines.append(f"- {title} at {company}")
    experience_str = "\n".join(experience_lines) if experience_lines else "No experience listed"

    target_titles = ", ".join(profile.target_titles) if profile.target_titles else "Not specified"
    seniority = profile.seniority_level or "Not specified"
    years = resume.total_years_experience

    user_message = (
        f"Generate job search queries for this candidate:\n\n"
        f"Target titles: {target_titles}\n"
        f"Seniority: {seniority}\n"
        f"Years of experience: {years}\n"
        f"Top skills: {skills_str}\n"
        f"Recent experience:\n{experience_str}\n"
    )

    if profile.remote_preference:
        user_message += f"Remote preference: {profile.remote_preference}\n"
    if profile.target_industries:
        user_message += f"Target industries: {', '.join(profile.target_industries)}\n"

    try:
        result: SearchQueries = structured_llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ])

        queries = [q.strip() for q in result.queries if q.strip()][:MAX_QUERIES]

        logger.info("LLM generated %d search queries: %s", len(queries), queries)
        return queries if queries else None

    except Exception as e:
        logger.warning("LLM query generation failed: %s", e)
        return None
