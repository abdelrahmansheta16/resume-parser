"""Tests for the retry decorator."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.job_discovery.retry import retry_on_network_error


class TestRetryDecorator:
    def test_succeeds_on_second_attempt(self):
        mock_fn = MagicMock(side_effect=[requests.ConnectionError("fail"), "ok"])

        @retry_on_network_error(max_retries=2, backoff=0.01)
        def flaky():
            return mock_fn()

        result = flaky()
        assert result == "ok"
        assert mock_fn.call_count == 2

    def test_exhausted_raises(self):
        mock_fn = MagicMock(side_effect=requests.Timeout("timeout"))

        @retry_on_network_error(max_retries=1, backoff=0.01)
        def always_fail():
            return mock_fn()

        with pytest.raises(requests.Timeout):
            always_fail()
        assert mock_fn.call_count == 2  # initial + 1 retry

    def test_no_retry_on_success(self):
        mock_fn = MagicMock(return_value="immediate")

        @retry_on_network_error(max_retries=3, backoff=0.01)
        def works():
            return mock_fn()

        assert works() == "immediate"
        assert mock_fn.call_count == 1

    def test_backoff_increases(self):
        """Verify that sleep is called with increasing delays."""
        mock_fn = MagicMock(
            side_effect=[requests.ConnectionError(), requests.ConnectionError(), "ok"]
        )

        @retry_on_network_error(max_retries=2, backoff=1.0)
        def flaky():
            return mock_fn()

        with patch("app.job_discovery.retry.time.sleep") as mock_sleep:
            flaky()

        assert mock_sleep.call_count == 2
        # First retry: 1.0 * 2^0 = 1.0, second: 1.0 * 2^1 = 2.0
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)
