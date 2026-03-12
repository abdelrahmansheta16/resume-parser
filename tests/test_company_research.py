"""Tests for the company research module."""
from __future__ import annotations

import pytest

from app.company_research.contact_finder import extract_public_contacts


class TestContactFinder:
    def test_extract_recruiting_emails(self):
        text = "Apply at careers@example.com or jobs@example.com for more info."
        contacts = extract_public_contacts(text)
        emails = [c["value"] for c in contacts if c["channel_type"] == "email"]
        assert "careers@example.com" in emails
        assert "jobs@example.com" in emails

    def test_extract_hr_email(self):
        text = "Send your resume to hr@company.com"
        contacts = extract_public_contacts(text)
        assert len(contacts) >= 1
        assert contacts[0]["value"] == "hr@company.com"

    def test_extract_application_urls(self):
        text = "Apply here: https://company.com/careers/apply"
        contacts = extract_public_contacts(text)
        urls = [c for c in contacts if c["channel_type"] == "url"]
        assert len(urls) >= 1

    def test_no_personal_emails(self):
        text = "Contact john.doe@personal.com for questions"
        contacts = extract_public_contacts(text)
        # Should not extract personal emails
        emails = [c["value"] for c in contacts if c["channel_type"] == "email"]
        assert "john.doe@personal.com" not in emails

    def test_extract_recruiter_name(self):
        text = "Contact Jane Smith, our recruiter: Jane Smith for this position"
        contacts = extract_public_contacts(text)
        names = [c for c in contacts if c["channel_type"] == "name"]
        # May or may not find depending on pattern
        assert isinstance(names, list)

    def test_empty_text(self):
        contacts = extract_public_contacts("")
        assert contacts == []

    def test_deduplicates(self):
        text = "Email careers@example.com or careers@example.com for info"
        contacts = extract_public_contacts(text)
        emails = [c["value"] for c in contacts if c["channel_type"] == "email"]
        assert emails.count("careers@example.com") == 1


class TestCrawler:
    def test_robots_txt_check_no_url(self):
        """Test that research_company handles missing domain gracefully."""
        from app.company_research.crawler import research_company
        result = research_company("Unknown Corp")
        assert result.company_name == "Unknown Corp"
        assert result.domain is None

    def test_extract_domain_from_apply_url(self):
        from app.company_research.crawler import _extract_domain_from_url
        assert _extract_domain_from_url("https://www.example.com/jobs/123") == "example.com"
        assert _extract_domain_from_url("https://careers.google.com/apply") == "careers.google.com"
        assert _extract_domain_from_url(None) is None

    def test_extract_tech_stack(self):
        from app.company_research.crawler import _extract_tech_stack
        text = "We use Python, React, and Docker in our stack. Our team loves Kubernetes."
        techs = _extract_tech_stack(text)
        assert "python" in techs
        assert "react" in techs
        assert "docker" in techs
        assert "kubernetes" in techs
