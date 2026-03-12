"""Tests for ATS search filters module."""
from app.api.schemas import EducationSchema, ExperienceSchema, ParsedResume, SearchFilters
from app.search.filters import apply_filters


def _make_resumes():
    return [
        ParsedResume(
            candidate_name="Alice",
            skills=["Python", "JavaScript", "React"],
            total_years_experience=5.0,
            location="San Francisco, CA",
            education=[EducationSchema(degree="Master of Science")],
            experience=[ExperienceSchema(job_title="Senior Engineer", company="Acme")],
        ),
        ParsedResume(
            candidate_name="Bob",
            skills=["Java", "Spring Boot"],
            total_years_experience=2.0,
            location="New York, NY",
            education=[EducationSchema(degree="Bachelor of Science")],
            experience=[ExperienceSchema(job_title="Junior Developer", company="Corp")],
        ),
        ParsedResume(
            candidate_name="Charlie",
            skills=["Python", "Django", "PostgreSQL"],
            total_years_experience=8.0,
            location="Austin, TX",
            education=[EducationSchema(degree="Doctorate in Computer Science")],
            experience=[ExperienceSchema(job_title="Staff Engineer", company="BigCo")],
        ),
    ]


class TestSearchFilters:
    def test_no_filters_returns_all(self):
        resumes = _make_resumes()
        result = apply_filters(resumes, SearchFilters())
        assert result.filtered == 3

    def test_filter_skills_all(self):
        resumes = _make_resumes()
        result = apply_filters(resumes, SearchFilters(skills=["Python"]))
        assert result.filtered == 2
        names = [r.candidate_name for r in result.candidates]
        assert "Alice" in names
        assert "Charlie" in names

    def test_filter_skills_any(self):
        resumes = _make_resumes()
        result = apply_filters(resumes, SearchFilters(skills_any=["Java", "Django"]))
        assert result.filtered == 2

    def test_filter_min_experience(self):
        resumes = _make_resumes()
        result = apply_filters(resumes, SearchFilters(min_years_experience=5.0))
        assert result.filtered == 2

    def test_filter_max_experience(self):
        resumes = _make_resumes()
        result = apply_filters(resumes, SearchFilters(max_years_experience=3.0))
        assert result.filtered == 1
        assert result.candidates[0].candidate_name == "Bob"

    def test_filter_education_level(self):
        resumes = _make_resumes()
        result = apply_filters(resumes, SearchFilters(education_level="master"))
        assert result.filtered == 2  # Alice (master) and Charlie (doctorate)

    def test_filter_location(self):
        resumes = _make_resumes()
        result = apply_filters(resumes, SearchFilters(location="San Francisco"))
        assert result.filtered == 1
        assert result.candidates[0].candidate_name == "Alice"

    def test_filter_job_title_keywords(self):
        resumes = _make_resumes()
        result = apply_filters(resumes, SearchFilters(job_title_keywords=["Senior", "Staff"]))
        assert result.filtered == 2

    def test_combined_filters(self):
        resumes = _make_resumes()
        result = apply_filters(resumes, SearchFilters(
            skills=["Python"],
            min_years_experience=6.0,
        ))
        assert result.filtered == 1
        assert result.candidates[0].candidate_name == "Charlie"
