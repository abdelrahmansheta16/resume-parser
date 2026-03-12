"""Supabase Storage helpers for uploading / downloading application files."""
from __future__ import annotations

from app.core.logging import get_logger
from app.core.supabase_client import get_supabase
from app.models.config import config

logger = get_logger(__name__)


def ensure_bucket(bucket: str | None = None) -> None:
    """Create the storage bucket if it doesn't already exist."""
    sb = get_supabase()
    bucket = bucket or config.supabase_storage_bucket
    try:
        sb.storage.get_bucket(bucket)
    except Exception:
        sb.storage.create_bucket(bucket, options={"public": False})
        logger.info("Created storage bucket: %s", bucket)


def upload_file(
    path_in_bucket: str,
    file_bytes: bytes,
    content_type: str = "application/octet-stream",
    bucket: str | None = None,
) -> str:
    """Upload a file to Supabase Storage. Returns the path in bucket."""
    sb = get_supabase()
    bucket = bucket or config.supabase_storage_bucket
    sb.storage.from_(bucket).upload(
        path_in_bucket,
        file_bytes,
        file_options={"content-type": content_type},
    )
    logger.info("Uploaded %s to bucket %s", path_in_bucket, bucket)
    return path_in_bucket


def download_file(path_in_bucket: str, bucket: str | None = None) -> bytes:
    """Download a file from Supabase Storage."""
    sb = get_supabase()
    bucket = bucket or config.supabase_storage_bucket
    return sb.storage.from_(bucket).download(path_in_bucket)


def get_signed_url(
    path_in_bucket: str,
    expires_in: int = 3600,
    bucket: str | None = None,
) -> str:
    """Generate a signed URL for temporary file access."""
    sb = get_supabase()
    bucket = bucket or config.supabase_storage_bucket
    result = sb.storage.from_(bucket).create_signed_url(path_in_bucket, expires_in)
    return result["signedURL"]


def delete_file(path_in_bucket: str, bucket: str | None = None) -> None:
    """Delete a file from Supabase Storage."""
    sb = get_supabase()
    bucket = bucket or config.supabase_storage_bucket
    sb.storage.from_(bucket).remove([path_in_bucket])
    logger.info("Deleted %s from bucket %s", path_in_bucket, bucket)
