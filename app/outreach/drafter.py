from __future__ import annotations

from app.api.schemas import JobMatchResult, JobPosting, OutreachDraft, ParsedResume
from app.core.logging import get_logger
from app.outreach.templates import TEMPLATES

logger = get_logger(__name__)

COMPLIANCE_NOTES = [
    "This is a draft only — review and personalize before sending.",
    "Ensure you have a legitimate reason to contact the recipient.",
    "Include an opt-out option if sending unsolicited emails (CAN-SPAM).",
    "For EU contacts, ensure GDPR compliance — do not store personal data without consent.",
    "Do not send automated bulk messages — each outreach should be individual and personalized.",
]


def draft_outreach(
    candidate: ParsedResume,
    job: JobPosting,
    match: JobMatchResult,
    target_role: str = "recruiter",
) -> OutreachDraft:
    """Draft an outreach message for a specific job and target role.

    Returns a draft with compliance notes. Messages are NOT auto-sent.
    """
    template = TEMPLATES.get(target_role, TEMPLATES["recruiter"])

    # Build template variables
    candidate_name = candidate.candidate_name or "Candidate"
    years = f"{candidate.total_years_experience:.0f}"
    top_skills = ", ".join(match.matched_skills[:4]) if match.matched_skills else ", ".join(candidate.skills[:4])

    # Pick top achievement from experience
    achievement = ""
    if candidate.experience and candidate.experience[0].description:
        bullet = candidate.experience[0].description[0]
        if len(bullet) > 120:
            bullet = bullet[:117] + "..."
        achievement = f"A key accomplishment: {bullet}"

    variables = {
        "candidate_name": candidate_name,
        "role": job.title or "the open position",
        "company": job.company or "your company",
        "years": years,
        "top_skills": top_skills,
        "achievement": achievement,
    }

    subject = template["subject"].format(**variables)
    body = template["body"].format(**variables)

    return OutreachDraft(
        target_role=target_role,
        subject=subject,
        body=body,
        compliance_notes=COMPLIANCE_NOTES,
    )


def draft_all_outreach(
    candidate: ParsedResume,
    job: JobPosting,
    match: JobMatchResult,
) -> list[OutreachDraft]:
    """Generate outreach drafts for all target roles."""
    drafts = []
    for role in ["recruiter", "hiring_manager", "referral"]:
        drafts.append(draft_outreach(candidate, job, match, role))
    return drafts
