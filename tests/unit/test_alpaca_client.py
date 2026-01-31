"""Unit tests for AlpacaClient.

Tests the Alpaca API client utility with mocked API responses.
"""

import os
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.utils.alpaca_client import AlpacaClient
from src.utils.exceptions import BrokerConnectionError, ConfigurationError


class TestAlpacaClient:
    """Test AlpacaClient initialization and configuration."""

    def test_init_with_credentials(self):
        """Test initialization with valid credentials."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            paper=True,
        )

        assert client.api_key == "test_key"
        assert client.secret_key == "test_secret"
        assert client.paper is True
        assert client.rate_limit_per_minute == 200
        assert client.retry_attempts == 3

    def test_init_missing_credentials(self):
        """Test initialization with missing credentials raises error."""
        with pytest.raises(ConfigurationError, match="API key and secret key are required"):
            AlpacaClient(api_key="", secret_key="test_secret")

        with pytest.raises(ConfigurationError, match="API key and secret key are required"):
            AlpacaClient(api_key="test_key", secret_key="")

    @patch.dict(os.environ, {
        "ALPACA_API_KEY": "env_key",
        "ALPACA_SECRET_KEY": "env_secret",
        "ALPACA_PAPER": "true"
    })
    def test_from_env_success(self):
        """Test creation from environment variables."""
        client = AlpacaClient.from_env()

        assert client.api_key == "env_key"
        assert client.secret_key == "env_secret"
        assert client.paper is True

    @patch.dict(os.environ, {
        "ALPACA_API_KEY": "env_key",
        "ALPACA_SECRET_KEY": "env_secret",
        "ALPACA_PAPER": "false"
    })
    def test_from_env_live_mode(self):
        """Test creation from environment variables with live mode."""
        client = AlpacaClient.from_env()

        assert client.paper is False

    @patch("src.utils.alpaca_client.load_dotenv")
    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_missing_api_key(self, mock_load_dotenv):
        """Test from_env raises error when API key is missing."""
        with pytest.raises(ConfigurationError, match="ALPACA_API_KEY not found"):
            AlpacaClient.from_env()

    @patch("src.utils.alpaca_client.load_dotenv")
    @patch.dict(os.environ, {"ALPACA_API_KEY": "test_key"}, clear=True)
    def test_from_env_missing_secret_key(self, mock_load_dotenv):
        """Test from_env raises error when secret key is missing."""
        with pytest.raises(ConfigurationError, match="ALPACA_SECRET_KEY not found"):
            AlpacaClient.from_env()


class TestAlpacaClientConnection:
    """Test AlpacaClient connection management."""

    @patch("src.utils.alpaca_client.TradingClient")
    def test_get_trading_client(self, mock_trading_client_class):
        """Test getting TradingClient instance."""
        mock_client_instance = Mock()
        mock_trading_client_class.return_value = mock_client_instance

        client = AlpacaClient(api_key="test_key", secret_key="test_secret")
        trading_client = client.get_trading_client()

        # Verify TradingClient was created with correct args
        mock_trading_client_class.assert_called_once_with(
            api_key="test_key",
            secret_key="test_secret",
            paper=True,
        )

        # Verify same instance returned on subsequent calls (singleton)
        trading_client2 = client.get_trading_client()
        assert trading_client is trading_client2

    @patch("src.utils.alpaca_client.StockHistoricalDataClient")
    def test_get_data_client(self, mock_data_client_class):
        """Test getting StockHistoricalDataClient instance."""
        mock_client_instance = Mock()
        mock_data_client_class.return_value = mock_client_instance

        client = AlpacaClient(api_key="test_key", secret_key="test_secret")
        data_client = client.get_data_client()

        # Verify DataClient was created with correct args
        mock_data_client_class.assert_called_once_with(
            api_key="test_key",
            secret_key="test_secret",
        )

        # Verify same instance returned on subsequent calls (singleton)
        data_client2 = client.get_data_client()
        assert data_client is data_client2

    @patch("src.utils.alpaca_client.TradingClient")
    def test_get_trading_client_failure(self, mock_trading_client_class):
        """Test TradingClient initialization failure."""
        mock_trading_client_class.side_effect = Exception("Connection failed")

        client = AlpacaClient(api_key="test_key", secret_key="test_secret")

        with pytest.raises(BrokerConnectionError, match="Failed to initialize TradingClient"):
            client.get_trading_client()


class TestAlpacaClientRateLimiting:
    """Test AlpacaClient rate limiting."""

    def test_check_rate_limit_under_limit(self):
        """Test rate limiting when under the limit."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            rate_limit_per_minute=10,
        )

        # Make 9 requests (under limit of 10)
        for _ in range(9):
            client.check_rate_limit()

        # Should not sleep
        assert len(client._request_times) == 9

    def test_check_rate_limit_at_limit(self):
        """Test rate limiting when at the limit."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            rate_limit_per_minute=5,
        )

        # Make requests up to the limit
        for _ in range(5):
            client.check_rate_limit()

        # Next request should sleep (we'll just check the logic, not actually sleep)
        assert len(client._request_times) == 5

    def test_check_rate_limit_clears_old_requests(self):
        """Test that old requests are cleared from tracking."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            rate_limit_per_minute=10,
        )

        # Add old request times (> 1 minute ago)
        current_time = time.time()
        client._request_times = [
            current_time - 70,  # 70 seconds ago
            current_time - 65,  # 65 seconds ago
        ]

        # Make new request
        client.check_rate_limit()

        # Old requests should be cleared
        assert len(client._request_times) == 1


class TestAlpacaClientRetry:
    """Test AlpacaClient retry logic."""

    def test_with_retry_success_first_attempt(self):
        """Test successful execution on first attempt."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            retry_attempts=3,
        )

        mock_func = Mock(return_value="success")
        result = client.with_retry(mock_func, "arg1", kwarg1="value1")

        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

    def test_with_retry_success_after_failures(self):
        """Test successful execution after retries."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            retry_attempts=3,
            retry_delay=0.01,  # Small delay for testing
        )

        # Fail twice, then succeed
        mock_func = Mock(side_effect=[
            Exception("Attempt 1 failed"),
            Exception("Attempt 2 failed"),
            "success",
        ])

        result = client.with_retry(mock_func)

        assert result == "success"
        assert mock_func.call_count == 3

    def test_with_retry_all_attempts_fail(self):
        """Test failure after all retry attempts."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            retry_attempts=3,
            retry_delay=0.01,
        )

        mock_func = Mock(side_effect=Exception("Always fails"))

        with pytest.raises(BrokerConnectionError, match="failed after 3 attempts"):
            client.with_retry(mock_func)

        assert mock_func.call_count == 3


class TestAlpacaClientConnectionTest:
    """Test AlpacaClient connection testing."""

    @patch("src.utils.alpaca_client.TradingClient")
    def test_test_connection_success(self, mock_trading_client_class):
        """Test successful connection test."""
        # Mock account object
        mock_account = Mock()
        mock_account.status = "ACTIVE"
        mock_account.buying_power = "100000.00"

        # Mock trading client
        mock_client = Mock()
        mock_client.get_account.return_value = mock_account
        mock_trading_client_class.return_value = mock_client

        client = AlpacaClient(api_key="test_key", secret_key="test_secret")
        result = client.test_connection()

        assert result is True
        mock_client.get_account.assert_called()

    @patch("src.utils.alpaca_client.TradingClient")
    def test_test_connection_failure(self, mock_trading_client_class):
        """Test failed connection test."""
        mock_trading_client_class.side_effect = Exception("Connection failed")

        client = AlpacaClient(api_key="test_key", secret_key="test_secret")
        result = client.test_connection()

        assert result is False
