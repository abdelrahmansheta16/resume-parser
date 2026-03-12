"""Tests for recruiter feedback loop module."""
import shutil

import pytest

from app.api.schemas import FeedbackSubmission
from app.core.paths import FEEDBACK_DIR
from app.feedback.store import FEEDBACK_FILE


class TestFeedbackStore:
    @pytest.fixture(autouse=True)
    def clean_feedback_dir(self):
        """Clean feedback directory before and after each test."""
        if FEEDBACK_DIR.exists():
            shutil.rmtree(FEEDBACK_DIR)
        yield
        if FEEDBACK_DIR.exists():
            shutil.rmtree(FEEDBACK_DIR)

    def test_save_and_load_feedback(self):
        from app.feedback.store import save_feedback, load_all_feedback
        submission = FeedbackSubmission(
            candidate_name="John Doe",
            match_score=85.0,
            feedback="positive",
        )
        save_feedback(submission)

        entries = load_all_feedback()
        assert len(entries) == 1
        assert entries[0]["candidate_name"] == "John Doe"
        assert entries[0]["feedback"] == "positive"

    def test_multiple_feedback_entries(self):
        from app.feedback.store import save_feedback, load_all_feedback
        for i in range(3):
            save_feedback(FeedbackSubmission(
                candidate_name=f"Candidate {i}",
                match_score=70.0 + i * 10,
                feedback="positive" if i % 2 == 0 else "negative",
            ))
        entries = load_all_feedback()
        assert len(entries) == 3

    def test_feedback_stats(self):
        from app.feedback.store import save_feedback, get_feedback_stats
        save_feedback(FeedbackSubmission(candidate_name="A", match_score=80.0, feedback="positive"))
        save_feedback(FeedbackSubmission(candidate_name="B", match_score=50.0, feedback="negative"))
        save_feedback(FeedbackSubmission(candidate_name="C", match_score=90.0, feedback="positive"))

        stats = get_feedback_stats()
        assert stats.total_feedback == 3
        assert stats.positive_count == 2
        assert stats.negative_count == 1

    def test_empty_stats(self):
        from app.feedback.store import get_feedback_stats
        stats = get_feedback_stats()
        assert stats.total_feedback == 0


class TestWeightAdjuster:
    @pytest.fixture(autouse=True)
    def clean_feedback_dir(self):
        if FEEDBACK_DIR.exists():
            shutil.rmtree(FEEDBACK_DIR)
        yield
        if FEEDBACK_DIR.exists():
            shutil.rmtree(FEEDBACK_DIR)

    def test_recalibrate_no_feedback(self):
        from app.feedback.weight_adjuster import recalibrate_weights
        weights = recalibrate_weights()
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_recalibrate_with_feedback(self):
        from app.feedback.store import save_feedback
        from app.feedback.weight_adjuster import recalibrate_weights

        # Positive feedback with high skill scores
        save_feedback(FeedbackSubmission(
            candidate_name="A",
            match_score=90.0,
            feedback="positive",
            dimension_scores={"skills": 95.0, "semantic": 80.0, "experience": 70.0, "title": 60.0, "education": 50.0},
        ))
        # Negative feedback with low skill scores
        save_feedback(FeedbackSubmission(
            candidate_name="B",
            match_score=40.0,
            feedback="negative",
            dimension_scores={"skills": 30.0, "semantic": 40.0, "experience": 50.0, "title": 60.0, "education": 70.0},
        ))

        weights = recalibrate_weights()
        assert abs(sum(weights.values()) - 1.0) < 0.01
        # Skills should have higher weight since it correlates with positive feedback
        assert weights["skills"] > 0.3
