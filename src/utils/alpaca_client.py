"""Alpaca API client utility.

This module provides a centralized client for Alpaca API access with
authentication, rate limiting, and error handling.
"""

import os
import time
from datetime import datetime
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from dotenv import load_dotenv

from src.utils.exceptions import BrokerConnectionError, ConfigurationError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AlpacaClient:
    """Centralized Alpaca API client with connection management.

    This class handles:
    - Authentication and connection setup
    - Rate limiting
    - Error handling and retry logic
    - Credential loading from environment variables

    Example:
        >>> client = AlpacaClient.from_env()
        >>> trading_client = client.get_trading_client()
        >>> data_client = client.get_data_client()
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        paper: bool = True,
        rate_limit_per_minute: int = 200,
        retry_attempts: int = 3,
        retry_delay: float = 2.0,
    ):
        """Initialize Alpaca client.

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
            paper: Use paper trading (True) or live trading (False)
            rate_limit_per_minute: Max API requests per minute
            retry_attempts: Number of retry attempts for failed requests
            retry_delay: Delay in seconds between retries

        Raises:
            ConfigurationError: If credentials are invalid
        """
        if not api_key or not secret_key:
            raise ConfigurationError("Alpaca API key and secret key are required")

        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.rate_limit_per_minute = rate_limit_per_minute
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

        # Rate limiting tracking
        self._request_times: list[float] = []

        # Lazy-initialized clients
        self._trading_client: Optional[TradingClient] = None
        self._data_client: Optional[StockHistoricalDataClient] = None

        logger.info(
            "AlpacaClient initialized (mode: %s, rate_limit: %d/min)",
            "paper" if paper else "live",
            rate_limit_per_minute,
        )

    @classmethod
    def from_env(cls, env_file: str = ".env") -> "AlpacaClient":
        """Create AlpacaClient from environment variables.

        Loads credentials from .env file using python-dotenv.

        Environment variables:
            - ALPACA_API_KEY: Alpaca API key
            - ALPACA_SECRET_KEY: Alpaca secret key
            - ALPACA_PAPER (optional): "true" or "false" (default: "true")

        Args:
            env_file: Path to .env file (default: ".env")

        Returns:
            AlpacaClient instance

        Raises:
            ConfigurationError: If required environment variables are missing

        Example:
            >>> client = AlpacaClient.from_env()
        """
        # Load environment variables
        load_dotenv(env_file)

        # Get credentials
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        paper_mode = os.getenv("ALPACA_PAPER", "true").lower() == "true"

        if not api_key:
            raise ConfigurationError(
                "ALPACA_API_KEY not found in environment variables. "
                "Please set it in your .env file."
            )

        if not secret_key:
            raise ConfigurationError(
                "ALPACA_SECRET_KEY not found in environment variables. "
                "Please set it in your .env file."
            )

        return cls(api_key=api_key, secret_key=secret_key, paper=paper_mode)

    def get_trading_client(self) -> TradingClient:
        """Get or create TradingClient instance.

        Returns:
            TradingClient for order execution and account management

        Raises:
            BrokerConnectionError: If client initialization fails
        """
        if self._trading_client is None:
            try:
                self._trading_client = TradingClient(
                    api_key=self.api_key,
                    secret_key=self.secret_key,
                    paper=self.paper,
                )
                logger.info("TradingClient initialized successfully")
            except Exception as e:
                error_msg = f"Failed to initialize TradingClient: {e}"
                logger.error(error_msg)
                raise BrokerConnectionError(error_msg) from e

        return self._trading_client

    def get_data_client(self) -> StockHistoricalDataClient:
        """Get or create StockHistoricalDataClient instance.

        Returns:
            StockHistoricalDataClient for historical and real-time data

        Raises:
            BrokerConnectionError: If client initialization fails
        """
        if self._data_client is None:
            try:
                self._data_client = StockHistoricalDataClient(
                    api_key=self.api_key,
                    secret_key=self.secret_key,
                )
                logger.info("StockHistoricalDataClient initialized successfully")
            except Exception as e:
                error_msg = f"Failed to initialize StockHistoricalDataClient: {e}"
                logger.error(error_msg)
                raise BrokerConnectionError(error_msg) from e

        return self._data_client

    def check_rate_limit(self) -> None:
        """Check rate limit and sleep if necessary.

        Implements simple token bucket rate limiting. Sleeps if the
        rate limit would be exceeded.
        """
        current_time = time.time()

        # Remove requests older than 1 minute
        one_minute_ago = current_time - 60
        self._request_times = [
            t for t in self._request_times if t > one_minute_ago
        ]

        # Check if we've hit the rate limit
        if len(self._request_times) >= self.rate_limit_per_minute:
            # Sleep until the oldest request is outside the 1-minute window
            sleep_time = self._request_times[0] + 60 - current_time
            if sleep_time > 0:
                logger.warning(
                    "Rate limit reached (%d requests/min). Sleeping for %.2f seconds.",
                    self.rate_limit_per_minute,
                    sleep_time,
                )
                time.sleep(sleep_time)

                # Clear old requests after sleeping
                current_time = time.time()
                one_minute_ago = current_time - 60
                self._request_times = [
                    t for t in self._request_times if t > one_minute_ago
                ]

        # Record this request
        self._request_times.append(current_time)

    def with_retry(self, func, *args, **kwargs):
        """Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            BrokerConnectionError: If all retry attempts fail
        """
        last_exception = None

        for attempt in range(self.retry_attempts):
            try:
                # Check rate limit before making request
                self.check_rate_limit()

                # Execute function
                result = func(*args, **kwargs)
                return result

            except Exception as e:
                last_exception = e
                logger.warning(
                    "API request failed (attempt %d/%d): %s",
                    attempt + 1,
                    self.retry_attempts,
                    e,
                )

                # Sleep before retry (except on last attempt)
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff

        # All retries failed
        error_msg = (
            f"API request failed after {self.retry_attempts} attempts: "
            f"{last_exception}"
        )
        logger.error(error_msg)
        raise BrokerConnectionError(error_msg) from last_exception

    def test_connection(self) -> bool:
        """Test connection to Alpaca API.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            trading_client = self.get_trading_client()
            account = self.with_retry(trading_client.get_account)
            logger.info(
                "Connection test successful. Account status: %s, "
                "Buying power: $%.2f",
                account.status,
                float(account.buying_power),
            )
            return True
        except Exception as e:
            logger.error("Connection test failed: %s", e)
            return False
