"""APScheduler engine for periodic job discovery."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.api.schemas import CandidateProfile
from app.models.config import config

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    """Return the singleton scheduler instance.

    Uses in-memory jobstore — jobs are re-synced from the SQLite
    scheduled_profiles table on every startup via _sync_profiles_to_scheduler().
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 3600,
            },
        )
    return _scheduler


def start_scheduler() -> None:
    """Start the scheduler if enabled in config."""
    if not config.scheduler_enabled:
        logger.info("Scheduler is disabled (SCHEDULER_ENABLED=false)")
        return
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")
        _sync_profiles_to_scheduler()


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
    _scheduler = None


def _sync_profiles_to_scheduler() -> None:
    """Load all active scheduled profiles from DB and ensure each has
    a corresponding APScheduler job. Called on startup."""
    from app.database.store import get_scheduled_profiles

    profiles = get_scheduled_profiles(active_only=True)
    scheduler = get_scheduler()

    for profile_row in profiles:
        job_id = f"scheduled_discovery_{profile_row['id']}"
        existing = scheduler.get_job(job_id)
        if existing is None:
            scheduler.add_job(
                func=run_scheduled_discovery,
                trigger=IntervalTrigger(minutes=profile_row["interval_minutes"]),
                id=job_id,
                args=[profile_row["id"]],
                replace_existing=True,
            )
            logger.info(
                "Scheduled job '%s' every %d min",
                job_id,
                profile_row["interval_minutes"],
            )


def add_profile_job(profile_id: int, interval_minutes: int) -> None:
    """Add or replace an APScheduler job for a specific profile."""
    scheduler = get_scheduler()
    job_id = f"scheduled_discovery_{profile_id}"
    scheduler.add_job(
        func=run_scheduled_discovery,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id=job_id,
        args=[profile_id],
        replace_existing=True,
    )


def remove_profile_job(profile_id: int) -> None:
    """Remove the APScheduler job for a profile (when deactivated or deleted)."""
    scheduler = get_scheduler()
    job_id = f"scheduled_discovery_{profile_id}"
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass  # Job may not exist


def run_scheduled_discovery(profile_id: int) -> None:
    """Execute a discovery run for a single scheduled profile.

    This is the function APScheduler calls on each tick.
    """
    from app.database.store import (
        create_alert,
        get_known_job_ids,
        get_scheduled_profile,
        update_scheduled_profile,
        upsert_jobs,
    )
    from app.job_discovery.orchestrator import discover_jobs
    from app.matching.job_ranker import rank_jobs_for_candidate

    profile_row = get_scheduled_profile(profile_id)
    if not profile_row or not profile_row["is_active"]:
        logger.info("Skipping inactive/missing profile %d", profile_id)
        return

    profile = CandidateProfile.model_validate_json(profile_row["profile_json"])

    # Snapshot existing job_ids BEFORE discovery
    known_ids = get_known_job_ids()

    logger.info(
        "Running scheduled discovery for profile %d ('%s')",
        profile_id,
        profile_row["profile_name"],
    )

    try:
        jobs = discover_jobs(profile)
    except Exception:
        logger.exception("Scheduled discovery failed for profile %d", profile_id)
        update_scheduled_profile(
            profile_id, last_run_at=datetime.now(timezone.utc).isoformat()
        )
        return

    if not jobs:
        update_scheduled_profile(
            profile_id, last_run_at=datetime.now(timezone.utc).isoformat()
        )
        return

    # Persist all discovered jobs
    upsert_jobs(jobs)

    # Identify truly new jobs (not previously in DB)
    new_jobs = [j for j in jobs if j.job_id not in known_ids]
    logger.info(
        "Scheduled run profile %d: %d total, %d new",
        profile_id,
        len(jobs),
        len(new_jobs),
    )

    if new_jobs:
        # Rank new jobs against the profile's resume
        ranked = rank_jobs_for_candidate(profile.resume, new_jobs)

        # Create alerts for high-match new jobs
        threshold = config.scheduler_match_threshold
        max_alerts = config.scheduler_max_alerts_per_run
        alert_count = 0

        for match_result in ranked:
            if match_result.match_score >= threshold and alert_count < max_alerts:
                create_alert(
                    profile_id=profile_id,
                    job_id=match_result.job.job_id,
                    match_score=match_result.match_score,
                    recommendation=match_result.recommendation,
                )
                alert_count += 1

        logger.info(
            "Created %d alerts for profile %d (threshold=%.1f)",
            alert_count,
            profile_id,
            threshold,
        )

    update_scheduled_profile(
        profile_id, last_run_at=datetime.now(timezone.utc).isoformat()
    )
