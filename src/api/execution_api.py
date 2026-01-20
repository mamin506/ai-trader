"""User-friendly API for Execution Layer.

This module provides a simplified interface for executing trades and
managing positions during backtesting.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.execution.backtest_executor import BacktestExecutor
from src.execution.base import (
    AccountInfo,
    ExecutionOrder,
    Fill,
    OrderStatus,
    Position,
)
from src.portfolio.base import Order, OrderAction
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ExecutionAPI:
    """User-friendly API for trade execution.

    This API provides a high-level interface for executing trades and
    tracking positions, designed for ease of use in backtesting scenarios.

    Example:
        >>> api = ExecutionAPI(initial_cash=100000)
        >>> api.set_prices({'AAPL': 150.0, 'MSFT': 350.0})
        >>>
        >>> # Execute a buy order
        >>> result = api.buy('AAPL', 100)
        >>> print(f"Bought {result['filled_qty']} shares at ${result['filled_price']:.2f}")
        >>>
        >>> # Check portfolio
        >>> print(api.get_portfolio_summary())
    """

    def __init__(
        self,
        initial_cash: float = 100000.0,
        slippage_pct: float = 0.001,
        commission_per_share: float = 0.0,
        commission_min: float = 0.0,
    ):
        """Initialize ExecutionAPI.

        Args:
            initial_cash: Starting cash balance (default $100,000)
            slippage_pct: Slippage as percentage of price (default 0.1%)
            commission_per_share: Commission per share (default $0)
            commission_min: Minimum commission per order (default $0)
        """
        config = {
            "initial_cash": initial_cash,
            "slippage_pct": slippage_pct,
            "commission_per_share": commission_per_share,
            "commission_min": commission_min,
        }
        self._executor = BacktestExecutor(config)
        logger.info(
            "ExecutionAPI initialized with $%.2f initial cash",
            initial_cash,
        )

    def set_prices(self, prices: Dict[str, float]) -> None:
        """Set current market prices.

        Args:
            prices: Dict mapping symbol to price

        Example:
            >>> api.set_prices({'AAPL': 150.0, 'MSFT': 350.0, 'GOOGL': 140.0})
        """
        self._executor.set_prices(prices)

    def set_timestamp(self, timestamp: datetime) -> None:
        """Set current simulation timestamp.

        Args:
            timestamp: Current simulation time
        """
        self._executor.set_timestamp(timestamp)

    def buy(
        self,
        symbol: str,
        shares: int,
        estimated_value: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute a buy order.

        Args:
            symbol: Ticker symbol to buy
            shares: Number of shares to buy
            estimated_value: Estimated order value (auto-calculated if not provided)

        Returns:
            Dict with order execution results

        Example:
            >>> result = api.buy('AAPL', 100)
            >>> if result['status'] == 'filled':
            ...     print(f"Bought at ${result['filled_price']:.2f}")
        """
        if estimated_value is None:
            price = self._executor._current_prices.get(symbol, 0)
            estimated_value = shares * price

        order = Order(
            action=OrderAction.BUY,
            symbol=symbol,
            shares=shares,
            estimated_value=estimated_value,
        )

        results = self._executor.submit_orders([order])
        return self._format_order_result(results[0])

    def sell(
        self,
        symbol: str,
        shares: int,
        estimated_value: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute a sell order.

        Args:
            symbol: Ticker symbol to sell
            shares: Number of shares to sell
            estimated_value: Estimated order value (auto-calculated if not provided)

        Returns:
            Dict with order execution results

        Example:
            >>> result = api.sell('AAPL', 50)
            >>> if result['status'] == 'filled':
            ...     print(f"Sold at ${result['filled_price']:.2f}")
        """
        if estimated_value is None:
            price = self._executor._current_prices.get(symbol, 0)
            estimated_value = shares * price

        order = Order(
            action=OrderAction.SELL,
            symbol=symbol,
            shares=shares,
            estimated_value=estimated_value,
        )

        results = self._executor.submit_orders([order])
        return self._format_order_result(results[0])

    def execute_orders(self, orders: List[Order]) -> List[Dict[str, Any]]:
        """Execute multiple orders.

        Args:
            orders: List of Order objects

        Returns:
            List of order execution results

        Example:
            >>> orders = [
            ...     Order(action=OrderAction.BUY, symbol='AAPL', shares=100, estimated_value=15000),
            ...     Order(action=OrderAction.BUY, symbol='MSFT', shares=50, estimated_value=17500),
            ... ]
            >>> results = api.execute_orders(orders)
        """
        results = self._executor.submit_orders(orders)
        return [self._format_order_result(r) for r in results]

    def _format_order_result(self, exec_order: ExecutionOrder) -> Dict[str, Any]:
        """Format ExecutionOrder to user-friendly dict."""
        return {
            "order_id": exec_order.order_id,
            "symbol": exec_order.order.symbol,
            "action": exec_order.order.action.value,
            "shares": exec_order.order.shares,
            "status": exec_order.status.value,
            "filled_qty": exec_order.filled_qty,
            "filled_price": exec_order.filled_avg_price,
            "commission": exec_order.commission,
            "rejected_reason": exec_order.rejected_reason or None,
        }

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for a specific symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            Position info dict or None if no position

        Example:
            >>> pos = api.get_position('AAPL')
            >>> if pos:
            ...     print(f"Holding {pos['shares']} shares, P&L: ${pos['unrealized_pnl']:.2f}")
        """
        position = self._executor.get_position(symbol)
        if position is None:
            return None
        return self._format_position(position)

    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all current positions.

        Returns:
            Dict mapping symbol to position info

        Example:
            >>> positions = api.get_all_positions()
            >>> for symbol, pos in positions.items():
            ...     print(f"{symbol}: {pos['shares']} shares")
        """
        positions = self._executor.get_positions()
        return {symbol: self._format_position(pos) for symbol, pos in positions.items()}

    def _format_position(self, position: Position) -> Dict[str, Any]:
        """Format Position to user-friendly dict."""
        return {
            "symbol": position.symbol,
            "shares": position.shares,
            "avg_cost": position.avg_cost,
            "market_value": position.market_value,
            "cost_basis": position.cost_basis,
            "unrealized_pnl": position.unrealized_pnl,
            "realized_pnl": position.realized_pnl,
        }

    def get_account_info(self) -> Dict[str, Any]:
        """Get account balance and status.

        Returns:
            Dict with account information

        Example:
            >>> account = api.get_account_info()
            >>> print(f"Cash: ${account['cash']:.2f}")
            >>> print(f"Portfolio Value: ${account['portfolio_value']:.2f}")
        """
        account = self._executor.get_account_info()
        return {
            "cash": account.cash,
            "portfolio_value": account.portfolio_value,
            "buying_power": account.buying_power,
            "positions_value": account.positions_value,
        }

    def get_fills(self) -> List[Dict[str, Any]]:
        """Get all fills (trade executions).

        Returns:
            List of fill information dicts

        Example:
            >>> fills = api.get_fills()
            >>> for fill in fills:
            ...     print(f"{fill['symbol']}: {fill['shares']} @ ${fill['price']:.2f}")
        """
        fills = self._executor.get_fills()
        return [self._format_fill(f) for f in fills]

    def _format_fill(self, fill: Fill) -> Dict[str, Any]:
        """Format Fill to user-friendly dict."""
        return {
            "order_id": fill.order_id,
            "symbol": fill.symbol,
            "shares": fill.shares,
            "price": fill.price,
            "value": fill.value,
            "commission": fill.commission,
            "timestamp": fill.timestamp.isoformat() if fill.timestamp else None,
        }

    def get_portfolio_summary(self) -> str:
        """Get formatted portfolio summary.

        Returns:
            Human-readable portfolio summary string

        Example:
            >>> print(api.get_portfolio_summary())
        """
        account = self._executor.get_account_info()
        positions = self._executor.get_positions()

        lines = [
            "=" * 60,
            "PORTFOLIO SUMMARY",
            "=" * 60,
            f"Cash:            ${account.cash:>15,.2f}",
            f"Positions Value: ${account.positions_value:>15,.2f}",
            f"Portfolio Value: ${account.portfolio_value:>15,.2f}",
            "-" * 60,
        ]

        if positions:
            lines.append("POSITIONS:")
            lines.append(
                f"{'Symbol':<8} {'Shares':>8} {'Avg Cost':>10} {'Mkt Value':>12} {'P&L':>12}"
            )
            lines.append("-" * 60)

            for symbol, pos in sorted(positions.items()):
                lines.append(
                    f"{symbol:<8} {pos.shares:>8} ${pos.avg_cost:>9.2f} "
                    f"${pos.market_value:>11.2f} ${pos.unrealized_pnl:>11.2f}"
                )
        else:
            lines.append("No positions")

        lines.append("=" * 60)
        return "\n".join(lines)

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary.

        Returns:
            Dict with performance metrics

        Example:
            >>> perf = api.get_performance_summary()
            >>> print(f"Total Return: {perf['total_return_pct']:.2f}%")
        """
        return self._executor.get_performance_summary()

    def format_performance_summary(self) -> str:
        """Get formatted performance summary.

        Returns:
            Human-readable performance summary string
        """
        summary = self._executor.get_performance_summary()

        return "\n".join(
            [
                "=" * 60,
                "PERFORMANCE SUMMARY",
                "=" * 60,
                f"Initial Cash:    ${summary['initial_cash']:>15,.2f}",
                f"Final Value:     ${summary['final_value']:>15,.2f}",
                f"Total Return:    {summary['total_return_pct']:>15.2f}%",
                "-" * 60,
                f"Cash:            ${summary['cash']:>15,.2f}",
                f"Positions Value: ${summary['positions_value']:>15,.2f}",
                f"Total Commission:${summary['total_commission']:>15,.2f}",
                "-" * 60,
                f"Number of Trades: {summary['num_trades']:>14}",
                f"  - Buys:         {summary['num_buys']:>14}",
                f"  - Sells:        {summary['num_sells']:>14}",
                f"Open Positions:   {summary['num_positions']:>14}",
                "=" * 60,
            ]
        )

    def reset(self) -> None:
        """Reset executor to initial state.

        Example:
            >>> api.reset()
            >>> # Start fresh backtesting run
        """
        self._executor.reset()
        logger.info("ExecutionAPI reset to initial state")

    @property
    def cash(self) -> float:
        """Get current cash balance."""
        return self._executor.get_account_info().cash

    @property
    def portfolio_value(self) -> float:
        """Get current portfolio value."""
        return self._executor.get_account_info().portfolio_value
