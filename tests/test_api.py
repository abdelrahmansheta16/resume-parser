import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app


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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_model_info():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/model-info")
    assert resp.status_code == 200
    data = resp.json()
    assert "extraction_version" in data
    assert "embedding_model" in data


@pytest.mark.asyncio
async def test_parse_resume(sample_resume_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/parse-resume",
            files={"file": ("resume.txt", sample_resume_bytes, "text/plain")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidate_name"] is not None
    assert len(data["skills"]) > 0


@pytest.mark.asyncio
async def test_parse_jd(sample_jd):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/parse-job-description",
            data={"job_description": sample_jd},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["required_skills"]) > 0


@pytest.mark.asyncio
async def test_match_resume(sample_resume_bytes, sample_jd):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/match-resume",
            files={"file": ("resume.txt", sample_resume_bytes, "text/plain")},
            data={"job_description": sample_jd},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["match_score"] > 0
    assert data["recommendation"] != ""


@pytest.mark.asyncio
async def test_rank_candidates(sample_resume_bytes, sample_jd):
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
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["candidates"]) == 2
    # Sorted descending
    assert data["candidates"][0]["match_score"] >= data["candidates"][1]["match_score"]


@pytest.mark.asyncio
async def test_unsupported_file_type():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/parse-resume",
            files={"file": ("resume.xyz", b"content", "application/octet-stream")},
        )
    assert resp.status_code == 400
