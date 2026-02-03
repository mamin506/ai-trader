"""
Quick Phase 2 Integration Tests

Simplified integration tests to verify basic functionality of all modules.
"""

import pytest
from datetime import datetime, timedelta
from src.utils.alpaca_client import AlpacaClient
from src.data.providers.alpaca_provider import AlpacaProvider
from src.execution.alpaca_executor import AlpacaExecutor
from src.risk.dynamic_risk_manager import DynamicRiskManager
from src.monitoring.performance_tracker import PerformanceTracker


@pytest.fixture(scope="module")
def alpaca_client():
    """Create AlpacaClient from environment."""
    return AlpacaClient.from_env()


@pytest.fixture(scope="module")
def alpaca_provider(alpaca_client):
    """Create AlpacaProvider instance."""
    return AlpacaProvider(alpaca_client)


@pytest.fixture(scope="module")
def alpaca_executor(alpaca_client):
    """Create AlpacaExecutor instance."""
    return AlpacaExecutor(alpaca_client)


@pytest.fixture
def risk_manager():
    """Create DynamicRiskManager instance."""
    return DynamicRiskManager()


@pytest.fixture
def performance_tracker():
    """Create PerformanceTracker instance."""
    return PerformanceTracker(initial_capital=100000.0)


class TestAlpacaIntegration:
    """Test Alpaca API integration."""

    @pytest.mark.integration
    def test_provider_can_fetch_trading_days(self, alpaca_provider):
        """Test AlpacaProvider can fetch trading days."""
        # Use dates with 00:00 time component (API requirement)
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=30)

        trading_days = alpaca_provider.get_trading_days(start_date, end_date)

        # get_trading_days returns pd.DatetimeIndex, not list
        import pandas as pd
        assert isinstance(trading_days, pd.DatetimeIndex)
        assert len(trading_days) > 0
        print(f"✅ Fetched {len(trading_days)} trading days")

    @pytest.mark.integration
    def test_provider_can_fetch_historical_data(self, alpaca_provider):
        """Test AlpacaProvider can fetch historical data.

        Note: This test may fail on Alpaca free tier which doesn't provide
        historical bar data. This is expected and OK - we use yfinance for
        historical data on free tier.
        """
        # Use fixed dates from mid-2024 to avoid recent data restrictions
        start_date = datetime(2024, 6, 1)
        end_date = datetime(2024, 6, 10)

        try:
            bars = alpaca_provider.get_historical_bars("AAPL", start_date, end_date)
            assert bars is not None
            assert len(bars) > 0
            print(f"✅ Fetched {len(bars)} bars for AAPL")
        except Exception as e:
            if "subscription does not permit" in str(e) or "No data returned" in str(e):
                pytest.skip("Alpaca free tier doesn't support historical bars - using yfinance instead")
            else:
                raise

    @pytest.mark.integration
    def test_executor_can_get_account_info(self, alpaca_executor):
        """Test AlpacaExecutor can retrieve account information."""
        account = alpaca_executor.get_account_info()

        assert account is not None
        assert hasattr(account, "cash")
        assert hasattr(account, "buying_power")
        assert float(account.cash) >= 0
        print(f"✅ Account cash: ${float(account.cash):,.2f}")

    @pytest.mark.integration
    def test_executor_can_get_positions(self, alpaca_executor):
        """Test AlpacaExecutor can retrieve positions."""
        positions = alpaca_executor.get_positions()

        # get_positions returns Dict[str, Position], not list
        assert isinstance(positions, dict)
        print(f"✅ Current positions: {len(positions)}")


class TestRiskManagement:
    """Test Dynamic Risk Management."""

    def test_risk_manager_initialization(self, risk_manager):
        """Test DynamicRiskManager can be initialized."""
        assert risk_manager is not None
        assert hasattr(risk_manager, "stop_loss_pct")
        assert hasattr(risk_manager, "take_profit_pct")
        print("✅ Risk manager initialized")

    def test_risk_manager_has_monitoring_methods(self, risk_manager):
        """Test DynamicRiskManager has required methods."""
        assert hasattr(risk_manager, "validate_weights")
        assert hasattr(risk_manager, "check_position_risk")
        print("✅ Risk manager has monitoring methods")


class TestMonitoring:
    """Test Monitoring & Performance Tracking."""

    def test_performance_tracker_initialization(self, performance_tracker):
        """Test PerformanceTracker initialization."""
        assert performance_tracker is not None
        assert performance_tracker.initial_capital == 100000.0
        print("✅ Performance tracker initialized")

    def test_performance_tracker_can_record_value(self, performance_tracker):
        """Test PerformanceTracker can record daily values."""
        # Use correct method name: record_daily_performance
        performance_tracker.record_daily_performance(
            date=datetime.now().date(),
            portfolio_value=101000.0,
            cash=50000.0,
            positions_value=51000.0
        )

        # Correct method name is get_performance_metrics, not get_metrics
        metrics = performance_tracker.get_performance_metrics()
        assert metrics is not None
        assert "total_return_pct" in metrics or "total_return" in metrics
        print("✅ Performance tracker can record values")


class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.mark.integration
    def test_can_fetch_data_and_check_account(
        self, alpaca_provider, alpaca_executor
    ):
        """Test data fetching → account check flow.

        Note: Data fetching may be skipped on Alpaca free tier which doesn't
        provide historical bar data. Account check still validates API access.
        """
        # 1. Try to fetch data (may fail on free tier)
        start_date = datetime(2024, 6, 1)
        end_date = datetime(2024, 6, 10)

        bars = None
        try:
            bars = alpaca_provider.get_historical_bars("AAPL", start_date, end_date)
            assert bars is not None
            assert len(bars) > 0
            print(f"   - Fetched {len(bars)} bars")
        except Exception as e:
            if "subscription does not permit" in str(e) or "No data returned" in str(e):
                print("   - Historical bars skipped (free tier limitation)")
            else:
                raise

        # 2. Get account info (this should always work)
        account = alpaca_executor.get_account_info()

        assert float(account.cash) > 0
        assert float(account.buying_power) > 0

        print(f"✅ E2E test passed:")
        print(f"   - Account cash: ${float(account.cash):,.2f}")
        print(f"   - Buying power: ${float(account.buying_power):,.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
