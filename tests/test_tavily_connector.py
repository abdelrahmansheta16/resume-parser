"""Tests for the Tavily web search connector."""
from unittest.mock import MagicMock, patch

import pytest

from app.job_discovery.tavily_connector import TavilyConnector, _parse_title


MOCK_TAVILY_RESPONSE = {
    "results": [
        {
            "title": "Senior Backend Engineer - Google | LinkedIn",
            "url": "https://linkedin.com/jobs/view/123",
            "content": "We are looking for a Senior Backend Engineer to join our platform team. Requirements: 5+ years Python...",
        },
        {
            "title": "Software Engineer at Meta - Apply Now",
            "url": "https://meta.com/careers/456",
            "content": "Meta is hiring a Software Engineer for the infrastructure team. Strong distributed systems experience required.",
        },
        {
            "title": "DeFi Engineer, Uniswap",
            "url": "https://boards.greenhouse.io/uniswap/789",
            "content": "Join Uniswap as a DeFi Engineer. Solidity, smart contracts, and protocol development.",
        },
    ],
}


class TestTavilyConnectorConfig:
    @patch("app.job_discovery.tavily_connector.config")
    def test_not_configured_without_key(self, mock_config):
        mock_config.tavily_api_key = ""
        connector = TavilyConnector()
        assert connector.is_configured() is False

    @patch("app.job_discovery.tavily_connector.config")
    def test_configured_with_key(self, mock_config):
        mock_config.tavily_api_key = "tvly-test-key"
        connector = TavilyConnector()
        assert connector.is_configured() is True

    @patch("app.job_discovery.tavily_connector.config")
    def test_search_returns_empty_when_not_configured(self, mock_config):
        mock_config.tavily_api_key = ""
        connector = TavilyConnector()
        result = connector.search("Python Developer")
        assert result == []


class TestTavilyConnectorSearch:
    @patch("app.job_discovery.tavily_connector.time.sleep")
    @patch("tavily.TavilyClient")
    @patch("app.job_discovery.tavily_connector.config")
    def test_successful_search(self, mock_config, mock_client_cls, mock_sleep):
        mock_config.tavily_api_key = "tvly-test-key"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.return_value = MOCK_TAVILY_RESPONSE

        connector = TavilyConnector()
        results = connector.search("Backend Engineer", "San Francisco")

        assert len(results) == 3
        assert results[0].title == "Senior Backend Engineer"
        assert results[0].company == "Google"
        assert results[0].source == "tavily"
        assert results[0].apply_url == "https://linkedin.com/jobs/view/123"

        assert results[1].title == "Software Engineer"
        assert results[1].company == "Meta"

        # Verify query includes "jobs" keyword
        call_kwargs = mock_client.search.call_args
        assert "jobs" in call_kwargs.kwargs["query"]
        assert "San Francisco" in call_kwargs.kwargs["query"]

    @patch("app.job_discovery.tavily_connector.time.sleep")
    @patch("tavily.TavilyClient")
    @patch("app.job_discovery.tavily_connector.config")
    def test_returns_empty_on_exception(self, mock_config, mock_client_cls, mock_sleep):
        mock_config.tavily_api_key = "tvly-test-key"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.side_effect = Exception("API error")

        connector = TavilyConnector()
        results = connector.search("Python Developer")
        assert results == []

    @patch("app.job_discovery.tavily_connector.time.sleep")
    @patch("tavily.TavilyClient")
    @patch("app.job_discovery.tavily_connector.config")
    def test_handles_empty_results(self, mock_config, mock_client_cls, mock_sleep):
        mock_config.tavily_api_key = "tvly-test-key"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.return_value = {"results": []}

        connector = TavilyConnector()
        results = connector.search("Nonexistent Role")
        assert results == []


class TestParseTitleHelper:
    def test_title_with_dash_company_and_pipe(self):
        title, company = _parse_title("Senior Engineer - Google | LinkedIn")
        assert title == "Senior Engineer"
        assert company == "Google"

    def test_title_with_at_pattern(self):
        title, company = _parse_title("Software Engineer at Meta - Apply Now")
        assert title == "Software Engineer"
        assert company == "Meta"

    def test_plain_title(self):
        title, company = _parse_title("DeFi Engineer, Uniswap")
        assert title == "DeFi Engineer, Uniswap"
        assert company == ""

    def test_strips_indeed_suffix(self):
        title, company = _parse_title("Data Scientist - Indeed.com")
        assert title == "Data Scientist"
        assert company == ""
