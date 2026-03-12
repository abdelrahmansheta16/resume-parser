"""Tests for human review queue module."""
import shutil

import pytest

from app.api.schemas import EducationSchema, ExperienceSchema, ParsedResume
from app.core.paths import REVIEW_DIR
from app.review.confidence import compute_confidence, needs_review, REVIEW_THRESHOLD


class TestConfidenceScoring:
    def test_full_confidence(self):
        resume = ParsedResume(
            candidate_name="John Doe",
            skills=["Python", "JavaScript", "React"],
            education=[EducationSchema(degree="BS", institution="MIT", graduation_date="2020")],
            experience=[ExperienceSchema(
                job_title="Engineer",
                company="Acme",
                start_date="2020",
                description=["Built systems"],
            )],
            raw_text="x" * 600,
        )
        conf = compute_confidence(resume)
        assert conf.name_confidence == 1.0
        assert conf.overall > REVIEW_THRESHOLD

    def test_low_confidence_no_name(self):
        resume = ParsedResume(
            skills=[],
            education=[],
            experience=[],
            raw_text="x" * 200,
        )
        conf = compute_confidence(resume)
        assert conf.name_confidence == 0.0
        assert conf.overall < REVIEW_THRESHOLD

    def test_needs_review_threshold(self):
        from app.api.schemas import ConfidenceScore
        low = ConfidenceScore(overall=0.3)
        high = ConfidenceScore(overall=0.9)
        assert needs_review(low) is True
        assert needs_review(high) is False


class TestReviewQueue:
    @pytest.fixture(autouse=True)
    def clean_review_dir(self):
        """Clean review directory before and after each test."""
        for subdir in ["pending", "approved", "rejected"]:
            d = REVIEW_DIR / subdir
            if d.exists():
                shutil.rmtree(d)
        yield
        for subdir in ["pending", "approved", "rejected"]:
            d = REVIEW_DIR / subdir
            if d.exists():
                shutil.rmtree(d)

    def test_add_to_queue(self):
        from app.review.queue import add_to_queue, get_queue
        resume = ParsedResume(candidate_name="Test User", skills=["Python"])
        item = add_to_queue(resume)
        assert item.status == "pending"
        assert item.review_id

        queue = get_queue()
        assert queue.pending == 1

    def test_approve_item(self):
        from app.review.queue import add_to_queue, update_status, get_queue
        resume = ParsedResume(candidate_name="Test User")
        item = add_to_queue(resume)

        updated = update_status(item.review_id, "approved", notes="Looks good")
        assert updated.status == "approved"
        assert updated.reviewer_notes == "Looks good"

        queue = get_queue()
        assert queue.approved == 1
        assert queue.pending == 0

    def test_reject_item(self):
        from app.review.queue import add_to_queue, update_status, get_queue
        resume = ParsedResume(candidate_name="Test User")
        item = add_to_queue(resume)

        updated = update_status(item.review_id, "rejected")
        assert updated.status == "rejected"

        queue = get_queue()
        assert queue.rejected == 1

    def test_get_item_by_id(self):
        from app.review.queue import add_to_queue, get_item
        resume = ParsedResume(candidate_name="Test User")
        item = add_to_queue(resume)

        fetched = get_item(item.review_id)
        assert fetched is not None
        assert fetched.resume.candidate_name == "Test User"

    def test_get_item_not_found(self):
        from app.review.queue import get_item
        assert get_item("nonexistent") is None
