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
    [
        "Overview",
        "Parse Resume",
        "Match Resume",
        "Rank Candidates",
        "Job Discovery",
        "Application Packs",
        "Company Research",
        "Outreach Drafts",
        "Search Candidates",
        "Semantic Search",
        "Review Queue",
        "Insights",
    ],
)

# Sidebar options
st.sidebar.markdown("---")
st.sidebar.subheader("Options")
blind_mode = st.sidebar.checkbox("Blind Screening Mode", value=False)


def _parse_uploaded_file(uploaded_file):
    """Parse a Streamlit uploaded file into a ParsedDocument."""
    content = uploaded_file.read()
    return load_from_bytes(content, uploaded_file.name)


def _display_parse_method(resume):
    """Show parse method badge if available."""
    if resume.parse_method:
        st.caption(f"Parsed via: **{resume.parse_method}**")
    if resume.detected_language and resume.detected_language != "en":
        st.caption(f"Language detected: **{resume.detected_language}**")


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
        - **Search candidates** with filters and semantic search
        - **Blind screening mode** for bias-free evaluation
        - **Review queue** for low-confidence parses
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
                resume.parse_method = doc.metadata.get("parse_method")

            if blind_mode:
                from app.anonymize.redactor import anonymize_resume
                resume = anonymize_resume(resume)

            _display_parse_method(resume)

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

                # Feedback buttons
                st.markdown("---")
                st.subheader("Was this match result helpful?")
                fb_col1, fb_col2 = st.columns(2)
                with fb_col1:
                    if st.button("👍 Good match"):
                        from app.feedback.store import save_feedback
                        from app.api.schemas import FeedbackSubmission
                        save_feedback(FeedbackSubmission(
                            candidate_name=match.candidate_name or "Unknown",
                            match_score=match.match_score,
                            feedback="positive",
                            dimension_scores={
                                "experience": match.experience_match_score,
                                "education": match.education_match_score,
                                "title": match.title_match_score,
                                "semantic": match.semantic_similarity_score,
                                "skills": match.keyword_relevance_score,
                            },
                        ))
                        st.success("Thanks for the feedback!")
                with fb_col2:
                    if st.button("👎 Bad match"):
                        from app.feedback.store import save_feedback
                        from app.api.schemas import FeedbackSubmission
                        save_feedback(FeedbackSubmission(
                            candidate_name=match.candidate_name or "Unknown",
                            match_score=match.match_score,
                            feedback="negative",
                            dimension_scores={
                                "experience": match.experience_match_score,
                                "education": match.education_match_score,
                                "title": match.title_match_score,
                                "semantic": match.semantic_similarity_score,
                                "skills": match.keyword_relevance_score,
                            },
                        ))
                        st.info("Thanks for the feedback!")

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

    col_opts1, col_opts2 = st.columns(2)
    with col_opts1:
        check_dupes = st.checkbox("Check for duplicates", value=False)

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
                    # Deduplication check
                    if check_dupes and len(parsed_resumes) >= 2:
                        from app.dedup.matcher import find_duplicates
                        dedup_result = find_duplicates(parsed_resumes)
                        if dedup_result.duplicate_groups:
                            st.warning(f"Found {len(dedup_result.duplicate_groups)} duplicate group(s)")
                            for group in dedup_result.duplicate_groups:
                                with st.expander(f"Duplicate Group {group.group_id}: {group.reason}"):
                                    st.write(f"Candidates: {', '.join(group.candidates)}")
                                    st.write(f"Confidence: {group.confidence:.0%}")

                    # Anonymize if blind mode
                    if blind_mode:
                        from app.anonymize.redactor import anonymize_resume
                        parsed_resumes = [anonymize_resume(r, i + 1) for i, r in enumerate(parsed_resumes)]

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
# PAGE 5: Job Discovery
# =============================================================================
elif page == "Job Discovery":
    st.title("Job Discovery")
    st.markdown("Upload your CV to discover matching jobs from multiple sources.")

    uploaded = st.file_uploader(
        "Upload Your Resume/CV",
        type=["pdf", "docx", "txt"],
        key="discovery_resume",
    )

    st.subheader("Search Preferences")
    col1, col2 = st.columns(2)
    with col1:
        target_titles = st.text_input("Target job titles (comma separated)", key="disc_titles")
        target_locations = st.text_input("Target locations (comma separated)", key="disc_locations")
    with col2:
        remote_pref = st.selectbox("Remote preference", ["any", "remote", "hybrid", "onsite"], key="disc_remote")
        min_salary = st.number_input("Minimum salary ($)", min_value=0, max_value=500000, value=0, step=5000, key="disc_salary")

    if uploaded and st.button("Discover Jobs", type="primary"):
        with st.spinner("Parsing resume and searching for jobs..."):
            doc = _parse_uploaded_file(uploaded)
            if not doc.success:
                st.error(f"Failed to parse: {doc.error}")
            else:
                resume = structure_resume(doc.cleaned_text, include_raw=True)
                resume.parse_method = doc.metadata.get("parse_method")

                from app.api.schemas import CandidateProfile
                profile = CandidateProfile(
                    resume=resume,
                    target_titles=[t.strip() for t in target_titles.split(",") if t.strip()],
                    target_locations=[l.strip() for l in target_locations.split(",") if l.strip()],
                    remote_preference=remote_pref if remote_pref != "any" else None,
                    min_salary=min_salary if min_salary > 0 else None,
                )

                # Discover jobs
                from app.job_discovery.orchestrator import discover_jobs
                jobs = discover_jobs(profile)

                if not jobs:
                    st.warning("No jobs found. Try broadening your search criteria or check API key configuration.")
                else:
                    # Rank them
                    from app.matching.job_ranker import rank_jobs_for_candidate
                    ranked = rank_jobs_for_candidate(resume, jobs)

                    st.success(f"Found {len(jobs)} jobs, ranked top {len(ranked)}")

                    # Store in session for use in other pages
                    st.session_state["ranked_jobs"] = ranked
                    st.session_state["discovery_resume"] = resume

                    # Display ranking table
                    rows = []
                    for i, match in enumerate(ranked, 1):
                        rows.append({
                            "Rank": i,
                            "Company": match.job.company or "N/A",
                            "Role": match.job.title or "N/A",
                            "Score": f"{match.match_score:.1f}",
                            "Recommendation": match.recommendation,
                            "Location": match.job.location or "N/A",
                            "Matched Skills": ", ".join(match.matched_skills[:4]),
                        })

                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True)

                    # Detailed view per job
                    for i, match in enumerate(ranked, 1):
                        with st.expander(f"#{i} {match.job.title} at {match.job.company} — {match.match_score:.1f}%"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Score Breakdown:**")
                                st.write(f"- Skill: {match.skill_score:.1f}")
                                st.write(f"- Experience: {match.experience_score:.1f}")
                                st.write(f"- Title: {match.title_score:.1f}")
                                st.write(f"- Education: {match.education_score:.1f}")
                            with col2:
                                st.write(f"**Matched Skills:** {', '.join(match.matched_skills[:8])}")
                                st.write(f"**Missing Skills:** {', '.join(match.missing_skills[:5])}")
                                if match.job.apply_url:
                                    st.write(f"**Apply:** {match.job.apply_url}")
                            if match.explanation:
                                for exp in match.explanation:
                                    st.write(f"- {exp}")


# =============================================================================
# PAGE 6: Application Packs
# =============================================================================
elif page == "Application Packs":
    st.title("Application Pack Generator")
    st.markdown("Generate tailored ATS-friendly resumes for your top jobs.")

    uploaded = st.file_uploader(
        "Upload Your Resume/CV",
        type=["pdf", "docx", "txt"],
        key="pack_resume",
    )

    jd_text = st.text_area(
        "Paste a job description (for single pack generation)",
        height=200,
        key="pack_jd",
    )

    if uploaded and jd_text:
        if st.button("Generate Application Pack", type="primary"):
            with st.spinner("Generating tailored resume..."):
                doc = _parse_uploaded_file(uploaded)
                if not doc.success:
                    st.error(f"Failed to parse: {doc.error}")
                else:
                    resume = structure_resume(doc.cleaned_text, include_raw=True)

                    from app.matching.jd_parser import parse_job_description as parse_jd_fn
                    from app.api.schemas import JobPosting
                    jd = parse_jd_fn(jd_text)

                    job = JobPosting(
                        job_id="manual_entry",
                        title=jd.title or "Target Role",
                        company="Target Company",
                        description=jd_text,
                        required_skills=jd.required_skills,
                        preferred_skills=jd.preferred_skills,
                        requirements=jd.requirements if hasattr(jd, "requirements") else [],
                        required_years_experience=jd.required_years_experience,
                        education_requirements=jd.education_requirements,
                    )

                    from app.matching.job_ranker import score_job_for_candidate
                    match = score_job_for_candidate(resume, job)

                    from app.tailoring.pack_generator import generate_application_pack
                    pack = generate_application_pack(resume, match)

                    st.success("Application pack generated!")

                    # Show tailored resume info
                    st.subheader("Tailored Resume")
                    st.write(f"**Summary:** {pack.tailored_resume.tailored_summary}")
                    st.write(f"**Skills (reordered):** {', '.join(pack.tailored_resume.tailored_skills[:15])}")

                    if pack.tailored_resume.docx_path:
                        st.write(f"**DOCX saved to:** `{pack.tailored_resume.docx_path}`")
                        try:
                            with open(pack.tailored_resume.docx_path, "rb") as f:
                                st.download_button(
                                    "Download Tailored Resume (DOCX)",
                                    data=f.read(),
                                    file_name="tailored_resume.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                )
                        except FileNotFoundError:
                            pass

                    # Match details
                    st.subheader("Match Details")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Match Score", f"{match.match_score:.1f}%")
                        st.write(f"**Recommendation:** {match.recommendation}")
                    with col2:
                        st.write(f"**Matched Skills:** {', '.join(match.matched_skills[:8])}")
                        st.write(f"**Missing Skills:** {', '.join(match.missing_skills[:5])}")


# =============================================================================
# PAGE 7: Company Research
# =============================================================================
elif page == "Company Research":
    st.title("Company Research")
    st.markdown("Research a company using publicly available web data.")

    company_name = st.text_input("Company Name", key="research_company")
    col1, col2 = st.columns(2)
    with col1:
        domain = st.text_input("Company Domain (e.g., example.com)", key="research_domain")
    with col2:
        apply_url = st.text_input("Apply URL (optional)", key="research_url")

    if company_name and st.button("Research Company", type="primary"):
        with st.spinner(f"Researching {company_name}..."):
            from app.company_research.crawler import research_company as _research
            result = _research(company_name, domain or None, apply_url or None)

        st.subheader(f"Research: {result.company_name}")

        if result.domain:
            st.write(f"**Domain:** {result.domain}")
        if result.about:
            st.write(f"**About:** {result.about}")
        if result.careers_url:
            st.write(f"**Careers Page:** {result.careers_url}")
        if result.tech_stack:
            st.write(f"**Tech Stack:** {', '.join(result.tech_stack)}")

        if result.public_contacts:
            st.subheader("Public Contacts")
            for contact in result.public_contacts:
                st.write(f"- [{contact.get('role', 'N/A')}] {contact.get('channel_type', '')}: {contact.get('value', '')}")
        else:
            st.info("No public recruiting contacts found.")


# =============================================================================
# PAGE 8: Outreach Drafts
# =============================================================================
elif page == "Outreach Drafts":
    st.title("Outreach Draft Generator")
    st.markdown("Generate personalized outreach drafts for job applications.")

    uploaded = st.file_uploader(
        "Upload Your Resume/CV",
        type=["pdf", "docx", "txt"],
        key="outreach_resume",
    )

    jd_text = st.text_area(
        "Paste the job description",
        height=200,
        key="outreach_jd",
    )

    col1, col2 = st.columns(2)
    with col1:
        company_name = st.text_input("Company Name", key="outreach_company")
        role_title = st.text_input("Role Title", key="outreach_role")
    with col2:
        target_roles = st.multiselect(
            "Generate drafts for",
            ["recruiter", "hiring_manager", "referral"],
            default=["recruiter"],
            key="outreach_targets",
        )

    if uploaded and jd_text and company_name and target_roles:
        if st.button("Generate Outreach Drafts", type="primary"):
            with st.spinner("Generating drafts..."):
                doc = _parse_uploaded_file(uploaded)
                if not doc.success:
                    st.error(f"Failed to parse: {doc.error}")
                else:
                    resume = structure_resume(doc.cleaned_text, include_raw=True)

                    from app.matching.jd_parser import parse_job_description as parse_jd_fn
                    from app.api.schemas import JobPosting
                    jd = parse_jd_fn(jd_text)

                    job = JobPosting(
                        job_id="outreach_manual",
                        title=role_title or jd.title or "Target Role",
                        company=company_name,
                        description=jd_text,
                        required_skills=jd.required_skills,
                        preferred_skills=jd.preferred_skills,
                    )

                    from app.matching.job_ranker import score_job_for_candidate
                    match = score_job_for_candidate(resume, job)

                    from app.outreach.drafter import draft_outreach
                    for role in target_roles:
                        draft = draft_outreach(resume, job, match, role)

                        st.subheader(f"Draft: {role.replace('_', ' ').title()}")
                        st.text_input("Subject", value=draft.subject, key=f"subj_{role}")
                        st.text_area("Body", value=draft.body, height=300, key=f"body_{role}")

                        with st.expander("Compliance Notes"):
                            for note in draft.compliance_notes:
                                st.write(f"- {note}")

                        st.markdown("---")


# =============================================================================
# PAGE 9: Search Candidates
# =============================================================================
elif page == "Search Candidates":
    st.title("ATS Search Filters")
    st.markdown("Upload resumes and filter by skills, experience, education, and more.")

    uploaded_files = st.file_uploader(
        "Upload Resumes",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="search_resumes",
    )

    st.subheader("Filters")
    col1, col2 = st.columns(2)

    with col1:
        skills_required = st.text_input("Required skills (comma separated)", key="search_skills")
        skills_any = st.text_input("Any of these skills (comma separated)", key="search_skills_any")
        location = st.text_input("Location", key="search_location")

    with col2:
        min_years = st.number_input("Min years experience", min_value=0.0, max_value=50.0, value=0.0, step=0.5)
        max_years = st.number_input("Max years experience", min_value=0.0, max_value=50.0, value=50.0, step=0.5)
        education_level = st.selectbox("Minimum education", ["Any", "High School", "Associate", "Bachelor", "Master", "Doctorate"])
        title_keywords = st.text_input("Job title keywords (comma separated)", key="search_titles")

    if uploaded_files and st.button("Search", type="primary"):
        with st.spinner("Parsing and filtering..."):
            parsed_resumes = []
            for f in uploaded_files:
                doc = _parse_uploaded_file(f)
                if doc.success:
                    resume = structure_resume(doc.cleaned_text, include_raw=True)
                    parsed_resumes.append(resume)

            from app.api.schemas import SearchFilters
            from app.search.filters import apply_filters

            filters = SearchFilters(
                skills=[s.strip() for s in skills_required.split(",") if s.strip()] or None,
                skills_any=[s.strip() for s in skills_any.split(",") if s.strip()] or None,
                min_years_experience=min_years if min_years > 0 else None,
                max_years_experience=max_years if max_years < 50 else None,
                education_level=education_level.lower() if education_level != "Any" else None,
                location=location or None,
                job_title_keywords=[s.strip() for s in title_keywords.split(",") if s.strip()] or None,
            )

            result = apply_filters(parsed_resumes, filters)

        st.markdown("---")
        st.metric("Results", f"{result.filtered} / {result.total} candidates")

        for resume in result.candidates:
            with st.expander(f"{resume.candidate_name or 'Unknown'} — {resume.total_years_experience} yrs"):
                st.write(f"**Skills:** {', '.join(resume.skills[:15])}")
                st.write(f"**Location:** {resume.location or 'N/A'}")
                for exp in resume.experience[:3]:
                    st.write(f"- {exp.job_title or 'N/A'} at {exp.company or 'N/A'}")


# =============================================================================
# PAGE 6: Semantic Search
# =============================================================================
elif page == "Semantic Search":
    st.title("Semantic Search (Vector Database)")
    st.markdown("Index resumes and search by meaning, not just keywords.")

    tab1, tab2 = st.tabs(["Index Resumes", "Search"])

    with tab1:
        uploaded_files = st.file_uploader(
            "Upload Resumes to Index",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            key="vector_index",
        )

        if uploaded_files and st.button("Index All", type="primary"):
            with st.spinner("Indexing resumes..."):
                try:
                    from app.vectordb.store import index_resume
                    indexed = 0
                    for f in uploaded_files:
                        doc = _parse_uploaded_file(f)
                        if doc.success:
                            resume = structure_resume(doc.cleaned_text, include_raw=True)
                            index_resume(resume)
                            indexed += 1
                    st.success(f"Indexed {indexed} resumes")
                except ImportError:
                    st.error("ChromaDB not installed. Run: pip install chromadb")

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("View Stats"):
                try:
                    from app.vectordb.store import get_stats
                    stats = get_stats()
                    st.json(stats)
                except ImportError:
                    st.error("ChromaDB not installed")
        with col2:
            if st.button("Clear Index"):
                try:
                    from app.vectordb.store import clear
                    clear()
                    st.success("Index cleared")
                except ImportError:
                    st.error("ChromaDB not installed")

    with tab2:
        query = st.text_area("Search query (describe the ideal candidate)", height=150, key="vector_query")
        n_results = st.slider("Number of results", 1, 50, 10)

        if query and st.button("Search", key="vector_search_btn", type="primary"):
            with st.spinner("Searching..."):
                try:
                    from app.vectordb.store import search
                    result = search(query, n_results)
                    st.metric("Total Indexed", result.total_indexed)

                    for hit in result.hits:
                        with st.expander(f"{hit.candidate_name or 'Unknown'} — {hit.similarity_score:.1%} match"):
                            st.write(f"**Skills:** {', '.join(hit.skills[:10])}")
                            st.write(f"**Similarity:** {hit.similarity_score:.4f}")
                            st.write(f"**ID:** {hit.resume_id}")
                except ImportError:
                    st.error("ChromaDB not installed. Run: pip install chromadb")


# =============================================================================
# PAGE 7: Review Queue
# =============================================================================
elif page == "Review Queue":
    st.title("Human Review Queue")
    st.markdown("Review low-confidence resume parses and approve or reject them.")

    try:
        from app.review.queue import get_queue, update_status

        queue = get_queue()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total", queue.total)
        col2.metric("Pending", queue.pending)
        col3.metric("Approved", queue.approved)
        col4.metric("Rejected", queue.rejected)

        status_filter = st.selectbox("Filter by status", ["All", "Pending", "Approved", "Rejected"])
        filter_val = None if status_filter == "All" else status_filter.lower()
        queue = get_queue(filter_val)

        for item in queue.items:
            with st.expander(f"[{item.status.upper()}] {item.resume.candidate_name or 'Unknown'} — Confidence: {item.confidence.overall:.0%}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Name:** {item.resume.candidate_name}")
                    st.write(f"**Skills:** {', '.join(item.resume.skills[:10])}")
                    st.write(f"**Experience:** {item.resume.total_years_experience} years")
                with col2:
                    st.write(f"**Name Confidence:** {item.confidence.name_confidence:.0%}")
                    st.write(f"**Skills Confidence:** {item.confidence.skills_confidence:.0%}")
                    st.write(f"**Education Confidence:** {item.confidence.education_confidence:.0%}")
                    st.write(f"**Experience Confidence:** {item.confidence.experience_confidence:.0%}")

                if item.status == "pending":
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("Approve", key=f"approve_{item.review_id}"):
                            update_status(item.review_id, "approved")
                            st.rerun()
                    with btn_col2:
                        if st.button("Reject", key=f"reject_{item.review_id}"):
                            update_status(item.review_id, "rejected")
                            st.rerun()
    except Exception as e:
        st.error(f"Error loading review queue: {e}")


# =============================================================================
# PAGE 8: Insights
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

            # Feedback stats
            st.markdown("---")
            st.subheader("Feedback Statistics")
            try:
                from app.feedback.store import get_feedback_stats
                stats = get_feedback_stats()
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Feedback", stats.total_feedback)
                col2.metric("Positive", stats.positive_count)
                col3.metric("Negative", stats.negative_count)

                if stats.total_feedback > 0:
                    st.write("**Current Weights:**")
                    st.json(stats.current_weights)

                    if st.button("Recalibrate Weights"):
                        from app.feedback.weight_adjuster import recalibrate_weights
                        new_weights = recalibrate_weights()
                        st.write("**Adjusted Weights:**")
                        st.json(new_weights)
            except Exception:
                st.info("No feedback data available yet.")
        else:
            st.warning("No skills could be extracted from uploaded resumes.")
