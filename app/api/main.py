from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.schemas import (
    AlertListResponse,
    ApplicationBundle,
    ApplicationListResponse,
    ApplicationPack,
    ApplicationRecord,
    CandidateProfile,
    CompanyResearch,
    DeduplicationResult,
    DiscoveryTask,
    FeedbackStats,
    FeedbackSubmission,
    HealthResponse,
    JobDiscoveryResult,
    JobMatchResult,
    JobPosting,
    MatchResult,
    ModelInfoResponse,
    OutreachDraft,
    ParsedJobDescription,
    ParsedResume,
    RankingResult,
    ReviewItem,
    ReviewQueueResponse,
    ScheduleAlert,
    ScheduledProfileCreate,
    ScheduledProfileListResponse,
    ScheduledProfileResponse,
    ScheduledProfileUpdate,
    SearchFilters,
    SearchResult,
    VectorSearchQuery,
    VectorSearchResult,
)
from app.api.utils import resumes_to_csv, resumes_to_excel_bytes
from app.auth.dependencies import AuthUser, get_current_user
from app.extraction.resume_structurer import structure_resume
from app.matching.jd_parser import parse_job_description
from app.matching.ranking import rank_candidates
from app.matching.scoring import score_candidate
from app.models.config import config
from app.parsing.file_loader import load_from_bytes

# ─── Rate Limiter ─────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Resume Parser API",
    description="Parse resumes, extract structured data, and rank candidates against job descriptions.",
    version=config.extraction_version,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins.split(",") if config.cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth routes
from app.auth.routes import router as auth_router  # noqa: E402

app.include_router(auth_router)


@app.on_event("startup")
async def startup_event():
    from app.core.supabase_client import get_supabase

    try:
        get_supabase()
    except RuntimeError:
        import logging
        logging.getLogger(__name__).warning(
            "Supabase not configured — database features disabled"
        )
    from app.scheduler.engine import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
async def shutdown_event():
    from app.scheduler.engine import stop_scheduler
    stop_scheduler()


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


def _validate_file(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(ALLOWED_EXTENSIONS)}",
        )


# ─── Public Endpoints ────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@app.get("/model-info", response_model=ModelInfoResponse)
async def model_info():
    return ModelInfoResponse(
        extraction_version=config.extraction_version,
        matching_version=config.matching_version,
        taxonomy_version=config.taxonomy_version,
        embedding_model=config.embedding_model,
    )


# ─── Core Endpoints (Authenticated) ──────────────────────────────────────────

@app.post("/parse-resume", response_model=ParsedResume)
@limiter.limit(config.rate_limit_parse)
async def parse_resume(
    request: Request,
    file: UploadFile = File(...),
    anonymize: bool = Form(False),
    user: AuthUser = Depends(get_current_user),
):
    _validate_file(file)
    content = await file.read()
    doc = load_from_bytes(content, file.filename)
    if not doc.success:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {doc.error}")

    resume = structure_resume(doc.cleaned_text, include_raw=True)
    if not resume.parse_method:
        resume.parse_method = doc.metadata.get("parse_method")

    # Auto-queue for review if low confidence
    from app.review.queue import auto_queue_if_needed
    auto_queue_if_needed(resume)

    if anonymize:
        from app.anonymize.redactor import anonymize_resume
        resume = anonymize_resume(resume)

    return resume


@app.post("/parse-job-description", response_model=ParsedJobDescription)
@limiter.limit(config.rate_limit_parse)
async def parse_jd(
    request: Request,
    job_description: str = Form(...),
    user: AuthUser = Depends(get_current_user),
):
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description text is required")
    return parse_job_description(job_description)


@app.post("/match-resume", response_model=MatchResult)
@limiter.limit(config.rate_limit_parse)
async def match_resume(
    request: Request,
    file: UploadFile = File(...),
    job_description: str = Form(...),
    user: AuthUser = Depends(get_current_user),
):
    _validate_file(file)
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description text is required")

    content = await file.read()
    doc = load_from_bytes(content, file.filename)
    if not doc.success:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {doc.error}")

    resume = structure_resume(doc.cleaned_text, include_raw=True)
    jd = parse_job_description(job_description)
    return score_candidate(resume, jd)


@app.post("/rank-candidates", response_model=RankingResult)
@limiter.limit(config.rate_limit_parse)
async def rank(
    request: Request,
    files: List[UploadFile] = File(...),
    job_description: str = Form(...),
    anonymize: bool = Form(False),
    user: AuthUser = Depends(get_current_user),
):
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description text is required")
    if not files:
        raise HTTPException(status_code=400, detail="At least one resume file is required")

    parsed_resumes: List[ParsedResume] = []
    errors: List[str] = []

    for file in files:
        try:
            _validate_file(file)
            content = await file.read()
            doc = load_from_bytes(content, file.filename)
            if doc.success:
                resume = structure_resume(doc.cleaned_text, include_raw=True)
                parsed_resumes.append(resume)
            else:
                errors.append(f"{file.filename}: {doc.error}")
        except HTTPException as e:
            errors.append(f"{file.filename}: {e.detail}")

    if not parsed_resumes:
        raise HTTPException(
            status_code=422,
            detail=f"No resumes could be parsed. Errors: {'; '.join(errors)}",
        )

    if anonymize:
        from app.anonymize.redactor import anonymize_resume
        parsed_resumes = [anonymize_resume(r, i + 1) for i, r in enumerate(parsed_resumes)]

    jd = parse_job_description(job_description)
    result = rank_candidates(parsed_resumes, jd)
    return result


@app.post("/export-ranking/csv")
@limiter.limit(config.rate_limit_default)
async def export_csv(
    request: Request,
    files: List[UploadFile] = File(...),
    job_description: str = Form(...),
    user: AuthUser = Depends(get_current_user),
):
    ranking = await rank(request, files, job_description, user=user)
    csv_data = resumes_to_csv([c.model_dump() for c in ranking.candidates])
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ranking.csv"},
    )


@app.post("/export-ranking/excel")
@limiter.limit(config.rate_limit_default)
async def export_excel(
    request: Request,
    files: List[UploadFile] = File(...),
    job_description: str = Form(...),
    user: AuthUser = Depends(get_current_user),
):
    ranking = await rank(request, files, job_description, user=user)
    excel_bytes = resumes_to_excel_bytes([c.model_dump() for c in ranking.candidates])
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ranking.xlsx"},
    )


# ─── Deduplication ────────────────────────────────────────────────────────────

@app.post("/dedup/check", response_model=DeduplicationResult)
@limiter.limit(config.rate_limit_parse)
async def dedup_check(
    request: Request,
    files: List[UploadFile] = File(...),
    user: AuthUser = Depends(get_current_user),
):
    parsed_resumes: List[ParsedResume] = []
    for file in files:
        try:
            _validate_file(file)
            content = await file.read()
            doc = load_from_bytes(content, file.filename)
            if doc.success:
                resume = structure_resume(doc.cleaned_text, include_raw=True)
                parsed_resumes.append(resume)
        except HTTPException:
            pass

    if len(parsed_resumes) < 2:
        raise HTTPException(status_code=400, detail="At least 2 resumes needed for deduplication")

    from app.dedup.matcher import find_duplicates
    return find_duplicates(parsed_resumes)


# ─── Search Filters ───────────────────────────────────────────────────────────

@app.post("/search/candidates", response_model=SearchResult)
@limiter.limit(config.rate_limit_parse)
async def search_candidates(
    request: Request,
    files: List[UploadFile] = File(...),
    filters: str = Form("{}"),
    user: AuthUser = Depends(get_current_user),
):
    import json
    try:
        filter_data = json.loads(filters)
        search_filters = SearchFilters(**filter_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid filters JSON: {e}")

    parsed_resumes: List[ParsedResume] = []
    for file in files:
        try:
            _validate_file(file)
            content = await file.read()
            doc = load_from_bytes(content, file.filename)
            if doc.success:
                resume = structure_resume(doc.cleaned_text, include_raw=True)
                parsed_resumes.append(resume)
        except HTTPException:
            pass

    from app.search.filters import apply_filters
    return apply_filters(parsed_resumes, search_filters)


# ─── Vector Database ──────────────────────────────────────────────────────────

@app.post("/vector/index")
@limiter.limit(config.rate_limit_parse)
async def vector_index(
    request: Request,
    file: UploadFile = File(...),
    user: AuthUser = Depends(get_current_user),
):
    _validate_file(file)
    content = await file.read()
    doc = load_from_bytes(content, file.filename)
    if not doc.success:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {doc.error}")

    resume = structure_resume(doc.cleaned_text, include_raw=True)
    from app.vectordb.store import index_resume
    doc_id = index_resume(resume)
    return {"status": "indexed", "document_id": doc_id, "candidate_name": resume.candidate_name}


@app.post("/vector/search", response_model=VectorSearchResult)
@limiter.limit(config.rate_limit_default)
async def vector_search(
    request: Request,
    query: VectorSearchQuery,
    user: AuthUser = Depends(get_current_user),
):
    from app.vectordb.store import search
    return search(query.query, query.n_results)


@app.get("/vector/stats")
@limiter.limit(config.rate_limit_default)
async def vector_stats(
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    from app.vectordb.store import get_stats
    return get_stats()


@app.delete("/vector/clear")
@limiter.limit(config.rate_limit_default)
async def vector_clear(
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    from app.vectordb.store import clear
    return clear()


# ─── Review Queue ─────────────────────────────────────────────────────────────

@app.get("/review/queue", response_model=ReviewQueueResponse)
@limiter.limit(config.rate_limit_default)
async def review_queue(
    request: Request,
    status: Optional[str] = None,
    user: AuthUser = Depends(get_current_user),
):
    from app.review.queue import get_queue
    return get_queue(status)


@app.get("/review/queue/{review_id}", response_model=ReviewItem)
@limiter.limit(config.rate_limit_default)
async def review_item(
    request: Request,
    review_id: str,
    user: AuthUser = Depends(get_current_user),
):
    from app.review.queue import get_item
    item = get_item(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


@app.post("/review/queue/{review_id}/approve", response_model=ReviewItem)
@limiter.limit(config.rate_limit_default)
async def review_approve(
    request: Request,
    review_id: str,
    notes: Optional[str] = Form(None),
    user: AuthUser = Depends(get_current_user),
):
    from app.review.queue import update_status
    item = update_status(review_id, "approved", notes)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


@app.post("/review/queue/{review_id}/reject", response_model=ReviewItem)
@limiter.limit(config.rate_limit_default)
async def review_reject(
    request: Request,
    review_id: str,
    notes: Optional[str] = Form(None),
    user: AuthUser = Depends(get_current_user),
):
    from app.review.queue import update_status
    item = update_status(review_id, "rejected", notes)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


# ─── Feedback Loop ────────────────────────────────────────────────────────────

@app.post("/feedback")
@limiter.limit(config.rate_limit_default)
async def submit_feedback(
    request: Request,
    submission: FeedbackSubmission,
    user: AuthUser = Depends(get_current_user),
):
    from app.feedback.store import save_feedback
    return save_feedback(submission)


@app.get("/feedback/stats", response_model=FeedbackStats)
@limiter.limit(config.rate_limit_default)
async def feedback_stats(
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    from app.feedback.store import get_feedback_stats
    return get_feedback_stats()


@app.post("/feedback/recalibrate")
@limiter.limit(config.rate_limit_discover)
async def feedback_recalibrate(
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    from app.feedback.weight_adjuster import recalibrate_weights
    new_weights = recalibrate_weights()
    return {"status": "recalibrated", "adjusted_weights": new_weights}


# ─── Job Discovery & Application Packs ────────────────────────────────────────

@app.post("/build-profile", response_model=CandidateProfile)
@limiter.limit(config.rate_limit_parse)
async def build_profile(
    request: Request,
    file: UploadFile = File(...),
    target_titles: str = Form(""),
    target_locations: str = Form(""),
    remote_preference: Optional[str] = Form(None),
    min_salary: Optional[float] = Form(None),
    user: AuthUser = Depends(get_current_user),
):
    """Upload a CV and build a CandidateProfile for job discovery."""
    _validate_file(file)
    content = await file.read()
    doc = load_from_bytes(content, file.filename)
    if not doc.success:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {doc.error}")

    resume = structure_resume(doc.cleaned_text, include_raw=True)
    if not resume.parse_method:
        resume.parse_method = doc.metadata.get("parse_method")

    titles = [t.strip() for t in target_titles.split(",") if t.strip()]
    locations = [l.strip() for l in target_locations.split(",") if l.strip()]

    return CandidateProfile(
        resume=resume,
        target_titles=titles,
        target_locations=locations,
        remote_preference=remote_preference,
        min_salary=min_salary,
    )


@app.post("/discover-jobs")
@limiter.limit(config.rate_limit_discover)
async def discover_jobs(
    request: Request,
    profile: CandidateProfile,
    async_mode: bool = False,
    user: AuthUser = Depends(get_current_user),
):
    """Discover jobs from all configured connectors and return ranked results."""
    if async_mode:
        import threading
        from app.job_discovery.task_store import create_task
        from app.job_discovery.orchestrator import discover_jobs_async

        task = create_task()
        thread = threading.Thread(
            target=discover_jobs_async,
            args=(profile, task.task_id),
            daemon=True,
        )
        thread.start()
        return task

    from app.job_discovery.orchestrator import discover_jobs as _discover
    from app.matching.job_ranker import rank_jobs_for_candidate

    jobs = _discover(profile)
    ranked = rank_jobs_for_candidate(profile.resume, jobs)

    return JobDiscoveryResult(
        total_found=len(jobs),
        total_after_dedup=len(jobs),
        ranked_jobs=ranked,
    )


@app.get("/discovery-status/{task_id}", response_model=DiscoveryTask)
@limiter.limit(config.rate_limit_default)
async def discovery_status(
    request: Request,
    task_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Check the status of an async job discovery task."""
    from app.job_discovery.task_store import get_task

    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Discovery task not found")
    return task


@app.delete("/discovery-status/{task_id}")
@limiter.limit(config.rate_limit_default)
async def discovery_cleanup(
    request: Request,
    task_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Remove a completed discovery task."""
    from app.job_discovery.task_store import delete_task

    if not delete_task(task_id):
        raise HTTPException(status_code=404, detail="Discovery task not found")
    return {"status": "deleted", "task_id": task_id}


@app.post("/rank-jobs", response_model=List[JobMatchResult])
@limiter.limit(config.rate_limit_parse)
async def rank_jobs(
    request: Request,
    file: UploadFile = File(...),
    jobs_json: str = Form(...),
    user: AuthUser = Depends(get_current_user),
):
    """Rank a list of jobs for a candidate."""
    import json as _json

    _validate_file(file)
    content = await file.read()
    doc = load_from_bytes(content, file.filename)
    if not doc.success:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {doc.error}")

    resume = structure_resume(doc.cleaned_text, include_raw=True)

    try:
        jobs_data = _json.loads(jobs_json)
        jobs = [JobPosting(**j) for j in jobs_data]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid jobs JSON: {e}")

    from app.matching.job_ranker import rank_jobs_for_candidate
    return rank_jobs_for_candidate(resume, jobs)


@app.post("/generate-single-pack", response_model=ApplicationPack)
@limiter.limit(config.rate_limit_discover)
async def generate_single_pack(
    request: Request,
    file: UploadFile = File(...),
    job_json: str = Form(...),
    user: AuthUser = Depends(get_current_user),
):
    """Generate an application pack for a single job."""
    import json as _json

    _validate_file(file)
    content = await file.read()
    doc = load_from_bytes(content, file.filename)
    if not doc.success:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {doc.error}")

    resume = structure_resume(doc.cleaned_text, include_raw=True)

    try:
        job_data = _json.loads(job_json)
        job = JobPosting(**job_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid job JSON: {e}")

    from app.matching.job_ranker import score_job_for_candidate
    match = score_job_for_candidate(resume, job)

    from app.tailoring.pack_generator import generate_application_pack
    return generate_application_pack(resume, match)


@app.post("/generate-packs", response_model=ApplicationBundle)
@limiter.limit(config.rate_limit_discover)
async def generate_packs(
    request: Request,
    file: UploadFile = File(...),
    jobs_json: str = Form(...),
    user: AuthUser = Depends(get_current_user),
):
    """Generate application packs for multiple jobs and bundle them."""
    import json as _json

    _validate_file(file)
    content = await file.read()
    doc = load_from_bytes(content, file.filename)
    if not doc.success:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {doc.error}")

    resume = structure_resume(doc.cleaned_text, include_raw=True)

    try:
        jobs_data = _json.loads(jobs_json)
        jobs = [JobPosting(**j) for j in jobs_data]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid jobs JSON: {e}")

    from app.matching.job_ranker import rank_jobs_for_candidate
    ranked = rank_jobs_for_candidate(resume, jobs)

    from app.tailoring.pack_generator import generate_application_bundle
    return generate_application_bundle(resume, ranked)


@app.post("/company-research", response_model=CompanyResearch)
@limiter.limit(config.rate_limit_discover)
async def company_research(
    request: Request,
    company_name: str = Form(...),
    domain: Optional[str] = Form(None),
    apply_url: Optional[str] = Form(None),
    user: AuthUser = Depends(get_current_user),
):
    """Research a company using public web data."""
    from app.company_research.crawler import research_company
    return research_company(company_name, domain, apply_url)


@app.post("/draft-outreach", response_model=OutreachDraft)
@limiter.limit(config.rate_limit_discover)
async def draft_outreach_endpoint(
    request: Request,
    file: UploadFile = File(...),
    job_json: str = Form(...),
    target_role: str = Form("recruiter"),
    user: AuthUser = Depends(get_current_user),
):
    """Draft an outreach message for a job application."""
    import json as _json

    _validate_file(file)
    content = await file.read()
    doc = load_from_bytes(content, file.filename)
    if not doc.success:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {doc.error}")

    resume = structure_resume(doc.cleaned_text, include_raw=True)

    try:
        job_data = _json.loads(job_json)
        job = JobPosting(**job_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid job JSON: {e}")

    from app.matching.job_ranker import score_job_for_candidate
    match = score_job_for_candidate(resume, job)

    from app.outreach.drafter import draft_outreach
    return draft_outreach(resume, job, match, target_role)


# ─── Application Tracking ────────────────────────────────────────────────────

@app.get("/applications", response_model=ApplicationListResponse)
@limiter.limit(config.rate_limit_default)
async def list_applications(
    request: Request,
    candidate_name: Optional[str] = None,
    status: Optional[str] = None,
    user: AuthUser = Depends(get_current_user),
):
    """List tracked application records."""
    from app.database.store import get_applications
    rows = get_applications(
        candidate_name=candidate_name, status=status, user_id=user.user_id
    )
    records = [ApplicationRecord(**r) for r in rows]
    return ApplicationListResponse(total=len(records), applications=records)


@app.patch("/applications/{app_id}/status")
@limiter.limit(config.rate_limit_default)
async def update_application(
    request: Request,
    app_id: int,
    status: str = Form(...),
    user: AuthUser = Depends(get_current_user),
):
    """Update the status of an application."""
    from app.database.store import update_application_status
    valid_statuses = {"generated", "applied", "interview", "rejected", "offer"}
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    if not update_application_status(app_id, status):
        raise HTTPException(status_code=404, detail="Application not found")
    return {"status": "updated", "app_id": app_id, "new_status": status}


@app.get("/jobs/history")
@limiter.limit(config.rate_limit_default)
async def jobs_history(
    request: Request,
    source: Optional[str] = None,
    company: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 100,
    user: AuthUser = Depends(get_current_user),
):
    """Query stored job history from the database."""
    from app.database.store import search_jobs
    jobs = search_jobs(source=source, company=company, keyword=keyword, limit=limit)
    return {"total": len(jobs), "jobs": [j.model_dump() for j in jobs]}


# ─── Cover Letter ─────────────────────────────────────────────────────────────

@app.post("/generate-cover-letter")
@limiter.limit(config.rate_limit_discover)
async def generate_cover_letter_endpoint(
    request: Request,
    file: UploadFile = File(...),
    job_json: str = Form(...),
    user: AuthUser = Depends(get_current_user),
):
    """Generate a cover letter for a single job."""
    import json as _json

    _validate_file(file)
    content = await file.read()
    doc = load_from_bytes(content, file.filename)
    if not doc.success:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {doc.error}")

    resume = structure_resume(doc.cleaned_text, include_raw=True)

    try:
        job_data = _json.loads(job_json)
        job = JobPosting(**job_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid job JSON: {e}")

    from app.matching.job_ranker import score_job_for_candidate
    match = score_job_for_candidate(resume, job)

    from app.tailoring.cover_letter import generate_cover_letter
    return {"cover_letter": generate_cover_letter(resume, job, match)}


# ─── Scheduled Job Discovery ─────────────────────────────────────────────────


def _row_to_scheduled_profile_response(row: dict) -> ScheduledProfileResponse:
    """Convert a DB row dict to a ScheduledProfileResponse."""
    profile = CandidateProfile.model_validate_json(row["profile_json"])
    return ScheduledProfileResponse(
        id=row["id"],
        profile_name=row["profile_name"],
        profile=profile,
        is_active=bool(row["is_active"]),
        interval_minutes=row["interval_minutes"],
        last_run_at=row.get("last_run_at"),
        next_run_at=row.get("next_run_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@app.post("/scheduled-profiles", response_model=ScheduledProfileResponse)
@limiter.limit(config.rate_limit_default)
async def create_scheduled_profile(
    request: Request,
    body: ScheduledProfileCreate,
    user: AuthUser = Depends(get_current_user),
):
    """Create a new scheduled profile for periodic job discovery."""
    from app.database.store import save_scheduled_profile, get_scheduled_profile
    from app.scheduler.engine import add_profile_job

    profile_id = save_scheduled_profile(
        body.profile_name, body.profile, body.interval_minutes, user_id=user.user_id
    )
    if config.scheduler_enabled:
        add_profile_job(profile_id, body.interval_minutes)
    row = get_scheduled_profile(profile_id)
    return _row_to_scheduled_profile_response(row)


@app.get("/scheduled-profiles", response_model=ScheduledProfileListResponse)
@limiter.limit(config.rate_limit_default)
async def list_scheduled_profiles(
    request: Request,
    active_only: bool = True,
    user: AuthUser = Depends(get_current_user),
):
    """List scheduled profiles."""
    from app.database.store import get_scheduled_profiles

    rows = get_scheduled_profiles(active_only=active_only, user_id=user.user_id)
    profiles = [_row_to_scheduled_profile_response(r) for r in rows]
    return ScheduledProfileListResponse(total=len(profiles), profiles=profiles)


@app.get("/scheduled-profiles/{profile_id}", response_model=ScheduledProfileResponse)
@limiter.limit(config.rate_limit_default)
async def get_scheduled_profile_endpoint(
    request: Request,
    profile_id: int,
    user: AuthUser = Depends(get_current_user),
):
    """Get a single scheduled profile."""
    from app.database.store import get_scheduled_profile

    row = get_scheduled_profile(profile_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scheduled profile not found")
    return _row_to_scheduled_profile_response(row)


@app.patch("/scheduled-profiles/{profile_id}", response_model=ScheduledProfileResponse)
@limiter.limit(config.rate_limit_default)
async def update_scheduled_profile_endpoint(
    request: Request,
    profile_id: int,
    body: ScheduledProfileUpdate,
    user: AuthUser = Depends(get_current_user),
):
    """Update a scheduled profile (toggle active, change interval, etc.)."""
    from app.database.store import update_scheduled_profile, get_scheduled_profile
    from app.scheduler.engine import add_profile_job, remove_profile_job

    updates = body.model_dump(exclude_none=True)
    if "profile" in updates:
        updates["profile_json"] = body.profile.model_dump_json()
        del updates["profile"]
    if not update_scheduled_profile(profile_id, **updates):
        raise HTTPException(status_code=404, detail="Scheduled profile not found")
    row = get_scheduled_profile(profile_id)
    if config.scheduler_enabled:
        if row["is_active"]:
            add_profile_job(profile_id, row["interval_minutes"])
        else:
            remove_profile_job(profile_id)
    return _row_to_scheduled_profile_response(row)


@app.delete("/scheduled-profiles/{profile_id}")
@limiter.limit(config.rate_limit_default)
async def delete_scheduled_profile_endpoint(
    request: Request,
    profile_id: int,
    user: AuthUser = Depends(get_current_user),
):
    """Delete a scheduled profile and its alerts."""
    from app.database.store import delete_scheduled_profile
    from app.scheduler.engine import remove_profile_job

    if not delete_scheduled_profile(profile_id):
        raise HTTPException(status_code=404, detail="Scheduled profile not found")
    if config.scheduler_enabled:
        remove_profile_job(profile_id)
    return {"status": "deleted", "profile_id": profile_id}


@app.post("/scheduled-profiles/{profile_id}/run-now")
@limiter.limit(config.rate_limit_discover)
async def run_scheduled_now(
    request: Request,
    profile_id: int,
    user: AuthUser = Depends(get_current_user),
):
    """Trigger an immediate discovery run for a scheduled profile."""
    import threading
    from app.database.store import get_scheduled_profile
    from app.scheduler.engine import run_scheduled_discovery

    row = get_scheduled_profile(profile_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scheduled profile not found")
    thread = threading.Thread(target=run_scheduled_discovery, args=[profile_id], daemon=True)
    thread.start()
    return {"status": "started", "profile_id": profile_id, "message": "Discovery running in background"}


# ─── Alerts ───────────────────────────────────────────────────────────────────


@app.get("/alerts", response_model=AlertListResponse)
@limiter.limit(config.rate_limit_default)
async def list_alerts(
    request: Request,
    profile_id: Optional[int] = None,
    unread_only: bool = False,
    limit: int = 100,
    user: AuthUser = Depends(get_current_user),
):
    """List job discovery alerts."""
    from app.database.store import get_alerts, get_job, get_scheduled_profile

    rows = get_alerts(profile_id=profile_id, unread_only=unread_only, limit=limit)
    alerts = []
    for r in rows:
        job = get_job(r["job_id"])
        profile_row = get_scheduled_profile(r["profile_id"])
        alerts.append(ScheduleAlert(
            id=r["id"],
            profile_id=r["profile_id"],
            profile_name=profile_row["profile_name"] if profile_row else None,
            job_id=r["job_id"],
            job=job,
            match_score=r["match_score"],
            recommendation=r.get("recommendation", ""),
            is_read=bool(r["is_read"]),
            created_at=r["created_at"],
        ))
    unread = sum(1 for a in alerts if not a.is_read)
    return AlertListResponse(total=len(alerts), unread_count=unread, alerts=alerts)


@app.patch("/alerts/{alert_id}/read")
@limiter.limit(config.rate_limit_default)
async def mark_alert_as_read(
    request: Request,
    alert_id: int,
    user: AuthUser = Depends(get_current_user),
):
    """Mark a single alert as read."""
    from app.database.store import mark_alert_read

    if not mark_alert_read(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "marked_read", "alert_id": alert_id}


@app.post("/alerts/mark-all-read")
@limiter.limit(config.rate_limit_default)
async def mark_all_read(
    request: Request,
    profile_id: Optional[int] = None,
    user: AuthUser = Depends(get_current_user),
):
    """Mark all alerts as read, optionally scoped to a profile."""
    from app.database.store import mark_all_alerts_read

    count = mark_all_alerts_read(profile_id)
    return {"status": "ok", "marked_count": count}


# ─── File Downloads (Supabase Storage) ────────────────────────────────────────

@app.get("/files/{path:path}")
@limiter.limit(config.rate_limit_default)
async def download_file(
    request: Request,
    path: str,
    user: AuthUser = Depends(get_current_user),
):
    """Redirect to a signed Supabase Storage URL for file download."""
    from app.storage.supabase_storage import get_signed_url
    url = get_signed_url(path, expires_in=300)
    return RedirectResponse(url)
