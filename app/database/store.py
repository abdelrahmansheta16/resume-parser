"""Supabase-backed store for jobs, searches, and application tracking."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.api.schemas import CandidateProfile, JobPosting
from app.core.logging import get_logger
from app.core.supabase_client import get_supabase

logger = get_logger(__name__)


def init_db(db_path=None) -> None:
    """Verify Supabase connectivity. The db_path parameter is kept for backward
    compatibility but ignored — tables are managed via Supabase migrations."""
    sb = get_supabase()
    # Quick connectivity check
    sb.table("jobs").select("job_id").limit(1).execute()
    logger.info("Supabase database connection verified")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Jobs ────────────────────────────────────────────────────────────────────


def upsert_job(job: JobPosting) -> None:
    """Insert or update a job posting."""
    sb = get_supabase()
    now = _now()
    data = {
        "job_id": job.job_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description,
        "apply_url": job.apply_url,
        "required_skills": job.required_skills or [],
        "preferred_skills": job.preferred_skills or [],
        "salary_range": job.salary_range,
        "posting_date": job.posting_date,
        "source": job.source,
        "raw_text": job.raw_text,
        "first_seen": now,
        "last_seen": now,
        "employment_type": job.employment_type,
        "required_years_experience": job.required_years_experience,
        "education_requirements": job.education_requirements or [],
    }
    sb.table("jobs").upsert(data, on_conflict="job_id").execute()


def upsert_jobs(jobs: list[JobPosting]) -> int:
    """Bulk upsert jobs. Returns count inserted/updated."""
    for job in jobs:
        upsert_job(job)
    return len(jobs)


def get_job(job_id: str) -> JobPosting | None:
    """Retrieve a single job by ID."""
    sb = get_supabase()
    resp = sb.table("jobs").select("*").eq("job_id", job_id).execute()
    if not resp.data:
        return None
    return _row_to_job(resp.data[0])


def search_jobs(
    source: str | None = None,
    company: str | None = None,
    keyword: str | None = None,
    limit: int = 100,
) -> list[JobPosting]:
    """Query stored jobs with optional filters."""
    sb = get_supabase()
    query = sb.table("jobs").select("*")

    if source:
        query = query.eq("source", source)
    if company:
        query = query.ilike("company", f"%{company}%")
    if keyword:
        query = query.or_(f"title.ilike.%{keyword}%,description.ilike.%{keyword}%")

    query = query.order("last_seen", desc=True).limit(limit)
    resp = query.execute()
    return [_row_to_job(r) for r in resp.data]


def _row_to_job(row: dict) -> JobPosting:
    """Convert a Supabase row dict to a JobPosting. JSONB columns are already
    native Python lists, so no json.loads() needed."""
    return JobPosting(
        job_id=row["job_id"],
        title=row["title"] or "",
        company=row["company"] or "",
        location=row.get("location"),
        description=row["description"] or "",
        apply_url=row.get("apply_url"),
        required_skills=row.get("required_skills") or [],
        preferred_skills=row.get("preferred_skills") or [],
        salary_range=row.get("salary_range"),
        posting_date=row.get("posting_date"),
        source=row.get("source") or "",
        raw_text=row.get("raw_text"),
        employment_type=row.get("employment_type"),
        required_years_experience=row.get("required_years_experience"),
        education_requirements=row.get("education_requirements") or [],
    )


# ─── Searches ────────────────────────────────────────────────────────────────


def log_search(connector: str, keywords: str, location: str, result_count: int) -> None:
    """Record a search query."""
    sb = get_supabase()
    sb.table("searches").insert({
        "connector": connector,
        "keywords": keywords,
        "location": location,
        "result_count": result_count,
        "timestamp": _now(),
    }).execute()


# ─── Applications ────────────────────────────────────────────────────────────


def save_application(
    job_id: str,
    candidate_name: str,
    match_score: float = 0.0,
    ats_score: float = 0.0,
    docx_path: str | None = None,
    pdf_path: str | None = None,
    cover_letter_path: str | None = None,
    user_id: str | None = None,
) -> int:
    """Save a generated application record. Returns the application ID."""
    sb = get_supabase()
    now = _now()
    data = {
        "job_id": job_id,
        "candidate_name": candidate_name,
        "match_score": match_score,
        "ats_score": ats_score,
        "docx_path": docx_path,
        "pdf_path": pdf_path,
        "cover_letter_path": cover_letter_path,
        "status": "generated",
        "created_at": now,
        "updated_at": now,
    }
    if user_id:
        data["user_id"] = user_id
    resp = sb.table("applications").insert(data).execute()
    return resp.data[0]["id"]


def update_application_status(app_id: int, status: str) -> bool:
    """Update the status of an application."""
    sb = get_supabase()
    resp = (
        sb.table("applications")
        .update({"status": status, "updated_at": _now()})
        .eq("id", app_id)
        .execute()
    )
    return len(resp.data) > 0


def get_applications(
    candidate_name: str | None = None,
    status: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """List applications with optional filters."""
    sb = get_supabase()
    query = sb.table("applications").select("*")

    if candidate_name:
        query = query.eq("candidate_name", candidate_name)
    if status:
        query = query.eq("status", status)
    if user_id:
        query = query.eq("user_id", user_id)

    query = query.order("created_at", desc=True).limit(limit)
    resp = query.execute()
    return resp.data


# ─── Scheduled Profiles ─────────────────────────────────────────────────────


def save_scheduled_profile(
    profile_name: str,
    profile: CandidateProfile,
    interval_minutes: int = 360,
    user_id: str | None = None,
) -> int:
    """Persist a candidate profile for scheduled discovery. Returns the profile ID."""
    sb = get_supabase()
    now = _now()
    data = {
        "profile_name": profile_name,
        "profile_json": profile.model_dump(),  # JSONB accepts dicts directly
        "is_active": True,
        "interval_minutes": interval_minutes,
        "created_at": now,
        "updated_at": now,
    }
    if user_id:
        data["user_id"] = user_id
    resp = sb.table("scheduled_profiles").insert(data).execute()
    return resp.data[0]["id"]


def get_scheduled_profiles(
    active_only: bool = True,
    user_id: str | None = None,
) -> list[dict]:
    """Retrieve scheduled profiles, optionally filtering to active ones only."""
    sb = get_supabase()
    query = sb.table("scheduled_profiles").select("*")
    if active_only:
        query = query.eq("is_active", True)
    if user_id:
        query = query.eq("user_id", user_id)
    query = query.order("created_at", desc=True)
    resp = query.execute()
    # Convert profile_json back to JSON string for _row_to_scheduled_profile_response
    rows = []
    for r in resp.data:
        row = dict(r)
        if isinstance(row.get("profile_json"), dict):
            row["profile_json"] = json.dumps(row["profile_json"])
        rows.append(row)
    return rows


def get_scheduled_profile(profile_id: int) -> dict | None:
    """Retrieve a single scheduled profile by ID."""
    sb = get_supabase()
    resp = (
        sb.table("scheduled_profiles")
        .select("*")
        .eq("id", profile_id)
        .execute()
    )
    if not resp.data:
        return None
    row = dict(resp.data[0])
    if isinstance(row.get("profile_json"), dict):
        row["profile_json"] = json.dumps(row["profile_json"])
    return row


def update_scheduled_profile(profile_id: int, **fields) -> bool:
    """Update fields on a scheduled profile."""
    if not fields:
        return False
    sb = get_supabase()
    fields["updated_at"] = _now()
    resp = (
        sb.table("scheduled_profiles")
        .update(fields)
        .eq("id", profile_id)
        .execute()
    )
    return len(resp.data) > 0


def delete_scheduled_profile(profile_id: int) -> bool:
    """Remove a scheduled profile and its alerts."""
    sb = get_supabase()
    # Explicitly delete alerts first (also handled by ON DELETE CASCADE in PG)
    sb.table("alerts").delete().eq("profile_id", profile_id).execute()
    resp = (
        sb.table("scheduled_profiles")
        .delete()
        .eq("id", profile_id)
        .execute()
    )
    return len(resp.data) > 0


# ─── Alerts ──────────────────────────────────────────────────────────────────


def create_alert(
    profile_id: int,
    job_id: str,
    match_score: float,
    recommendation: str = "",
) -> int:
    """Create an alert for a newly discovered high-match job. Returns alert ID."""
    sb = get_supabase()
    resp = sb.table("alerts").insert({
        "profile_id": profile_id,
        "job_id": job_id,
        "match_score": match_score,
        "recommendation": recommendation,
        "is_read": False,
        "created_at": _now(),
    }).execute()
    return resp.data[0]["id"]


def get_alerts(
    profile_id: int | None = None,
    unread_only: bool = False,
    limit: int = 100,
) -> list[dict]:
    """Retrieve alerts with optional filters."""
    sb = get_supabase()
    query = sb.table("alerts").select("*")

    if profile_id is not None:
        query = query.eq("profile_id", profile_id)
    if unread_only:
        query = query.eq("is_read", False)

    query = query.order("created_at", desc=True).limit(limit)
    resp = query.execute()
    return resp.data


def mark_alert_read(alert_id: int) -> bool:
    """Mark a single alert as read."""
    sb = get_supabase()
    resp = (
        sb.table("alerts")
        .update({"is_read": True})
        .eq("id", alert_id)
        .execute()
    )
    return len(resp.data) > 0


def mark_all_alerts_read(profile_id: int | None = None) -> int:
    """Mark all alerts as read, optionally scoped to a profile. Returns count updated."""
    sb = get_supabase()
    query = sb.table("alerts").update({"is_read": True}).eq("is_read", False)
    if profile_id is not None:
        query = query.eq("profile_id", profile_id)
    resp = query.execute()
    return len(resp.data)


def get_known_job_ids() -> set[str]:
    """Return the set of all job_ids currently in the jobs table."""
    sb = get_supabase()
    resp = sb.table("jobs").select("job_id").execute()
    return {r["job_id"] for r in resp.data}
