"""Unit tests for DailyWorkflow.

Tests the daily trading workflows with mocked components.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from src.execution.base import AccountInfo, OrderStatus, Position
from src.orchestration.workflows import DailyWorkflow, WorkflowConfig
from src.portfolio.base import Order, OrderAction
from src.strategy.ma_crossover import MACrossoverStrategy


@pytest.fixture
def mock_alpaca_client():
    """Create mock AlpacaClient."""
    client = Mock()
    client.with_retry = Mock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs))
    return client


@pytest.fixture
def workflow_config():
    """Create workflow configuration."""
    strategy = MACrossoverStrategy({"fast_period": 50, "slow_period": 200})

    return WorkflowConfig(
        symbols=["AAPL", "MSFT", "GOOGL"],
        strategy=strategy,
        initial_capital=100000.0,
        min_signal_threshold=0.3,
        max_positions=3,
        max_position_size=0.4,
        cash_buffer=0.05,
    )


@pytest.fixture
def daily_workflow(mock_alpaca_client, workflow_config):
    """Create DailyWorkflow instance with mocked client."""
    return DailyWorkflow(mock_alpaca_client, workflow_config)


class TestDailyWorkflowInit:
    """Test DailyWorkflow initialization."""

    def test_init(self, daily_workflow, workflow_config):
        """Test workflow initialization."""
        assert daily_workflow is not None
        assert daily_workflow.config == workflow_config
        assert daily_workflow.data_provider is not None
        assert daily_workflow.executor is not None
        assert daily_workflow.portfolio_manager is not None
        assert daily_workflow.risk_manager is not None
        assert daily_workflow.strategy is not None


class TestMarketOpenWorkflow:
    """Test market open workflow."""

    def test_market_open_success(self, daily_workflow):
        """Test successful market open workflow."""
        # Mock account info
        mock_account = AccountInfo(
            cash=50000.0,
            portfolio_value=100000.0,
            buying_power=75000.0,
            positions_value=50000.0,
        )

        # Mock positions
        mock_positions = {
            "AAPL": Position(
                symbol="AAPL",
                shares=100,
                avg_cost=150.0,
                market_value=15500.0,
                unrealized_pnl=500.0,
            )
        }

        daily_workflow.executor.get_account_info = Mock(return_value=mock_account)
        daily_workflow.executor.get_positions = Mock(return_value=mock_positions)

        # Execute workflow
        result = daily_workflow.market_open_workflow()

        # Verify
        assert result["status"] == "success"
        assert result["account_info"] == mock_account
        assert result["positions"] == mock_positions
        assert "timestamp" in result

    def test_market_open_connection_failure(self, daily_workflow):
        """Test market open workflow with connection failure."""
        from src.utils.exceptions import BrokerConnectionError

        # Mock connection failure
        daily_workflow.executor.get_account_info = Mock(
            side_effect=Exception("Connection failed")
        )

        # Should raise BrokerConnectionError
        with pytest.raises(BrokerConnectionError):
            daily_workflow.market_open_workflow()


class TestRebalancingWorkflow:
    """Test rebalancing workflow."""

    @patch.object(DailyWorkflow, "_fetch_latest_data")
    @patch.object(DailyWorkflow, "_generate_signals")
    @patch.object(DailyWorkflow, "_build_portfolio_state")
    def test_rebalancing_success(
        self,
        mock_build_portfolio,
        mock_generate_signals,
        mock_fetch_data,
        daily_workflow,
    ):
        """Test successful rebalancing workflow."""
        # Mock data fetching
        mock_data = {
            "AAPL": pd.DataFrame(
                {"close": [150.0, 151.0, 152.0]},
                index=pd.date_range("2024-01-01", periods=3),
            )
        }
        mock_fetch_data.return_value = mock_data

        # Mock signal generation
        mock_signals = {"AAPL": 0.5, "MSFT": -0.3, "GOOGL": 0.8}
        mock_generate_signals.return_value = mock_signals

        # Mock portfolio state
        from src.portfolio.base import PortfolioState

        mock_portfolio_state = PortfolioState(
            positions={},
            total_value=100000.0,
            cash=100000.0,
            prices={"AAPL": 150.0, "MSFT": 300.0, "GOOGL": 140.0},
        )
        mock_build_portfolio.return_value = mock_portfolio_state

        # Mock portfolio allocation
        from src.portfolio.base import AllocationResult

        mock_orders = [
            Order(
                action=OrderAction.BUY,
                symbol="AAPL",
                shares=100,
                estimated_value=15000.0,
                reason="Buy signal",
            )
        ]

        mock_allocation = AllocationResult(
            target_weights={"AAPL": 0.3, "GOOGL": 0.2, "Cash": 0.5},
            orders=mock_orders,
        )

        daily_workflow.portfolio_manager.allocate = Mock(return_value=mock_allocation)

        # Mock risk validation
        daily_workflow.risk_manager.validate_orders = Mock(return_value=mock_orders)

        # Mock order execution
        from src.execution.base import ExecutionOrder

        mock_execution_result = ExecutionOrder(
            order_id="order-123",
            order=mock_orders[0],
            status=OrderStatus.SUBMITTED,
        )

        daily_workflow.executor.submit_orders = Mock(
            return_value=[mock_execution_result]
        )

        # Execute workflow
        result = daily_workflow.rebalancing_workflow()

        # Verify
        assert result["status"] == "success"
        assert result["signals"] == mock_signals
        assert result["orders_submitted"] == 1
        assert result["orders_successful"] == 1
        assert result["orders_rejected"] == 0

    @patch.object(DailyWorkflow, "_fetch_latest_data")
    def test_rebalancing_data_fetch_failure(self, mock_fetch_data, daily_workflow):
        """Test rebalancing workflow with data fetch failure."""
        from src.utils.exceptions import ExecutionError

        # Mock data fetch failure
        mock_fetch_data.side_effect = Exception("Data fetch failed")

        # Should raise ExecutionError
        with pytest.raises(ExecutionError):
            daily_workflow.rebalancing_workflow()


class TestMarketCloseWorkflow:
    """Test market close workflow."""

    def test_market_close_success(self, daily_workflow):
        """Test successful market close workflow."""
        # Mock open orders
        daily_workflow.executor.get_open_orders = Mock(return_value=[])

        # Mock positions
        mock_positions = {
            "AAPL": Position(
                symbol="AAPL",
                shares=100,
                avg_cost=150.0,
                market_value=15500.0,
                unrealized_pnl=500.0,
            )
        }

        daily_workflow.executor.get_positions = Mock(return_value=mock_positions)

        # Mock account info
        mock_account = AccountInfo(
            cash=50000.0,
            portfolio_value=100000.0,
            buying_power=75000.0,
            positions_value=50000.0,
        )

        daily_workflow.executor.get_account_info = Mock(return_value=mock_account)

        # Execute workflow
        result = daily_workflow.market_close_workflow()

        # Verify
        assert result["status"] == "success"
        assert result["open_orders"] == 0
        assert result["positions_count"] == 1
        assert result["portfolio_value"] == 100000.0
        assert result["total_unrealized_pnl"] == 500.0

    def test_market_close_with_open_orders(self, daily_workflow):
        """Test market close workflow with open orders."""
        from src.execution.base import ExecutionOrder

        # Mock open order
        mock_order = ExecutionOrder(
            order_id="order-123",
            order=Order(
                action=OrderAction.BUY,
                symbol="AAPL",
                shares=100,
                estimated_value=15000.0,
            ),
            status=OrderStatus.SUBMITTED,
        )

        daily_workflow.executor.get_open_orders = Mock(return_value=[mock_order])
        daily_workflow.executor.get_positions = Mock(return_value={})

        mock_account = AccountInfo(
            cash=100000.0,
            portfolio_value=100000.0,
            buying_power=100000.0,
            positions_value=0.0,
        )

        daily_workflow.executor.get_account_info = Mock(return_value=mock_account)

        # Execute workflow (should log warning but not fail)
        result = daily_workflow.market_close_workflow()

        # Verify
        assert result["status"] == "success"
        assert result["open_orders"] == 1


class TestWorkflowHelperMethods:
    """Test workflow helper methods."""

    def test_fetch_latest_data(self, daily_workflow):
        """Test _fetch_latest_data method."""
        # Mock data provider
        mock_df = pd.DataFrame(
            {
                "open": [150.0, 151.0],
                "high": [152.0, 153.0],
                "low": [149.0, 150.0],
                "close": [151.0, 152.0],
                "volume": [1000000, 1100000],
            },
            index=pd.date_range("2024-01-01", periods=2),
        )

        daily_workflow.data_provider.get_historical_bars = Mock(return_value=mock_df)

        # Execute
        result = daily_workflow._fetch_latest_data()

        # Verify
        assert "AAPL" in result
        assert "MSFT" in result
        assert "GOOGL" in result

    def test_generate_signals(self, daily_workflow):
        """Test _generate_signals method."""
        # Mock data
        mock_data = {
            "AAPL": pd.DataFrame(
                {"close": [150.0] * 250},  # 250 days for MA calculation
                index=pd.date_range("2024-01-01", periods=250),
            )
        }

        # Execute
        result = daily_workflow._generate_signals(mock_data)

        # Verify
        assert "AAPL" in result
        assert isinstance(result["AAPL"], float)

    def test_build_portfolio_state(self, daily_workflow):
        """Test _build_portfolio_state method."""
        # Mock executor responses
        mock_positions = {
            "AAPL": Position(
                symbol="AAPL",
                shares=100,
                avg_cost=150.0,
                market_value=15500.0,
                unrealized_pnl=500.0,
            )
        }

        mock_account = AccountInfo(
            cash=50000.0,
            portfolio_value=100000.0,
            buying_power=75000.0,
            positions_value=50000.0,
        )

        daily_workflow.executor.get_positions = Mock(return_value=mock_positions)
        daily_workflow.executor.get_account_info = Mock(return_value=mock_account)

        # Mock data with latest prices
        mock_data = {
            "AAPL": pd.DataFrame(
                {"close": [152.0]}, index=pd.date_range("2024-01-01", periods=1)
            )
        }

        # Execute
        result = daily_workflow._build_portfolio_state(mock_data)

        # Verify
        assert result.total_value == 100000.0
        assert result.cash == 50000.0
        assert "AAPL" in result.positions
        assert "AAPL" in result.prices
        assert result.prices["AAPL"] == 152.0
