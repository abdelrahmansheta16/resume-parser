from __future__ import annotations

import os


def get_env(key: str, default: str = "") -> str:
    """Get environment variable with a default fallback."""
    return os.environ.get(key, default)


def get_env_bool(key: str, default: bool = False) -> bool:
    return get_env(key, str(default)).lower() in ("true", "1", "yes")


def get_env_int(key: str, default: int = 0) -> int:
    try:
        return int(get_env(key, str(default)))
    except ValueError:
        return default
