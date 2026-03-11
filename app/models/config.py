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


config = AppConfig()
