"""Tavily web search connector for discovering jobs across the open web."""
from __future__ import annotations

import hashlib
import re
import time

from app.api.schemas import JobPosting
from app.core.logging import get_logger
from app.job_discovery.base_connector import BaseJobConnector
from app.models.config import config

logger = get_logger(__name__)


class TavilyConnector(BaseJobConnector):
    """Search the open web for job postings using Tavily API."""

    name = "tavily"

    def is_configured(self) -> bool:
        return bool(config.tavily_api_key)

    def search(self, keywords: str, location: str = "", **kwargs) -> list[JobPosting]:
        if not self.is_configured():
            logger.warning("Tavily API key not configured")
            return []

        from tavily import TavilyClient

        client = TavilyClient(api_key=config.tavily_api_key)
        max_results = kwargs.get("max_results", 20)

        # Build a job-focused search query
        query = f"{keywords} jobs"
        if location:
            query += f" {location}"

        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
            )
        except Exception as e:
            logger.warning("Tavily search error: %s", e)
            return []

        results = response.get("results", [])
        all_jobs: list[JobPosting] = []

        for item in results:
            url = item.get("url", "")
            raw_title = item.get("title", "")
            content = item.get("content", "")

            if not raw_title:
                continue

            title, company = _parse_title(raw_title)
            if not title:
                continue

            job_id = hashlib.md5(url.encode()).hexdigest()

            all_jobs.append(JobPosting(
                job_id=job_id,
                title=title,
                company=company,
                location=location or None,
                description=content[:1000],
                apply_url=url,
                source="tavily",
                raw_text=content,
            ))

        logger.info("Tavily: found %d jobs for '%s'", len(all_jobs), keywords)
        time.sleep(1)  # rate limiting
        return all_jobs


def _parse_title(raw_title: str) -> tuple[str, str]:
    """Extract job title and company from a web search result title.

    Common patterns:
    - "Software Engineer - Google | LinkedIn"
    - "Software Engineer at Google - Apply Now"
    - "Software Engineer, Google | Indeed"
    """
    # Strip common suffixes
    title = re.sub(r"\s*\|.*$", "", raw_title).strip()
    title = re.sub(r"\s*-\s*(Apply|LinkedIn|Indeed|Glassdoor|ZipRecruiter).*$", "", title, flags=re.IGNORECASE).strip()

    company = ""

    # Try "Title - Company" pattern
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        title = parts[0].strip()
        company = parts[1].strip()
    # Try "Title at Company" pattern
    elif " at " in title.lower():
        idx = title.lower().rfind(" at ")
        company = title[idx + 4:].strip()
        title = title[:idx].strip()

    return title, company
