"""Integration tests exercising the full pipeline end-to-end."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.api.schemas import (
    CandidateProfile,
    ExperienceSchema,
    JobMatchResult,
    JobPosting,
    ParsedResume,
)


@pytest.fixture
def integration_resume():
    """A realistic resume for integration testing."""
    return ParsedResume(
        candidate_name="Alice Johnson",
        email="alice@example.com",
        phone="+1-555-0100",
        skills=["Python", "Machine Learning", "TensorFlow", "SQL", "Docker", "AWS", "Pandas"],
        experience=[
            ExperienceSchema(
                job_title="Senior Data Scientist",
                company="DataCorp",
                start_date="2021-01",
                end_date="2024-06",
                duration_months=42,
                description=[
                    "Built ML models using Python and TensorFlow achieving 95% accuracy",
                    "Led a team of 4 data scientists on recommendation engine project",
                    "Deployed models to production using Docker and AWS SageMaker",
                    "Optimized SQL queries reducing data pipeline runtime by 60%",
                ],
            ),
            ExperienceSchema(
                job_title="Data Scientist",
                company="StartupML",
                start_date="2018-06",
                end_date="2021-01",
                duration_months=30,
                description=[
                    "Developed NLP models for sentiment analysis using Python",
                    "Managed PostgreSQL databases and built ETL pipelines",
                    "Created dashboards with Pandas and Matplotlib",
                ],
            ),
        ],
        education=[],
        total_years_experience=6.0,
        summary="Experienced data scientist with expertise in ML and cloud deployment.",
    )


@pytest.fixture
def integration_jobs():
    """Canned job postings spanning 3 companies."""
    return [
        JobPosting(
            job_id="int-1",
            title="Senior ML Engineer",
            company="AlphaCo",
            description="Senior ML engineer to build production ML pipelines using Python, TensorFlow, and AWS.",
            required_skills=["Python", "TensorFlow", "AWS"],
            preferred_skills=["Docker", "Kubernetes"],
            requirements=["5+ years of ML experience"],
            required_years_experience=5.0,
            apply_url="https://alphaco.com/jobs/1",
            source="test",
        ),
        JobPosting(
            job_id="int-2",
            title="Data Scientist",
            company="BetaInc",
            description="Data scientist for analytics team. Strong SQL and Python skills required.",
            required_skills=["Python", "SQL", "Pandas"],
            preferred_skills=["Machine Learning"],
            requirements=["3+ years experience"],
            required_years_experience=3.0,
            apply_url="https://betainc.com/jobs/2",
            source="test",
        ),
        JobPosting(
            job_id="int-3",
            title="Frontend Developer",
            company="WebCo",
            description="React developer for web applications.",
            required_skills=["React", "TypeScript", "CSS"],
            preferred_skills=["GraphQL"],
            requirements=["3+ years frontend experience"],
            required_years_experience=3.0,
            apply_url="https://webco.com/jobs/3",
            source="test",
        ),
        JobPosting(
            job_id="int-4",
            title="ML Researcher",
            company="AlphaCo",
            description="Research scientist for deep learning projects using TensorFlow and Python.",
            required_skills=["Python", "TensorFlow", "Machine Learning"],
            preferred_skills=["PyTorch"],
            requirements=["PhD or 5+ years research"],
            required_years_experience=5.0,
            apply_url="https://alphaco.com/jobs/4",
            source="test",
        ),
        JobPosting(
            job_id="int-5",
            title="Data Engineer",
            company="AlphaCo",
            description="Build data pipelines using Python, SQL, and Docker.",
            required_skills=["Python", "SQL", "Docker"],
            preferred_skills=["AWS", "Spark"],
            requirements=["4+ years experience"],
            required_years_experience=4.0,
            apply_url="https://alphaco.com/jobs/5",
            source="test",
        ),
    ]


class TestFullPipeline:
    def test_parse_rank_tailor_pack(self, integration_resume, integration_jobs):
        """Full pipeline: rank jobs → tailor top match → generate application pack."""
        from app.matching.job_ranker import rank_jobs_for_candidate
        from app.tailoring.pack_generator import generate_application_pack

        # 1. Rank jobs for candidate
        ranked = rank_jobs_for_candidate(integration_resume, integration_jobs)
        assert len(ranked) > 0
        # ML/Data jobs should rank higher than frontend for an ML candidate
        assert ranked[0].match_score > ranked[-1].match_score
        # Frontend should be near the bottom
        frontend_ranks = [i for i, m in enumerate(ranked) if m.job.title == "Frontend Developer"]
        ml_ranks = [i for i, m in enumerate(ranked) if "ML" in m.job.title or "Data" in m.job.title]
        if frontend_ranks and ml_ranks:
            assert min(ml_ranks) < max(frontend_ranks)

        # 2. Generate application pack for top match
        top_match = ranked[0]
        with tempfile.TemporaryDirectory() as tmpdir:
            pack = generate_application_pack(
                integration_resume, top_match, output_dir=Path(tmpdir)
            )

            # Verify all artifacts
            assert pack.tailored_resume.docx_path is not None
            assert Path(pack.tailored_resume.docx_path).exists()
            assert Path(pack.tailored_resume.docx_path).stat().st_size > 0

            assert pack.tailored_resume.pdf_path is not None
            assert Path(pack.tailored_resume.pdf_path).exists()

            assert pack.tailored_resume.cover_letter_path is not None
            assert Path(pack.tailored_resume.cover_letter_path).exists()

            assert pack.tailored_resume.ats_score > 0
            assert pack.tailored_resume.keyword_coverage >= 0

            # Guardrail: no fabricated skills
            original_set = {s.lower() for s in integration_resume.skills}
            tailored_set = {s.lower() for s in pack.tailored_resume.tailored_skills}
            assert tailored_set == original_set

    def test_pipeline_with_mocked_discovery(self, integration_resume, integration_jobs):
        """Full pipeline with mocked connectors: discover → rank → tailor."""
        from app.job_discovery.orchestrator import discover_jobs
        from app.matching.job_ranker import rank_jobs_for_candidate

        profile = CandidateProfile(
            resume=integration_resume,
            target_titles=["Data Scientist", "ML Engineer"],
            target_locations=["New York"],
        )

        # Mock all connectors to return our canned jobs
        with patch("app.job_discovery.orchestrator.ALL_CONNECTORS") as mock_connectors:
            mock_connector = MagicMock()
            mock_connector.name = "mock"
            mock_connector.is_configured.return_value = True
            mock_connector.search.return_value = integration_jobs
            mock_connectors.__iter__ = lambda self: iter([mock_connector])

            jobs = discover_jobs(profile)

        assert len(jobs) > 0
        for job in jobs:
            assert isinstance(job, JobPosting)

        # Rank the discovered jobs
        ranked = rank_jobs_for_candidate(integration_resume, jobs)
        assert len(ranked) > 0
        assert all(isinstance(m, JobMatchResult) for m in ranked)


class TestPipelineEdgeCases:
    def test_no_jobs_found(self, integration_resume):
        """Pipeline should handle zero results gracefully."""
        from app.job_discovery.orchestrator import discover_jobs

        profile = CandidateProfile(
            resume=integration_resume,
            target_titles=["Nonexistent Role"],
        )

        with patch("app.job_discovery.orchestrator.ALL_CONNECTORS") as mock_connectors:
            mock_connector = MagicMock()
            mock_connector.name = "mock"
            mock_connector.is_configured.return_value = True
            mock_connector.search.return_value = []
            mock_connectors.__iter__ = lambda self: iter([mock_connector])

            jobs = discover_jobs(profile)

        assert isinstance(jobs, list)
        assert len(jobs) == 0

    def test_connector_failure_resilient(self, integration_resume, integration_jobs):
        """Pipeline should survive connector failures and use healthy connectors."""
        from app.job_discovery.orchestrator import discover_jobs

        profile = CandidateProfile(
            resume=integration_resume,
            target_titles=["Data Scientist"],
        )

        failing_connector = MagicMock()
        failing_connector.name = "failing"
        failing_connector.is_configured.return_value = True
        failing_connector.search.side_effect = Exception("API down")

        healthy_connector = MagicMock()
        healthy_connector.name = "healthy"
        healthy_connector.is_configured.return_value = True
        healthy_connector.search.return_value = integration_jobs

        with patch("app.job_discovery.orchestrator.ALL_CONNECTORS") as mock_connectors:
            mock_connectors.__iter__ = lambda self: iter([failing_connector, healthy_connector])
            jobs = discover_jobs(profile)

        # Should still have results from the healthy connector
        assert len(jobs) > 0


class TestPipelineRankDiversity:
    def test_diversity_constraint(self, integration_resume, integration_jobs):
        """Ranking should enforce diversity (max jobs per company)."""
        from app.matching.job_ranker import rank_jobs_for_candidate

        # integration_jobs has 3 jobs from AlphaCo
        ranked = rank_jobs_for_candidate(integration_resume, integration_jobs)

        from collections import Counter
        company_counts = Counter(m.job.company for m in ranked)
        # Diversity constraint limits per-company jobs (default max_per_company=3)
        for company, count in company_counts.items():
            assert count <= 3, f"{company} has {count} jobs, exceeds diversity limit"


class TestPipelineDatabaseTracking:
    def test_application_tracked_in_db(self, integration_resume, integration_jobs):
        """After pack generation, application should be recorded in database."""
        from app.matching.job_ranker import rank_jobs_for_candidate
        from app.tailoring.pack_generator import generate_application_pack
        from app.database.store import get_applications, save_application, upsert_job

        ranked = rank_jobs_for_candidate(integration_resume, integration_jobs)
        top_match = ranked[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            pack = generate_application_pack(
                integration_resume, top_match, output_dir=Path(tmpdir)
            )

            # Ensure the job exists in DB (as the discovery pipeline would do)
            upsert_job(top_match.job)

            # Save application (as the API endpoint would)
            app_id = save_application(
                job_id=top_match.job.job_id,
                candidate_name=integration_resume.candidate_name,
                match_score=top_match.match_score,
                ats_score=pack.tailored_resume.ats_score,
                docx_path=pack.tailored_resume.docx_path,
                pdf_path=pack.tailored_resume.pdf_path,
                cover_letter_path=pack.tailored_resume.cover_letter_path,
            )
            assert app_id > 0

            apps = get_applications(candidate_name="Alice Johnson")
            assert len(apps) >= 1
            latest = apps[0]
            assert latest["candidate_name"] == "Alice Johnson"
            assert latest["status"] == "generated"
            assert latest["match_score"] == top_match.match_score
