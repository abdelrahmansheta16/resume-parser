"""Authentication proxy routes (signup / login via Supabase Auth)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger
from app.core.supabase_client import get_supabase

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    email: str


@router.post("/signup", response_model=AuthResponse)
async def signup(body: AuthRequest):
    """Create a new user via Supabase Auth."""
    sb = get_supabase()
    try:
        resp = sb.auth.sign_up({"email": body.email, "password": body.password})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not resp.user:
        raise HTTPException(status_code=400, detail="Signup failed")

    session = resp.session
    if not session:
        # Email confirmation required — user created but no session yet
        return AuthResponse(
            access_token="",
            refresh_token="",
            user_id=resp.user.id,
            email=resp.user.email or body.email,
        )

    return AuthResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        user_id=resp.user.id,
        email=resp.user.email or body.email,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: AuthRequest):
    """Sign in with email and password."""
    sb = get_supabase()
    try:
        resp = sb.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    if not resp.user or not resp.session:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return AuthResponse(
        access_token=resp.session.access_token,
        refresh_token=resp.session.refresh_token,
        user_id=resp.user.id,
        email=resp.user.email or body.email,
    )
