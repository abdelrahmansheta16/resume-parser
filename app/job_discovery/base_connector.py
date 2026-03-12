from __future__ import annotations

from abc import ABC, abstractmethod

import requests

from app.api.schemas import JobPosting
from app.core.logging import get_logger
from app.job_discovery.retry import retry_on_network_error

logger = get_logger(__name__)

_DEFAULT_USER_AGENT = "ResumeParser/1.0"


class BaseJobConnector(ABC):
    """Abstract base class for job board API connectors."""

    name: str = "base"
    default_timeout: int = 15
    max_retries: int = 2

    @abstractmethod
    def search(self, keywords: str, location: str = "", **kwargs) -> list[JobPosting]:
        """Search for jobs matching the given keywords and location."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if required API credentials are available."""
        ...

    def _request_get(self, url: str, **kwargs) -> requests.Response:
        """GET with retry, timeout, and standard User-Agent."""
        kwargs.setdefault("timeout", self.default_timeout)
        kwargs.setdefault("headers", {})
        kwargs["headers"].setdefault("User-Agent", _DEFAULT_USER_AGENT)

        @retry_on_network_error(max_retries=self.max_retries)
        def _do():
            resp = requests.get(url, **kwargs)
            resp.raise_for_status()
            return resp

        return _do()

    def _request_post(self, url: str, **kwargs) -> requests.Response:
        """POST with retry, timeout, and standard User-Agent."""
        kwargs.setdefault("timeout", self.default_timeout)
        kwargs.setdefault("headers", {})
        kwargs["headers"].setdefault("User-Agent", _DEFAULT_USER_AGENT)

        @retry_on_network_error(max_retries=self.max_retries)
        def _do():
            resp = requests.post(url, **kwargs)
            resp.raise_for_status()
            return resp

        return _do()
