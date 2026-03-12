"""Tests for the Supabase-backed database module."""
from __future__ import annotations

import pytest

from app.api.schemas import JobPosting


@pytest.fixture
def sample_job():
    return JobPosting(
        job_id="test-1",
        title="Data Scientist",
        company="Acme Corp",
        description="Looking for a data scientist",
        apply_url="https://acme.com/jobs/1",
        location="New York",
        source="test",
        required_skills=["Python", "SQL"],
    )


class TestDatabaseInit:
    def test_init_verifies_connection(self, mock_supabase):
        from app.database.store import init_db
        # Should not raise with mock
        init_db()


class TestJobOperations:
    def test_upsert_and_get(self, sample_job):
        from app.database.store import upsert_job, get_job
        upsert_job(sample_job)
        retrieved = get_job("test-1")
        assert retrieved is not None
        assert retrieved.title == "Data Scientist"
        assert retrieved.company == "Acme Corp"
        assert "Python" in retrieved.required_skills

    def test_upsert_updates_existing(self, sample_job):
        from app.database.store import upsert_job, get_job
        upsert_job(sample_job)
        # Update with new description
        updated = sample_job.model_copy()
        updated.description = "Updated description"
        upsert_job(updated)
        retrieved = get_job("test-1")
        assert retrieved.description == "Updated description"

    def test_get_nonexistent(self):
        from app.database.store import get_job
        assert get_job("nonexistent-id") is None

    def test_search_by_source(self, sample_job):
        from app.database.store import upsert_job, search_jobs
        upsert_job(sample_job)
        results = search_jobs(source="test")
        assert len(results) >= 1
        assert results[0].source == "test"

    def test_search_by_keyword(self, sample_job):
        from app.database.store import upsert_job, search_jobs
        upsert_job(sample_job)
        results = search_jobs(keyword="Data Scientist")
        assert len(results) >= 1

    def test_bulk_upsert(self):
        from app.database.store import upsert_jobs, search_jobs
        jobs = [
            JobPosting(job_id=f"bulk-{i}", title=f"Role {i}", company="BulkCo",
                       description="desc", source="bulk")
            for i in range(5)
        ]
        count = upsert_jobs(jobs)
        assert count == 5
        results = search_jobs(source="bulk")
        assert len(results) == 5


class TestApplicationTracking:
    def test_save_and_get_application(self, sample_job):
        from app.database.store import upsert_job, save_application, get_applications
        upsert_job(sample_job)
        app_id = save_application("test-1", "Jane Doe", match_score=85.0, ats_score=72.0)
        assert app_id > 0
        apps = get_applications(candidate_name="Jane Doe")
        assert len(apps) >= 1
        assert apps[0]["match_score"] == 85.0

    def test_update_status(self, sample_job):
        from app.database.store import upsert_job, save_application, update_application_status, get_applications
        upsert_job(sample_job)
        app_id = save_application("test-1", "Bob", match_score=70.0)
        assert update_application_status(app_id, "applied") is True
        apps = get_applications(candidate_name="Bob")
        assert apps[0]["status"] == "applied"

    def test_update_nonexistent(self):
        from app.database.store import update_application_status
        assert update_application_status(99999, "applied") is False

    def test_filter_by_status(self, sample_job):
        from app.database.store import upsert_job, save_application, get_applications
        upsert_job(sample_job)
        save_application("test-1", "Alice", match_score=90.0)
        apps = get_applications(status="generated")
        assert all(a["status"] == "generated" for a in apps)


class TestSearchLog:
    def test_log_search(self):
        from app.database.store import log_search
        # Should not raise
        log_search("jooble", "python developer", "New York", 42)
