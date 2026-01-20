"""Unit tests for BacktestAPI."""

from datetime import datetime
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from src.api.backtest_api import BacktestAPI
from src.orchestration.backtest_orchestrator import BacktestConfig, BacktestResult
from src.strategy.ma_crossover import MACrossoverStrategy


def create_sample_price_data(
    symbol: str,
    start_date: datetime,
    num_days: int = 60,
    base_price: float = 100.0,
) -> pd.DataFrame:
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start=start_date, periods=num_days, freq="B")
    prices = [base_price + i * 0.1 for i in range(num_days)]

    return pd.DataFrame(
        {
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [1000000] * num_days,
        },
        index=dates,
    )


class TestBacktestAPIInit:
    """Test cases for BacktestAPI initialization."""

    def test_default_init(self) -> None:
        """Test API with default initialization."""
        api = BacktestAPI()
        assert api.data_api is not None

    def test_custom_data_api(self) -> None:
        """Test API with custom data API."""
        mock_data_api = Mock()
        api = BacktestAPI(data_api=mock_data_api)
        assert api.data_api == mock_data_api


class TestRunBacktest:
    """Test cases for run_backtest method."""

    @pytest.fixture
    def api(self) -> BacktestAPI:
        """Create BacktestAPI for testing."""
        return BacktestAPI()

    @pytest.fixture
    def price_data(self) -> dict:
        """Create sample price data."""
        start_date = datetime(2024, 1, 1)
        return {
            "AAPL": create_sample_price_data("AAPL", start_date, 60, 150.0),
            "MSFT": create_sample_price_data("MSFT", start_date, 60, 350.0),
        }

    def test_run_backtest_with_strategy(
        self, api: BacktestAPI, price_data: dict
    ) -> None:
        """Test running backtest with custom strategy."""
        strategy = MACrossoverStrategy({"fast_period": 5, "slow_period": 15})

        result = api.run_backtest(
            strategy=strategy,
            symbols=["AAPL", "MSFT"],
            start_date="2024-01-01",
            end_date="2024-03-31",
            price_data=price_data,
        )

        assert isinstance(result, BacktestResult)
        assert result.initial_value == 100000.0

    def test_run_backtest_with_datetime_dates(
        self, api: BacktestAPI, price_data: dict
    ) -> None:
        """Test running backtest with datetime dates."""
        strategy = MACrossoverStrategy({"fast_period": 5, "slow_period": 15})

        result = api.run_backtest(
            strategy=strategy,
            symbols=["AAPL"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 31),
            price_data=price_data,
        )

        assert isinstance(result, BacktestResult)


class TestRunMACrossover:
    """Test cases for run_ma_crossover method."""

    @pytest.fixture
    def api(self) -> BacktestAPI:
        """Create BacktestAPI for testing."""
        return BacktestAPI()

    @pytest.fixture
    def price_data(self) -> dict:
        """Create sample price data."""
        start_date = datetime(2024, 1, 1)
        return {
            "AAPL": create_sample_price_data("AAPL", start_date, 60, 150.0),
        }

    def test_run_ma_crossover(self, api: BacktestAPI, price_data: dict) -> None:
        """Test running MA crossover backtest."""
        result = api.run_ma_crossover(
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-03-31",
            fast_period=5,
            slow_period=15,
            price_data=price_data,
        )

        assert isinstance(result, BacktestResult)

    def test_run_ma_crossover_custom_params(
        self, api: BacktestAPI, price_data: dict
    ) -> None:
        """Test MA crossover with custom parameters."""
        result = api.run_ma_crossover(
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-03-31",
            fast_period=10,
            slow_period=30,
            initial_cash=50000.0,
            slippage_pct=0.002,
            rebalance_frequency="weekly",
            price_data=price_data,
        )

        assert result.config.initial_cash == 50000.0
        assert result.config.slippage_pct == 0.002
        assert result.config.rebalance_frequency == "weekly"


class TestFormatResults:
    """Test cases for format_results method."""

    @pytest.fixture
    def api(self) -> BacktestAPI:
        """Create BacktestAPI for testing."""
        return BacktestAPI()

    @pytest.fixture
    def sample_result(self) -> BacktestResult:
        """Create sample backtest result."""
        return BacktestResult(
            config=BacktestConfig(),
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 30),
            initial_value=100000.0,
            final_value=110000.0,
            total_return=0.10,
            total_return_pct=10.0,
            annualized_return=0.20,
            max_drawdown=0.05,
            sharpe_ratio=1.5,
            num_trades=20,
            num_winning_trades=12,
            num_losing_trades=8,
            win_rate=0.6,
            equity_curve=pd.DataFrame({"portfolio_value": [100000, 110000]}),
            trades=[],
            daily_returns=pd.Series([0.001, 0.002]),
        )

    def test_format_results(self, api: BacktestAPI, sample_result: BacktestResult) -> None:
        """Test formatting backtest results."""
        output = api.format_results(sample_result)

        assert "BACKTEST RESULTS" in output
        assert "Total Return" in output
        assert "10.00%" in output
        assert "Max Drawdown" in output
        assert "Sharpe Ratio" in output


class TestResultAccessors:
    """Test cases for result accessor methods."""

    @pytest.fixture
    def api(self) -> BacktestAPI:
        """Create BacktestAPI for testing."""
        return BacktestAPI()

    @pytest.fixture
    def sample_result(self) -> BacktestResult:
        """Create sample backtest result."""
        return BacktestResult(
            config=BacktestConfig(),
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 30),
            initial_value=100000.0,
            final_value=110000.0,
            total_return=0.10,
            total_return_pct=10.0,
            annualized_return=0.20,
            max_drawdown=0.05,
            sharpe_ratio=1.5,
            num_trades=2,
            num_winning_trades=1,
            num_losing_trades=1,
            win_rate=0.5,
            equity_curve=pd.DataFrame(
                {"portfolio_value": [100000, 105000, 110000]},
                index=pd.date_range("2024-01-01", periods=3),
            ),
            trades=[
                {"date": datetime(2024, 1, 15), "symbol": "AAPL", "action": "BUY"},
                {"date": datetime(2024, 2, 15), "symbol": "AAPL", "action": "SELL"},
            ],
            daily_returns=pd.Series([0.05, 0.047619]),
        )

    def test_get_equity_curve(self, api: BacktestAPI, sample_result: BacktestResult) -> None:
        """Test getting equity curve."""
        equity = api.get_equity_curve(sample_result)

        assert isinstance(equity, pd.DataFrame)
        assert "portfolio_value" in equity.columns
        assert len(equity) == 3

    def test_get_trades(self, api: BacktestAPI, sample_result: BacktestResult) -> None:
        """Test getting trades."""
        trades = api.get_trades(sample_result)

        assert isinstance(trades, pd.DataFrame)
        assert len(trades) == 2
        assert "symbol" in trades.columns

    def test_get_trades_empty(self, api: BacktestAPI) -> None:
        """Test getting trades when empty."""
        result = BacktestResult(
            config=BacktestConfig(),
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 30),
            initial_value=100000.0,
            final_value=100000.0,
            total_return=0.0,
            total_return_pct=0.0,
            annualized_return=0.0,
            max_drawdown=0.0,
            sharpe_ratio=None,
            num_trades=0,
            num_winning_trades=0,
            num_losing_trades=0,
            win_rate=0.0,
            equity_curve=pd.DataFrame(),
            trades=[],
            daily_returns=pd.Series(dtype=float),
        )

        trades = api.get_trades(result)
        assert isinstance(trades, pd.DataFrame)
        assert len(trades) == 0

    def test_get_daily_returns(self, api: BacktestAPI, sample_result: BacktestResult) -> None:
        """Test getting daily returns."""
        returns = api.get_daily_returns(sample_result)

        assert isinstance(returns, pd.Series)
        assert len(returns) == 2


class TestCompareResults:
    """Test cases for comparing multiple results."""

    @pytest.fixture
    def api(self) -> BacktestAPI:
        """Create BacktestAPI for testing."""
        return BacktestAPI()

    @pytest.fixture
    def results(self) -> dict:
        """Create multiple backtest results for comparison."""
        base_result = {
            "config": BacktestConfig(),
            "start_date": datetime(2024, 1, 1),
            "end_date": datetime(2024, 6, 30),
            "initial_value": 100000.0,
            "equity_curve": pd.DataFrame(),
            "trades": [],
            "daily_returns": pd.Series(dtype=float),
        }

        return {
            "Strategy A": BacktestResult(
                **base_result,
                final_value=110000.0,
                total_return=0.10,
                total_return_pct=10.0,
                annualized_return=0.20,
                max_drawdown=0.05,
                sharpe_ratio=1.5,
                num_trades=20,
                num_winning_trades=12,
                num_losing_trades=8,
                win_rate=0.6,
            ),
            "Strategy B": BacktestResult(
                **base_result,
                final_value=105000.0,
                total_return=0.05,
                total_return_pct=5.0,
                annualized_return=0.10,
                max_drawdown=0.03,
                sharpe_ratio=1.2,
                num_trades=10,
                num_winning_trades=6,
                num_losing_trades=4,
                win_rate=0.6,
            ),
        }

    def test_compare_results(self, api: BacktestAPI, results: dict) -> None:
        """Test comparing multiple results."""
        comparison = api.compare_results(results)

        assert isinstance(comparison, pd.DataFrame)
        assert "Strategy A" in comparison.index
        assert "Strategy B" in comparison.index
        assert "Total Return (%)" in comparison.columns

    def test_format_comparison(self, api: BacktestAPI, results: dict) -> None:
        """Test formatting comparison."""
        output = api.format_comparison(results)

        assert "STRATEGY COMPARISON" in output
        assert "Strategy A" in output
        assert "Strategy B" in output
