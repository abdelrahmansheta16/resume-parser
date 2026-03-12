"""LLM-based job description parsing using LangChain + Claude structured output."""
from __future__ import annotations

from app.api.schemas import ParsedJobDescription
from app.core.logging import get_logger
from app.models.config import config

logger = get_logger(__name__)

SYSTEM_PROMPT = """\
You are an expert job description parser. Extract structured data from the job posting text below.

Rules:
1. Only extract information explicitly stated in the text. Never fabricate.
2. Distinguish between required_skills and preferred_skills:
   - required_skills: mentioned under "required", "must have", "qualifications", or stated as mandatory
   - preferred_skills: mentioned under "nice to have", "preferred", "bonus", or stated as optional
   - If no clear distinction, treat all skills as required_skills.
3. tools_and_technologies should be the union of required and preferred skills.
4. For required_years_experience, extract the number of years mentioned (e.g., "5+ years" → 5.0).
5. education_requirements should list degree types mentioned (e.g., "Bachelor's in Computer Science").
6. soft_skills are non-technical skills like communication, leadership, teamwork, etc.
7. title should be the job title/position name.
"""

MAX_INPUT_CHARS = 6000


def parse_jd_with_llm(text: str) -> ParsedJobDescription | None:
    """Parse job description text using LangChain + Claude structured output.

    Returns a ParsedJobDescription on success, or None if parsing fails.
    """
    from langchain_anthropic import ChatAnthropic

    if not config.anthropic_api_key:
        logger.warning("No Anthropic API key configured for LLM parsing")
        return None

    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=config.anthropic_api_key,
        max_tokens=4096,
        temperature=0,
    )

    structured_llm = llm.with_structured_output(ParsedJobDescription)

    # Truncate to control cost
    truncated = text[:MAX_INPUT_CHARS]

    try:
        result: ParsedJobDescription = structured_llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this job description:\n\n{truncated}"},
        ])

        logger.info(
            "LLM parsed JD: title=%s, required_skills=%d, preferred=%d, years=%s",
            result.title,
            len(result.required_skills),
            len(result.preferred_skills),
            result.required_years_experience,
        )
        return result

    except Exception as e:
        logger.warning("LLM JD parsing failed: %s", e)
        return None
