"""Singleton Supabase client for backend operations."""
from __future__ import annotations

from app.core.logging import get_logger
from app.models.config import config

logger = get_logger(__name__)

_client = None


def get_supabase():
    """Return the singleton Supabase client (service-role key for backend)."""
    global _client
    if _client is None:
        if not config.supabase_url or not config.supabase_service_role_key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
            )
        from supabase import create_client

        _client = create_client(config.supabase_url, config.supabase_service_role_key)
        logger.info("Supabase client initialized for %s", config.supabase_url)
    return _client
