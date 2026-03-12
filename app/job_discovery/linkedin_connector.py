from __future__ import annotations

import hashlib
import re
import time
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from app.api.schemas import JobPosting
from app.core.logging import get_logger
from app.job_discovery.base_connector import BaseJobConnector
from app.models.config import config

logger = get_logger(__name__)

GOOGLE_SEARCH_URL = "https://www.google.com/search"


class LinkedInConnector(BaseJobConnector):
    name = "linkedin"
    max_retries = 1  # conservative for scraping

    def is_configured(self) -> bool:
        return getattr(config, "linkedin_search_enabled", True)

    def search(self, keywords: str, location: str = "", **kwargs) -> list[JobPosting]:
        if not self.is_configured():
            return []

        query = f'site:linkedin.com/jobs "{keywords}"'
        if location:
            query += f' "{location}"'

        try:
            resp = self._request_get(
                GOOGLE_SEARCH_URL,
                params={"q": query, "num": 20},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )
        except requests.RequestException as e:
            logger.warning("LinkedIn Google search error: %s", e)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        all_jobs: list[JobPosting] = []

        for result in soup.select("div.g"):
            link_tag = result.select_one("a[href]")
            if not link_tag:
                continue
            url = link_tag.get("href", "")
            if "linkedin.com/jobs" not in url:
                continue

            # Extract title from heading
            title_tag = result.select_one("h3")
            title_text = title_tag.get_text() if title_tag else ""

            # Extract snippet
            snippet_tag = result.select_one("div.VwiC3b") or result.select_one("span.aCOpRe")
            snippet = snippet_tag.get_text() if snippet_tag else ""

            # Parse title — typical format: "Job Title - Company | LinkedIn"
            title = title_text
            company = ""
            if " - " in title_text:
                parts = title_text.split(" - ", 1)
                title = parts[0].strip()
                remainder = parts[1] if len(parts) > 1 else ""
                # Remove "| LinkedIn" or similar suffixes
                company = re.sub(r"\s*\|.*$", "", remainder).strip()

            if not title or title.lower() == "linkedin":
                continue

            job_id = hashlib.md5(url.encode()).hexdigest()

            all_jobs.append(JobPosting(
                job_id=job_id,
                title=title,
                company=company,
                location=location or None,
                description=snippet,
                apply_url=url,
                source="linkedin",
                raw_text=snippet,
            ))

        logger.info("LinkedIn: found %d jobs for '%s'", len(all_jobs), keywords)
        time.sleep(3)  # conservative rate limiting
        return all_jobs
