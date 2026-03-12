"""Retry decorator for network operations."""
from __future__ import annotations

import functools
import time

import requests

from app.core.logging import get_logger

logger = get_logger(__name__)


def retry_on_network_error(max_retries: int = 2, backoff: float = 1.0):
    """Retry on requests.RequestException with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts after the initial try.
        backoff: Base delay in seconds (doubles each retry).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.RequestException as e:
                    if attempt == max_retries:
                        raise
                    wait = backoff * (2 ** attempt)
                    logger.warning(
                        "Retry %d/%d for %s: %s (waiting %.1fs)",
                        attempt + 1, max_retries, func.__name__, e, wait,
                    )
                    time.sleep(wait)
        return wrapper
    return decorator
