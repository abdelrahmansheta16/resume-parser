from __future__ import annotations

import json
from datetime import datetime, timezone

from app.api.schemas import FeedbackStats, FeedbackSubmission
from app.core.logging import get_logger
from app.core.paths import FEEDBACK_DIR

logger = get_logger(__name__)

FEEDBACK_FILE = FEEDBACK_DIR / "feedback.jsonl"

# Default scoring weights (must match scoring.py)
DEFAULT_WEIGHTS = {
    "skills": 0.40,
    "semantic": 0.20,
    "experience": 0.20,
    "title": 0.10,
    "education": 0.10,
}


def _ensure_dir():
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def save_feedback(submission: FeedbackSubmission) -> dict:
    """Append a feedback entry to the JSONL store."""
    _ensure_dir()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **submission.model_dump(),
    }
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    logger.info("Saved feedback: %s for '%s'", submission.feedback, submission.candidate_name)
    return {"status": "saved"}


def load_all_feedback() -> list[dict]:
    """Load all feedback entries."""
    _ensure_dir()
    if not FEEDBACK_FILE.exists():
        return []
    entries = []
    with open(FEEDBACK_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def get_feedback_stats() -> FeedbackStats:
    """Compute feedback statistics."""
    entries = load_all_feedback()
    positive = [e for e in entries if e.get("feedback") == "positive"]
    negative = [e for e in entries if e.get("feedback") == "negative"]

    return FeedbackStats(
        total_feedback=len(entries),
        positive_count=len(positive),
        negative_count=len(negative),
        current_weights=dict(DEFAULT_WEIGHTS),
    )
