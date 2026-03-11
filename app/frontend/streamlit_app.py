import json
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from app.api.utils import resumes_to_csv
from app.extraction.resume_structurer import structure_resume
from app.matching.jd_parser import parse_job_description
from app.matching.ranking import rank_candidates
from app.matching.scoring import score_candidate
from app.parsing.file_loader import load_from_bytes


st.set_page_config(
    page_title="Resume Parser",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar Navigation ---
st.sidebar.title("Resume Parser")
page = st.sidebar.radio(
    "Navigate",
    ["Overview", "Parse Resume", "Match Resume", "Rank Candidates", "Insights"],
)


def _parse_uploaded_file(uploaded_file):
    """Parse a Streamlit uploaded file into a ParsedDocument."""
    content = uploaded_file.read()
    return load_from_bytes(content, uploaded_file.name)


# =============================================================================
# PAGE 1: Overview
# =============================================================================
if page == "Overview":
    st.title("Resume Parser & Candidate Ranker")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("What This App Does")
        st.markdown("""
        - **Parse resumes** from PDF, DOCX, or TXT files
        - **Extract structured data**: name, contact, skills, education, experience
        - **Match candidates** against job descriptions
        - **Rank multiple candidates** with explainable scores
        - **Export results** to CSV or JSON
        """)

    with col2:
        st.subheader("How It Works")
        st.markdown("""
        1. Upload a resume file
        2. The parser extracts raw text and detects sections
        3. NLP extracts entities, skills, education, and experience
        4. Skills are normalized using a curated taxonomy
        5. Match against a job description using weighted scoring
        6. Semantic similarity adds context beyond exact keywords
        """)

    st.markdown("---")
    st.subheader("Supported Formats")
    c1, c2, c3 = st.columns(3)
    c1.metric("PDF", "✓ Supported")
    c2.metric("DOCX", "✓ Supported")
    c3.metric("TXT", "✓ Supported")

    st.markdown("---")
    st.subheader("Scoring Dimensions")
    st.markdown("""
    | Dimension | Weight | Description |
    |-----------|--------|-------------|
    | Skill Match | 40% | Overlap of resume skills with required skills |
    | Semantic Similarity | 20% | Embedding-based text similarity |
    | Experience Match | 20% | Years of experience alignment |
    | Title Relevance | 10% | Job title similarity |
    | Education Match | 10% | Education level alignment |
    """)


# =============================================================================
# PAGE 2: Parse Single Resume
# =============================================================================
elif page == "Parse Resume":
    st.title("Parse Single Resume")
    st.markdown("Upload a resume to extract structured information.")

    uploaded = st.file_uploader(
        "Upload Resume",
        type=["pdf", "docx", "txt"],
        key="parse_single",
    )

    if uploaded:
        with st.spinner("Parsing resume..."):
            doc = _parse_uploaded_file(uploaded)

        if not doc.success:
            st.error(f"Failed to parse: {doc.error}")
        else:
            st.success(f"Parsed in {doc.processing_time_ms:.0f}ms")

            with st.spinner("Extracting structured data..."):
                resume = structure_resume(doc.cleaned_text, include_raw=True)

            # Contact info
            st.subheader("Contact Information")
            col1, col2, col3 = st.columns(3)
            col1.write(f"**Name:** {resume.candidate_name or 'Not detected'}")
            col1.write(f"**Email:** {resume.email or 'Not detected'}")
            col2.write(f"**Phone:** {resume.phone or 'Not detected'}")
            col2.write(f"**Location:** {resume.location or 'Not detected'}")
            col3.write(f"**LinkedIn:** {resume.linkedin or 'Not detected'}")
            col3.write(f"**GitHub:** {resume.github or 'Not detected'}")

            # Summary
            if resume.summary:
                st.subheader("Summary")
                st.write(resume.summary)

            # Skills
            st.subheader(f"Skills ({len(resume.skills)})")
            if resume.skills:
                st.write(", ".join(resume.skills))

            # Education
            st.subheader(f"Education ({len(resume.education)})")
            for edu in resume.education:
                parts = []
                if edu.degree:
                    parts.append(edu.degree)
                if edu.field_of_study:
                    parts.append(f"in {edu.field_of_study}")
                if edu.institution:
                    parts.append(f"— {edu.institution}")
                if edu.graduation_date:
                    parts.append(f"({edu.graduation_date})")
                if edu.gpa:
                    parts.append(f"GPA: {edu.gpa}")
                st.write(" ".join(parts) if parts else "Entry found (details not extracted)")

            # Experience
            st.subheader(f"Experience ({len(resume.experience)}) — {resume.total_years_experience} years estimated")
            for exp in resume.experience:
                title = exp.job_title or "Unknown Role"
                company = exp.company or "Unknown Company"
                dates = ""
                if exp.start_date:
                    dates = f"{exp.start_date} - {exp.end_date or 'Present'}"
                st.markdown(f"**{title}** at {company}")
                if dates:
                    st.caption(dates)
                if exp.description:
                    for bullet in exp.description[:5]:
                        st.write(f"  - {bullet}")

            # Projects
            if resume.projects:
                st.subheader("Projects")
                for p in resume.projects:
                    st.write(f"- {p}")

            # Certifications
            if resume.certifications:
                st.subheader("Certifications")
                for c in resume.certifications:
                    st.write(f"- {c}")

            # Raw text preview
            with st.expander("Raw Extracted Text"):
                st.text(doc.cleaned_text[:3000])

            # JSON export
            with st.expander("Structured JSON Output"):
                resume_dict = resume.model_dump()
                resume_dict.pop("raw_text", None)
                st.json(resume_dict)


# =============================================================================
# PAGE 3: Match Resume to JD
# =============================================================================
elif page == "Match Resume":
    st.title("Match Resume to Job Description")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Upload Resume")
        uploaded = st.file_uploader(
            "Resume file",
            type=["pdf", "docx", "txt"],
            key="match_resume",
        )

    with col2:
        st.subheader("Job Description")
        jd_text = st.text_area(
            "Paste job description",
            height=300,
            key="match_jd",
        )

    if uploaded and jd_text:
        if st.button("Match", type="primary"):
            with st.spinner("Parsing and matching..."):
                doc = _parse_uploaded_file(uploaded)
                if not doc.success:
                    st.error(f"Failed to parse resume: {doc.error}")
                else:
                    resume = structure_resume(doc.cleaned_text, include_raw=True)
                    jd = parse_job_description(jd_text)
                    match = score_candidate(resume, jd)

            if doc.success:
                st.markdown("---")

                # Score display
                col1, col2, col3 = st.columns(3)
                col1.metric("Match Score", f"{match.match_score:.1f}%")
                col2.metric("Recommendation", match.recommendation)
                col3.metric("Skills Matched", f"{len(match.matched_skills)}/{len(match.matched_skills) + len(match.missing_skills)}")

                # Detailed scores
                st.subheader("Score Breakdown")
                scores_df = pd.DataFrame([
                    {"Dimension": "Experience", "Score": match.experience_match_score},
                    {"Dimension": "Education", "Score": match.education_match_score},
                    {"Dimension": "Title Relevance", "Score": match.title_match_score},
                    {"Dimension": "Semantic Similarity", "Score": match.semantic_similarity_score},
                    {"Dimension": "Keyword Relevance", "Score": match.keyword_relevance_score},
                ])
                st.bar_chart(scores_df.set_index("Dimension"))

                # Skills
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Matched Skills")
                    if match.matched_skills:
                        st.write(", ".join(match.matched_skills))
                    else:
                        st.write("No skills matched")
                with col2:
                    st.subheader("Missing Skills")
                    if match.missing_skills:
                        st.write(", ".join(match.missing_skills))
                    else:
                        st.write("No missing required skills")

                # Explanation
                st.subheader("Explanation")
                for exp in match.explanation:
                    st.write(f"- {exp}")

                # Full JSON
                with st.expander("Full Match JSON"):
                    st.json(match.model_dump())


# =============================================================================
# PAGE 4: Rank Multiple Candidates
# =============================================================================
elif page == "Rank Candidates":
    st.title("Rank Multiple Candidates")

    uploaded_files = st.file_uploader(
        "Upload Resumes (multiple)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="rank_resumes",
    )

    jd_text = st.text_area(
        "Job Description",
        height=250,
        key="rank_jd",
    )

    if uploaded_files and jd_text:
        if st.button("Rank Candidates", type="primary"):
            with st.spinner("Parsing and ranking candidates..."):
                parsed_resumes = []
                errors = []
                for f in uploaded_files:
                    doc = _parse_uploaded_file(f)
                    if doc.success:
                        resume = structure_resume(doc.cleaned_text, include_raw=True)
                        parsed_resumes.append(resume)
                    else:
                        errors.append(f"{f.name}: {doc.error}")

                if errors:
                    for err in errors:
                        st.warning(err)

                if parsed_resumes:
                    jd = parse_job_description(jd_text)
                    ranking = rank_candidates(parsed_resumes, jd)

                    st.markdown("---")
                    st.subheader(f"Ranking Results ({len(ranking.candidates)} candidates)")

                    # Leaderboard table
                    rows = []
                    for i, c in enumerate(ranking.candidates, 1):
                        rows.append({
                            "Rank": i,
                            "Candidate": c.candidate_name or "Unknown",
                            "Score": f"{c.match_score:.1f}",
                            "Recommendation": c.recommendation,
                            "Matched Skills": ", ".join(c.matched_skills[:5]),
                            "Missing Skills": ", ".join(c.missing_skills[:5]),
                            "Experience Score": c.experience_match_score,
                            "Education Score": c.education_match_score,
                        })

                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True)

                    # Individual details
                    for c in ranking.candidates:
                        with st.expander(f"{c.candidate_name or 'Unknown'} — {c.match_score:.1f}% ({c.recommendation})"):
                            for exp in c.explanation:
                                st.write(f"- {exp}")

                    # Export
                    st.markdown("---")
                    st.subheader("Export Results")
                    col1, col2, col3 = st.columns(3)

                    # CSV export
                    csv_data = resumes_to_csv([c.model_dump() for c in ranking.candidates])
                    col1.download_button(
                        "Download CSV",
                        data=csv_data,
                        file_name="candidate_ranking.csv",
                        mime="text/csv",
                    )

                    # JSON export
                    json_data = json.dumps(
                        ranking.model_dump(),
                        indent=2,
                        default=str,
                    )
                    col2.download_button(
                        "Download JSON",
                        data=json_data,
                        file_name="candidate_ranking.json",
                        mime="application/json",
                    )
                else:
                    st.error("No resumes could be parsed.")


# =============================================================================
# PAGE 5: Insights
# =============================================================================
elif page == "Insights":
    st.title("Insights & Analytics")
    st.markdown("Upload multiple resumes to see aggregate insights.")

    uploaded_files = st.file_uploader(
        "Upload Resumes",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="insights_resumes",
    )

    if uploaded_files:
        with st.spinner("Analyzing resumes..."):
            all_skills: list[str] = []
            all_years: list[float] = []
            names: list[str] = []

            for f in uploaded_files:
                doc = _parse_uploaded_file(f)
                if doc.success:
                    resume = structure_resume(doc.cleaned_text)
                    all_skills.extend(resume.skills)
                    all_years.append(resume.total_years_experience)
                    names.append(resume.candidate_name or f.name)

        if all_skills:
            st.subheader("Most Common Skills")
            skill_counts = pd.Series(all_skills).value_counts().head(20)
            st.bar_chart(skill_counts)

            st.subheader("Experience Distribution")
            exp_df = pd.DataFrame({"Candidate": names, "Years of Experience": all_years})
            st.bar_chart(exp_df.set_index("Candidate"))

            # Skill gap analysis if JD provided
            st.markdown("---")
            jd_text = st.text_area("Optional: Paste JD for skill gap analysis", key="insights_jd")
            if jd_text:
                jd = parse_job_description(jd_text)
                required = set(s.lower() for s in jd.required_skills)
                found = set(s.lower() for s in all_skills)
                covered = required & found
                gaps = required - found

                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Skills Covered")
                    st.write(", ".join(sorted(covered)) if covered else "None")
                with col2:
                    st.subheader("Skill Gaps")
                    st.write(", ".join(sorted(gaps)) if gaps else "All required skills covered!")
        else:
            st.warning("No skills could be extracted from uploaded resumes.")
