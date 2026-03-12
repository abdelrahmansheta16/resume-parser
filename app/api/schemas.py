from typing import Dict, List, Optional

from pydantic import BaseModel


class EducationSchema(BaseModel):
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    institution: Optional[str] = None
    graduation_date: Optional[str] = None
    gpa: Optional[str] = None


class ExperienceSchema(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_months: Optional[int] = None
    description: List[str] = []


class ParsedResume(BaseModel):
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = []
    education: List[EducationSchema] = []
    experience: List[ExperienceSchema] = []
    certifications: List[str] = []
    projects: List[str] = []
    total_years_experience: float = 0.0
    raw_text: Optional[str] = None
    detected_language: Optional[str] = None
    anonymized: bool = False
    parse_method: Optional[str] = None


class ParsedJobDescription(BaseModel):
    title: Optional[str] = None
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    required_years_experience: Optional[float] = None
    education_requirements: List[str] = []
    tools_and_technologies: List[str] = []
    soft_skills: List[str] = []
    raw_text: Optional[str] = None


class MatchResult(BaseModel):
    candidate_name: Optional[str] = None
    match_score: float = 0.0
    recommendation: str = "No Match"
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    experience_match_score: float = 0.0
    education_match_score: float = 0.0
    title_match_score: float = 0.0
    semantic_similarity_score: float = 0.0
    keyword_relevance_score: float = 0.0
    explanation: List[str] = []


class RankingResult(BaseModel):
    job_description: ParsedJobDescription
    candidates: List[MatchResult] = []


class ModelInfoResponse(BaseModel):
    extraction_version: str
    matching_version: str
    taxonomy_version: str
    embedding_model: str


class HealthResponse(BaseModel):
    status: str = "ok"


# --- Goal 6: Deduplication ---

class DuplicateGroup(BaseModel):
    group_id: int
    candidates: List[str] = []
    reason: str = ""
    confidence: float = 0.0


class DeduplicationResult(BaseModel):
    total_candidates: int = 0
    duplicate_groups: List[DuplicateGroup] = []
    unique_candidates: int = 0


# --- Goal 7: ATS Search Filters ---

class SearchFilters(BaseModel):
    skills: Optional[List[str]] = None
    skills_any: Optional[List[str]] = None
    min_years_experience: Optional[float] = None
    max_years_experience: Optional[float] = None
    education_level: Optional[str] = None
    location: Optional[str] = None
    job_title_keywords: Optional[List[str]] = None


class SearchResult(BaseModel):
    total: int = 0
    filtered: int = 0
    candidates: List[ParsedResume] = []


# --- Goal 8: Vector Database Search ---

class VectorSearchQuery(BaseModel):
    query: str
    n_results: int = 10
    filter_skills: Optional[List[str]] = None


class VectorSearchHit(BaseModel):
    candidate_name: Optional[str] = None
    similarity_score: float = 0.0
    skills: List[str] = []
    summary: Optional[str] = None
    resume_id: Optional[str] = None


class VectorSearchResult(BaseModel):
    query: str
    hits: List[VectorSearchHit] = []
    total_indexed: int = 0


# --- Goal 9: Human Review Queue ---

class ConfidenceScore(BaseModel):
    name_confidence: float = 0.0
    skills_confidence: float = 0.0
    education_confidence: float = 0.0
    experience_confidence: float = 0.0
    overall: float = 0.0


class ReviewItem(BaseModel):
    review_id: str
    resume: ParsedResume
    confidence: ConfidenceScore
    status: str = "pending"
    reviewer_notes: Optional[str] = None
    created_at: Optional[str] = None


class ReviewQueueResponse(BaseModel):
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    items: List[ReviewItem] = []


# --- Goal 10: Recruiter Feedback Loop ---

class FeedbackSubmission(BaseModel):
    candidate_name: str
    job_title: Optional[str] = None
    match_score: float = 0.0
    feedback: str  # "positive" or "negative"
    dimension_scores: Optional[Dict[str, float]] = None
    notes: Optional[str] = None


class FeedbackStats(BaseModel):
    total_feedback: int = 0
    positive_count: int = 0
    negative_count: int = 0
    current_weights: Dict[str, float] = {}
    adjusted_weights: Optional[Dict[str, float]] = None


# === Job Discovery & Application Pack Schemas ===

class JobPosting(BaseModel):
    job_id: str
    title: str
    company: str
    location: Optional[str] = None
    employment_type: Optional[str] = None
    description: str = ""
    requirements: List[str] = []
    preferred_qualifications: List[str] = []
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    required_years_experience: Optional[float] = None
    education_requirements: List[str] = []
    salary_range: Optional[str] = None
    apply_url: Optional[str] = None
    posting_date: Optional[str] = None
    source: str = ""
    raw_text: Optional[str] = None


class CandidateProfile(BaseModel):
    resume: ParsedResume
    target_titles: List[str] = []
    target_locations: List[str] = []
    target_industries: List[str] = []
    remote_preference: Optional[str] = None
    min_salary: Optional[float] = None
    seniority_level: Optional[str] = None


class JobMatchResult(BaseModel):
    job: JobPosting
    match_score: float = 0.0
    recommendation: str = ""
    skill_score: float = 0.0
    semantic_score: float = 0.0
    experience_score: float = 0.0
    title_score: float = 0.0
    education_score: float = 0.0
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    explanation: List[str] = []


class JobDiscoveryResult(BaseModel):
    total_found: int = 0
    total_after_dedup: int = 0
    ranked_jobs: List[JobMatchResult] = []


class TailoredResume(BaseModel):
    job_id: str = ""
    tailored_summary: str = ""
    tailored_skills: List[str] = []
    tailored_experience: List[ExperienceSchema] = []
    ats_score: float = 0.0
    keyword_coverage: float = 0.0
    docx_path: Optional[str] = None
    pdf_path: Optional[str] = None
    cover_letter_path: Optional[str] = None


class ApplicationRecord(BaseModel):
    id: int
    job_id: str
    candidate_name: str
    match_score: float = 0.0
    ats_score: float = 0.0
    status: str = "generated"
    created_at: str = ""

class ApplicationListResponse(BaseModel):
    total: int = 0
    applications: List[ApplicationRecord] = []


class ApplicationPack(BaseModel):
    job: JobPosting
    match_result: JobMatchResult
    tailored_resume: TailoredResume
    company_summary: Optional[str] = None
    outreach_drafts: List[str] = []


class ApplicationBundle(BaseModel):
    candidate_name: Optional[str] = None
    total_jobs: int = 0
    packs: List[ApplicationPack] = []
    master_spreadsheet_path: Optional[str] = None
    bundle_zip_path: Optional[str] = None


class CompanyResearch(BaseModel):
    company_name: str
    domain: Optional[str] = None
    about: Optional[str] = None
    tech_stack: List[str] = []
    careers_url: Optional[str] = None
    public_contacts: List[Dict[str, str]] = []


class OutreachDraft(BaseModel):
    target_role: str = "recruiter"
    subject: str = ""
    body: str = ""
    compliance_notes: List[str] = []


class DiscoveryTask(BaseModel):
    task_id: str
    status: str = "pending"  # pending, running, completed, failed
    progress: float = 0.0  # 0.0 - 1.0
    message: str = ""
    result: Optional[JobDiscoveryResult] = None
    created_at: str = ""
    completed_at: Optional[str] = None


# === Scheduled Job Discovery Schemas ===


class ScheduledProfileCreate(BaseModel):
    profile_name: str
    profile: CandidateProfile
    interval_minutes: int = 360


class ScheduledProfileResponse(BaseModel):
    id: int
    profile_name: str
    profile: CandidateProfile
    is_active: bool = True
    interval_minutes: int = 360
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class ScheduledProfileListResponse(BaseModel):
    total: int = 0
    profiles: List[ScheduledProfileResponse] = []


class ScheduledProfileUpdate(BaseModel):
    profile_name: Optional[str] = None
    profile: Optional[CandidateProfile] = None
    is_active: Optional[bool] = None
    interval_minutes: Optional[int] = None


class ScheduleAlert(BaseModel):
    id: int
    profile_id: int
    profile_name: Optional[str] = None
    job: Optional[JobPosting] = None
    job_id: str
    match_score: float = 0.0
    recommendation: str = ""
    is_read: bool = False
    created_at: str = ""


class AlertListResponse(BaseModel):
    total: int = 0
    unread_count: int = 0
    alerts: List[ScheduleAlert] = []
