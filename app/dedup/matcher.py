from __future__ import annotations

from rapidfuzz import fuzz

from app.api.schemas import DeduplicationResult, DuplicateGroup, ParsedResume
from app.core.logging import get_logger
from app.dedup.fingerprint import compute_fingerprint

logger = get_logger(__name__)


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def find_duplicates(resumes: list[ParsedResume]) -> DeduplicationResult:
    """Find duplicate candidates across a list of parsed resumes.

    Detection strategy (3 phases):
    1. Exact email match -> definite duplicate
    2. Fuzzy name match (>85) + skill Jaccard overlap (>0.6) -> probable duplicate
    3. Exact phone match -> possible duplicate
    """
    fingerprints = [compute_fingerprint(r) for r in resumes]
    names = [r.candidate_name or f"Resume {i+1}" for i, r in enumerate(resumes)]

    # Track which indices are already grouped
    grouped: set[int] = set()
    groups: list[DuplicateGroup] = []
    group_id = 0

    n = len(resumes)
    for i in range(n):
        if i in grouped:
            continue
        current_group_members = [names[i]]
        current_group_indices = [i]
        best_reason = ""
        best_confidence = 0.0

        for j in range(i + 1, n):
            if j in grouped:
                continue

            fp_i = fingerprints[i]
            fp_j = fingerprints[j]
            reason = ""
            confidence = 0.0

            # Phase 1: Exact email match
            if fp_i["email"] and fp_i["email"] == fp_j["email"]:
                reason = f"Exact email match: {fp_i['email']}"
                confidence = 1.0

            # Phase 2: Fuzzy name + skill overlap
            if not reason and fp_i["name"] and fp_j["name"]:
                name_score = fuzz.ratio(fp_i["name"], fp_j["name"])
                skill_overlap = _jaccard_similarity(fp_i["skills"], fp_j["skills"])
                if name_score > 85 and skill_overlap >= 0.6:
                    reason = f"Similar name ({name_score}%) + skill overlap ({skill_overlap:.0%})"
                    confidence = 0.8

            # Phase 3: Exact phone match
            if not reason and fp_i["phone"] and fp_i["phone"] == fp_j["phone"]:
                reason = f"Exact phone match"
                confidence = 0.7

            if reason:
                current_group_members.append(names[j])
                current_group_indices.append(j)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_reason = reason

        if len(current_group_members) > 1:
            group_id += 1
            groups.append(DuplicateGroup(
                group_id=group_id,
                candidates=current_group_members,
                reason=best_reason,
                confidence=best_confidence,
            ))
            grouped.update(current_group_indices)

    result = DeduplicationResult(
        total_candidates=n,
        duplicate_groups=groups,
        unique_candidates=n - sum(len(g.candidates) - 1 for g in groups),
    )
    logger.info("Dedup: %d candidates, %d duplicate groups", n, len(groups))
    return result
