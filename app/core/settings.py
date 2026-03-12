from __future__ import annotations

import os
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

# Fix SSL certificate verification on macOS
if not os.environ.get("SSL_CERT_FILE"):
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass


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
