"""Tests for deduplication module."""
from app.api.schemas import ParsedResume
from app.dedup.fingerprint import compute_fingerprint, normalize_name, normalize_email
from app.dedup.matcher import find_duplicates


class TestFingerprint:
    def test_normalize_name(self):
        assert normalize_name("John Doe") == "john doe"
        assert normalize_name("Dr. Jane Smith") == "jane smith"
        assert normalize_name("  Mr.  Bob  ") == "bob"
        assert normalize_name(None) == ""

    def test_normalize_email(self):
        assert normalize_email("John@EXAMPLE.com") == "john@example.com"
        assert normalize_email(None) == ""

    def test_compute_fingerprint(self):
        resume = ParsedResume(
            candidate_name="John Doe",
            email="john@example.com",
            phone="555-123-4567",
            skills=["Python", "JavaScript"],
        )
        fp = compute_fingerprint(resume)
        assert fp["name"] == "john doe"
        assert fp["email"] == "john@example.com"
        assert fp["phone"] == "5551234567"
        assert fp["skills"] == {"python", "javascript"}


class TestDeduplication:
    def test_exact_email_duplicate(self):
        resumes = [
            ParsedResume(candidate_name="John Doe", email="john@example.com", skills=["Python"]),
            ParsedResume(candidate_name="John D.", email="john@example.com", skills=["Python"]),
        ]
        result = find_duplicates(resumes)
        assert len(result.duplicate_groups) == 1
        assert result.duplicate_groups[0].confidence == 1.0

    def test_no_duplicates(self):
        resumes = [
            ParsedResume(candidate_name="John Doe", email="john@example.com", skills=["Python"]),
            ParsedResume(candidate_name="Jane Smith", email="jane@example.com", skills=["Java"]),
        ]
        result = find_duplicates(resumes)
        assert len(result.duplicate_groups) == 0
        assert result.unique_candidates == 2

    def test_phone_duplicate(self):
        resumes = [
            ParsedResume(candidate_name="Alice", phone="555-123-4567", skills=["Go"]),
            ParsedResume(candidate_name="Bob", phone="(555) 123-4567", skills=["Rust"]),
        ]
        result = find_duplicates(resumes)
        assert len(result.duplicate_groups) == 1

    def test_name_and_skill_overlap(self):
        resumes = [
            ParsedResume(candidate_name="John Doe", skills=["Python", "JavaScript", "React", "Docker"]),
            ParsedResume(candidate_name="John Doe", skills=["Python", "JavaScript", "React", "AWS"]),
        ]
        result = find_duplicates(resumes)
        assert len(result.duplicate_groups) == 1
