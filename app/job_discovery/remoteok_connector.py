from __future__ import annotations

import hashlib
import time

import requests

from app.api.schemas import JobPosting
from app.core.logging import get_logger
from app.job_discovery.base_connector import BaseJobConnector

logger = get_logger(__name__)

REMOTEOK_API_URL = "https://remoteok.com/api"


class RemoteOKConnector(BaseJobConnector):
    name = "remoteok"

    def is_configured(self) -> bool:
        return True  # No API key needed

    def search(self, keywords: str, location: str = "", **kwargs) -> list[JobPosting]:
        try:
            resp = self._request_get(REMOTEOK_API_URL)
            data = resp.json()
        except requests.RequestException as e:
            logger.warning("RemoteOK API error: %s", e)
            return []

        # First element is a metadata object, skip it
        jobs_data = data[1:] if isinstance(data, list) and len(data) > 1 else []
        keywords_lower = keywords.lower()
        all_jobs: list[JobPosting] = []

        for raw in jobs_data:
            # Filter by keywords
            title = raw.get("position", "")
            company = raw.get("company", "")
            tags = " ".join(raw.get("tags", []))
            description = raw.get("description", "")
            searchable = f"{title} {company} {tags} {description}".lower()

            if keywords_lower not in searchable:
                continue

            job_id = str(raw.get("id", hashlib.md5(
                f"{title}{company}".encode()
            ).hexdigest()))

            salary_min = raw.get("salary_min")
            salary_max = raw.get("salary_max")
            salary_range = None
            if salary_min and salary_max:
                salary_range = f"${int(salary_min):,} - ${int(salary_max):,}"

            all_jobs.append(JobPosting(
                job_id=job_id,
                title=title,
                company=company,
                location=raw.get("location", "Remote"),
                description=description,
                salary_range=salary_range,
                apply_url=raw.get("url", None),
                posting_date=raw.get("date", None),
                employment_type="remote",
                source="remoteok",
                raw_text=description,
                required_skills=raw.get("tags", []),
            ))

        logger.info("RemoteOK: found %d jobs matching '%s'", len(all_jobs), keywords)
        time.sleep(1)  # rate limiting
        return all_jobs
