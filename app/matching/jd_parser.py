import re

from app.api.schemas import ParsedJobDescription
from app.core.logging import get_logger
from app.extraction.skills import extract_skills_from_text, get_taxonomy
from app.models.config import config

logger = get_logger(__name__)

YEARS_EXP_RE = re.compile(r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)?", re.I)

REQUIRED_SECTION_RE = re.compile(
    r"(?:required|must\s+have|requirements?|qualifications?|what\s+you.ll\s+need)[:\s]*",
    re.I,
)
PREFERRED_SECTION_RE = re.compile(
    r"(?:preferred|nice\s+to\s+have|bonus|desired|plus|optional)[:\s]*",
    re.I,
)
EDUCATION_RE = re.compile(
    r"((?:bachelor|master|phd|ph\.d|doctorate|associate|degree|bs|ba|ms|ma|mba)"
    r"[a-z\s'.]*(?:in\s+[a-zA-Z\s]+)?)",
    re.I,
)

SOFT_SKILL_KEYWORDS = [
    "communication",
    "leadership",
    "teamwork",
    "collaboration",
    "problem solving",
    "problem-solving",
    "analytical",
    "critical thinking",
    "mentoring",
    "detail-oriented",
    "self-motivated",
    "time management",
    "adaptability",
    "creative",
    "initiative",
]


def parse_job_description(text: str) -> ParsedJobDescription:
    """Parse a job description into structured requirements."""
    # Try LLM parsing first if enabled
    if config.llm_parsing_enabled and config.anthropic_api_key:
        from app.matching.llm_jd_parser import parse_jd_with_llm
        try:
            llm_result = parse_jd_with_llm(text)
            if llm_result:
                llm_result.raw_text = text
                return llm_result
        except Exception as e:
            logger.warning("LLM JD parsing failed, falling back to rule-based: %s", e)

    # Rule-based pipeline
    result = ParsedJobDescription(raw_text=text)
    taxonomy = get_taxonomy()

    # Extract title: usually the first non-empty line
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line and len(line) < 80:
            result.title = line
            break

    # Extract years of experience
    years_match = YEARS_EXP_RE.search(text)
    if years_match:
        result.required_years_experience = float(years_match.group(1))

    # Split text into required vs preferred sections
    required_text = text
    preferred_text = ""

    # Try to find required/preferred section boundaries
    req_match = REQUIRED_SECTION_RE.search(text)
    pref_match = PREFERRED_SECTION_RE.search(text)

    if req_match and pref_match and pref_match.start() > req_match.start():
        required_text = text[req_match.start() : pref_match.start()]
        preferred_text = text[pref_match.start() :]
    elif pref_match:
        required_text = text[: pref_match.start()]
        preferred_text = text[pref_match.start() :]

    # Extract skills from required section
    result.required_skills = extract_skills_from_text(required_text, taxonomy)

    # Extract skills from preferred section
    if preferred_text:
        result.preferred_skills = extract_skills_from_text(preferred_text, taxonomy)

    # All tools/technologies = union of required + preferred
    result.tools_and_technologies = sorted(
        set(result.required_skills + result.preferred_skills)
    )

    # Extract education requirements
    edu_matches = EDUCATION_RE.findall(text)
    result.education_requirements = list(set(m.strip() for m in edu_matches if m.strip()))

    # Extract soft skills
    text_lower = text.lower()
    result.soft_skills = [s for s in SOFT_SKILL_KEYWORDS if s in text_lower]

    logger.info(
        "Parsed JD: title=%s, required_skills=%d, preferred=%d, years=%s",
        result.title,
        len(result.required_skills),
        len(result.preferred_skills),
        result.required_years_experience,
    )
    return result
