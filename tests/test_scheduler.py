"""Tests for scheduled job discovery: profiles, alerts, dedup, and engine."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.api.schemas import (
    CandidateProfile,
    ExperienceSchema,
    JobMatchResult,
    JobPosting,
    ParsedResume,
)
from app.database.store import (
    create_alert,
    delete_scheduled_profile,
    get_alerts,
    get_known_job_ids,
    get_scheduled_profile,
    get_scheduled_profiles,
    mark_alert_read,
    mark_all_alerts_read,
    save_scheduled_profile,
    update_scheduled_profile,
    upsert_job,
)


@pytest.fixture
def sample_resume():
    return ParsedResume(
        candidate_name="Test User",
        email="test@example.com",
        skills=["Python", "SQL", "Docker"],
        experience=[
            ExperienceSchema(
                job_title="Engineer",
                company="TestCo",
                start_date="2020-01",
                end_date="2024-01",
                duration_months=48,
                description=["Built things"],
            )
        ],
        education=[],
        total_years_experience=4.0,
        summary="An engineer.",
    )


@pytest.fixture
def sample_profile(sample_resume):
    return CandidateProfile(
        resume=sample_resume,
        target_titles=["Software Engineer"],
        target_locations=["Remote"],
    )


@pytest.fixture
def sample_jobs():
    uid = uuid.uuid4().hex[:8]
    return [
        JobPosting(
            job_id=f"sched-{uid}-1",
            title="Python Developer",
            company="AlphaCo",
            description="Python developer needed.",
            required_skills=["Python", "SQL"],
            source="test",
        ),
        JobPosting(
            job_id=f"sched-{uid}-2",
            title="DevOps Engineer",
            company="BetaInc",
            description="DevOps role with Docker and AWS.",
            required_skills=["Docker", "AWS"],
            source="test",
        ),
        JobPosting(
            job_id=f"sched-{uid}-3",
            title="Frontend Developer",
            company="GammaCo",
            description="React developer for web apps.",
            required_skills=["React", "TypeScript"],
            source="test",
        ),
    ]


class TestScheduledProfilesCRUD:
    def test_save_and_get_scheduled_profile(self, sample_profile):
        """CRUD roundtrip for scheduled profiles."""
        profile_id = save_scheduled_profile("My Search", sample_profile, 120)
        assert profile_id > 0

        row = get_scheduled_profile(profile_id)
        assert row is not None
        assert row["profile_name"] == "My Search"
        assert row["interval_minutes"] == 120
        assert row["is_active"] in (1, True)

        # Deserialize and verify
        restored = CandidateProfile.model_validate_json(row["profile_json"])
        assert restored.resume.candidate_name == "Test User"
        assert restored.target_titles == ["Software Engineer"]

    def test_list_scheduled_profiles(self, sample_profile):
        """List active profiles."""
        save_scheduled_profile("Active Profile", sample_profile, 360)
        pid2 = save_scheduled_profile("Inactive Profile", sample_profile, 360)
        update_scheduled_profile(pid2, is_active=False)

        active = get_scheduled_profiles(active_only=True)
        all_profiles = get_scheduled_profiles(active_only=False)

        active_names = [p["profile_name"] for p in active]
        all_names = [p["profile_name"] for p in all_profiles]

        assert "Active Profile" in active_names
        assert "Inactive Profile" not in active_names
        assert "Inactive Profile" in all_names

    def test_update_scheduled_profile(self, sample_profile):
        """Update fields on a scheduled profile."""
        pid = save_scheduled_profile("Original", sample_profile, 360)
        assert update_scheduled_profile(pid, profile_name="Updated", interval_minutes=60)

        row = get_scheduled_profile(pid)
        assert row["profile_name"] == "Updated"
        assert row["interval_minutes"] == 60

    def test_delete_scheduled_profile_cascades(self, sample_profile, sample_jobs):
        """Deleting a profile should also delete its alerts."""
        pid = save_scheduled_profile("To Delete", sample_profile, 360)
        # Create a job so the FK constraint is satisfied
        upsert_job(sample_jobs[0])
        create_alert(pid, sample_jobs[0].job_id, 85.0, "Great match")

        alerts_before = get_alerts(profile_id=pid)
        assert len(alerts_before) >= 1

        assert delete_scheduled_profile(pid)

        alerts_after = get_alerts(profile_id=pid)
        assert len(alerts_after) == 0
        assert get_scheduled_profile(pid) is None


class TestAlerts:
    def test_create_and_get_alerts(self, sample_profile, sample_jobs):
        """Create alerts and retrieve them."""
        pid = save_scheduled_profile("Alert Test", sample_profile, 360)
        upsert_job(sample_jobs[0])
        upsert_job(sample_jobs[1])

        aid1 = create_alert(pid, sample_jobs[0].job_id, 90.0, "Excellent")
        aid2 = create_alert(pid, sample_jobs[1].job_id, 65.0, "Good")
        assert aid1 > 0
        assert aid2 > 0

        alerts = get_alerts(profile_id=pid)
        assert len(alerts) >= 2
        scores = [a["match_score"] for a in alerts]
        assert 90.0 in scores
        assert 65.0 in scores

    def test_mark_alerts_read(self, sample_profile, sample_jobs):
        """Test mark single and mark all read."""
        pid = save_scheduled_profile("Read Test", sample_profile, 360)
        upsert_job(sample_jobs[0])
        upsert_job(sample_jobs[1])

        aid1 = create_alert(pid, sample_jobs[0].job_id, 80.0, "Good")
        aid2 = create_alert(pid, sample_jobs[1].job_id, 75.0, "Good")

        # Initially unread
        unread = get_alerts(profile_id=pid, unread_only=True)
        assert len(unread) >= 2

        # Mark one as read
        assert mark_alert_read(aid1)
        unread = get_alerts(profile_id=pid, unread_only=True)
        unread_ids = [a["id"] for a in unread]
        assert aid1 not in unread_ids
        assert aid2 in unread_ids

        # Mark all read
        count = mark_all_alerts_read(pid)
        assert count >= 1
        unread = get_alerts(profile_id=pid, unread_only=True)
        assert len(unread) == 0


class TestKnownJobIds:
    def test_get_known_job_ids(self, sample_jobs):
        """Verify snapshot of known job_ids."""
        for job in sample_jobs:
            upsert_job(job)

        known = get_known_job_ids()
        for job in sample_jobs:
            assert job.job_id in known


class TestScheduledDiscoveryRun:
    def test_run_creates_alerts_for_high_match(self, sample_profile, sample_jobs):
        """Scheduled run should create alerts for new high-match jobs."""
        from app.scheduler.engine import run_scheduled_discovery

        pid = save_scheduled_profile("Run Test", sample_profile, 360)

        mock_ranked = [
            JobMatchResult(job=sample_jobs[0], match_score=85.0, recommendation="Great"),
            JobMatchResult(job=sample_jobs[1], match_score=70.0, recommendation="Good"),
            JobMatchResult(job=sample_jobs[2], match_score=30.0, recommendation="Poor"),
        ]

        with patch("app.job_discovery.orchestrator.discover_jobs", return_value=sample_jobs), \
             patch("app.matching.job_ranker.rank_jobs_for_candidate", return_value=mock_ranked):
            run_scheduled_discovery(pid)

        alerts = get_alerts(profile_id=pid)
        alert_scores = [a["match_score"] for a in alerts]
        assert 85.0 in alert_scores
        assert 70.0 in alert_scores
        assert 30.0 not in alert_scores

        row = get_scheduled_profile(pid)
        assert row["last_run_at"] is not None

    def test_run_dedup_only_alerts_new_jobs(self, sample_profile, sample_jobs):
        """Only truly new jobs (not already in DB) should trigger alerts."""
        from app.scheduler.engine import run_scheduled_discovery

        pid = save_scheduled_profile("Dedup Test", sample_profile, 360)

        # Pre-populate job[0] as a known job
        upsert_job(sample_jobs[0])

        new_ranked = [
            JobMatchResult(job=sample_jobs[1], match_score=80.0, recommendation="Good"),
            JobMatchResult(job=sample_jobs[2], match_score=75.0, recommendation="OK"),
        ]

        with patch("app.job_discovery.orchestrator.discover_jobs", return_value=sample_jobs), \
             patch("app.matching.job_ranker.rank_jobs_for_candidate", return_value=new_ranked):
            run_scheduled_discovery(pid)

        alerts = get_alerts(profile_id=pid)
        alert_job_ids = [a["job_id"] for a in alerts]
        assert sample_jobs[0].job_id not in alert_job_ids
        assert sample_jobs[1].job_id in alert_job_ids
        assert sample_jobs[2].job_id in alert_job_ids

    def test_inactive_profile_skipped(self, sample_profile):
        """Inactive profiles should be skipped."""
        from app.scheduler.engine import run_scheduled_discovery

        pid = save_scheduled_profile("Inactive", sample_profile, 360)
        update_scheduled_profile(pid, is_active=False)

        with patch("app.job_discovery.orchestrator.discover_jobs") as mock_discover:
            run_scheduled_discovery(pid)

        mock_discover.assert_not_called()
