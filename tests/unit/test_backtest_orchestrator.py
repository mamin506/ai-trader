"""Unit tests for BacktestOrchestrator."""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.orchestration.backtest_orchestrator import (
    BacktestConfig,
    BacktestOrchestrator,
    BacktestResult,
)
from src.strategy.ma_crossover import MACrossoverStrategy


def create_sample_price_data(
    symbol: str,
    start_date: datetime,
    num_days: int = 100,
    base_price: float = 100.0,
) -> pd.DataFrame:
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start=start_date, periods=num_days, freq="B")

    # Create trending data with some noise
    prices = []
    price = base_price
    for i in range(num_days):
        # Add trend and noise
        trend = 0.001 * (i - num_days / 2)  # Slight uptrend in second half
        noise = (i % 7 - 3) * 0.5  # Small oscillation
        price = base_price * (1 + trend) + noise
        prices.append(max(price, 1.0))

    df = pd.DataFrame(
        {
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [1000000] * num_days,
        },
        index=dates,
    )
    return df


class TestBacktestConfig:
    """Test cases for BacktestConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = BacktestConfig()

        assert config.initial_cash == 100000.0
        assert config.slippage_pct == 0.001
        assert config.rebalance_frequency == "daily"
        assert config.max_positions == 10

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = BacktestConfig(
            initial_cash=50000.0,
            slippage_pct=0.002,
            rebalance_frequency="weekly",
            max_positions=5,
        )

        assert config.initial_cash == 50000.0
        assert config.slippage_pct == 0.002
        assert config.rebalance_frequency == "weekly"
        assert config.max_positions == 5


class TestBacktestOrchestrator:
    """Test cases for BacktestOrchestrator."""

    @pytest.fixture
    def strategy(self) -> MACrossoverStrategy:
        """Create MA Crossover strategy for testing."""
        return MACrossoverStrategy({"fast_period": 5, "slow_period": 15})

    @pytest.fixture
    def price_data(self) -> dict:
        """Create sample price data for testing."""
        start_date = datetime(2024, 1, 1)
        return {
            "AAPL": create_sample_price_data("AAPL", start_date, 100, 150.0),
            "MSFT": create_sample_price_data("MSFT", start_date, 100, 350.0),
        }

    def test_orchestrator_init(self, strategy: MACrossoverStrategy) -> None:
        """Test orchestrator initialization."""
        orchestrator = BacktestOrchestrator(strategy)

        assert orchestrator.strategy == strategy
        assert orchestrator.config.initial_cash == 100000.0
        assert orchestrator.executor is not None
        assert orchestrator.allocator is not None
        assert orchestrator.risk_manager is not None

    def test_orchestrator_with_custom_config(
        self, strategy: MACrossoverStrategy
    ) -> None:
        """Test orchestrator with custom config."""
        config = BacktestConfig(
            initial_cash=50000.0,
            slippage_pct=0.002,
        )
        orchestrator = BacktestOrchestrator(strategy, config)

        assert orchestrator.config.initial_cash == 50000.0
        assert orchestrator.config.slippage_pct == 0.002

    def test_run_backtest(
        self, strategy: MACrossoverStrategy, price_data: dict
    ) -> None:
        """Test running a backtest."""
        orchestrator = BacktestOrchestrator(strategy)
        result = orchestrator.run(price_data)

        assert isinstance(result, BacktestResult)
        assert result.initial_value == 100000.0
        assert result.final_value > 0
        assert result.start_date is not None
        assert result.end_date is not None
        assert not result.equity_curve.empty

    def test_run_backtest_empty_data(self, strategy: MACrossoverStrategy) -> None:
        """Test backtest with empty data raises error."""
        orchestrator = BacktestOrchestrator(strategy)

        with pytest.raises(ValueError, match="price_data cannot be empty"):
            orchestrator.run({})

    def test_run_backtest_single_day(self, strategy: MACrossoverStrategy) -> None:
        """Test backtest with single day data raises error."""
        orchestrator = BacktestOrchestrator(strategy)

        single_day_data = {
            "AAPL": pd.DataFrame(
                {
                    "open": [150.0],
                    "high": [151.0],
                    "low": [149.0],
                    "close": [150.5],
                    "volume": [1000000],
                },
                index=[datetime(2024, 1, 1)],
            )
        }

        with pytest.raises(ValueError, match="Need at least 2 trading days"):
            orchestrator.run(single_day_data)

    def test_backtest_result_metrics(
        self, strategy: MACrossoverStrategy, price_data: dict
    ) -> None:
        """Test that backtest result contains expected metrics."""
        orchestrator = BacktestOrchestrator(strategy)
        result = orchestrator.run(price_data)

        # Check all expected fields exist
        assert hasattr(result, "total_return")
        assert hasattr(result, "total_return_pct")
        assert hasattr(result, "annualized_return")
        assert hasattr(result, "max_drawdown")
        assert hasattr(result, "sharpe_ratio")
        assert hasattr(result, "num_trades")
        assert hasattr(result, "equity_curve")
        assert hasattr(result, "trades")
        assert hasattr(result, "daily_returns")

    def test_rebalance_frequency_weekly(
        self, strategy: MACrossoverStrategy, price_data: dict
    ) -> None:
        """Test weekly rebalancing."""
        config = BacktestConfig(rebalance_frequency="weekly")
        orchestrator = BacktestOrchestrator(strategy, config)
        result = orchestrator.run(price_data)

        # Weekly rebalancing should have fewer trades than daily
        assert isinstance(result, BacktestResult)

    def test_rebalance_frequency_monthly(
        self, strategy: MACrossoverStrategy, price_data: dict
    ) -> None:
        """Test monthly rebalancing."""
        config = BacktestConfig(rebalance_frequency="monthly")
        orchestrator = BacktestOrchestrator(strategy, config)
        result = orchestrator.run(price_data)

        # Monthly rebalancing should have even fewer trades
        assert isinstance(result, BacktestResult)

    def test_reset(self, strategy: MACrossoverStrategy, price_data: dict) -> None:
        """Test orchestrator reset."""
        orchestrator = BacktestOrchestrator(strategy)

        # Run backtest
        orchestrator.run(price_data)

        # Reset
        orchestrator.reset()

        # Verify reset state
        account = orchestrator.executor.get_account_info()
        assert account.cash == orchestrator.config.initial_cash
        assert len(orchestrator.executor.get_positions()) == 0

    def test_equity_curve_columns(
        self, strategy: MACrossoverStrategy, price_data: dict
    ) -> None:
        """Test equity curve has expected columns."""
        orchestrator = BacktestOrchestrator(strategy)
        result = orchestrator.run(price_data)

        assert "portfolio_value" in result.equity_curve.columns
        assert "cash" in result.equity_curve.columns
        assert "positions_value" in result.equity_curve.columns


class TestBacktestResultMetrics:
    """Test cases for backtest result metrics calculation."""

    @pytest.fixture
    def strategy(self) -> MACrossoverStrategy:
        """Create MA Crossover strategy for testing."""
        return MACrossoverStrategy({"fast_period": 5, "slow_period": 15})

    def test_total_return_calculation(self, strategy: MACrossoverStrategy) -> None:
        """Test total return calculation."""
        start_date = datetime(2024, 1, 1)
        price_data = {
            "AAPL": create_sample_price_data("AAPL", start_date, 60, 100.0),
        }

        orchestrator = BacktestOrchestrator(strategy)
        result = orchestrator.run(price_data)

        # Verify return calculation is consistent
        expected_return = (result.final_value - result.initial_value) / result.initial_value
        assert abs(result.total_return - expected_return) < 0.0001
        assert abs(result.total_return_pct - expected_return * 100) < 0.01

    def test_max_drawdown_non_negative(self, strategy: MACrossoverStrategy) -> None:
        """Test max drawdown is non-negative."""
        start_date = datetime(2024, 1, 1)
        price_data = {
            "AAPL": create_sample_price_data("AAPL", start_date, 60, 100.0),
        }

        orchestrator = BacktestOrchestrator(strategy)
        result = orchestrator.run(price_data)

        assert result.max_drawdown >= 0

    def test_daily_returns_length(self, strategy: MACrossoverStrategy) -> None:
        """Test daily returns series length."""
        start_date = datetime(2024, 1, 1)
        price_data = {
            "AAPL": create_sample_price_data("AAPL", start_date, 60, 100.0),
        }

        orchestrator = BacktestOrchestrator(strategy)
        result = orchestrator.run(price_data)

        # Daily returns should be one less than equity curve length
        expected_length = len(result.equity_curve) - 1
        assert len(result.daily_returns) == expected_length


class TestTradeExecution:
    """Test cases for trade execution in backtest."""

    @pytest.fixture
    def strategy(self) -> MACrossoverStrategy:
        """Create MA Crossover strategy for testing."""
        return MACrossoverStrategy({"fast_period": 5, "slow_period": 15})

    def test_trades_recorded(self, strategy: MACrossoverStrategy) -> None:
        """Test that trades are recorded."""
        start_date = datetime(2024, 1, 1)
        price_data = {
            "AAPL": create_sample_price_data("AAPL", start_date, 100, 100.0),
        }

        orchestrator = BacktestOrchestrator(strategy)
        result = orchestrator.run(price_data)

        # Trades list should exist (may be empty if no signals)
        assert isinstance(result.trades, list)

    def test_trade_structure(self, strategy: MACrossoverStrategy) -> None:
        """Test trade record structure."""
        start_date = datetime(2024, 1, 1)
        # Create data with clear trend change to generate signals
        prices = [100.0] * 20 + [110.0] * 80  # Jump up to trigger buy
        dates = pd.date_range(start=start_date, periods=100, freq="B")

        price_data = {
            "AAPL": pd.DataFrame(
                {
                    "open": prices,
                    "high": [p * 1.01 for p in prices],
                    "low": [p * 0.99 for p in prices],
                    "close": prices,
                    "volume": [1000000] * 100,
                },
                index=dates,
            )
        }

        orchestrator = BacktestOrchestrator(strategy)
        result = orchestrator.run(price_data)

        # If there are trades, check structure
        if result.trades:
            trade = result.trades[0]
            assert "date" in trade
            assert "symbol" in trade
            assert "action" in trade
            assert "shares" in trade
            assert "price" in trade
