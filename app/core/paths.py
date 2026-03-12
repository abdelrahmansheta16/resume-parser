from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
TAXONOMIES_DIR = DATA_DIR / "taxonomies"
SAMPLES_DIR = DATA_DIR / "samples"
MODELS_DIR = PROJECT_ROOT / "app" / "models"
ARTIFACTS_DIR = MODELS_DIR / "artifacts"
REPORTS_DIR = PROJECT_ROOT / "reports"
FEEDBACK_DIR = DATA_DIR / "feedback"
REVIEW_DIR = DATA_DIR / "review"
CHROMADB_DIR = DATA_DIR / "chromadb"
JOBS_DIR = DATA_DIR / "jobs"
TEMPLATES_DIR = DATA_DIR / "templates"
APPLICATION_PACKS_DIR = DATA_DIR / "application_packs"
