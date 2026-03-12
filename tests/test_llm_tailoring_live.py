"""Live LLM tailoring tests — compare deterministic vs Claude-powered output.

These tests make real API calls to Anthropic and are marked with @pytest.mark.live_llm.
Run selectively: pytest tests/test_llm_tailoring_live.py -v -s

If the API key has no credits, tests verify the graceful fallback path instead.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.api.schemas import JobMatchResult, JobPosting
from app.extraction.resume_structurer import structure_resume
from app.models.config import config
from app.tailoring.cover_letter import (
    generate_cover_letter,
    generate_cover_letter_template,
)
from app.tailoring.rewriter import tailor_resume

live_llm = pytest.mark.skipif(
    not (config.llm_tailoring_enabled and config.anthropic_api_key),
    reason="LLM tailoring not enabled (set ANTHROPIC_API_KEY + LLM_TAILORING_ENABLED=true)",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_RESUME_1 = PROJECT_ROOT / "data" / "samples" / "sample_resume_1.txt"
SAMPLE_RESUME_2 = PROJECT_ROOT / "data" / "samples" / "sample_resume_2.txt"
SAMPLE_JD_1 = PROJECT_ROOT / "data" / "samples" / "sample_jd_1.txt"


def _parse_sample_job() -> JobPosting:
    """Parse sample_jd_1.txt into a JobPosting."""
    return JobPosting(
        job_id="test-jd-1",
        title="Senior Backend Engineer",
        company="TechForward Inc.",
        location="San Francisco, CA (Hybrid)",
        description=SAMPLE_JD_1.read_text(encoding="utf-8"),
        required_skills=[
            "Python", "FastAPI", "Django", "PostgreSQL", "Redis",
            "Docker", "Kubernetes", "AWS", "REST APIs", "CI/CD",
        ],
        preferred_skills=[
            "Kafka", "RabbitMQ", "GraphQL", "Terraform",
        ],
        requirements=[
            "5+ years of experience in backend development",
            "Strong proficiency in Python",
            "Experience with FastAPI or Django",
            "Deep knowledge of PostgreSQL and Redis",
            "Experience with Docker and Kubernetes",
        ],
        required_years_experience=5.0,
        source="test",
    )


@pytest.fixture
def sample_job():
    return _parse_sample_job()


@pytest.fixture
def resume_john():
    """Parse sample_resume_1.txt (John Doe — Backend Developer)."""
    text = SAMPLE_RESUME_1.read_text(encoding="utf-8")
    return structure_resume(text)


@pytest.fixture
def resume_sarah():
    """Parse sample_resume_2.txt (Sarah Johnson — Data Scientist)."""
    text = SAMPLE_RESUME_2.read_text(encoding="utf-8")
    return structure_resume(text)


def _print_comparison(label: str, deterministic: str, llm: str) -> None:
    """Print side-by-side comparison."""
    print(f"\n{'='*80}")
    print(f"  {label}")
    print(f"{'='*80}")
    print(f"\n--- DETERMINISTIC ---\n{deterministic}")
    print(f"\n--- LLM-POWERED ---\n{llm}")
    if deterministic == llm:
        print("\n  [NOTE: Outputs identical — LLM likely fell back to deterministic]")
    print(f"{'='*80}\n")


@live_llm
class TestLLMvsDeteriministicJohnDoe:
    """Compare LLM vs deterministic output for John Doe (high match)."""

    def test_summary_comparison(self, resume_john, sample_job):
        """LLM summary should be produced (or gracefully fall back)."""
        # Deterministic
        with patch.object(config, "llm_tailoring_enabled", False):
            det_result = tailor_resume(resume_john, sample_job)

        # LLM (may fall back to deterministic if API credits exhausted)
        with patch.object(config, "llm_tailoring_enabled", True):
            llm_result = tailor_resume(resume_john, sample_job)

        _print_comparison("SUMMARY — John Doe", det_result.tailored_summary, llm_result.tailored_summary)

        # Guardrails always hold regardless of mode
        assert len(llm_result.tailored_summary) <= 500
        assert llm_result.tailored_summary  # not empty

        # If LLM actually worked, output should differ
        if llm_result.tailored_summary != det_result.tailored_summary:
            print("  [LLM produced a distinct summary]")

    def test_bullet_rewriting_comparison(self, resume_john, sample_job):
        """LLM bullets should preserve structure (count, employers, titles, dates)."""
        with patch.object(config, "llm_tailoring_enabled", False):
            det_result = tailor_resume(resume_john, sample_job)

        with patch.object(config, "llm_tailoring_enabled", True):
            llm_result = tailor_resume(resume_john, sample_job)

        for det_exp, llm_exp in zip(
            det_result.tailored_experience, llm_result.tailored_experience
        ):
            det_bullets = "\n".join(f"  - {b}" for b in det_exp.description)
            llm_bullets = "\n".join(f"  - {b}" for b in llm_exp.description)
            _print_comparison(
                f"BULLETS — {det_exp.company} ({det_exp.job_title})",
                det_bullets,
                llm_bullets,
            )

            # Guardrails: same count
            assert len(llm_exp.description) == len(det_exp.description)

            # Guardrails: no new employers/titles/dates
            assert llm_exp.company == det_exp.company
            assert llm_exp.job_title == det_exp.job_title
            assert llm_exp.start_date == det_exp.start_date
            assert llm_exp.end_date == det_exp.end_date

    def test_skills_ordering(self, resume_john, sample_job):
        """Skills should be reordered with required first (same in both modes)."""
        with patch.object(config, "llm_tailoring_enabled", False):
            det_result = tailor_resume(resume_john, sample_job)

        with patch.object(config, "llm_tailoring_enabled", True):
            llm_result = tailor_resume(resume_john, sample_job)

        # Skills ordering is deterministic (not LLM-enhanced)
        assert det_result.tailored_skills == llm_result.tailored_skills

        # No new skills introduced
        original_set = set(s.lower() for s in resume_john.skills)
        assert set(s.lower() for s in llm_result.tailored_skills) == original_set

    def test_cover_letter_comparison(self, resume_john, sample_job):
        """Cover letter should be generated (LLM or template fallback)."""
        match = JobMatchResult(
            job=sample_job,
            match_score=90.0,
            recommendation="Excellent match",
            matched_skills=["Python", "FastAPI", "Docker", "Kubernetes", "PostgreSQL"],
            missing_skills=["Kafka"],
        )

        det_letter = generate_cover_letter_template(resume_john, sample_job, match)
        # generate_cover_letter tries LLM first, falls back to template
        llm_letter = generate_cover_letter(resume_john, sample_job, match)

        _print_comparison("COVER LETTER — John Doe", det_letter, llm_letter)

        # Should always produce a non-empty letter
        assert llm_letter
        assert "Dear" in llm_letter or "Sincerely" in llm_letter or len(llm_letter) > 100

    def test_no_fabricated_skills_in_tailored(self, resume_john, sample_job):
        """LLM mode must not introduce skills not in the original resume."""
        with patch.object(config, "llm_tailoring_enabled", True):
            result = tailor_resume(resume_john, sample_job)

        original_skills_lower = set(s.lower() for s in resume_john.skills)
        tailored_skills_lower = set(s.lower() for s in result.tailored_skills)
        assert tailored_skills_lower == original_skills_lower


@live_llm
class TestLLMvsDeteriministicSarahJohnson:
    """Compare output for Sarah Johnson (Data Scientist — weaker match to backend role)."""

    def test_summary_for_weaker_match(self, resume_sarah, sample_job):
        """Summary should be produced even for a less-matched candidate."""
        with patch.object(config, "llm_tailoring_enabled", False):
            det_result = tailor_resume(resume_sarah, sample_job)

        with patch.object(config, "llm_tailoring_enabled", True):
            llm_result = tailor_resume(resume_sarah, sample_job)

        _print_comparison(
            "SUMMARY — Sarah Johnson (Data Scientist → Backend role)",
            det_result.tailored_summary,
            llm_result.tailored_summary,
        )

        assert len(llm_result.tailored_summary) <= 500
        assert llm_result.tailored_summary

    def test_bullet_rewriting_weaker_match(self, resume_sarah, sample_job):
        """Bullets should maintain structure for a less-matched candidate."""
        with patch.object(config, "llm_tailoring_enabled", False):
            det_result = tailor_resume(resume_sarah, sample_job)

        with patch.object(config, "llm_tailoring_enabled", True):
            llm_result = tailor_resume(resume_sarah, sample_job)

        if llm_result.tailored_experience:
            exp = llm_result.tailored_experience[0]
            det_exp = det_result.tailored_experience[0]
            det_bullets = "\n".join(f"  - {b}" for b in det_exp.description)
            llm_bullets = "\n".join(f"  - {b}" for b in exp.description)
            _print_comparison(
                f"BULLETS — {exp.company} ({exp.job_title})",
                det_bullets,
                llm_bullets,
            )

            assert len(exp.description) == len(det_exp.description)
            assert exp.company == det_exp.company

    def test_no_fabricated_employers(self, resume_sarah, sample_job):
        """Must not introduce employers not in the original resume."""
        with patch.object(config, "llm_tailoring_enabled", True):
            result = tailor_resume(resume_sarah, sample_job)

        original_companies = {e.company for e in resume_sarah.experience}
        tailored_companies = {e.company for e in result.tailored_experience}
        assert tailored_companies == original_companies


@live_llm
class TestLLMGracefulFallback:
    """Verify graceful degradation when LLM fails."""

    def test_bad_api_key_falls_back(self, resume_john, sample_job):
        """With a bad API key, should fall back to deterministic mode."""
        with patch.object(config, "anthropic_api_key", "sk-bad-key"):
            result = tailor_resume(resume_john, sample_job)

        # Should still produce output (deterministic fallback)
        assert result.tailored_summary
        assert len(result.tailored_experience) > 0
        print(f"\nFallback summary: {result.tailored_summary}")

    def test_fallback_preserves_all_fields(self, resume_john, sample_job):
        """Fallback output should have all expected fields populated."""
        with patch.object(config, "anthropic_api_key", "sk-bad-key"):
            result = tailor_resume(resume_john, sample_job)

        assert result.job_id == sample_job.job_id
        assert len(result.tailored_skills) > 0
        assert len(result.tailored_experience) == len(resume_john.experience)
        for exp in result.tailored_experience:
            assert exp.description  # bullets not empty
