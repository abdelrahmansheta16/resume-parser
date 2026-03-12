"""Tests for the job ranking engine."""
from __future__ import annotations

import pytest

from app.api.schemas import JobPosting, ParsedResume, ExperienceSchema, EducationSchema
from app.matching.job_ranker import job_to_jd, rank_jobs_for_candidate, score_job_for_candidate


@pytest.fixture
def candidate():
    return ParsedResume(
        candidate_name="Alice Johnson",
        email="alice@example.com",
        skills=["Python", "Machine Learning", "TensorFlow", "SQL", "Docker", "AWS"],
        experience=[
            ExperienceSchema(
                job_title="Senior Data Scientist",
                company="TechCo",
                start_date="2020-01",
                end_date="2024-01",
                duration_months=48,
                description=[
                    "Built ML models for customer churn prediction using TensorFlow",
                    "Managed team of 3 junior data scientists",
                    "Deployed models to production using Docker and AWS",
                ],
            ),
            ExperienceSchema(
                job_title="Data Scientist",
                company="StartupInc",
                start_date="2018-01",
                end_date="2020-01",
                duration_months=24,
                description=[
                    "Developed recommendation engine using Python and SQL",
                    "Increased user engagement by 25%",
                ],
            ),
        ],
        education=[
            EducationSchema(
                degree="Master",
                field_of_study="Computer Science",
                institution="MIT",
            ),
        ],
        total_years_experience=6.0,
    )


@pytest.fixture
def jobs():
    return [
        JobPosting(
            job_id="1",
            title="Senior Data Scientist",
            company="BigTech",
            description="Looking for senior DS with ML experience",
            required_skills=["Python", "Machine Learning", "SQL"],
            preferred_skills=["TensorFlow", "Docker"],
            required_years_experience=5.0,
            apply_url="https://bigtech.com/apply",
        ),
        JobPosting(
            job_id="2",
            title="Frontend Developer",
            company="WebCo",
            description="React developer needed for UI work",
            required_skills=["React", "JavaScript", "CSS"],
            preferred_skills=["TypeScript", "Next.js"],
            required_years_experience=3.0,
        ),
        JobPosting(
            job_id="3",
            title="ML Engineer",
            company="AI Labs",
            description="ML engineer for production systems",
            required_skills=["Python", "TensorFlow", "Docker"],
            preferred_skills=["AWS", "Kubernetes"],
            required_years_experience=4.0,
            apply_url="https://ailabs.com/apply",
        ),
        JobPosting(
            job_id="4",
            title="Data Analyst",
            company="BigTech",
            description="Data analyst with SQL skills",
            required_skills=["SQL", "Python"],
            preferred_skills=["Tableau"],
            required_years_experience=2.0,
            apply_url="https://bigtech.com/apply/analyst",
        ),
        JobPosting(
            job_id="5",
            title="Junior Data Scientist",
            company="BigTech",
            description="Entry level DS position",
            required_skills=["Python", "SQL"],
            required_years_experience=0.0,
            apply_url="https://bigtech.com/apply/junior",
        ),
        JobPosting(
            job_id="6",
            title="Senior ML Engineer",
            company="BigTech",
            description="Senior ML position",
            required_skills=["Python", "TensorFlow", "AWS"],
            required_years_experience=5.0,
            apply_url="https://bigtech.com/apply/senior-ml",
        ),
    ]


class TestJobToJD:
    def test_converts_job_posting(self):
        job = JobPosting(
            job_id="1",
            title="Data Scientist",
            company="Acme",
            description="A data science role",
            required_skills=["Python", "SQL"],
            preferred_skills=["TensorFlow"],
            required_years_experience=3.0,
            education_requirements=["Bachelor"],
        )
        jd = job_to_jd(job)
        assert jd.title == "Data Scientist"
        assert "Python" in jd.required_skills
        assert "TensorFlow" in jd.preferred_skills
        assert jd.required_years_experience == 3.0


class TestScoreJob:
    def test_good_match_scores_high(self, candidate):
        job = JobPosting(
            job_id="1",
            title="Senior Data Scientist",
            company="Acme",
            description="Senior DS role requiring Python and ML",
            required_skills=["Python", "Machine Learning", "SQL"],
            preferred_skills=["TensorFlow"],
            required_years_experience=5.0,
        )
        result = score_job_for_candidate(candidate, job)
        assert result.match_score > 50
        assert "Python" in result.matched_skills or "python" in [s.lower() for s in result.matched_skills]

    def test_poor_match_scores_low(self, candidate):
        job = JobPosting(
            job_id="2",
            title="Frontend Developer",
            company="WebCo",
            description="React developer needed",
            required_skills=["React", "JavaScript", "CSS", "Vue.js"],
            required_years_experience=3.0,
        )
        result = score_job_for_candidate(candidate, job)
        # Should have low skill match since candidate doesn't have React/JS/CSS
        assert result.match_score < 70

    def test_result_has_explanation(self, candidate):
        job = JobPosting(
            job_id="1",
            title="Data Scientist",
            company="Acme",
            description="DS role",
            required_skills=["Python"],
        )
        result = score_job_for_candidate(candidate, job)
        assert len(result.explanation) > 0


class TestRankJobs:
    def test_ranking_order(self, candidate, jobs):
        ranked = rank_jobs_for_candidate(candidate, jobs)
        # Should be sorted by score descending
        for i in range(len(ranked) - 1):
            assert ranked[i].match_score >= ranked[i + 1].match_score

    def test_top_n_limit(self, candidate, jobs):
        ranked = rank_jobs_for_candidate(candidate, jobs, top_n=3)
        assert len(ranked) <= 3

    def test_diversity_constraint(self, candidate, jobs):
        ranked = rank_jobs_for_candidate(candidate, jobs, max_per_company=2)
        # Count jobs per company
        company_counts: dict[str, int] = {}
        for r in ranked:
            company_counts[r.job.company] = company_counts.get(r.job.company, 0) + 1
        for count in company_counts.values():
            assert count <= 2

    def test_empty_jobs(self, candidate):
        ranked = rank_jobs_for_candidate(candidate, [])
        assert ranked == []

    def test_ml_job_ranks_higher_than_frontend(self, candidate, jobs):
        ranked = rank_jobs_for_candidate(candidate, jobs)
        # Find positions of ML and frontend jobs
        ml_positions = [i for i, r in enumerate(ranked) if "ML" in r.job.title or "Data Scientist" in r.job.title]
        frontend_positions = [i for i, r in enumerate(ranked) if "Frontend" in r.job.title]
        if ml_positions and frontend_positions:
            # At least one ML job should rank higher than frontend
            assert min(ml_positions) < min(frontend_positions)
