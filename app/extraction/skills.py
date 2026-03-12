from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.core.logging import get_logger
from app.core.paths import TAXONOMIES_DIR

logger = get_logger(__name__)


@dataclass
class SkillTaxonomy:
    canonical_to_aliases: dict[str, list[str]] = field(default_factory=dict)
    alias_to_canonical: dict[str, str] = field(default_factory=dict)
    canonical_to_category: dict[str, str] = field(default_factory=dict)


def load_skill_taxonomy(path=None) -> SkillTaxonomy:
    """Load skills taxonomy from CSV."""
    path = path or TAXONOMIES_DIR / "skills.csv"
    taxonomy = SkillTaxonomy()

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            canonical = row["canonical"].strip()
            aliases = [a.strip() for a in row["aliases"].split(",")]
            category = row.get("category", "").strip()

            taxonomy.canonical_to_aliases[canonical] = aliases
            if category:
                taxonomy.canonical_to_category[canonical] = category

            # Map each alias -> canonical (lowered for matching)
            for alias in aliases:
                taxonomy.alias_to_canonical[alias.lower()] = canonical
            taxonomy.alias_to_canonical[canonical.lower()] = canonical

    logger.info("Loaded %d skills from taxonomy", len(taxonomy.canonical_to_aliases))
    return taxonomy


def _load_language_taxonomy(taxonomy: SkillTaxonomy, lang: str) -> None:
    """Merge a language-specific taxonomy file into the existing taxonomy."""
    lang_file = TAXONOMIES_DIR / f"skills_{lang}.csv"
    if not lang_file.exists():
        return
    with open(lang_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            canonical = row["canonical"].strip()
            aliases = [a.strip() for a in row["aliases"].split(",")]
            # Merge aliases into existing canonical entries
            if canonical in taxonomy.canonical_to_aliases:
                taxonomy.canonical_to_aliases[canonical].extend(aliases)
            else:
                taxonomy.canonical_to_aliases[canonical] = aliases
            for alias in aliases:
                taxonomy.alias_to_canonical[alias.lower()] = canonical
    logger.info("Merged %s aliases from skills_%s.csv", lang, lang)


# Module-level singletons per language
_taxonomy_cache: dict[str, SkillTaxonomy] = {}


def get_taxonomy(lang: str = "en") -> SkillTaxonomy:
    global _taxonomy_cache
    if lang not in _taxonomy_cache:
        taxonomy = load_skill_taxonomy()
        if lang != "en":
            _load_language_taxonomy(taxonomy, lang)
        _taxonomy_cache[lang] = taxonomy
    return _taxonomy_cache[lang]


def normalize_skill(raw_skill: str, taxonomy: SkillTaxonomy | None = None) -> str | None:
    """Normalize a skill string to its canonical form."""
    if taxonomy is None:
        taxonomy = get_taxonomy()

    cleaned = raw_skill.strip()
    lower = cleaned.lower()

    # Exact alias match
    if lower in taxonomy.alias_to_canonical:
        return taxonomy.alias_to_canonical[lower]

    # Fuzzy match against all aliases
    best_score = 0
    best_canonical = None
    for alias, canonical in taxonomy.alias_to_canonical.items():
        score = fuzz.ratio(lower, alias)
        if score > best_score:
            best_score = score
            best_canonical = canonical

    if best_score >= 85:
        return best_canonical

    # Return the original cleaned skill if no taxonomy match
    return cleaned if len(cleaned) > 1 else None


def _make_skill_pattern(form_lower: str) -> str:
    """Build a regex pattern for a skill form, handling special characters.

    \\b doesn't work at non-word characters (C++, C#, .NET), so we use
    lookaround-based boundaries for forms that start/end with non-alnum chars.
    """
    escaped = re.escape(form_lower)
    if form_lower[0].isalnum():
        prefix = r"\b"
    else:
        prefix = r"(?:^|(?<=[\s,;|/(\[]))"
    if form_lower[-1].isalnum():
        suffix = r"\b"
    else:
        suffix = r"(?=$|[\s,;|/)\].])"
    return prefix + escaped + suffix


def extract_skills_from_text(text: str, taxonomy: SkillTaxonomy | None = None) -> list[str]:
    """Extract and normalize skills from text using taxonomy matching."""
    if taxonomy is None:
        taxonomy = get_taxonomy()

    found_skills: set[str] = set()
    text_lower = text.lower()

    # Direct scan: look for each canonical skill and alias in the text
    for canonical, aliases in taxonomy.canonical_to_aliases.items():
        all_forms = [canonical] + aliases
        for form in all_forms:
            pattern = _make_skill_pattern(form.lower())
            if re.search(pattern, text_lower):
                found_skills.add(canonical)
                break

    return sorted(found_skills)


def extract_skills_from_section(section_text: str, taxonomy: SkillTaxonomy | None = None) -> list[str]:
    """Extract skills from a skills section (comma/pipe/bullet separated)."""
    if taxonomy is None:
        taxonomy = get_taxonomy()

    found_skills: set[str] = set()

    # Split by common delimiters
    raw_items = re.split(r"[,|;\n]|\s{2,}|[-*]\s+", section_text)
    for item in raw_items:
        item = item.strip().strip("-").strip("*").strip()
        if not item or len(item) > 60:
            continue

        # Check for "Category: skill1, skill2" pattern
        if ":" in item:
            parts = item.split(":", 1)
            sub_items = re.split(r"[,|;]", parts[1])
            for sub in sub_items:
                sub = sub.strip()
                if sub:
                    normalized = normalize_skill(sub, taxonomy)
                    if normalized:
                        found_skills.add(normalized)
        else:
            normalized = normalize_skill(item, taxonomy)
            if normalized:
                found_skills.add(normalized)

    return sorted(found_skills)
