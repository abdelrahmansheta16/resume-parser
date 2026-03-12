"""Tests for the resume tailoring module."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.api.schemas import (
    ExperienceSchema,
    JobMatchResult,
    JobPosting,
    ParsedResume,
)
from app.tailoring.evidence_mapper import build_evidence_map
from app.tailoring.rewriter import (
    _generate_tailored_summary,
    _prioritize_bullets,
    _reorder_skills,
    tailor_resume,
)


@pytest.fixture
def resume():
    return ParsedResume(
        candidate_name="Bob Wilson",
        email="bob@example.com",
        skills=["Python", "Java", "SQL", "Docker", "Kubernetes", "React", "TensorFlow"],
        experience=[
            ExperienceSchema(
                job_title="Senior Software Engineer",
                company="TechCorp",
                start_date="2020-01",
                end_date="2024-01",
                duration_months=48,
                description=[
                    "Led development of microservices architecture using Python and Docker",
                    "Improved API response time by 40% through query optimization",
                    "Mentored 5 junior developers on best practices",
                    "Deployed ML models using TensorFlow serving",
                ],
            ),
            ExperienceSchema(
                job_title="Software Engineer",
                company="StartupXYZ",
                start_date="2018-01",
                end_date="2020-01",
                duration_months=24,
                description=[
                    "Built REST APIs using Java and Spring Boot",
                    "Managed PostgreSQL databases and wrote complex SQL queries",
                    "Implemented CI/CD pipeline using Jenkins",
                ],
            ),
        ],
        education=[],
        total_years_experience=6.0,
        summary="Experienced software engineer with expertise in Python and cloud technologies.",
    )


@pytest.fixture
def job():
    return JobPosting(
        job_id="job1",
        title="Senior Python Developer",
        company="CloudCo",
        description="Senior Python developer for cloud infrastructure team",
        required_skills=["Python", "Docker", "Kubernetes"],
        preferred_skills=["TensorFlow", "AWS"],
        requirements=["5+ years of software development experience", "Experience with microservices"],
        required_years_experience=5.0,
    )


class TestEvidenceMapper:
    def test_builds_evidence_map(self, resume, job):
        evidence = build_evidence_map(resume, job)
        assert isinstance(evidence, dict)
        # Should have entries for requirements
        assert "Python" in evidence

    def test_python_has_evidence(self, resume, job):
        evidence = build_evidence_map(resume, job)
        assert len(evidence.get("Python", [])) > 0

    def test_missing_skill_no_evidence(self, resume):
        job = JobPosting(
            job_id="1",
            title="Go Developer",
            company="X",
            description="Go developer",
            required_skills=["Golang", "Rust"],
        )
        evidence = build_evidence_map(resume, job)
        # Golang and Rust should have no evidence
        assert len(evidence.get("Golang", [])) == 0


class TestReorderSkills:
    def test_required_skills_first(self, resume, job):
        reordered = _reorder_skills(resume, job)
        # Python, Docker, Kubernetes should come first
        assert reordered[0] == "Python"
        # Docker and Kubernetes should be near top
        top_3 = set(s.lower() for s in reordered[:3])
        assert "docker" in top_3
        assert "kubernetes" in top_3

    def test_all_skills_preserved(self, resume, job):
        reordered = _reorder_skills(resume, job)
        assert len(reordered) == len(resume.skills)
        assert set(s.lower() for s in reordered) == set(s.lower() for s in resume.skills)


class TestPrioritizeBullets:
    def test_relevant_bullets_first(self, job):
        bullets = [
            "Managed PostgreSQL databases",
            "Led development of microservices architecture using Python and Docker",
            "Organized team events and social activities",
        ]
        prioritized = _prioritize_bullets(bullets, job)
        # Python/Docker bullet should be first
        assert "Python" in prioritized[0] or "Docker" in prioritized[0]

    def test_empty_bullets(self, job):
        assert _prioritize_bullets([], job) == []

    def test_preserves_all_bullets(self, job):
        bullets = ["bullet 1", "bullet 2", "bullet 3"]
        prioritized = _prioritize_bullets(bullets, job)
        assert len(prioritized) == 3


class TestTailoredSummary:
    def test_includes_candidate_name(self, resume, job):
        summary = _generate_tailored_summary(resume, job, ["Python", "Docker"])
        assert "Bob Wilson" in summary

    def test_includes_matched_skills(self, resume, job):
        summary = _generate_tailored_summary(resume, job, ["Python", "Docker", "Kubernetes"])
        assert "Python" in summary


class TestTailorResume:
    def test_produces_tailored_resume(self, resume, job):
        tailored = tailor_resume(resume, job)
        assert tailored.tailored_summary
        assert len(tailored.tailored_skills) > 0
        assert len(tailored.tailored_experience) == len(resume.experience)

    def test_no_new_employers(self, resume, job):
        tailored = tailor_resume(resume, job)
        original_companies = {e.company for e in resume.experience}
        tailored_companies = {e.company for e in tailored.tailored_experience}
        assert tailored_companies == original_companies

    def test_no_new_titles(self, resume, job):
        tailored = tailor_resume(resume, job)
        original_titles = {e.job_title for e in resume.experience}
        tailored_titles = {e.job_title for e in tailored.tailored_experience}
        assert tailored_titles == original_titles

    def test_no_new_skills(self, resume, job):
        tailored = tailor_resume(resume, job)
        original_set = set(s.lower() for s in resume.skills)
        tailored_set = set(s.lower() for s in tailored.tailored_skills)
        assert tailored_set == original_set

    def test_dates_preserved(self, resume, job):
        tailored = tailor_resume(resume, job)
        for orig, tail in zip(resume.experience, tailored.tailored_experience):
            assert tail.start_date == orig.start_date
            assert tail.end_date == orig.end_date


class TestPDFGenerator:
    def test_reportlab_fallback_generates_pdf(self, resume, job):
        """Generate a DOCX then convert to PDF via reportlab."""
        from app.tailoring.docx_generator import generate_ats_docx
        from app.tailoring.pdf_generator import generate_pdf_from_docx

        tailored = tailor_resume(resume, job)
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "test_resume.docx"
            generate_ats_docx(resume, tailored, docx_path)
            assert docx_path.exists()

            pdf_path = generate_pdf_from_docx(docx_path)
            assert pdf_path.exists()
            assert pdf_path.suffix == ".pdf"
            assert pdf_path.stat().st_size > 0

    def test_pdf_path_has_same_stem(self, resume, job):
        from app.tailoring.docx_generator import generate_ats_docx
        from app.tailoring.pdf_generator import generate_pdf_from_docx

        tailored = tailor_resume(resume, job)
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "my_resume.docx"
            generate_ats_docx(resume, tailored, docx_path)
            pdf_path = generate_pdf_from_docx(docx_path)
            assert pdf_path.stem == "my_resume"


class TestATSIntegration:
    def test_pack_has_ats_score(self, resume, job):
        """ATS score should be populated when generating an application pack."""
        from app.tailoring.pack_generator import generate_application_pack

        match = JobMatchResult(
            job=job,
            match_score=85.0,
            matched_skills=["Python", "Docker"],
            missing_skills=["AWS"],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            pack = generate_application_pack(resume, match, output_dir=Path(tmpdir))
            assert pack.tailored_resume.ats_score > 0
            assert pack.tailored_resume.keyword_coverage >= 0

    def test_pack_has_pdf(self, resume, job):
        """PDF should be generated alongside DOCX in application pack."""
        from app.tailoring.pack_generator import generate_application_pack

        match = JobMatchResult(
            job=job,
            match_score=85.0,
            matched_skills=["Python", "Docker"],
            missing_skills=["AWS"],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            pack = generate_application_pack(resume, match, output_dir=Path(tmpdir))
            assert pack.tailored_resume.docx_path is not None
            assert pack.tailored_resume.pdf_path is not None
            assert Path(pack.tailored_resume.pdf_path).exists()

    def test_pack_has_cover_letter(self, resume, job):
        """Cover letter should be generated in application pack."""
        from app.tailoring.pack_generator import generate_application_pack

        match = JobMatchResult(
            job=job,
            match_score=85.0,
            matched_skills=["Python", "Docker"],
            missing_skills=["AWS"],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            pack = generate_application_pack(resume, match, output_dir=Path(tmpdir))
            assert pack.tailored_resume.cover_letter_path is not None
            assert Path(pack.tailored_resume.cover_letter_path).exists()


class TestCoverLetter:
    def test_template_cover_letter(self, resume, job):
        from app.tailoring.cover_letter import generate_cover_letter_template

        match = JobMatchResult(
            job=job,
            match_score=85.0,
            matched_skills=["Python", "Docker", "Kubernetes"],
            missing_skills=["AWS"],
        )
        letter = generate_cover_letter_template(resume, job, match)
        assert "Bob Wilson" in letter
        assert "CloudCo" in letter or "Senior Python Developer" in letter
        assert "Dear Hiring Manager" in letter
        assert "Sincerely" in letter

    def test_cover_letter_includes_skills(self, resume, job):
        from app.tailoring.cover_letter import generate_cover_letter_template

        match = JobMatchResult(
            job=job,
            match_score=85.0,
            matched_skills=["Python", "Docker"],
            missing_skills=[],
        )
        letter = generate_cover_letter_template(resume, job, match)
        assert "Python" in letter

    def test_cover_letter_docx(self, resume, job):
        from app.tailoring.cover_letter import generate_cover_letter_template
        from app.tailoring.cover_letter_docx import generate_cover_letter_docx

        match = JobMatchResult(
            job=job, match_score=85.0,
            matched_skills=["Python"], missing_skills=[],
        )
        letter = generate_cover_letter_template(resume, job, match)
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "cover_letter.docx"
            result = generate_cover_letter_docx(letter, resume, docx_path)
            assert result.exists()
            assert result.stat().st_size > 0


class TestLLMRewriter:
    def test_validate_rewritten_bullets_accepts_valid(self, resume):
        from app.tailoring.llm_rewriter import _validate_rewritten_bullets

        originals = ["Led development of microservices using Python and Docker"]
        rewritten = ["Led microservices development leveraging Python and Docker"]
        result = _validate_rewritten_bullets(rewritten, originals, resume)
        assert result[0] == rewritten[0]

    def test_validate_rewritten_bullets_rejects_fabricated(self, resume):
        from app.tailoring.llm_rewriter import _validate_rewritten_bullets

        originals = ["Led development of microservices using Python"]
        # "Scala" is not in the resume skills
        rewritten = ["Led development of microservices using Scala"]
        result = _validate_rewritten_bullets(rewritten, originals, resume)
        assert result[0] == originals[0]  # Should fall back to original

    def test_parse_numbered_bullets(self):
        from app.tailoring.llm_rewriter import _parse_numbered_bullets

        text = "1. First bullet\n2. Second bullet\n3. Third bullet"
        result = _parse_numbered_bullets(text, 3)
        assert len(result) == 3
        assert result[0] == "First bullet"

    def test_parse_numbered_bullets_pads_short(self):
        from app.tailoring.llm_rewriter import _parse_numbered_bullets

        text = "1. Only one"
        result = _parse_numbered_bullets(text, 3)
        assert len(result) == 3
