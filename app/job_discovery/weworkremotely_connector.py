from __future__ import annotations

import hashlib
import re
import time
import xml.etree.ElementTree as ET

import requests

from app.api.schemas import JobPosting
from app.core.logging import get_logger
from app.job_discovery.base_connector import BaseJobConnector

logger = get_logger(__name__)

WWR_RSS_URL = "https://weworkremotely.com/remote-jobs.rss"


class WeWorkRemotelyConnector(BaseJobConnector):
    name = "weworkremotely"

    def is_configured(self) -> bool:
        return True  # No API key needed

    def search(self, keywords: str, location: str = "", **kwargs) -> list[JobPosting]:
        try:
            resp = self._request_get(WWR_RSS_URL)
        except requests.RequestException as e:
            logger.warning("WeWorkRemotely RSS error: %s", e)
            return []

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            logger.warning("WeWorkRemotely RSS parse error: %s", e)
            return []

        keywords_lower = keywords.lower()
        all_jobs: list[JobPosting] = []
        channel = root.find("channel")
        if channel is None:
            return []

        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description_html = item.findtext("description") or ""
            pub_date = item.findtext("pubDate") or ""

            # Strip HTML from description
            description = re.sub(r"<[^>]+>", " ", description_html)
            description = re.sub(r"\s+", " ", description).strip()

            # Filter by keywords
            searchable = f"{title} {description}".lower()
            if keywords_lower not in searchable:
                continue

            # Extract company from title (format: "Company: Role")
            company = ""
            if ":" in title:
                parts = title.split(":", 1)
                company = parts[0].strip()
                title = parts[1].strip()

            job_id = hashlib.md5(f"{title}{company}{link}".encode()).hexdigest()

            all_jobs.append(JobPosting(
                job_id=job_id,
                title=title,
                company=company,
                location="Remote",
                description=description[:500],
                apply_url=link,
                posting_date=pub_date,
                employment_type="remote",
                source="weworkremotely",
                raw_text=description,
            ))

        logger.info("WeWorkRemotely: found %d jobs matching '%s'", len(all_jobs), keywords)
        time.sleep(1)
        return all_jobs
