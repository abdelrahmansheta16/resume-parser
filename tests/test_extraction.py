from app.extraction.links import extract_contact_info
from app.extraction.sections import detect_sections
from app.extraction.entities import extract_name_from_header, extract_location
from app.extraction.skills import (
    extract_skills_from_text,
    extract_skills_from_section,
    normalize_skill,
    load_skill_taxonomy,
)
from app.extraction.education import extract_education
from app.extraction.experience import extract_experience, estimate_total_years
from app.extraction.resume_structurer import structure_resume


class TestContactExtraction:
    def test_email(self):
        info = extract_contact_info("Contact: john@example.com for details")
        assert "john@example.com" in info.emails

    def test_phone(self):
        info = extract_contact_info("Call me at +1-555-123-4567")
        assert len(info.phones) >= 1

    def test_linkedin(self):
        info = extract_contact_info("LinkedIn: https://linkedin.com/in/johndoe")
        assert info.linkedin is not None
        assert "johndoe" in info.linkedin

    def test_github(self):
        info = extract_contact_info("GitHub: https://github.com/johndoe")
        assert info.github is not None
        assert "johndoe" in info.github


class TestSectionDetection:
    def test_detects_common_sections(self, sample_resume_text):
        sections = detect_sections(sample_resume_text)
        assert "header" in sections
        assert "skills" in sections
        assert "experience" in sections
        assert "education" in sections

    def test_no_sections_returns_full_text(self):
        sections = detect_sections("Just a random block of text with no headings")
        assert "full_text" in sections


class TestNameExtraction:
    def test_from_header(self):
        header = "JOHN DOE\njohn@email.com\n+1-555-123-4567"
        name = extract_name_from_header(header)
        assert name == "JOHN DOE"

    def test_from_header_with_label(self):
        header = "Sarah Johnson\nEmail: sarah@gmail.com"
        name = extract_name_from_header(header)
        assert name == "Sarah Johnson"


class TestLocationExtraction:
    def test_city_state(self):
        loc = extract_location("Based in San Francisco, CA\njohn@email.com")
        assert loc is not None
        assert "San Francisco" in loc

    def test_explicit_location(self):
        loc = extract_location("Location: New York, NY")
        assert loc is not None
        assert "New York" in loc


class TestSkillExtraction:
    def test_normalize_exact(self):
        taxonomy = load_skill_taxonomy()
        assert normalize_skill("python3", taxonomy) == "Python"
        assert normalize_skill("js", taxonomy) == "JavaScript"
        assert normalize_skill("react", taxonomy) == "React"

    def test_normalize_fuzzy(self):
        taxonomy = load_skill_taxonomy()
        result = normalize_skill("nodejs", taxonomy)
        assert result == "Node.js"

    def test_extract_from_text(self):
        text = "Experienced in Python, Docker, and PostgreSQL development"
        skills = extract_skills_from_text(text)
        assert "Python" in skills
        assert "Docker" in skills
        assert "PostgreSQL" in skills

    def test_extract_from_section(self):
        section = "Python, FastAPI, Django, Flask, PostgreSQL, MongoDB, Redis, Docker, Kubernetes"
        skills = extract_skills_from_section(section)
        assert "Python" in skills
        assert "FastAPI" in skills
        assert "Docker" in skills


class TestEducationExtraction:
    def test_basic(self):
        text = """Bachelor of Science in Computer Science
University of California, Berkeley
Graduated: May 2019
GPA: 3.7/4.0"""
        entries = extract_education(text)
        assert len(entries) >= 1
        edu = entries[0]
        assert edu.degree is not None
        assert "Computer Science" in (edu.field_of_study or "")

    def test_multiple_entries(self):
        text = """Master of Science in Data Science
Columbia University, New York, NY
Graduated: December 2021

Bachelor of Science in Mathematics
Boston University, Boston, MA
Graduated: May 2019"""
        entries = extract_education(text)
        assert len(entries) >= 2


class TestExperienceExtraction:
    def test_basic(self):
        text = """Senior Backend Developer
ABC Technology Inc., San Francisco, CA
January 2022 - Present
- Led development of microservices architecture
- Designed event-driven data pipeline"""
        entries = extract_experience(text)
        assert len(entries) >= 1
        exp = entries[0]
        assert exp.start_date is not None

    def test_estimate_total_years(self):
        text = """Backend Developer
XYZ Corp
June 2019 - December 2021
- Built REST APIs"""
        entries = extract_experience(text)
        years = estimate_total_years(entries)
        assert years >= 1.0


class TestResumeStructurer:
    def test_full_pipeline(self, sample_resume_text):
        resume = structure_resume(sample_resume_text)
        assert resume.candidate_name is not None
        assert resume.email is not None
        assert len(resume.skills) > 0
        assert len(resume.experience) > 0
        assert resume.total_years_experience > 0

    def test_second_resume(self, sample_resume_text_2):
        resume = structure_resume(sample_resume_text_2)
        assert resume.candidate_name is not None
        assert resume.email is not None
        assert len(resume.skills) > 0
