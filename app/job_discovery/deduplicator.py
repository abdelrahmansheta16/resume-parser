from __future__ import annotations

from urllib.parse import urlparse

from rapidfuzz import fuzz

from app.api.schemas import JobPosting
from app.core.logging import get_logger

logger = get_logger(__name__)


def _normalize_url(url: str | None) -> str:
    """Normalize a URL for comparison."""
    if not url:
        return ""
    parsed = urlparse(url.lower().strip())
    return f"{parsed.netloc}{parsed.path}".rstrip("/")


def deduplicate_jobs(jobs: list[JobPosting]) -> list[JobPosting]:
    """Remove duplicate job postings.

    Phase 1: Exact apply_url match
    Phase 2: Fuzzy title + company + location match (>85%)
    """
    seen_urls: set[str] = set()
    seen_signatures: list[str] = []
    unique: list[JobPosting] = []

    for job in jobs:
        # Phase 1: URL dedup
        norm_url = _normalize_url(job.apply_url)
        if norm_url and norm_url in seen_urls:
            continue
        if norm_url:
            seen_urls.add(norm_url)

        # Phase 2: Fuzzy signature dedup
        signature = f"{job.title} | {job.company} | {job.location or ''}".lower()
        is_dup = False
        for existing in seen_signatures:
            if fuzz.ratio(signature, existing) > 85:
                is_dup = True
                break

        if not is_dup:
            seen_signatures.append(signature)
            unique.append(job)

    removed = len(jobs) - len(unique)
    if removed:
        logger.info("Dedup: removed %d duplicates, %d unique jobs remain", removed, len(unique))
    return unique
