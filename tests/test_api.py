import time

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app

TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests"


def _make_auth_headers():
    """Generate valid Bearer auth headers for testing."""
    from unittest.mock import patch
    from app.models.config import config

    # Ensure config uses our test secret
    original = config.supabase_jwt_secret
    config.supabase_jwt_secret = TEST_JWT_SECRET

    payload = {
        "sub": "test-user-id-123",
        "email": "test@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

    # Restore original after encoding (fixture will handle patching)
    config.supabase_jwt_secret = original

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_hdrs():
    """Auth headers fixture that also patches the config for JWT validation."""
    from app.models.config import config
    config.supabase_jwt_secret = TEST_JWT_SECRET

    payload = {
        "sub": "test-user-id-123",
        "email": "test@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_resume_bytes():
    from tests.conftest import SAMPLE_RESUME_1
    return SAMPLE_RESUME_1.read_bytes()


@pytest.fixture
def sample_jd():
    from tests.conftest import SAMPLE_JD_1
    return SAMPLE_JD_1.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_health():
    """Health endpoint is public — no auth required."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_model_info():
    """Model info endpoint is public — no auth required."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/model-info")
    assert resp.status_code == 200
    data = resp.json()
    assert "extraction_version" in data
    assert "embedding_model" in data


@pytest.mark.asyncio
async def test_parse_resume_requires_auth(sample_resume_bytes):
    """Authenticated endpoints should return 403 without a token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/parse-resume",
            files={"file": ("resume.txt", sample_resume_bytes, "text/plain")},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_parse_resume(sample_resume_bytes, auth_hdrs):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/parse-resume",
            files={"file": ("resume.txt", sample_resume_bytes, "text/plain")},
            headers=auth_hdrs,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidate_name"] is not None
    assert len(data["skills"]) > 0


@pytest.mark.asyncio
async def test_parse_jd(sample_jd, auth_hdrs):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/parse-job-description",
            data={"job_description": sample_jd},
            headers=auth_hdrs,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["required_skills"]) > 0


@pytest.mark.asyncio
async def test_match_resume(sample_resume_bytes, sample_jd, auth_hdrs):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/match-resume",
            files={"file": ("resume.txt", sample_resume_bytes, "text/plain")},
            data={"job_description": sample_jd},
            headers=auth_hdrs,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["match_score"] > 0
    assert data["recommendation"] != ""


@pytest.mark.asyncio
async def test_rank_candidates(sample_resume_bytes, sample_jd, auth_hdrs):
    from tests.conftest import SAMPLE_RESUME_2
    resume_2_bytes = SAMPLE_RESUME_2.read_bytes()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/rank-candidates",
            files=[
                ("files", ("resume1.txt", sample_resume_bytes, "text/plain")),
                ("files", ("resume2.txt", resume_2_bytes, "text/plain")),
            ],
            data={"job_description": sample_jd},
            headers=auth_hdrs,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["candidates"]) == 2
    # Sorted descending
    assert data["candidates"][0]["match_score"] >= data["candidates"][1]["match_score"]


@pytest.mark.asyncio
async def test_unsupported_file_type(auth_hdrs):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/parse-resume",
            files={"file": ("resume.xyz", b"content", "application/octet-stream")},
            headers=auth_hdrs,
        )
    assert resp.status_code == 400
