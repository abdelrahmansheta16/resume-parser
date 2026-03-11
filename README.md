# Resume Parser & Candidate Ranker

An end-to-end NLP application that automatically parses resumes, extracts structured candidate information, and ranks candidates against job descriptions.

## Business Problem

Recruiters spend significant time manually reviewing resumes. This tool automates early-stage screening by:
- Extracting key candidate information (name, contact, skills, education, experience)
- Normalizing skills using a curated taxonomy
- Comparing candidates against job requirements
- Ranking applicants with explainable scores

## Supported File Types

| Format | Support |
|--------|---------|
| PDF | ✓ (pdfplumber + PyMuPDF fallback) |
| DOCX | ✓ (python-docx) |
| TXT | ✓ (direct read) |

## Architecture

```
Resume File → Document Loader → Text Extractor → Cleaner
    → Section Detector → Entity Extractor → Skill Normalizer
    → Resume Structurer → Matcher/Ranker → API/Frontend
```

### Pipeline Components

1. **Document Loader** — Detects file type, dispatches to appropriate parser
2. **Text Extractor** — PDF (pdfplumber/PyMuPDF), DOCX (python-docx), TXT
3. **Cleaner** — Normalizes whitespace, fixes broken characters, preserves structure
4. **Section Detector** — Regex + heuristic heading matching for 8 section types
5. **Entity Extractor** — Rule-based (email, phone, links) + spaCy NER (names, orgs)
6. **Skill Normalizer** — Taxonomy-based with fuzzy matching (80+ canonical skills)
7. **Resume Structurer** — Combines all extractors into a unified JSON profile
8. **JD Parser** — Extracts required/preferred skills, years, education from job descriptions
9. **Matcher/Ranker** — Multi-dimensional scoring with configurable weights

### Scoring Dimensions

| Dimension | Default Weight | Description |
|-----------|---------------|-------------|
| Skill Match | 40% | Overlap of resume skills with required JD skills |
| Semantic Similarity | 20% | Embedding-based text similarity (MiniLM) |
| Experience Match | 20% | Years of experience alignment |
| Title Relevance | 10% | Job title fuzzy matching |
| Education Match | 10% | Education level comparison |

## Extraction Pipeline

### Contact Info (Rule-based)
- Email, phone, LinkedIn, GitHub, portfolio URLs via regex

### Skills (Taxonomy + Fuzzy Matching)
- 80+ canonical skills across categories: programming, database, frontend, backend, cloud, devops, ML, data, tools
- Alias resolution: "JS" → "JavaScript", "k8s" → "Kubernetes"
- Fuzzy matching threshold: 85%

### Education (Pattern + Heuristic)
- Degree normalization via taxonomy (16 degree types)
- Field of study, institution, graduation date, GPA extraction

### Experience (Date + Heuristic)
- Date range detection with multiple formats
- Job title and company extraction
- Duration calculation and total years estimation

## Example Output

### Parsed Resume
```json
{
  "candidate_name": "John Doe",
  "email": "john.doe@email.com",
  "phone": "+1-555-123-4567",
  "location": "San Francisco, CA",
  "linkedin": "https://linkedin.com/in/johndoe",
  "github": "https://github.com/johndoe",
  "skills": ["AWS", "CI/CD", "Django", "Docker", "FastAPI", "Flask", "Git", "GraphQL", "Kubernetes", "Linux", "MongoDB", "PostgreSQL", "Python", "REST API", "Redis", "Terraform"],
  "education": [{"degree": "Bachelor of Science", "field_of_study": "Computer Science", "institution": "University of California, Berkeley", "graduation_date": "2019", "gpa": "3.7/4.0"}],
  "experience": [{"job_title": "Senior Backend Developer", "company": "ABC Technology Inc.", "start_date": "January 2022", "end_date": "Present"}],
  "total_years_experience": 6.5
}
```

### Match Result
```json
{
  "candidate_name": "John Doe",
  "match_score": 84.5,
  "recommendation": "Good Match",
  "matched_skills": ["Python", "FastAPI", "Docker", "PostgreSQL", "Redis", "Kubernetes", "AWS", "REST API", "CI/CD"],
  "missing_skills": ["Kafka"],
  "explanation": [
    "Strong alignment in: Python, FastAPI, Docker, PostgreSQL, Redis",
    "Meets experience requirement (6.5 years vs 5+ required)",
    "Most recent role: Senior Backend Developer"
  ]
}
```

## API Usage

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/model-info` | GET | Version and model info |
| `/parse-resume` | POST | Parse a single resume file |
| `/parse-job-description` | POST | Parse job description text |
| `/match-resume` | POST | Match one resume against one JD |
| `/rank-candidates` | POST | Rank multiple resumes against one JD |
| `/export-ranking/csv` | POST | Export ranking as CSV |
| `/export-ranking/excel` | POST | Export ranking as Excel |

### Example API Call

```bash
# Parse a resume
curl -X POST http://localhost:8000/parse-resume \
  -F "file=@resume.pdf"

# Match resume to JD
curl -X POST http://localhost:8000/match-resume \
  -F "file=@resume.pdf" \
  -F "job_description=Senior Backend Engineer with 5+ years Python..."

# Rank multiple candidates
curl -X POST http://localhost:8000/rank-candidates \
  -F "files=@resume1.pdf" \
  -F "files=@resume2.pdf" \
  -F "job_description=Senior Backend Engineer..."
```

## Frontend

The Streamlit frontend provides 5 pages:

1. **Overview** — Project description and scoring methodology
2. **Parse Resume** — Upload and view extracted structured data
3. **Match Resume** — Upload resume + paste JD → score breakdown
4. **Rank Candidates** — Upload multiple resumes → ranked leaderboard with export
5. **Insights** — Aggregate skill analysis and skill gap visualization

## How to Run Locally

### Prerequisites
- Python 3.11+
- pip

### Setup

```bash
cd resume-parser

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

### Run API

```bash
uvicorn app.api.main:app --reload --port 8000
```

### Run Frontend

```bash
streamlit run app/frontend/streamlit_app.py
```

### Run Tests

```bash
pytest tests/ -v
```

### Docker

```bash
# Build
docker build -t resume-parser .

# Run API
docker run -p 8000:8000 resume-parser

# Run Streamlit
docker run -p 8501:8501 resume-parser \
  streamlit run app/frontend/streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

## Limitations

- Name extraction relies on heuristics and spaCy NER — may fail on unusual formats
- Section detection uses heading patterns — non-standard headings may not be detected
- Experience date parsing handles common formats but may miss edge cases
- Skill taxonomy covers ~80 canonical skills — domain-specific skills may not normalize
- Semantic similarity requires `sentence-transformers` — falls back to 0 if unavailable
- No OCR support for image-based PDFs (stretch goal)

## Future Improvements

- OCR fallback for scanned/image-based resumes
- Multilingual resume support
- Fine-tuned NER model for resume entities
- Vector database for semantic candidate search
- Recruiter feedback loop for score calibration
- Bias-aware anonymized screening mode
- ATS-style search filters
- GitHub Actions CI pipeline
- Cloud deployment (AWS/GCP)

## Tech Stack

- **NLP/Data**: spaCy, NLTK, scikit-learn, pandas, rapidfuzz
- **Document Parsing**: pdfplumber, PyMuPDF, python-docx
- **Semantic**: sentence-transformers (all-MiniLM-L6-v2)
- **API**: FastAPI, Pydantic
- **Frontend**: Streamlit
- **Testing**: pytest, httpx
- **Deployment**: Docker
