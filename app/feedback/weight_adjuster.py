from __future__ import annotations

from app.core.logging import get_logger
from app.feedback.store import DEFAULT_WEIGHTS, load_all_feedback

logger = get_logger(__name__)

LEARNING_RATE = 0.1
DIMENSIONS = ["skills", "semantic", "experience", "title", "education"]


def recalibrate_weights() -> dict[str, float]:
    """Adjust scoring weights based on accumulated feedback.

    Algorithm:
    1. Group feedback into positive/negative
    2. For each dimension, compute avg score diff between groups
    3. Increase weight for dimensions that correlate with positive feedback
    4. Apply learning rate and normalize to sum to 1.0
    """
    entries = load_all_feedback()
    if not entries:
        return dict(DEFAULT_WEIGHTS)

    positive = [e for e in entries if e.get("feedback") == "positive" and e.get("dimension_scores")]
    negative = [e for e in entries if e.get("feedback") == "negative" and e.get("dimension_scores")]

    if not positive or not negative:
        logger.info("Insufficient feedback for recalibration (need both positive and negative)")
        return dict(DEFAULT_WEIGHTS)

    # Compute average dimension scores per group
    def avg_scores(group):
        avgs = {}
        for dim in DIMENSIONS:
            values = [e["dimension_scores"].get(dim, 0.0) for e in group if dim in e.get("dimension_scores", {})]
            avgs[dim] = sum(values) / len(values) if values else 0.0
        return avgs

    pos_avgs = avg_scores(positive)
    neg_avgs = avg_scores(negative)

    # Compute adjustments
    new_weights = dict(DEFAULT_WEIGHTS)
    for dim in DIMENSIONS:
        diff = pos_avgs.get(dim, 0.0) - neg_avgs.get(dim, 0.0)
        adjustment = diff * LEARNING_RATE
        new_weights[dim] = max(0.05, new_weights[dim] + adjustment)

    # Normalize to sum to 1.0
    total = sum(new_weights.values())
    if total > 0:
        new_weights = {k: round(v / total, 4) for k, v in new_weights.items()}

    logger.info("Recalibrated weights: %s (from %d positive, %d negative)", new_weights, len(positive), len(negative))
    return new_weights
