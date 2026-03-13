from __future__ import annotations

from datetime import datetime, timezone

from app.api.schemas import CandidateProfile, JobDiscoveryResult, JobPosting
from app.core.logging import get_logger
from app.job_discovery.cache import get_cached, set_cache
from app.job_discovery.deduplicator import deduplicate_jobs
from app.job_discovery.normalizer import normalize_jobs
from app.job_discovery.query_generator import generate_queries
from app.job_discovery.tavily_connector import TavilyConnector
from app.models.config import config

logger = get_logger(__name__)

# Active connectors — Tavily only for now
ALL_CONNECTORS = [
    TavilyConnector(),
]


def discover_jobs(profile: CandidateProfile) -> list[JobPosting]:
    """Main job discovery pipeline.

    1. Generate search queries from candidate profile
    2. Fan out to all configured connectors
    3. Normalize and enrich results
    4. Deduplicate
    5. Return corpus
    """
    # 1. Generate queries
    queries = generate_queries(profile)
    if not queries:
        logger.warning("No search queries generated from profile")
        return []

    # Determine locations to search
    locations = profile.target_locations or []
    if not locations and profile.resume.location:
        locations = [profile.resume.location]
    if not locations:
        locations = [""]

    # 2. Fan out to connectors
    active_connectors = [c for c in ALL_CONNECTORS if c.is_configured()]
    if not active_connectors:
        logger.warning("No job connectors configured. Set API keys in .env")
        return []

    logger.info(
        "Discovering jobs: %d queries x %d locations x %d connectors",
        len(queries), len(locations), len(active_connectors),
    )

    all_jobs: list[JobPosting] = []
    max_results = config.job_discovery_max_results
    per_connector_limit = max(max_results // len(active_connectors), 20)

    for connector in active_connectors:
        connector_jobs: list[JobPosting] = []
        for query in queries:
            for location in locations:
                # Check cache first
                cached = get_cached(connector.name, query, location)
                if cached is not None:
                    connector_jobs.extend(cached)
                    logger.debug("Cache hit: %s/%s/%s (%d jobs)", connector.name, query, location, len(cached))
                else:
                    # Fetch from API
                    try:
                        jobs = connector.search(query, location)
                        set_cache(connector.name, query, location, jobs)
                        connector_jobs.extend(jobs)
                    except Exception as e:
                        logger.warning("Connector %s failed for '%s': %s", connector.name, query, e)

                if len(connector_jobs) >= per_connector_limit:
                    break
            if len(connector_jobs) >= per_connector_limit:
                break
        all_jobs.extend(connector_jobs)
        logger.info("Connector %s returned %d jobs", connector.name, len(connector_jobs))

    logger.info("Raw job corpus: %d postings from %d connectors", len(all_jobs), len(active_connectors))

    # 3. Normalize
    normalized = normalize_jobs(all_jobs)

    # 4. Deduplicate
    unique = deduplicate_jobs(normalized)

    logger.info("Final job corpus: %d unique postings (from %d raw)", len(unique), len(all_jobs))
    return unique


def discover_jobs_async(profile: CandidateProfile, task_id: str) -> None:
    """Run job discovery in background, updating task progress as it goes."""
    from app.job_discovery.task_store import update_task
    from app.matching.job_ranker import rank_jobs_for_candidate

    try:
        update_task(task_id, status="running", progress=0.05, message="Generating search queries")

        # 1. Generate queries
        queries = generate_queries(profile)
        if not queries:
            update_task(task_id, status="completed", progress=1.0, message="No queries generated",
                        result=JobDiscoveryResult(),
                        completed_at=datetime.now(timezone.utc).isoformat())
            return

        update_task(task_id, progress=0.10, message=f"Generated {len(queries)} queries")

        locations = profile.target_locations or []
        if not locations and profile.resume.location:
            locations = [profile.resume.location]
        if not locations:
            locations = [""]

        active_connectors = [c for c in ALL_CONNECTORS if c.is_configured()]
        if not active_connectors:
            update_task(task_id, status="completed", progress=1.0,
                        message="No connectors configured",
                        result=JobDiscoveryResult(),
                        completed_at=datetime.now(timezone.utc).isoformat())
            return

        # 2. Fan out to connectors with progress
        all_jobs: list[JobPosting] = []
        max_results = config.job_discovery_max_results
        per_connector_limit = max(max_results // len(active_connectors), 20)
        total_steps = len(active_connectors) * len(queries) * len(locations)
        step_count = 0

        for i, connector in enumerate(active_connectors):
            connector_jobs: list[JobPosting] = []
            for query in queries:
                for location in locations:
                    step_count += 1
                    progress = 0.10 + (0.70 * step_count / total_steps)
                    update_task(task_id, progress=progress,
                                message=f"Searching {connector.name}: '{query}'...")

                    cached = get_cached(connector.name, query, location)
                    if cached is not None:
                        connector_jobs.extend(cached)
                        continue
                    try:
                        jobs = connector.search(query, location)
                        set_cache(connector.name, query, location, jobs)
                        connector_jobs.extend(jobs)
                    except Exception as e:
                        logger.warning("Connector %s failed for '%s': %s", connector.name, query, e)

                    if len(connector_jobs) >= per_connector_limit:
                        break
                if len(connector_jobs) >= per_connector_limit:
                    break
            all_jobs.extend(connector_jobs)
            logger.info("Connector %s returned %d jobs", connector.name, len(connector_jobs))

        # 3. Normalize
        update_task(task_id, progress=0.85, message=f"Normalizing {len(all_jobs)} jobs")
        normalized = normalize_jobs(all_jobs)

        # 4. Deduplicate
        update_task(task_id, progress=0.90, message="Deduplicating")
        unique = deduplicate_jobs(normalized)

        # 5. Rank
        update_task(task_id, progress=0.95, message=f"Ranking {len(unique)} jobs")
        ranked = rank_jobs_for_candidate(profile.resume, unique)

        result = JobDiscoveryResult(
            total_found=len(all_jobs),
            total_after_dedup=len(unique),
            ranked_jobs=ranked,
        )

        update_task(task_id, status="completed", progress=1.0,
                    message=f"Done: {len(ranked)} jobs ranked",
                    result=result,
                    completed_at=datetime.now(timezone.utc).isoformat())

    except Exception as e:
        logger.error("Async discovery failed: %s", e, exc_info=True)
        update_task(task_id, status="failed", message=str(e),
                    completed_at=datetime.now(timezone.utc).isoformat())
