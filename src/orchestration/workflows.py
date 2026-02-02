"""Daily Trading Workflows - Orchestrates paper trading operations.

This module implements the three main daily workflows:
1. Market Open (9:30 AM): Health checks and initialization
2. Rebalancing (3:45 PM): Full trading pipeline execution
3. Market Close (4:05 PM): Confirmation and reporting

Workflow Chain:
Data Fetch → Signal Generation → Portfolio Allocation → Risk Validation → Order Execution
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from src.data.providers.alpaca_provider import AlpacaProvider
from src.execution.alpaca_executor import AlpacaExecutor
from src.portfolio.base import Order, PortfolioState
from src.portfolio.heuristic_allocator import HeuristicAllocator
from src.risk.basic_risk_manager import BasicRiskManager
from src.strategy.base import Strategy
from src.utils.alpaca_client import AlpacaClient
from src.utils.exceptions import (
    BrokerConnectionError,
    CircuitBreakerError,
    ExecutionError,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class WorkflowConfig:
    """Configuration for daily workflows.

    Attributes:
        symbols: List of symbols to trade
        strategy: Trading strategy instance
        initial_capital: Starting capital (for first run)
        min_signal_threshold: Minimum signal strength
        max_positions: Maximum number of positions
        max_position_size: Maximum weight per position
        cash_buffer: Cash reserve percentage
    """

    symbols: List[str]
    strategy: Strategy
    initial_capital: float = 100000.0
    min_signal_threshold: float = 0.3
    max_positions: int = 10
    max_position_size: float = 0.25
    cash_buffer: float = 0.05


class DailyWorkflow:
    """Orchestrates daily paper trading workflows.

    Coordinates all trading layers for paper trading execution:
    - Data Layer: Fetch latest market data
    - Strategy Layer: Generate trading signals
    - Portfolio Layer: Calculate target allocations
    - Risk Layer: Validate and enforce risk rules
    - Execution Layer: Submit orders to broker

    Example:
        >>> client = AlpacaClient.from_env()
        >>> workflow = DailyWorkflow(client, config)
        >>> workflow.market_open_workflow()  # 9:30 AM
        >>> workflow.rebalancing_workflow()  # 3:45 PM
        >>> workflow.market_close_workflow()  # 4:05 PM
    """

    def __init__(self, alpaca_client: AlpacaClient, config: WorkflowConfig):
        """Initialize daily workflow orchestrator.

        Args:
            alpaca_client: Alpaca API client
            config: Workflow configuration
        """
        self.config = config

        # Initialize components
        self.data_provider = AlpacaProvider(alpaca_client)
        self.executor = AlpacaExecutor(alpaca_client)
        self.portfolio_manager = HeuristicAllocator(
            {
                "min_signal_threshold": config.min_signal_threshold,
                "max_positions": config.max_positions,
                "max_position_size": config.max_position_size,
                "cash_buffer": config.cash_buffer,
            }
        )
        self.risk_manager = BasicRiskManager()
        self.strategy = config.strategy

        logger.info("DailyWorkflow initialized with %d symbols", len(config.symbols))

    def market_open_workflow(self) -> Dict[str, any]:
        """Market Open Workflow (9:30 AM ET).

        Performs health checks and initialization:
        - Check API connection
        - Verify account status
        - Log account information

        Returns:
            Dict with workflow results

        Raises:
            BrokerConnectionError: If health checks fail
        """
        logger.info("=" * 60)
        logger.info("MARKET OPEN WORKFLOW - %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("=" * 60)

        try:
            # 1. Check API connection
            logger.info("Step 1/3: Checking API connection...")
            account_info = self.executor.get_account_info()

            # 2. Verify account status
            logger.info("Step 2/3: Verifying account status...")
            logger.info(
                "  Cash: $%.2f", account_info.cash
            )
            logger.info(
                "  Portfolio Value: $%.2f", account_info.portfolio_value
            )
            logger.info(
                "  Buying Power: $%.2f", account_info.buying_power
            )

            # 3. Get current positions
            logger.info("Step 3/3: Fetching current positions...")
            positions = self.executor.get_positions()
            logger.info(
                "  Current Positions: %d", len(positions)
            )

            for symbol, position in positions.items():
                logger.info(
                    "    %s: %d shares @ $%.2f (P&L: $%.2f)",
                    symbol,
                    position.shares,
                    position.avg_cost,
                    position.unrealized_pnl,
                )

            logger.info("✓ Market open workflow completed successfully")

            return {
                "status": "success",
                "account_info": account_info,
                "positions": positions,
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error("✗ Market open workflow failed: %s", e, exc_info=True)
            raise BrokerConnectionError(f"Market open health check failed: {e}") from e

    def rebalancing_workflow(self) -> Dict[str, any]:
        """Rebalancing Workflow (3:45 PM ET).

        Executes the full trading pipeline:
        1. Fetch latest daily data
        2. Generate trading signals
        3. Calculate target allocations
        4. Validate risk rules
        5. Submit orders
        6. Log results

        Returns:
            Dict with workflow results including orders submitted

        Raises:
            ExecutionError: If workflow fails
        """
        logger.info("=" * 60)
        logger.info("REBALANCING WORKFLOW - %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("=" * 60)

        try:
            # 1. Fetch latest daily data
            logger.info("Step 1/6: Fetching latest market data...")
            latest_data = self._fetch_latest_data()
            logger.info(
                "  Fetched data for %d symbols", len(latest_data)
            )

            # 2. Generate trading signals
            logger.info("Step 2/6: Generating trading signals...")
            signals = self._generate_signals(latest_data)
            logger.info(
                "  Generated %d signals", len(signals)
            )

            # Log top signals
            sorted_signals = sorted(
                signals.items(), key=lambda x: abs(x[1]), reverse=True
            )
            for symbol, signal in sorted_signals[:5]:
                logger.info(
                    "    %s: %.3f", symbol, signal
                )

            # 3. Calculate target allocations
            logger.info("Step 3/6: Calculating target allocations...")
            portfolio_state = self._build_portfolio_state(latest_data)
            allocation_result = self.portfolio_manager.allocate(signals, portfolio_state)

            logger.info(
                "  Target weights calculated for %d positions",
                len(allocation_result.target_weights) - 1,  # -1 for Cash
            )

            # Log target allocations
            for symbol, weight in allocation_result.target_weights.items():
                if symbol != "Cash" and weight > 0:
                    logger.info(
                        "    %s: %.2f%%", symbol, weight * 100
                    )

            # 4. Validate risk rules
            logger.info("Step 4/6: Validating risk rules...")
            validated_orders = self.risk_manager.validate_orders(
                allocation_result.orders, portfolio_state
            )

            logger.info(
                "  Risk validation: %d orders approved, %d rejected",
                len(validated_orders),
                len(allocation_result.orders) - len(validated_orders),
            )

            # 5. Submit orders
            logger.info("Step 5/6: Submitting orders to Alpaca...")
            if validated_orders:
                execution_results = self.executor.submit_orders(validated_orders)

                # Log execution results
                for result in execution_results:
                    logger.info(
                        "    Order %s: %s %d %s @ est. $%.2f - %s",
                        result.order_id,
                        result.order.action.value,
                        result.order.shares,
                        result.order.symbol,
                        result.order.estimated_value / result.order.shares
                        if result.order.shares > 0
                        else 0,
                        result.status.value,
                    )
            else:
                logger.info("  No orders to submit")
                execution_results = []

            # 6. Log summary
            logger.info("Step 6/6: Workflow summary...")
            logger.info(
                "  Total orders submitted: %d", len(execution_results)
            )

            successful_orders = [
                r for r in execution_results if r.status.value != "rejected"
            ]
            rejected_orders = [
                r for r in execution_results if r.status.value == "rejected"
            ]

            logger.info(
                "  Successful: %d, Rejected: %d",
                len(successful_orders),
                len(rejected_orders),
            )

            logger.info("✓ Rebalancing workflow completed successfully")

            return {
                "status": "success",
                "signals": signals,
                "target_weights": allocation_result.target_weights,
                "orders_submitted": len(execution_results),
                "orders_successful": len(successful_orders),
                "orders_rejected": len(rejected_orders),
                "execution_results": execution_results,
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error("✗ Rebalancing workflow failed: %s", e, exc_info=True)
            raise ExecutionError(f"Rebalancing workflow failed: {e}") from e

    def market_close_workflow(self) -> Dict[str, any]:
        """Market Close Workflow (4:05 PM ET).

        Performs end-of-day confirmation and reporting:
        1. Confirm all orders filled
        2. Update position tracking
        3. Generate daily performance report

        Returns:
            Dict with workflow results including performance metrics

        Raises:
            ExecutionError: If workflow fails
        """
        logger.info("=" * 60)
        logger.info("MARKET CLOSE WORKFLOW - %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("=" * 60)

        try:
            # 1. Confirm all orders filled
            logger.info("Step 1/3: Confirming order fills...")
            open_orders = self.executor.get_open_orders()

            if open_orders:
                logger.warning(
                    "  WARNING: %d orders still open at market close",
                    len(open_orders),
                )
                for order in open_orders:
                    logger.warning(
                        "    Order %s: %s %s - %s",
                        order.order_id,
                        order.order.action.value,
                        order.order.symbol,
                        order.status.value,
                    )
            else:
                logger.info("  All orders filled or cancelled")

            # 2. Update position tracking
            logger.info("Step 2/3: Updating position tracking...")
            positions = self.executor.get_positions()
            account_info = self.executor.get_account_info()

            logger.info(
                "  Current Positions: %d", len(positions)
            )
            logger.info(
                "  Portfolio Value: $%.2f", account_info.portfolio_value
            )

            # Calculate total P&L
            total_pnl = sum(pos.unrealized_pnl for pos in positions.values())
            logger.info(
                "  Total Unrealized P&L: $%.2f", total_pnl
            )

            # 3. Generate daily performance report
            logger.info("Step 3/3: Generating performance report...")

            # Calculate daily metrics
            positions_value = account_info.positions_value
            cash = account_info.cash
            total_value = account_info.portfolio_value

            logger.info("  Daily Performance Report:")
            logger.info("    Cash: $%.2f (%.1f%%)", cash, (cash / total_value * 100))
            logger.info(
                "    Positions: $%.2f (%.1f%%)",
                positions_value,
                (positions_value / total_value * 100),
            )
            logger.info(
                "    Total Value: $%.2f", total_value
            )

            # Log individual positions
            if positions:
                logger.info("  Position Details:")
                for symbol, position in positions.items():
                    pnl_pct = (
                        (position.unrealized_pnl / position.cost_basis * 100)
                        if position.cost_basis > 0
                        else 0
                    )
                    logger.info(
                        "    %s: %d shares @ $%.2f, Value: $%.2f, P&L: $%.2f (%.2f%%)",
                        symbol,
                        position.shares,
                        position.avg_cost,
                        position.market_value,
                        position.unrealized_pnl,
                        pnl_pct,
                    )

            logger.info("✓ Market close workflow completed successfully")

            return {
                "status": "success",
                "open_orders": len(open_orders),
                "positions_count": len(positions),
                "portfolio_value": total_value,
                "positions_value": positions_value,
                "cash": cash,
                "total_unrealized_pnl": total_pnl,
                "positions": positions,
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error("✗ Market close workflow failed: %s", e, exc_info=True)
            raise ExecutionError(f"Market close workflow failed: {e}") from e

    def _fetch_latest_data(self) -> Dict[str, any]:
        """Fetch latest market data for all symbols.

        Returns:
            Dict mapping symbol to latest data

        Raises:
            DataProviderError: If data fetching fails
        """
        from datetime import timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)  # 1 year of data for indicators

        latest_data = {}
        for symbol in self.config.symbols:
            try:
                df = self.data_provider.get_historical_bars(symbol, start_date, end_date)
                latest_data[symbol] = df
            except Exception as e:
                logger.warning("Failed to fetch data for %s: %s", symbol, e)

        return latest_data

    def _generate_signals(self, data: Dict[str, any]) -> Dict[str, float]:
        """Generate trading signals for all symbols.

        Supports both single Strategy and MultiStrategyEnsemble.

        Args:
            data: Dict mapping symbol to price data

        Returns:
            Dict mapping symbol to signal strength [-1.0, 1.0]
        """
        from src.strategy.ensemble import MultiStrategyEnsemble

        # Check if strategy is an ensemble
        if isinstance(self.strategy, MultiStrategyEnsemble):
            # Use ensemble's batch signal generation
            signals = self.strategy.get_signals_for_all(self.config.symbols, data)
        else:
            # Single strategy - generate signals and extract latest
            signals = {}
            for symbol, df in data.items():
                try:
                    # Generate full time series
                    signal_series = self.strategy.generate_signals(df)
                    # Extract latest signal
                    if not signal_series.empty:
                        signals[symbol] = float(signal_series.iloc[-1])
                    else:
                        logger.warning("Empty signals for %s, using 0.0", symbol)
                        signals[symbol] = 0.0
                except Exception as e:
                    logger.warning("Failed to generate signal for %s: %s", symbol, e)
                    signals[symbol] = 0.0

        return signals

    def _build_portfolio_state(self, data: Dict[str, any]) -> PortfolioState:
        """Build current portfolio state.

        Args:
            data: Dict mapping symbol to price data

        Returns:
            PortfolioState with current positions and prices
        """
        # Get current positions from broker
        positions_data = self.executor.get_positions()
        account_info = self.executor.get_account_info()

        # Convert positions to dollar values
        positions = {
            symbol: pos.market_value for symbol, pos in positions_data.items()
        }

        # Get latest prices
        prices = {}
        for symbol, df in data.items():
            if not df.empty:
                prices[symbol] = float(df["close"].iloc[-1])

        return PortfolioState(
            positions=positions,
            total_value=account_info.portfolio_value,
            cash=account_info.cash,
            prices=prices,
            timestamp=datetime.now(),
        )
