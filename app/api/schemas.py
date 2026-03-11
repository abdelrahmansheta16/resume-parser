from typing import List, Optional

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
