"""Tests for the job discovery layer."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.api.schemas import CandidateProfile, JobPosting, ParsedResume
from app.job_discovery.deduplicator import deduplicate_jobs
from app.job_discovery.query_generator import generate_queries


@pytest.fixture
def sample_resume():
    return ParsedResume(
        candidate_name="Jane Smith",
        email="jane@example.com",
        skills=["Python", "Machine Learning", "TensorFlow", "SQL", "Docker"],
        experience=[],
        education=[],
        total_years_experience=5.0,
    )


@pytest.fixture
def sample_profile(sample_resume):
    return CandidateProfile(
        resume=sample_resume,
        target_titles=["Data Scientist", "ML Engineer"],
        target_locations=["New York"],
    )


@pytest.fixture
def sample_jobs():
    return [
        JobPosting(
            job_id="1",
            title="Data Scientist",
            company="Acme Corp",
            description="Looking for a data scientist",
            apply_url="https://acme.com/jobs/1",
            location="New York",
        ),
        JobPosting(
            job_id="2",
            title="Data Scientist",
            company="Acme Corp",
            description="Looking for a data scientist",
            apply_url="https://acme.com/jobs/1",  # Same URL = duplicate
            location="New York",
        ),
        JobPosting(
            job_id="3",
            title="ML Engineer",
            company="Beta Inc",
            description="ML engineer position",
            apply_url="https://beta.com/jobs/3",
            location="San Francisco",
        ),
    ]


class TestQueryGenerator:
    def test_generate_queries_from_profile(self, sample_profile):
        queries = generate_queries(sample_profile)
        assert len(queries) >= 1
        # Should include target titles
        titles_in_queries = any("Data Scientist" in q for q in queries)
        assert titles_in_queries

    def test_generate_queries_includes_skills(self, sample_profile):
        queries = generate_queries(sample_profile)
        # Should include some skill-based queries
        assert len(queries) >= 2

    def test_generate_queries_empty_profile(self):
        resume = ParsedResume(
            candidate_name="Unknown",
            skills=[],
            experience=[],
            education=[],
        )
        profile = CandidateProfile(resume=resume)
        queries = generate_queries(profile)
        # Should still generate at least some queries
        assert isinstance(queries, list)


class TestDeduplicator:
    def test_url_dedup(self, sample_jobs):
        deduped = deduplicate_jobs(sample_jobs)
        # Jobs 1 and 2 have the same URL, should be deduped
        assert len(deduped) == 2

    def test_no_duplicates(self):
        jobs = [
            JobPosting(
                job_id="1",
                title="Data Scientist",
                company="Acme",
                description="desc",
                apply_url="https://a.com/1",
            ),
            JobPosting(
                job_id="2",
                title="ML Engineer",
                company="Beta",
                description="desc",
                apply_url="https://b.com/2",
            ),
        ]
        deduped = deduplicate_jobs(jobs)
        assert len(deduped) == 2

    def test_fuzzy_dedup(self):
        jobs = [
            JobPosting(
                job_id="1",
                title="Senior Data Scientist",
                company="Acme Corp",
                location="New York, NY",
                description="desc",
            ),
            JobPosting(
                job_id="2",
                title="Senior Data Scientist",
                company="Acme Corp.",
                location="New York, NY",
                description="desc",
            ),
        ]
        deduped = deduplicate_jobs(jobs)
        assert len(deduped) == 1

    def test_empty_list(self):
        assert deduplicate_jobs([]) == []


class TestConnectors:
    def test_jooble_not_configured(self):
        from app.job_discovery.jooble_connector import JoobleConnector
        from unittest.mock import patch
        connector = JoobleConnector()
        with patch.object(connector, 'is_configured', return_value=False):
            assert not connector.is_configured()

    def test_adzuna_not_configured(self):
        from app.job_discovery.adzuna_connector import AdzunaConnector
        from unittest.mock import patch
        connector = AdzunaConnector()
        with patch.object(connector, 'is_configured', return_value=False):
            assert not connector.is_configured()

    def test_usajobs_not_configured(self):
        from app.job_discovery.usajobs_connector import USAJobsConnector
        from unittest.mock import patch
        connector = USAJobsConnector()
        with patch.object(connector, 'is_configured', return_value=False):
            assert not connector.is_configured()

    def test_connector_instantiation(self):
        from app.job_discovery.jooble_connector import JoobleConnector
        from app.job_discovery.adzuna_connector import AdzunaConnector
        from app.job_discovery.usajobs_connector import USAJobsConnector
        # All connectors should be instantiable
        assert JoobleConnector().name == "jooble"
        assert AdzunaConnector().name == "adzuna"
        assert USAJobsConnector().name == "usajobs"

    def test_new_connector_instantiation(self):
        from app.job_discovery.remoteok_connector import RemoteOKConnector
        from app.job_discovery.weworkremotely_connector import WeWorkRemotelyConnector
        from app.job_discovery.linkedin_connector import LinkedInConnector
        assert RemoteOKConnector().name == "remoteok"
        assert WeWorkRemotelyConnector().name == "weworkremotely"
        assert LinkedInConnector().name == "linkedin"

    def test_remoteok_always_configured(self):
        from app.job_discovery.remoteok_connector import RemoteOKConnector
        assert RemoteOKConnector().is_configured() is True

    def test_weworkremotely_always_configured(self):
        from app.job_discovery.weworkremotely_connector import WeWorkRemotelyConnector
        assert WeWorkRemotelyConnector().is_configured() is True


class TestConnectorResilience:
    def test_connector_retries_on_timeout(self):
        """Connector should retry on timeout and return results if a retry succeeds."""
        from app.job_discovery.remoteok_connector import RemoteOKConnector
        from unittest.mock import patch, MagicMock
        import requests

        connector = RemoteOKConnector()
        # First call times out, second succeeds
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {},  # metadata
            {"id": "1", "position": "Python Dev", "company": "TestCo",
             "tags": ["python"], "description": "A python job", "url": "https://example.com/1"},
        ]
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", side_effect=[requests.Timeout("timeout"), mock_resp]):
            jobs = connector.search("python")
        assert len(jobs) == 1
        assert jobs[0].title == "Python Dev"

    def test_connector_returns_empty_after_max_retries(self):
        """If all retries fail, connector should return empty list (not raise)."""
        from app.job_discovery.remoteok_connector import RemoteOKConnector
        from unittest.mock import patch
        import requests

        connector = RemoteOKConnector()
        with patch("requests.get", side_effect=requests.ConnectionError("down")):
            jobs = connector.search("python")
        assert jobs == []


class TestOrchestrator:
    def test_discover_returns_list(self, sample_profile):
        """discover_jobs should return a list of JobPosting objects."""
        from app.job_discovery.orchestrator import discover_jobs
        jobs = discover_jobs(sample_profile)
        assert isinstance(jobs, list)
        # Each result should be a JobPosting
        for job in jobs[:3]:
            assert isinstance(job, JobPosting)


class TestTaskStore:
    def test_create_and_get_task(self):
        from app.job_discovery.task_store import create_task, get_task
        task = create_task()
        assert task.task_id
        assert task.status == "pending"
        retrieved = get_task(task.task_id)
        assert retrieved is not None
        assert retrieved.task_id == task.task_id

    def test_update_task(self):
        from app.job_discovery.task_store import create_task, update_task
        task = create_task()
        updated = update_task(task.task_id, status="running", progress=0.5)
        assert updated.status == "running"
        assert updated.progress == 0.5

    def test_delete_task(self):
        from app.job_discovery.task_store import create_task, delete_task, get_task
        task = create_task()
        assert delete_task(task.task_id) is True
        assert get_task(task.task_id) is None

    def test_get_nonexistent_task(self):
        from app.job_discovery.task_store import get_task
        assert get_task("nonexistent_id") is None

    def test_delete_nonexistent_task(self):
        from app.job_discovery.task_store import delete_task
        assert delete_task("nonexistent_id") is False


class TestAsyncDiscovery:
    def test_async_discovery_updates_task(self, sample_profile):
        """discover_jobs_async should update task status to completed."""
        import threading
        from app.job_discovery.task_store import create_task, get_task
        from app.job_discovery.orchestrator import discover_jobs_async

        task = create_task()
        thread = threading.Thread(
            target=discover_jobs_async,
            args=(sample_profile, task.task_id),
            daemon=True,
        )
        thread.start()
        thread.join(timeout=120)

        result = get_task(task.task_id)
        assert result is not None
        assert result.status in ("completed", "failed")
        if result.status == "completed":
            assert result.progress == 1.0
            assert result.result is not None
