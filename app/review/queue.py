from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.api.schemas import ConfidenceScore, ParsedResume, ReviewItem, ReviewQueueResponse
from app.core.logging import get_logger
from app.core.paths import REVIEW_DIR
from app.review.confidence import compute_confidence, needs_review

logger = get_logger(__name__)


def _ensure_dirs():
    """Ensure review directories exist."""
    for subdir in ["pending", "approved", "rejected"]:
        (REVIEW_DIR / subdir).mkdir(parents=True, exist_ok=True)


def add_to_queue(resume: ParsedResume, confidence: ConfidenceScore | None = None) -> ReviewItem:
    """Add a resume to the review queue."""
    _ensure_dirs()

    if confidence is None:
        confidence = compute_confidence(resume)

    review_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    item = ReviewItem(
        review_id=review_id,
        resume=resume,
        confidence=confidence,
        status="pending",
        created_at=now,
    )

    path = REVIEW_DIR / "pending" / f"{review_id}.json"
    path.write_text(item.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Added review item %s (confidence=%.2f)", review_id, confidence.overall)
    return item


def auto_queue_if_needed(resume: ParsedResume) -> ReviewItem | None:
    """Automatically add to review queue if confidence is below threshold."""
    confidence = compute_confidence(resume)
    if needs_review(confidence):
        return add_to_queue(resume, confidence)
    return None


def get_queue(status: str | None = None) -> ReviewQueueResponse:
    """Get the review queue, optionally filtered by status."""
    _ensure_dirs()
    items = []
    counts = {"pending": 0, "approved": 0, "rejected": 0}

    for subdir in ["pending", "approved", "rejected"]:
        dir_path = REVIEW_DIR / subdir
        for f in sorted(dir_path.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                item = ReviewItem(**data)
                counts[subdir] += 1
                if status is None or status == subdir:
                    items.append(item)
            except Exception as e:
                logger.warning("Failed to load review item %s: %s", f.name, e)

    return ReviewQueueResponse(
        total=sum(counts.values()),
        pending=counts["pending"],
        approved=counts["approved"],
        rejected=counts["rejected"],
        items=items,
    )


def get_item(review_id: str) -> ReviewItem | None:
    """Get a single review item by ID."""
    _ensure_dirs()
    for subdir in ["pending", "approved", "rejected"]:
        path = REVIEW_DIR / subdir / f"{review_id}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return ReviewItem(**data)
    return None


def update_status(review_id: str, new_status: str, notes: str | None = None) -> ReviewItem | None:
    """Move a review item to approved or rejected."""
    _ensure_dirs()
    if new_status not in ("approved", "rejected"):
        return None

    # Find the item in any status directory
    for subdir in ["pending", "approved", "rejected"]:
        path = REVIEW_DIR / subdir / f"{review_id}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            item = ReviewItem(**data)
            item.status = new_status
            if notes:
                item.reviewer_notes = notes

            # Move file
            new_path = REVIEW_DIR / new_status / f"{review_id}.json"
            new_path.write_text(item.model_dump_json(indent=2), encoding="utf-8")
            if path != new_path:
                path.unlink()

            logger.info("Review item %s -> %s", review_id, new_status)
            return item
    return None
