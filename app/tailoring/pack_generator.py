from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import pandas as pd

from app.api.schemas import (
    ApplicationBundle,
    ApplicationPack,
    JobMatchResult,
    ParsedResume,
    TailoredResume,
)
from app.core.logging import get_logger
from app.core.paths import APPLICATION_PACKS_DIR
from app.tailoring.ats_checker import ats_self_check
from app.tailoring.cover_letter import generate_cover_letter
from app.tailoring.cover_letter_docx import generate_cover_letter_docx
from app.tailoring.docx_generator import generate_ats_docx
from app.tailoring.pdf_generator import generate_pdf_from_docx
from app.tailoring.rewriter import tailor_resume

logger = get_logger(__name__)


def _safe_filename(text: str) -> str:
    """Convert text to a safe filename."""
    return re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_")[:50]


def generate_application_pack(
    resume: ParsedResume,
    match: JobMatchResult,
    output_dir: Path | None = None,
) -> ApplicationPack:
    """Generate a complete application pack for one job."""
    job = match.job

    if output_dir is None:
        candidate_name = _safe_filename(resume.candidate_name or "candidate")
        company = _safe_filename(job.company or "company")
        role = _safe_filename(job.title or "role")
        output_dir = APPLICATION_PACKS_DIR / candidate_name / f"{company}_{role}"

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Tailor resume
    tailored = tailor_resume(resume, job, match.matched_skills)

    # 2. Generate DOCX
    docx_path = output_dir / f"resume_{_safe_filename(job.company)}_{_safe_filename(job.title)}.docx"
    generate_ats_docx(resume, tailored, docx_path)
    tailored.docx_path = str(docx_path)

    # 3. ATS self-check
    ats_result = ats_self_check(docx_path, resume, match.job)
    tailored.ats_score = ats_result["ats_score"]
    tailored.keyword_coverage = ats_result["keyword_coverage"]
    if tailored.ats_score < 60:
        logger.warning("Low ATS score %.1f for %s at %s", tailored.ats_score, job.title, job.company)

    # 4. Generate PDF
    try:
        pdf_path = generate_pdf_from_docx(docx_path)
        tailored.pdf_path = str(pdf_path)
    except Exception as e:
        logger.warning("PDF generation failed for %s: %s", docx_path, e)

    # 5. Cover letter
    try:
        cl_text = generate_cover_letter(resume, job, match)
        safe_company = _safe_filename(job.company or "company")
        safe_role = _safe_filename(job.title or "role")
        cl_docx_path = output_dir / f"cover_letter_{safe_company}_{safe_role}.docx"
        generate_cover_letter_docx(cl_text, resume, cl_docx_path)
        tailored.cover_letter_path = str(cl_docx_path)
        try:
            generate_pdf_from_docx(cl_docx_path)
        except Exception:
            pass
    except Exception as e:
        logger.warning("Cover letter generation failed: %s", e)

    # 6. Job summary JSON
    job_summary_path = output_dir / "job_summary.json"
    job_summary_path.write_text(
        json.dumps(job.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )

    # 7. Match explanation JSON
    explanation_path = output_dir / "match_explanation.json"
    explanation_path.write_text(
        json.dumps(match.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )

    return ApplicationPack(
        job=job,
        match_result=match,
        tailored_resume=tailored,
    )


def generate_application_bundle(
    resume: ParsedResume,
    ranked_jobs: list[JobMatchResult],
) -> ApplicationBundle:
    """Generate application packs for all ranked jobs and bundle them."""
    candidate_name = _safe_filename(resume.candidate_name or "candidate")
    bundle_dir = APPLICATION_PACKS_DIR / candidate_name
    bundle_dir.mkdir(parents=True, exist_ok=True)

    packs: list[ApplicationPack] = []
    spreadsheet_rows = []

    for i, match in enumerate(ranked_jobs, 1):
        pack = generate_application_pack(resume, match)
        packs.append(pack)

        spreadsheet_rows.append({
            "Rank": i,
            "Company": match.job.company,
            "Role": match.job.title,
            "Score": f"{match.match_score:.1f}",
            "Recommendation": match.recommendation,
            "Apply URL": match.job.apply_url or "",
            "Matched Skills": ", ".join(match.matched_skills[:5]),
            "Missing Skills": ", ".join(match.missing_skills[:5]),
            "ATS Score": f"{pack.tailored_resume.ats_score:.1f}",
            "Keyword Coverage": f"{pack.tailored_resume.keyword_coverage:.1%}",
            "Resume DOCX": pack.tailored_resume.docx_path or "",
            "Resume PDF": pack.tailored_resume.pdf_path or "",
            "Cover Letter": pack.tailored_resume.cover_letter_path or "",
        })

    # Master spreadsheet
    spreadsheet_path = bundle_dir / "master_ranking.csv"
    df = pd.DataFrame(spreadsheet_rows)
    df.to_csv(str(spreadsheet_path), index=False)

    # Also generate Excel
    excel_path = bundle_dir / "master_ranking.xlsx"
    df.to_excel(str(excel_path), index=False)

    # ZIP everything
    zip_path = bundle_dir / f"{candidate_name}_application_packs.zip"
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for file in bundle_dir.rglob("*"):
            if file.is_file() and file != zip_path:
                arcname = file.relative_to(bundle_dir)
                zf.write(str(file), str(arcname))

    logger.info("Generated application bundle: %d packs, zip at %s", len(packs), zip_path)

    return ApplicationBundle(
        candidate_name=resume.candidate_name,
        total_jobs=len(packs),
        packs=packs,
        master_spreadsheet_path=str(spreadsheet_path),
        bundle_zip_path=str(zip_path),
    )
