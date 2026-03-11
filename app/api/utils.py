from __future__ import annotations

import io
import csv as csv_module
import json

import pandas as pd


def resumes_to_csv(match_results: list[dict]) -> str:
    """Convert ranking results to CSV string."""
    if not match_results:
        return ""

    output = io.StringIO()
    fieldnames = [
        "candidate_name",
        "match_score",
        "recommendation",
        "matched_skills",
        "missing_skills",
        "experience_match_score",
        "education_match_score",
        "semantic_similarity_score",
    ]
    writer = csv_module.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for result in match_results:
        row = {
            "candidate_name": result.get("candidate_name", ""),
            "match_score": result.get("match_score", 0),
            "recommendation": result.get("recommendation", ""),
            "matched_skills": "; ".join(result.get("matched_skills", [])),
            "missing_skills": "; ".join(result.get("missing_skills", [])),
            "experience_match_score": result.get("experience_match_score", 0),
            "education_match_score": result.get("education_match_score", 0),
            "semantic_similarity_score": result.get("semantic_similarity_score", 0),
        }
        writer.writerow(row)

    return output.getvalue()


def resumes_to_excel_bytes(match_results: list[dict]) -> bytes:
    """Convert ranking results to Excel bytes."""
    rows = []
    for result in match_results:
        rows.append({
            "Candidate Name": result.get("candidate_name", ""),
            "Match Score": result.get("match_score", 0),
            "Recommendation": result.get("recommendation", ""),
            "Matched Skills": "; ".join(result.get("matched_skills", [])),
            "Missing Skills": "; ".join(result.get("missing_skills", [])),
            "Experience Score": result.get("experience_match_score", 0),
            "Education Score": result.get("education_match_score", 0),
            "Semantic Score": result.get("semantic_similarity_score", 0),
        })

    df = pd.DataFrame(rows)
    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()
