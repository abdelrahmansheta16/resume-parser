import re

from app.api.schemas import EducationSchema, ExperienceSchema, ParsedResume
from app.core.logging import get_logger
from app.extraction.education import extract_education
from app.models.config import config
from app.extraction.entities import (
    extract_location,
    extract_name_from_header,
    extract_name_with_spacy,
)
from app.extraction.experience import estimate_total_years, extract_experience
from app.extraction.links import extract_contact_info
from app.extraction.sections import detect_sections
from app.extraction.skills import extract_skills_from_section, extract_skills_from_text
from app.parsing.language_detect import detect_language

logger = get_logger(__name__)


def structure_resume(cleaned_text: str, include_raw: bool = False) -> ParsedResume:
    """Run full extraction pipeline on cleaned resume text."""
    # Try LLM parsing first if enabled
    if config.llm_parsing_enabled and config.anthropic_api_key:
        from app.extraction.llm_resume_parser import parse_resume_with_llm
        try:
            llm_result = parse_resume_with_llm(cleaned_text)
            if llm_result:
                if include_raw:
                    llm_result.raw_text = cleaned_text
                return llm_result
        except Exception as e:
            logger.warning("LLM resume parsing failed, falling back to rule-based: %s", e)

    # Rule-based pipeline
    result = ParsedResume()
    if include_raw:
        result.raw_text = cleaned_text

    # 0. Detect language
    lang = detect_language(cleaned_text)
    result.detected_language = lang

    # 1. Extract contact info from full text
    contact = extract_contact_info(cleaned_text)
    result.email = contact.emails[0] if contact.emails else None
    result.phone = contact.phones[0] if contact.phones else None
    result.linkedin = contact.linkedin
    result.github = contact.github
    result.portfolio = contact.portfolio

    # 2. Detect sections (language-aware)
    sections = detect_sections(cleaned_text, lang=lang)

    # 3. Extract name from header
    if "header" in sections:
        result.candidate_name = extract_name_from_header(sections["header"].content)
    if not result.candidate_name:
        result.candidate_name = extract_name_with_spacy(cleaned_text)

    # 4. Extract location
    header_text = sections["header"].content if "header" in sections else cleaned_text[:500]
    result.location = extract_location(header_text)

    # 5. Extract summary
    if "summary" in sections:
        result.summary = sections["summary"].content.strip()

    # 6. Extract skills (language-aware taxonomy)
    from app.extraction.skills import get_taxonomy
    taxonomy = get_taxonomy(lang=lang)
    skills: set[str] = set()
    if "skills" in sections:
        skills.update(extract_skills_from_section(sections["skills"].content, taxonomy))
    # Also scan full text for skills not in a dedicated section
    skills.update(extract_skills_from_text(cleaned_text, taxonomy))
    result.skills = sorted(skills)

    # 7. Extract education
    if "education" in sections:
        edu_entries = extract_education(sections["education"].content)
    else:
        edu_entries = extract_education(cleaned_text)
    result.education = [
        EducationSchema(
            degree=e.degree,
            field_of_study=e.field_of_study,
            institution=e.institution,
            graduation_date=e.graduation_date,
            gpa=e.gpa,
        )
        for e in edu_entries
    ]

    # 8. Extract experience
    if "experience" in sections:
        exp_entries = extract_experience(sections["experience"].content)
    else:
        exp_entries = extract_experience(cleaned_text)
    result.experience = [
        ExperienceSchema(
            job_title=e.job_title,
            company=e.company,
            start_date=e.start_date,
            end_date=e.end_date,
            duration_months=e.duration_months,
            description=e.description,
        )
        for e in exp_entries
    ]
    result.total_years_experience = estimate_total_years(exp_entries)

    # 9. Extract certifications
    if "certifications" in sections:
        certs = []
        for line in sections["certifications"].content.split("\n"):
            line = line.strip().lstrip("-* ")
            if line:
                certs.append(line)
        result.certifications = certs

    # 10. Extract projects
    if "projects" in sections:
        projects = []
        for line in sections["projects"].content.split("\n"):
            line = line.strip().lstrip("-* ")
            if line:
                projects.append(line)
        result.projects = projects

    logger.info(
        "Structured resume: name=%s, skills=%d, edu=%d, exp=%d",
        result.candidate_name,
        len(result.skills),
        len(result.education),
        len(result.experience),
    )
    return result
