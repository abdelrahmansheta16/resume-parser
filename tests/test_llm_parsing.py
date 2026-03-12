"""Tests for LangChain-based LLM parsing (resume + job description)."""
from unittest.mock import MagicMock, patch

import pytest

from app.api.schemas import EducationSchema, ExperienceSchema, ParsedJobDescription, ParsedResume


SAMPLE_RESUME_TEXT = """
John Smith
john.smith@email.com | (555) 123-4567 | linkedin.com/in/johnsmith
San Francisco, CA

SUMMARY
Senior Software Engineer with 8 years of experience building scalable web applications.

SKILLS
Python, JavaScript, React, Node.js, PostgreSQL, Docker, AWS, Kubernetes

EXPERIENCE
Senior Software Engineer | Google | Jan 2020 - Present
- Led migration of monolithic service to microservices architecture
- Reduced API latency by 40% through caching and query optimization

Software Engineer | Meta | Jun 2016 - Dec 2019
- Built real-time notification system serving 50M users
- Implemented CI/CD pipeline reducing deployment time by 60%

EDUCATION
Bachelor of Science in Computer Science | MIT | 2016
GPA: 3.8

CERTIFICATIONS
AWS Solutions Architect - Professional
"""

SAMPLE_JD_TEXT = """
Senior Backend Engineer

About the role:
We are looking for a Senior Backend Engineer to join our platform team.

Requirements:
- 5+ years of experience in backend development
- Proficiency in Python, Go, or Java
- Experience with distributed systems and microservices
- Strong knowledge of SQL and NoSQL databases
- Bachelor's degree in Computer Science or related field

Nice to have:
- Experience with Kubernetes and Docker
- Knowledge of event-driven architecture
- AWS or GCP certification

Soft skills:
- Strong communication and collaboration
- Leadership and mentoring abilities
"""


def _make_mock_resume() -> ParsedResume:
    return ParsedResume(
        candidate_name="John Smith",
        email="john.smith@email.com",
        phone="(555) 123-4567",
        location="San Francisco, CA",
        linkedin="linkedin.com/in/johnsmith",
        summary="Senior Software Engineer with 8 years of experience building scalable web applications.",
        skills=["Python", "JavaScript", "React", "Node.js", "PostgreSQL", "Docker", "AWS", "Kubernetes"],
        experience=[
            ExperienceSchema(
                job_title="Senior Software Engineer",
                company="Google",
                start_date="Jan 2020",
                end_date="Present",
                description=["Led migration of monolithic service to microservices architecture"],
            ),
            ExperienceSchema(
                job_title="Software Engineer",
                company="Meta",
                start_date="Jun 2016",
                end_date="Dec 2019",
                description=["Built real-time notification system serving 50M users"],
            ),
        ],
        education=[
            EducationSchema(
                degree="Bachelor of Science",
                field_of_study="Computer Science",
                institution="MIT",
                graduation_date="2016",
                gpa="3.8",
            ),
        ],
        certifications=["AWS Solutions Architect - Professional"],
        total_years_experience=8.0,
        parse_method="llm",
    )


def _make_mock_jd() -> ParsedJobDescription:
    return ParsedJobDescription(
        title="Senior Backend Engineer",
        required_skills=["Python", "Go", "Java", "SQL", "NoSQL"],
        preferred_skills=["Kubernetes", "Docker"],
        required_years_experience=5.0,
        education_requirements=["Bachelor's degree in Computer Science"],
        tools_and_technologies=["Python", "Go", "Java", "SQL", "NoSQL", "Kubernetes", "Docker"],
        soft_skills=["communication", "collaboration", "leadership", "mentoring"],
    )


class TestLLMResumeParsing:
    @patch("app.extraction.llm_resume_parser.config")
    def test_returns_none_without_api_key(self, mock_config):
        mock_config.anthropic_api_key = ""
        from app.extraction.llm_resume_parser import parse_resume_with_llm
        result = parse_resume_with_llm(SAMPLE_RESUME_TEXT)
        assert result is None

    @patch("langchain_anthropic.ChatAnthropic")
    @patch("app.extraction.llm_resume_parser.config")
    def test_successful_parse(self, mock_config, mock_chat_cls):
        mock_config.anthropic_api_key = "test-key"
        mock_resume = _make_mock_resume()

        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = mock_resume

        from app.extraction.llm_resume_parser import parse_resume_with_llm
        result = parse_resume_with_llm(SAMPLE_RESUME_TEXT)

        assert result is not None
        assert result.candidate_name == "John Smith"
        assert result.parse_method == "llm"
        assert len(result.skills) == 8
        assert len(result.experience) == 2
        assert len(result.education) == 1

    @patch("langchain_anthropic.ChatAnthropic")
    @patch("app.extraction.llm_resume_parser.config")
    def test_returns_none_on_exception(self, mock_config, mock_chat_cls):
        mock_config.anthropic_api_key = "test-key"

        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.invoke.side_effect = Exception("API error")

        from app.extraction.llm_resume_parser import parse_resume_with_llm
        result = parse_resume_with_llm(SAMPLE_RESUME_TEXT)
        assert result is None


class TestLLMJDParsing:
    @patch("app.matching.llm_jd_parser.config")
    def test_returns_none_without_api_key(self, mock_config):
        mock_config.anthropic_api_key = ""
        from app.matching.llm_jd_parser import parse_jd_with_llm
        result = parse_jd_with_llm(SAMPLE_JD_TEXT)
        assert result is None

    @patch("langchain_anthropic.ChatAnthropic")
    @patch("app.matching.llm_jd_parser.config")
    def test_successful_parse(self, mock_config, mock_chat_cls):
        mock_config.anthropic_api_key = "test-key"
        mock_jd = _make_mock_jd()

        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = mock_jd

        from app.matching.llm_jd_parser import parse_jd_with_llm
        result = parse_jd_with_llm(SAMPLE_JD_TEXT)

        assert result is not None
        assert result.title == "Senior Backend Engineer"
        assert "Python" in result.required_skills
        assert "Kubernetes" in result.preferred_skills
        assert result.required_years_experience == 5.0

    @patch("langchain_anthropic.ChatAnthropic")
    @patch("app.matching.llm_jd_parser.config")
    def test_returns_none_on_exception(self, mock_config, mock_chat_cls):
        mock_config.anthropic_api_key = "test-key"

        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.invoke.side_effect = Exception("API error")

        from app.matching.llm_jd_parser import parse_jd_with_llm
        result = parse_jd_with_llm(SAMPLE_JD_TEXT)
        assert result is None


class TestFallbackBehavior:
    def test_structure_resume_fallback_when_llm_disabled(self):
        """When LLM_PARSING_ENABLED is False, rule-based parsing is used."""
        from app.extraction.resume_structurer import structure_resume
        result = structure_resume(SAMPLE_RESUME_TEXT, include_raw=True)
        # Rule-based parsing should work and not set parse_method to "llm"
        assert result.parse_method != "llm"
        assert result.raw_text == SAMPLE_RESUME_TEXT

    def test_parse_jd_fallback_when_llm_disabled(self):
        """When LLM_PARSING_ENABLED is False, rule-based JD parsing is used."""
        from app.matching.jd_parser import parse_job_description
        result = parse_job_description(SAMPLE_JD_TEXT)
        assert result.raw_text == SAMPLE_JD_TEXT
        assert result.title is not None

    @patch("app.extraction.resume_structurer.config")
    def test_structure_resume_falls_back_on_llm_failure(self, mock_config):
        """When LLM is enabled but fails, rule-based parsing takes over."""
        mock_config.llm_parsing_enabled = True
        mock_config.anthropic_api_key = "test-key"

        with patch("app.extraction.llm_resume_parser.parse_resume_with_llm", side_effect=Exception("API down")):
            from app.extraction.resume_structurer import structure_resume
            result = structure_resume(SAMPLE_RESUME_TEXT, include_raw=True)
            # Should still get a result from rule-based parsing
            assert result is not None
            assert result.raw_text == SAMPLE_RESUME_TEXT
