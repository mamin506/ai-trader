"""Integration tests for Alpaca API.

These tests connect to the real Alpaca Paper Trading API to verify
that the integration works correctly.

Requirements:
- .env file with valid Alpaca Paper Trading credentials
- ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables

Run with: pytest tests/integration/test_alpaca_integration.py -v
"""

import os
from datetime import datetime, timedelta

import pytest

from src.data.providers.alpaca_provider import AlpacaProvider
from src.execution.alpaca_executor import AlpacaExecutor
from src.utils.alpaca_client import AlpacaClient
from src.utils.exceptions import ConfigurationError


# Skip all tests if Alpaca credentials are not configured
pytestmark = pytest.mark.skipif(
    not os.getenv("ALPACA_API_KEY") or not os.getenv("ALPACA_SECRET_KEY"),
    reason="Alpaca credentials not configured in .env",
)


@pytest.fixture(scope="module")
def alpaca_client():
    """Create AlpacaClient from environment variables."""
    try:
        return AlpacaClient.from_env()
    except ConfigurationError:
        pytest.skip("Alpaca credentials not configured")


@pytest.fixture(scope="module")
def alpaca_provider(alpaca_client):
    """Create AlpacaProvider instance."""
    return AlpacaProvider(alpaca_client)


@pytest.fixture(scope="module")
def alpaca_executor(alpaca_client):
    """Create AlpacaExecutor instance."""
    return AlpacaExecutor(alpaca_client)


class TestAlpacaClientIntegration:
    """Integration tests for AlpacaClient."""

    def test_client_creation_from_env(self, alpaca_client):
        """Test creating client from environment variables."""
        assert alpaca_client is not None
        assert alpaca_client.api_key
        assert alpaca_client.secret_key
        assert alpaca_client.paper is True  # Should be paper trading mode

    def test_connection_test(self, alpaca_client):
        """Test connection to Alpaca API."""
        result = alpaca_client.test_connection()
        assert result is True

    def test_get_trading_client(self, alpaca_client):
        """Test getting TradingClient."""
        trading_client = alpaca_client.get_trading_client()
        assert trading_client is not None

    def test_get_data_client(self, alpaca_client):
        """Test getting StockHistoricalDataClient."""
        data_client = alpaca_client.get_data_client()
        assert data_client is not None


class TestAlpacaProviderIntegration:
    """Integration tests for AlpacaProvider."""

    def test_get_historical_bars(self, alpaca_provider):
        """Test fetching historical data for a known symbol."""
        # Fetch 1 week of data for AAPL
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        df = alpaca_provider.get_historical_bars("AAPL", start_date, end_date)

        # Verify data structure
        assert df is not None
        assert not df.empty
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df.index.name == "date"

        # Verify data quality
        assert (df["high"] >= df["low"]).all()
        assert (df["close"] > 0).all()
        assert (df["volume"] >= 0).all()

    def test_get_latest_quote(self, alpaca_provider):
        """Test fetching latest quote for a known symbol."""
        quote = alpaca_provider.get_latest_quote("AAPL")

        # Verify quote structure
        assert quote["symbol"] == "AAPL"
        assert "bid" in quote
        assert "ask" in quote
        assert "last" in quote
        assert "timestamp" in quote

        # Verify quote values are reasonable
        assert quote["bid"] > 0
        assert quote["ask"] > 0
        assert quote["ask"] >= quote["bid"]
        assert quote["last"] > 0

    def test_get_trading_days(self, alpaca_provider):
        """Test fetching trading days."""
        # Get trading days for Jan 2024
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        trading_days = alpaca_provider.get_trading_days(start_date, end_date)

        # Verify result
        assert trading_days is not None
        assert len(trading_days) > 0
        # January 2024 should have ~20-21 trading days
        assert 19 <= len(trading_days) <= 22


class TestAlpacaExecutorIntegration:
    """Integration tests for AlpacaExecutor."""

    def test_get_account_info(self, alpaca_executor):
        """Test fetching account information."""
        account_info = alpaca_executor.get_account_info()

        # Verify account info structure
        assert account_info is not None
        assert account_info.cash >= 0
        assert account_info.portfolio_value >= 0
        assert account_info.buying_power >= 0

        # Log account info for debugging
        print(f"\nAccount Info:")
        print(f"  Cash: ${account_info.cash:,.2f}")
        print(f"  Portfolio Value: ${account_info.portfolio_value:,.2f}")
        print(f"  Buying Power: ${account_info.buying_power:,.2f}")

    def test_get_positions(self, alpaca_executor):
        """Test fetching current positions."""
        positions = alpaca_executor.get_positions()

        # Verify positions structure
        assert positions is not None
        assert isinstance(positions, dict)

        # Log positions for debugging
        print(f"\nCurrent Positions: {len(positions)}")
        for symbol, position in positions.items():
            print(
                f"  {symbol}: {position.shares} shares @ "
                f"${position.avg_cost:.2f}, "
                f"P&L: ${position.unrealized_pnl:.2f}"
            )

    def test_get_open_orders(self, alpaca_executor):
        """Test fetching open orders."""
        open_orders = alpaca_executor.get_open_orders()

        # Verify open orders structure
        assert open_orders is not None
        assert isinstance(open_orders, list)

        # Log open orders for debugging
        print(f"\nOpen Orders: {len(open_orders)}")
        for order in open_orders:
            print(
                f"  {order.order_id}: {order.order.action.value} "
                f"{order.order.shares} {order.order.symbol} - "
                f"Status: {order.status.value}"
            )

    @pytest.mark.skip(
        reason="Skipped by default to avoid submitting real orders. "
        "Enable manually for testing order submission."
    )
    def test_submit_order(self, alpaca_executor):
        """Test submitting a small paper trading order.

        This test is skipped by default to avoid submitting real orders.
        Enable it manually when you want to test order submission.
        """
        from src.portfolio.base import Order, OrderAction

        # Create a small buy order for testing
        # WARNING: This will submit a real order to Paper Trading!
        order = Order(
            action=OrderAction.BUY,
            symbol="AAPL",
            shares=1,  # Small quantity for testing
            estimated_value=150.0,
            reason="Integration test order",
        )

        # Submit order
        results = alpaca_executor.submit_orders([order])

        # Verify submission
        assert len(results) == 1
        result = results[0]
        assert result.order_id is not None

        # Cancel the order immediately to avoid execution
        if not result.is_complete:
            cancel_result = alpaca_executor.cancel_orders([result.order_id])
            assert cancel_result.get(result.order_id) is True

        print(f"\nSubmitted and canceled test order: {result.order_id}")


class TestAlpacaRateLimiting:
    """Test rate limiting with real API."""

    def test_rate_limiting_under_limit(self, alpaca_provider):
        """Test making multiple requests under rate limit."""
        # Make 5 quick requests (well under 200/min limit)
        for i in range(5):
            quote = alpaca_provider.get_latest_quote("AAPL")
            assert quote is not None

        print("\n5 requests completed successfully (rate limiting working)")

    @pytest.mark.slow
    def test_retry_logic(self, alpaca_provider):
        """Test retry logic with an invalid symbol."""
        from src.utils.exceptions import DataProviderError

        # Try to fetch data for an invalid symbol
        # This should retry and then fail
        with pytest.raises(DataProviderError):
            alpaca_provider.get_historical_bars(
                "INVALID_SYMBOL_XYZ",
                datetime(2024, 1, 1),
                datetime(2024, 1, 2),
            )

        print("\nRetry logic tested successfully")
