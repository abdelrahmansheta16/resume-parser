from typing import List

from pydantic import BaseModel

from app.core.settings import get_env, get_env_bool, get_env_int


class MatchingWeights(BaseModel):
    skills: float = 0.40
    semantic_similarity: float = 0.20
    experience: float = 0.20
    title_relevance: float = 0.10
    education: float = 0.10


class AppConfig(BaseModel):
    embedding_model: str = get_env("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    spacy_model: str = get_env("SPACY_MODEL", "en_core_web_sm")
    matching_weights: MatchingWeights = MatchingWeights()
    max_upload_size_mb: int = get_env_int("MAX_UPLOAD_SIZE_MB", 10)
    supported_formats: List[str] = [".pdf", ".docx", ".txt"]
    extraction_version: str = "2.0.0"
    matching_version: str = "2.0.0"
    taxonomy_version: str = "2.0.0"
    cors_origins: str = get_env("CORS_ORIGINS", "*")
    # Feature flags
    ocr_enabled: bool = get_env_bool("OCR_ENABLED", True)
    feedback_enabled: bool = get_env_bool("FEEDBACK_ENABLED", True)
    supported_languages: List[str] = ["en", "ar", "fr"]
    # Vector DB
    chromadb_persist_dir: str = "data/chromadb"
    vector_collection_name: str = "resumes"
    # Job Discovery
    jooble_api_key: str = get_env("JOOBLE_API_KEY", "")
    adzuna_app_id: str = get_env("ADZUNA_APP_ID", "")
    adzuna_api_key: str = get_env("ADZUNA_API_KEY", "")
    usajobs_api_key: str = get_env("USAJOBS_API_KEY", "")
    usajobs_email: str = get_env("USAJOBS_EMAIL", "")
    job_discovery_max_results: int = get_env_int("JOB_DISCOVERY_MAX_RESULTS", 500)
    # Tailoring
    max_top_jobs: int = get_env_int("MAX_TOP_JOBS", 50)
    # LLM Enhancement
    anthropic_api_key: str = get_env("ANTHROPIC_API_KEY", "")
    llm_tailoring_enabled: bool = get_env_bool("LLM_TAILORING_ENABLED", False)
    llm_parsing_enabled: bool = get_env_bool("LLM_PARSING_ENABLED", False)
    # LinkedIn
    linkedin_search_enabled: bool = get_env_bool("LINKEDIN_SEARCH_ENABLED", True)
    # Connector resilience
    connector_timeout: int = get_env_int("CONNECTOR_TIMEOUT", 15)
    connector_max_retries: int = get_env_int("CONNECTOR_MAX_RETRIES", 2)
    # Scheduled Job Discovery
    scheduler_enabled: bool = get_env_bool("SCHEDULER_ENABLED", False)
    scheduler_interval_minutes: int = get_env_int("SCHEDULER_INTERVAL_MINUTES", 360)
    scheduler_match_threshold: float = float(get_env("SCHEDULER_MATCH_THRESHOLD", "60.0"))
    scheduler_max_alerts_per_run: int = get_env_int("SCHEDULER_MAX_ALERTS_PER_RUN", 20)
    # Supabase
    supabase_url: str = get_env("SUPABASE_URL", "")
    supabase_anon_key: str = get_env("SUPABASE_ANON_KEY", "")
    supabase_service_role_key: str = get_env("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_jwt_secret: str = get_env("SUPABASE_JWT_SECRET", "")
    supabase_storage_bucket: str = get_env("SUPABASE_STORAGE_BUCKET", "documents")
    # Rate Limiting
    rate_limit_default: str = get_env("RATE_LIMIT_DEFAULT", "60/minute")
    rate_limit_parse: str = get_env("RATE_LIMIT_PARSE", "20/minute")
    rate_limit_discover: str = get_env("RATE_LIMIT_DISCOVER", "10/minute")


def get_config() -> AppConfig:
    return config


config = AppConfig()
