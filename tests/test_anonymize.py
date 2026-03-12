"""Tests for anonymization module."""
from app.anonymize.redactor import anonymize_resume
from app.api.schemas import EducationSchema, ParsedResume


class TestAnonymizeResume:
    def _make_resume(self):
        return ParsedResume(
            candidate_name="John Doe",
            email="john@example.com",
            phone="555-123-4567",
            location="San Francisco, CA",
            linkedin="linkedin.com/in/johndoe",
            github="github.com/johndoe",
            portfolio="johndoe.dev",
            skills=["Python", "JavaScript"],
            education=[
                EducationSchema(
                    degree="Bachelor of Science",
                    institution="Stanford University",
                )
            ],
        )

    def test_name_replaced(self):
        resume = self._make_resume()
        anon = anonymize_resume(resume, candidate_id=1)
        assert anon.candidate_name == "Candidate A"
        assert anon.anonymized is True

    def test_contact_info_stripped(self):
        resume = self._make_resume()
        anon = anonymize_resume(resume)
        assert anon.email is None
        assert anon.phone is None
        assert anon.linkedin is None
        assert anon.github is None
        assert anon.portfolio is None
        assert anon.location is None

    def test_institution_anonymized(self):
        resume = self._make_resume()
        anon = anonymize_resume(resume)
        assert anon.education[0].institution == "[University]"
        # Degree should be preserved
        assert anon.education[0].degree == "Bachelor of Science"

    def test_skills_preserved(self):
        resume = self._make_resume()
        anon = anonymize_resume(resume)
        assert anon.skills == ["Python", "JavaScript"]

    def test_original_not_modified(self):
        resume = self._make_resume()
        anonymize_resume(resume)
        assert resume.candidate_name == "John Doe"
        assert resume.email == "john@example.com"

    def test_candidate_id_labeling(self):
        resume = self._make_resume()
        assert anonymize_resume(resume, 1).candidate_name == "Candidate A"
        assert anonymize_resume(resume, 2).candidate_name == "Candidate B"
        assert anonymize_resume(resume, 3).candidate_name == "Candidate C"
