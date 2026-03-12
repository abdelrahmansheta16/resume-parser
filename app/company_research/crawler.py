from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.api.schemas import CompanyResearch
from app.core.logging import get_logger
from app.core.paths import JOBS_DIR

logger = get_logger(__name__)

COMPANY_CACHE_DIR = JOBS_DIR / "company_cache"
COMPANY_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Respect rate limits
_REQUEST_DELAY = 2.0
_TIMEOUT = 10
_USER_AGENT = "ResumeParserBot/1.0 (job-application-research)"


def _check_robots_txt(base_url: str) -> bool:
    """Check robots.txt to see if crawling is allowed."""
    try:
        robots_url = urljoin(base_url, "/robots.txt")
        resp = requests.get(robots_url, timeout=_TIMEOUT, headers={"User-Agent": _USER_AGENT})
        if resp.status_code != 200:
            return True  # No robots.txt = allowed

        text = resp.text.lower()
        # Simple check: look for disallow-all for all user agents
        in_wildcard = False
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                in_wildcard = agent == "*"
            elif in_wildcard and line.startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path == "/":
                    logger.info("robots.txt disallows crawling: %s", base_url)
                    return False
        return True
    except Exception:
        return True  # If we can't fetch robots.txt, assume allowed


def _fetch_page(url: str) -> str | None:
    """Fetch a page and return its text content."""
    try:
        resp = requests.get(
            url,
            timeout=_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
            allow_redirects=True,
        )
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        logger.debug("Failed to fetch %s: %s", url, e)
    return None


def _extract_text(html: str) -> str:
    """Extract clean text from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style elements
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text[:5000]  # Cap length


def _find_about_page(base_url: str, html: str) -> str | None:
    """Find the about page URL from the homepage."""
    soup = BeautifulSoup(html, "html.parser")
    about_patterns = ["about", "about-us", "company", "who-we-are"]

    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        text = link.get_text(strip=True).lower()
        if any(p in href or p in text for p in about_patterns):
            return urljoin(base_url, link["href"])
    return None


def _find_careers_page(base_url: str, html: str) -> str | None:
    """Find the careers page URL from the homepage."""
    soup = BeautifulSoup(html, "html.parser")
    career_patterns = ["career", "jobs", "join-us", "work-with-us", "hiring", "openings"]

    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        text = link.get_text(strip=True).lower()
        if any(p in href or p in text for p in career_patterns):
            return urljoin(base_url, link["href"])
    return None


def _extract_tech_stack(text: str) -> list[str]:
    """Extract technology mentions from text."""
    tech_keywords = {
        "python", "javascript", "typescript", "react", "angular", "vue",
        "node.js", "django", "flask", "fastapi", "spring", "java", "kotlin",
        "swift", "go", "golang", "rust", "c++", "c#", ".net", "ruby",
        "rails", "php", "laravel", "aws", "azure", "gcp", "docker",
        "kubernetes", "terraform", "jenkins", "circleci", "github actions",
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "kafka", "rabbitmq", "graphql", "rest api", "microservices",
        "machine learning", "deep learning", "tensorflow", "pytorch",
    }

    text_lower = text.lower()
    found = []
    for tech in tech_keywords:
        if tech in text_lower:
            found.append(tech)

    return sorted(set(found))


def _extract_domain_from_url(url: str | None) -> str | None:
    """Extract domain from a URL."""
    if not url:
        return None
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    domain = domain.replace("www.", "")
    return domain if domain else None


def research_company(
    company_name: str,
    domain: str | None = None,
    apply_url: str | None = None,
) -> CompanyResearch:
    """Research a company using public web data.

    Respects robots.txt and rate limits. Only extracts publicly available information.
    """
    result = CompanyResearch(company_name=company_name)

    # Determine domain
    if not domain and apply_url:
        domain = _extract_domain_from_url(apply_url)

    if not domain:
        logger.info("No domain available for company: %s", company_name)
        return result

    result.domain = domain
    base_url = f"https://{domain}"

    # Check robots.txt
    if not _check_robots_txt(base_url):
        logger.info("Crawling blocked by robots.txt for %s", domain)
        return result

    # Fetch homepage
    homepage_html = _fetch_page(base_url)
    if not homepage_html:
        return result

    homepage_text = _extract_text(homepage_html)

    # Try to find and fetch about page
    time.sleep(_REQUEST_DELAY)
    about_url = _find_about_page(base_url, homepage_html)
    about_text = ""
    if about_url:
        about_html = _fetch_page(about_url)
        if about_html:
            about_text = _extract_text(about_html)

    # Try to find careers page
    time.sleep(_REQUEST_DELAY)
    careers_url = _find_careers_page(base_url, homepage_html)
    if careers_url:
        result.careers_url = careers_url

    # Build about summary
    combined_text = f"{homepage_text} {about_text}"
    # Take first 500 chars as about summary
    if about_text:
        result.about = about_text[:500]
    elif homepage_text:
        result.about = homepage_text[:500]

    # Extract tech stack
    result.tech_stack = _extract_tech_stack(combined_text)

    logger.info("Researched company %s: domain=%s, tech=%d items",
                company_name, domain, len(result.tech_stack))

    return result
