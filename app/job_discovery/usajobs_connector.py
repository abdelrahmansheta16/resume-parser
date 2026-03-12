from __future__ import annotations

import time

import requests

from app.api.schemas import JobPosting
from app.core.logging import get_logger
from app.job_discovery.base_connector import BaseJobConnector
from app.models.config import config

logger = get_logger(__name__)

USAJOBS_API_URL = "https://data.usajobs.gov/api/Search"


class USAJobsConnector(BaseJobConnector):
    name = "usajobs"

    def is_configured(self) -> bool:
        return bool(config.usajobs_api_key and config.usajobs_email)

    def search(self, keywords: str, location: str = "", **kwargs) -> list[JobPosting]:
        if not self.is_configured():
            logger.warning("USAJOBS API credentials not configured")
            return []

        max_pages = kwargs.get("max_pages", 3)
        results_per_page = kwargs.get("results_per_page", 25)
        all_jobs: list[JobPosting] = []

        headers = {
            "Authorization-Key": config.usajobs_api_key,
            "User-Agent": config.usajobs_email,
            "Host": "data.usajobs.gov",
        }

        for page in range(1, max_pages + 1):
            params = {
                "Keyword": keywords,
                "ResultsPerPage": results_per_page,
                "Page": page,
            }
            if location:
                params["LocationName"] = location

            try:
                resp = self._request_get(USAJOBS_API_URL, headers=headers, params=params)
                data = resp.json()
            except requests.RequestException as e:
                logger.warning("USAJOBS API error (page %d): %s", page, e)
                break

            search_result = data.get("SearchResult", {})
            items = search_result.get("SearchResultItems", [])
            if not items:
                break

            for item in items:
                match = item.get("MatchedObjectDescriptor", {})
                position = match.get("PositionTitle", "")
                org = match.get("OrganizationName", "")
                locations = match.get("PositionLocation", [])
                loc_str = locations[0].get("LocationName", "") if locations else ""

                # Salary
                remuneration = match.get("PositionRemuneration", [])
                salary_range = None
                if remuneration:
                    r = remuneration[0]
                    salary_range = f"${r.get('MinimumRange', '')} - ${r.get('MaximumRange', '')} {r.get('RateIntervalCode', '')}"

                apply_url = match.get("ApplyURI", [""])[0] if match.get("ApplyURI") else None
                description = match.get("UserArea", {}).get("Details", {}).get("MajorDuties", [""])
                desc_text = " ".join(description) if isinstance(description, list) else str(description)

                qual_summary = match.get("QualificationSummary", "")

                all_jobs.append(JobPosting(
                    job_id=match.get("PositionID", ""),
                    title=position,
                    company=org,
                    location=loc_str,
                    description=desc_text or qual_summary,
                    salary_range=salary_range,
                    apply_url=apply_url,
                    posting_date=match.get("PublicationStartDate", None),
                    employment_type=match.get("PositionSchedule", [{}])[0].get("Name", "") if match.get("PositionSchedule") else None,
                    source="usajobs",
                    raw_text=f"{position}\n{desc_text}\n{qual_summary}",
                ))

            total_count = int(search_result.get("SearchResultCount", 0))
            if page * results_per_page >= total_count:
                break

            time.sleep(1)

        logger.info("USAJOBS: found %d jobs for '%s'", len(all_jobs), keywords)
        return all_jobs
