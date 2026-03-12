"""FastAPI authentication dependencies using Supabase JWT validation."""
from __future__ import annotations

import threading
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.logging import get_logger
from app.models.config import config

logger = get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=True)
_bearer_scheme_optional = HTTPBearer(auto_error=False)

# Lazy-initialized JWKS client
_jwks_client = None
_jwks_lock = threading.Lock()


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        with _jwks_lock:
            if _jwks_client is None:
                jwks_url = f"{config.supabase_url}/auth/v1/.well-known/jwks.json"
                _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
                logger.info("JWKS client initialized for %s", jwks_url)
    return _jwks_client


@dataclass
class AuthUser:
    user_id: str
    email: str
    role: str = "authenticated"


def _decode_token(token: str) -> dict:
    """Decode and validate a Supabase JWT (supports both ES256/JWKS and HS256)."""
    try:
        # First try ES256 via JWKS (modern Supabase projects)
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "ES256" and config.supabase_url:
            jwks = _get_jwks_client()
            signing_key = jwks.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256"],
                audience="authenticated",
            )
            return payload

        # Fallback to HS256 with JWT secret (older Supabase projects / tests)
        payload = jwt.decode(
            token,
            config.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> AuthUser:
    """Validate the Bearer token and return the authenticated user."""
    payload = _decode_token(credentials.credentials)
    user_id = payload.get("sub")
    email = payload.get("email", "")
    role = payload.get("role", "authenticated")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
        )
    return AuthUser(user_id=user_id, email=email, role=role)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme_optional),
) -> AuthUser | None:
    """Return the authenticated user if a valid token is present, else None."""
    if credentials is None:
        return None
    try:
        payload = _decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return AuthUser(
            user_id=user_id,
            email=payload.get("email", ""),
            role=payload.get("role", "authenticated"),
        )
    except HTTPException:
        return None
