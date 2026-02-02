"""
Phase 2 Integration Tests

Tests the integration of all Phase 2 modules:
- Module 1: Alpaca Integration (AlpacaProvider, AlpacaExecutor)
- Module 2: Scheduler & Workflows
- Module 3: Dynamic Risk Management
- Module 4: Monitoring & CLI Tools

These tests verify that all components work together correctly.
"""

import pytest
import os
from datetime import datetime, timedelta, date
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

# Import Phase 2 components
from src.data.providers.alpaca_provider import AlpacaProvider
from src.execution.alpaca_executor import AlpacaExecutor
from src.risk.dynamic_risk_manager import DynamicRiskManager
from src.orchestration.scheduler import TradingScheduler
from src.orchestration.workflows import DailyWorkflow
from src.monitoring.performance_tracker import PerformanceTracker
from src.utils.config import load_alpaca_config


@pytest.fixture
def alpaca_client():
    """Create AlpacaClient from environment."""
    from src.utils.alpaca_client import AlpacaClient

    return AlpacaClient.from_env()


@pytest.fixture
def alpaca_provider(alpaca_client):
    """Create AlpacaProvider instance."""
    return AlpacaProvider(alpaca_client)


@pytest.fixture
def alpaca_executor(alpaca_client):
    """Create AlpacaExecutor instance."""
    return AlpacaExecutor(alpaca_client)


@pytest.fixture
def risk_manager():
    """Create DynamicRiskManager instance."""
    return DynamicRiskManager(
        stop_loss_pct=0.03,  # 3%
        take_profit_pct=0.10,  # 10%
        daily_loss_limit=0.02,  # 2%
        max_drawdown=0.05,  # 5%
    )


@pytest.fixture
def performance_tracker():
    """Create PerformanceTracker instance."""
    return PerformanceTracker(initial_capital=100000.0)


class TestModule1_AlpacaIntegration:
    """Test Module 1: Alpaca API Integration."""

    @pytest.mark.integration
    def test_alpaca_provider_connection(self, alpaca_provider):
        """Test AlpacaProvider can connect to Alpaca API."""
        # Test get_trading_days (should not raise)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        trading_days = alpaca_provider.get_trading_days(start_date, end_date)

        assert isinstance(trading_days, list)
        assert len(trading_days) > 0
        assert all(isinstance(d, date) for d in trading_days)

    @pytest.mark.integration
    def test_alpaca_provider_historical_data(self, alpaca_provider):
        """Test AlpacaProvider can fetch historical data."""
        end_date = date.today()
        start_date = end_date - timedelta(days=10)

        # Fetch AAPL data
        bars = alpaca_provider.get_daily_bars("AAPL", start_date, end_date)

        assert isinstance(bars, pd.DataFrame)
        assert not bars.empty
        assert all(
            col in bars.columns for col in ["open", "high", "low", "close", "volume"]
        )

    @pytest.mark.integration
    def test_alpaca_executor_account_info(self, alpaca_executor):
        """Test AlpacaExecutor can retrieve account information."""
        account = alpaca_executor.get_account_info()

        assert account is not None
        assert hasattr(account, "cash")
        assert hasattr(account, "buying_power")
        assert hasattr(account, "portfolio_value")
        assert float(account.cash) >= 0
        assert float(account.buying_power) >= 0

    @pytest.mark.integration
    def test_alpaca_executor_positions(self, alpaca_executor):
        """Test AlpacaExecutor can retrieve positions."""
        positions = alpaca_executor.get_positions()

        assert isinstance(positions, list)
        # Positions may be empty if no trades yet


class TestModule2_SchedulerIntegration:
    """Test Module 2: Scheduler & Workflows."""

    def test_scheduler_initialization(self):
        """Test TradingScheduler can be initialized."""
        config = {"timezone": "US/Eastern"}

        scheduler = TradingScheduler(config)

        assert scheduler is not None
        assert hasattr(scheduler, "register_task")
        assert hasattr(scheduler, "start")
        assert hasattr(scheduler, "shutdown")

    def test_daily_workflow_initialization(self, alpaca_provider, alpaca_executor):
        """Test DailyWorkflow can be initialized with real components."""
        workflow = DailyWorkflow(
            data_provider=alpaca_provider,
            executor=alpaca_executor,
            symbols=["AAPL", "MSFT"],
        )

        assert workflow is not None
        assert hasattr(workflow, "run_market_open")
        assert hasattr(workflow, "run_rebalancing")
        assert hasattr(workflow, "run_market_close")


class TestModule3_RiskManagement:
    """Test Module 3: Dynamic Risk Management."""

    def test_risk_manager_position_monitoring(self, risk_manager):
        """Test DynamicRiskManager can monitor positions."""
        from src.execution.base import Position

        # Create mock position with 5% loss (should trigger stop-loss)
        position = Position(
            symbol="AAPL",
            qty=10,
            avg_entry_price=150.0,
            current_price=142.5,  # -5% loss
            market_value=1425.0,
            unrealized_pl=-75.0,
            unrealized_pl_pct=-0.05,
        )

        current_prices = {"AAPL": 142.5}

        exit_signals = risk_manager.monitor_positions([position], current_prices)

        # Should trigger stop-loss (3% threshold)
        assert len(exit_signals) == 1
        assert exit_signals[0].symbol == "AAPL"
        assert exit_signals[0].reason == "stop_loss"

    def test_risk_manager_circuit_breaker(self, risk_manager):
        """Test circuit breaker triggers on drawdown."""
        portfolio_value = 95000.0  # Down from peak
        peak_value = 100000.0  # Peak value
        daily_start_value = 99000.0

        # Should trigger circuit breaker (5% drawdown)
        should_halt = risk_manager.check_circuit_breaker(
            portfolio_value, peak_value, daily_start_value
        )

        assert should_halt is True


class TestModule4_Monitoring:
    """Test Module 4: Monitoring & Performance Tracking."""

    def test_performance_tracker_initialization(self, performance_tracker):
        """Test PerformanceTracker initialization."""
        assert performance_tracker is not None
        assert performance_tracker.initial_capital == 100000.0

    def test_performance_tracker_update(self, performance_tracker):
        """Test PerformanceTracker can record portfolio updates."""
        # Record daily portfolio value
        performance_tracker.record_daily_value(
            date=datetime.now().date(), portfolio_value=101000.0
        )

        metrics = performance_tracker.get_metrics()

        assert metrics is not None
        assert "total_return" in metrics
        assert metrics["total_return"] > 0  # 1% gain


class TestEndToEndIntegration:
    """End-to-end integration tests combining all modules."""

    @pytest.mark.integration
    def test_data_to_execution_flow(self, alpaca_provider, alpaca_executor):
        """Test data fetching → order execution flow."""
        # 1. Fetch historical data
        end_date = date.today()
        start_date = end_date - timedelta(days=5)

        bars = alpaca_provider.get_daily_bars("AAPL", start_date, end_date)

        assert not bars.empty

        # 2. Get account info
        account = alpaca_executor.get_account_info()

        assert float(account.cash) > 0

        # 3. Verify we can calculate position size
        latest_price = bars.iloc[-1]["close"]
        max_position_value = float(account.buying_power) * 0.1  # 10% max
        max_shares = int(max_position_value / latest_price)

        assert max_shares > 0

    @pytest.mark.integration
    def test_risk_manager_with_real_account(
        self, alpaca_executor, risk_manager, performance_tracker
    ):
        """Test risk manager with real account data."""
        # Get current positions
        positions = alpaca_executor.get_positions()
        account = alpaca_executor.get_account_info()

        # Check circuit breaker
        portfolio_value = float(account.portfolio_value)
        peak_value = portfolio_value  # Assume current is peak for test

        should_halt = risk_manager.check_circuit_breaker(
            portfolio_value, peak_value, portfolio_value
        )

        # Should not halt if at peak
        assert should_halt is False

    @pytest.mark.integration
    def test_complete_workflow_dry_run(
        self, alpaca_provider, alpaca_executor, risk_manager, performance_tracker
    ):
        """Test complete daily workflow (dry run - no actual trades)."""
        # 1. Market Open: Health check
        account = alpaca_executor.get_account_info()
        assert account.status == "ACTIVE"
        assert not account.trading_blocked

        # 2. Data Fetching
        symbols = ["AAPL", "MSFT", "GOOGL"]
        end_date = date.today()
        start_date = end_date - timedelta(days=60)

        data = {}
        for symbol in symbols:
            try:
                bars = alpaca_provider.get_daily_bars(symbol, start_date, end_date)
                if not bars.empty:
                    data[symbol] = bars
            except Exception as e:
                print(f"Failed to fetch {symbol}: {e}")

        assert len(data) > 0

        # 3. Generate signals (mock for now - use Phase 1 strategy)
        signals = {}
        for symbol in data.keys():
            # Mock signal: just check if we have enough data
            if len(data[symbol]) >= 50:
                signals[symbol] = 0.5  # Mock buy signal

        # 4. Risk validation
        portfolio_value = float(account.portfolio_value)
        cash = float(account.cash)

        # Check total exposure
        total_signal = sum(abs(s) for s in signals.values())
        if total_signal > 0:
            # Would allocate here
            pass

        # 5. Performance tracking
        performance_tracker.record_daily_value(
            date=datetime.now().date(), portfolio_value=portfolio_value
        )

        metrics = performance_tracker.get_metrics()
        assert metrics is not None


class TestInterfaceCompatibility:
    """Test that all module interfaces are compatible."""

    def test_alpaca_provider_implements_data_provider(self, alpaca_provider):
        """Test AlpacaProvider implements DataProvider interface."""
        from src.data.base import DataProvider

        assert isinstance(alpaca_provider, DataProvider)
        assert hasattr(alpaca_provider, "get_daily_bars")
        assert hasattr(alpaca_provider, "get_trading_days")

    def test_alpaca_executor_implements_order_executor(self, alpaca_executor):
        """Test AlpacaExecutor implements OrderExecutor interface."""
        from src.execution.base import OrderExecutor

        assert isinstance(alpaca_executor, OrderExecutor)
        assert hasattr(alpaca_executor, "submit_orders")
        assert hasattr(alpaca_executor, "get_positions")
        assert hasattr(alpaca_executor, "get_account_info")

    def test_risk_manager_implements_risk_manager_interface(self, risk_manager):
        """Test DynamicRiskManager implements RiskManager interface."""
        from src.risk.base import RiskManager

        assert isinstance(risk_manager, RiskManager)
        assert hasattr(risk_manager, "monitor_positions")
        assert hasattr(risk_manager, "check_circuit_breaker")


# Test configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires API access)"
    )


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "-m", "integration"])
