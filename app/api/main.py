from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from app.api.schemas import (
    HealthResponse,
    MatchResult,
    ModelInfoResponse,
    ParsedJobDescription,
    ParsedResume,
    RankingResult,
)
from app.api.utils import resumes_to_csv, resumes_to_excel_bytes
from app.extraction.resume_structurer import structure_resume
from app.matching.jd_parser import parse_job_description
from app.matching.ranking import rank_candidates
from app.matching.scoring import score_candidate
from app.models.config import config
from app.parsing.file_loader import load_from_bytes

app = FastAPI(
    title="Resume Parser API",
    description="Parse resumes, extract structured data, and rank candidates against job descriptions.",
    version=config.extraction_version,
)

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


@app.post("/parse-resume", response_model=ParsedResume)
async def parse_resume(file: UploadFile = File(...)):
    _validate_file(file)
    content = await file.read()
    doc = load_from_bytes(content, file.filename)
    if not doc.success:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {doc.error}")
    return structure_resume(doc.cleaned_text, include_raw=True)


@app.post("/parse-job-description", response_model=ParsedJobDescription)
async def parse_jd(job_description: str = Form(...)):
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description text is required")
    return parse_job_description(job_description)


@app.post("/match-resume", response_model=MatchResult)
async def match_resume(
    file: UploadFile = File(...),
    job_description: str = Form(...),
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
async def rank(
    files: list[UploadFile] = File(...),
    job_description: str = Form(...),
):
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description text is required")
    if not files:
        raise HTTPException(status_code=400, detail="At least one resume file is required")

    parsed_resumes: list[ParsedResume] = []
    errors: list[str] = []

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

    jd = parse_job_description(job_description)
    result = rank_candidates(parsed_resumes, jd)
    return result


@app.post("/export-ranking/csv")
async def export_csv(
    files: list[UploadFile] = File(...),
    job_description: str = Form(...),
):
    ranking = await rank(files, job_description)
    csv_data = resumes_to_csv([c.model_dump() for c in ranking.candidates])
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ranking.csv"},
    )


@app.post("/export-ranking/excel")
async def export_excel(
    files: list[UploadFile] = File(...),
    job_description: str = Form(...),
):
    ranking = await rank(files, job_description)
    excel_bytes = resumes_to_excel_bytes([c.model_dump() for c in ranking.candidates])
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ranking.xlsx"},
    )
