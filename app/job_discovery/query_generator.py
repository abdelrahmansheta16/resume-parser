from __future__ import annotations

import csv

from app.api.schemas import CandidateProfile
from app.core.logging import get_logger
from app.core.paths import TAXONOMIES_DIR

logger = get_logger(__name__)


def _load_title_variants() -> dict[str, list[str]]:
    """Load job title aliases from taxonomy."""
    path = TAXONOMIES_DIR / "job_titles.csv"
    mapping: dict[str, list[str]] = {}
    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                canonical = row["canonical"].strip()
                aliases = [a.strip() for a in row["aliases"].split(",")]
                mapping[canonical.lower()] = [canonical] + aliases
    except FileNotFoundError:
        pass
    return mapping


def generate_queries(profile: CandidateProfile) -> list[str]:
    """Generate search queries from a candidate profile.

    Strategy:
    1. Use explicit target titles if provided
    2. Infer from most recent job titles
    3. Expand via title taxonomy
    4. Add top skills as query modifiers
    """
    queries: list[str] = []

    # 1. Explicit target titles
    if profile.target_titles:
        queries.extend(profile.target_titles)

    # 2. Infer from recent experience
    if profile.resume.experience:
        for exp in profile.resume.experience[:3]:
            if exp.job_title and exp.job_title not in queries:
                queries.append(exp.job_title)

    # 3. Expand via taxonomy
    title_variants = _load_title_variants()
    expanded = []
    for q in queries:
        q_lower = q.lower()
        for canonical, variants in title_variants.items():
            if q_lower == canonical or q_lower in [v.lower() for v in variants]:
                for v in variants[:3]:
                    if v not in expanded and v.lower() != q_lower:
                        expanded.append(v)
    queries.extend(expanded[:5])

    # 4. Add skill-based queries for broader discovery
    top_skills = profile.resume.skills[:5]
    if top_skills and profile.resume.experience:
        recent_title = profile.resume.experience[0].job_title or ""
        skill_str = " ".join(top_skills[:3])
        if recent_title:
            queries.append(f"{recent_title} {skill_str}")
        else:
            queries.append(skill_str)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower and q_lower not in seen:
            seen.add(q_lower)
            unique.append(q)

    logger.info("Generated %d search queries from profile", len(unique))
    return unique[:10]  # cap at 10 queries
