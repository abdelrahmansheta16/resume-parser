from __future__ import annotations

from app.api.schemas import MatchResult, ParsedJobDescription, ParsedResume, RankingResult
from app.core.logging import get_logger
from app.matching.scoring import score_candidate

logger = get_logger(__name__)


def rank_candidates(
    resumes: list[ParsedResume],
    jd: ParsedJobDescription,
) -> RankingResult:
    """Rank multiple candidates against one job description."""
    results: list[MatchResult] = []

    for resume in resumes:
        match = score_candidate(resume, jd)
        results.append(match)

    # Sort by match score descending
    results.sort(key=lambda r: r.match_score, reverse=True)

    logger.info(
        "Ranked %d candidates. Top: %s (%.1f), Bottom: %s (%.1f)",
        len(results),
        results[0].candidate_name if results else "N/A",
        results[0].match_score if results else 0,
        results[-1].candidate_name if results else "N/A",
        results[-1].match_score if results else 0,
    )

    return RankingResult(job_description=jd, candidates=results)
