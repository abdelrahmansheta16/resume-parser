from __future__ import annotations

import hashlib
import time

import requests

from app.api.schemas import JobPosting
from app.core.logging import get_logger
from app.job_discovery.base_connector import BaseJobConnector
from app.models.config import config

logger = get_logger(__name__)

ADZUNA_API_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


class AdzunaConnector(BaseJobConnector):
    name = "adzuna"

    def is_configured(self) -> bool:
        return bool(config.adzuna_app_id and config.adzuna_api_key)

    def search(self, keywords: str, location: str = "", **kwargs) -> list[JobPosting]:
        if not self.is_configured():
            logger.warning("Adzuna API credentials not configured")
            return []

        country = kwargs.get("country", "us")
        max_pages = kwargs.get("max_pages", 5)
        results_per_page = kwargs.get("results_per_page", 20)
        all_jobs: list[JobPosting] = []

        for page in range(1, max_pages + 1):
            url = ADZUNA_API_URL.format(country=country, page=page)
            params = {
                "app_id": config.adzuna_app_id,
                "app_key": config.adzuna_api_key,
                "what": keywords,
                "results_per_page": results_per_page,
            }
            if location:
                params["where"] = location

            try:
                resp = self._request_get(url, params=params)
                data = resp.json()
            except requests.RequestException as e:
                logger.warning("Adzuna API error (page %d): %s", page, e)
                break

            results = data.get("results", [])
            if not results:
                break

            for raw in results:
                job_id = raw.get("id", hashlib.md5(
                    f"{raw.get('title', '')}{raw.get('company', {}).get('display_name', '')}".encode()
                ).hexdigest())

                company = raw.get("company", {}).get("display_name", "")
                loc = raw.get("location", {}).get("display_name", "")

                salary_min = raw.get("salary_min")
                salary_max = raw.get("salary_max")
                salary_range = None
                if salary_min and salary_max:
                    salary_range = f"${salary_min:,.0f} - ${salary_max:,.0f}"
                elif salary_min:
                    salary_range = f"${salary_min:,.0f}+"

                all_jobs.append(JobPosting(
                    job_id=str(job_id),
                    title=raw.get("title", ""),
                    company=company,
                    location=loc,
                    description=raw.get("description", ""),
                    salary_range=salary_range,
                    apply_url=raw.get("redirect_url", None),
                    posting_date=raw.get("created", None),
                    employment_type=raw.get("contract_type", None),
                    source="adzuna",
                    raw_text=raw.get("description", ""),
                ))

            logger.debug("Adzuna page %d: %d jobs", page, len(results))
            total = data.get("count", 0)
            if page * results_per_page >= total:
                break

            time.sleep(1)

        logger.info("Adzuna: found %d jobs for '%s'", len(all_jobs), keywords)
        return all_jobs
