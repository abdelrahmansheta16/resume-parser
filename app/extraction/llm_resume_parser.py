"""LLM-based resume parsing using LangChain + Claude structured output."""
from __future__ import annotations

from app.api.schemas import ParsedResume
from app.core.logging import get_logger
from app.models.config import config

logger = get_logger(__name__)

SYSTEM_PROMPT = """\
You are an expert resume parser. Extract structured data from the resume text below.

Rules:
1. Only extract information explicitly present in the text. Never fabricate or infer.
2. For skills, list each distinct technical skill, tool, framework, or language mentioned.
3. For experience, extract each job entry with title, company, dates, and bullet descriptions.
4. For education, extract degree, field, institution, graduation date, and GPA if present.
5. Calculate total_years_experience by summing durations across all jobs.
6. If a field is not found in the text, leave it as null or empty.
7. For dates, use formats like "Jan 2020", "2020-01", or "2020" as they appear.
8. Certifications and projects should be simple string lists.
"""

MAX_INPUT_CHARS = 6000


def parse_resume_with_llm(cleaned_text: str) -> ParsedResume | None:
    """Parse resume text using LangChain + Claude structured output.

    Returns a ParsedResume on success, or None if parsing fails.
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

    structured_llm = llm.with_structured_output(ParsedResume)

    # Truncate to control cost
    text = cleaned_text[:MAX_INPUT_CHARS]

    try:
        result: ParsedResume = structured_llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this resume:\n\n{text}"},
        ])

        result.parse_method = "llm"
        result.detected_language = result.detected_language or "en"

        logger.info(
            "LLM parsed resume: name=%s, skills=%d, edu=%d, exp=%d",
            result.candidate_name,
            len(result.skills),
            len(result.education),
            len(result.experience),
        )
        return result

    except Exception as e:
        logger.warning("LLM resume parsing failed: %s", e)
        return None
