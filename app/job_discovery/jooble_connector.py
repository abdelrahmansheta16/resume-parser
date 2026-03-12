from __future__ import annotations

import hashlib
import time

import requests

from app.api.schemas import JobPosting
from app.core.logging import get_logger
from app.job_discovery.base_connector import BaseJobConnector

from app.models.config import config

logger = get_logger(__name__)

JOOBLE_API_URL = "https://jooble.org/api/{api_key}"


class JoobleConnector(BaseJobConnector):
    name = "jooble"

    def is_configured(self) -> bool:
        return bool(config.jooble_api_key)

    def search(self, keywords: str, location: str = "", **kwargs) -> list[JobPosting]:
        if not self.is_configured():
            logger.warning("Jooble API key not configured")
            return []

        max_pages = kwargs.get("max_pages", 5)
        results_per_page = kwargs.get("results_per_page", 20)
        all_jobs: list[JobPosting] = []

        url = JOOBLE_API_URL.format(api_key=config.jooble_api_key)

        for page in range(1, max_pages + 1):
            payload = {
                "keywords": keywords,
                "location": location,
                "page": page,
                "ResultOnPage": results_per_page,
            }

            try:
                resp = self._request_post(url, json=payload)
                data = resp.json()
            except requests.RequestException as e:
                logger.warning("Jooble API error (page %d): %s", page, e)
                break

            jobs = data.get("jobs", [])
            if not jobs:
                break

            for raw in jobs:
                job_id = raw.get("id", hashlib.md5(
                    f"{raw.get('title', '')}{raw.get('company', '')}".encode()
                ).hexdigest())

                all_jobs.append(JobPosting(
                    job_id=str(job_id),
                    title=raw.get("title", ""),
                    company=raw.get("company", ""),
                    location=raw.get("location", ""),
                    description=raw.get("snippet", ""),
                    salary_range=raw.get("salary", None),
                    apply_url=raw.get("link", None),
                    posting_date=raw.get("updated", None),
                    employment_type=raw.get("type", None),
                    source="jooble",
                    raw_text=raw.get("snippet", ""),
                ))

            logger.debug("Jooble page %d: %d jobs", page, len(jobs))
            total = data.get("totalCount", 0)
            if page * results_per_page >= total:
                break

            time.sleep(1)  # rate limiting

        logger.info("Jooble: found %d jobs for '%s'", len(all_jobs), keywords)
        return all_jobs
