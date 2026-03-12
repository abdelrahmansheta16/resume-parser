"""Tests for the outreach drafting module."""
from __future__ import annotations

import pytest

from app.api.schemas import ExperienceSchema, JobMatchResult, JobPosting, ParsedResume
from app.outreach.drafter import draft_all_outreach, draft_outreach
from app.outreach.templates import TEMPLATES


@pytest.fixture
def candidate():
    return ParsedResume(
        candidate_name="Alice Johnson",
        email="alice@example.com",
        skills=["Python", "Machine Learning", "SQL", "Docker"],
        experience=[
            ExperienceSchema(
                job_title="Data Scientist",
                company="TechCo",
                start_date="2020-01",
                end_date="2024-01",
                duration_months=48,
                description=[
                    "Built predictive models improving revenue by 15%",
                    "Led team of 3 data scientists",
                ],
            ),
        ],
        education=[],
        total_years_experience=4.0,
    )


@pytest.fixture
def job():
    return JobPosting(
        job_id="1",
        title="Senior Data Scientist",
        company="AI Corp",
        description="Senior DS role",
        required_skills=["Python", "Machine Learning"],
    )


@pytest.fixture
def match(job):
    return JobMatchResult(
        job=job,
        match_score=85.0,
        recommendation="Strong Match",
        matched_skills=["Python", "Machine Learning", "SQL"],
        missing_skills=["Spark"],
    )


class TestTemplates:
    def test_all_templates_exist(self):
        assert "recruiter" in TEMPLATES
        assert "hiring_manager" in TEMPLATES
        assert "referral" in TEMPLATES

    def test_templates_have_required_fields(self):
        for name, template in TEMPLATES.items():
            assert "subject" in template, f"{name} missing subject"
            assert "body" in template, f"{name} missing body"

    def test_templates_have_placeholders(self):
        for name, template in TEMPLATES.items():
            assert "{candidate_name}" in template["body"]
            assert "{role}" in template["body"]
            assert "{company}" in template["body"]


class TestDraftOutreach:
    def test_draft_recruiter(self, candidate, job, match):
        draft = draft_outreach(candidate, job, match, "recruiter")
        assert "Alice Johnson" in draft.body
        assert "Senior Data Scientist" in draft.subject or "Senior Data Scientist" in draft.body
        assert "AI Corp" in draft.body
        assert draft.target_role == "recruiter"

    def test_draft_hiring_manager(self, candidate, job, match):
        draft = draft_outreach(candidate, job, match, "hiring_manager")
        assert "Alice Johnson" in draft.body
        assert draft.target_role == "hiring_manager"

    def test_draft_referral(self, candidate, job, match):
        draft = draft_outreach(candidate, job, match, "referral")
        assert "referral" in draft.body.lower()

    def test_includes_matched_skills(self, candidate, job, match):
        draft = draft_outreach(candidate, job, match, "recruiter")
        # At least one matched skill should appear
        assert any(skill in draft.body for skill in match.matched_skills)

    def test_includes_compliance_notes(self, candidate, job, match):
        draft = draft_outreach(candidate, job, match, "recruiter")
        assert len(draft.compliance_notes) >= 3
        # Should mention CAN-SPAM or GDPR
        combined = " ".join(draft.compliance_notes).lower()
        assert "can-spam" in combined or "gdpr" in combined

    def test_not_auto_sent(self, candidate, job, match):
        draft = draft_outreach(candidate, job, match, "recruiter")
        # Should have a compliance note about reviewing before sending
        combined = " ".join(draft.compliance_notes).lower()
        assert "draft" in combined or "review" in combined


class TestDraftAll:
    def test_generates_three_drafts(self, candidate, job, match):
        drafts = draft_all_outreach(candidate, job, match)
        assert len(drafts) == 3
        roles = {d.target_role for d in drafts}
        assert roles == {"recruiter", "hiring_manager", "referral"}

    def test_each_draft_personalized(self, candidate, job, match):
        drafts = draft_all_outreach(candidate, job, match)
        for draft in drafts:
            assert "Alice Johnson" in draft.body
            assert "AI Corp" in draft.body
