"""Backtesting executor for historical simulation.

This module implements order execution against historical data for
strategy validation. Orders are filled instantly at simulated prices
with configurable slippage and commission models.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from src.execution.base import (
    AccountInfo,
    ExecutionOrder,
    Fill,
    OrderExecutor,
    OrderStatus,
    OrderType,
    Position,
)
from src.portfolio.base import Order, OrderAction
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BacktestExecutor(OrderExecutor):
    """Backtesting executor for historical simulation.

    Simulates order execution against historical prices with configurable
    slippage and commission models. All orders are filled instantly.

    Configuration:
        initial_cash: Starting cash balance (default $100,000)
        slippage_pct: Slippage as percentage of price (default 0.1%)
        commission_per_share: Commission per share (default $0)
        commission_min: Minimum commission per order (default $0)

    Example:
        >>> config = {
        ...     'initial_cash': 100000.0,
        ...     'slippage_pct': 0.001,
        ...     'commission_per_share': 0.0
        ... }
        >>> executor = BacktestExecutor(config)
        >>> executor.set_prices({'AAPL': 150.0, 'MSFT': 350.0})
        >>> orders = [Order(action=OrderAction.BUY, symbol='AAPL', shares=100, ...)]
        >>> results = executor.submit_orders(orders)
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize backtest executor.

        Args:
            config: Configuration dictionary
        """
        config = config or {}

        self.initial_cash = config.get("initial_cash", 100000.0)
        self.slippage_pct = config.get("slippage_pct", 0.001)  # 0.1%
        self.commission_per_share = config.get("commission_per_share", 0.0)
        self.commission_min = config.get("commission_min", 0.0)

        # State
        self._cash = self.initial_cash
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, ExecutionOrder] = {}
        self._fills: List[Fill] = []
        self._current_prices: Dict[str, float] = {}
        self._current_time: datetime = datetime.now()

        self._validate_config()

        logger.debug(
            "BacktestExecutor initialized: cash=$%.2f, slippage=%.2f%%, commission=$%.4f/share",
            self.initial_cash,
            self.slippage_pct * 100,
            self.commission_per_share,
        )

    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        if self.initial_cash <= 0:
            raise ValueError(f"initial_cash must be positive, got {self.initial_cash}")
        if self.slippage_pct < 0:
            raise ValueError(f"slippage_pct must be non-negative, got {self.slippage_pct}")
        if self.commission_per_share < 0:
            raise ValueError(
                f"commission_per_share must be non-negative, got {self.commission_per_share}"
            )

    def set_prices(self, prices: Dict[str, float]) -> None:
        """Set current market prices for simulation.

        Args:
            prices: Dict mapping symbol to price
        """
        self._current_prices = prices.copy()

    def set_timestamp(self, timestamp: datetime) -> None:
        """Set current simulation timestamp.

        Args:
            timestamp: Current simulation time
        """
        self._current_time = timestamp

    def submit_orders(self, orders: List[Order]) -> List[ExecutionOrder]:
        """Submit orders for execution.

        In backtesting mode, orders are filled immediately at current prices
        with slippage applied.

        Args:
            orders: List of Order objects

        Returns:
            List of ExecutionOrder objects with fill status
        """
        results = []

        for order in orders:
            exec_order = self._create_execution_order(order)

            # Validate order
            if not self._validate_order(exec_order):
                results.append(exec_order)
                continue

            # Execute order
            self._execute_order(exec_order)
            results.append(exec_order)

        return results

    def _create_execution_order(self, order: Order) -> ExecutionOrder:
        """Create ExecutionOrder from Order."""
        order_id = str(uuid.uuid4())[:8]
        return ExecutionOrder(
            order_id=order_id,
            order=order,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
            submitted_at=self._current_time,
        )

    def _validate_order(self, exec_order: ExecutionOrder) -> bool:
        """Validate order before execution.

        Returns:
            True if valid, False otherwise (sets rejected status)
        """
        order = exec_order.order
        symbol = order.symbol

        # Check if price is available
        if symbol not in self._current_prices:
            exec_order.status = OrderStatus.REJECTED
            exec_order.rejected_reason = f"No price available for {symbol}"
            logger.warning("Order rejected: %s", exec_order.rejected_reason)
            return False

        price = self._current_prices[symbol]

        # Check buying power for buy orders
        if order.action == OrderAction.BUY:
            cost = self._calculate_buy_cost(order.shares, price)
            if cost > self._cash:
                exec_order.status = OrderStatus.REJECTED
                exec_order.rejected_reason = (
                    f"Insufficient funds: need ${cost:.2f}, have ${self._cash:.2f}"
                )
                logger.warning("Order rejected: %s", exec_order.rejected_reason)
                return False

        # Check position for sell orders
        if order.action == OrderAction.SELL:
            position = self._positions.get(symbol)
            if position is None or position.shares < order.shares:
                current_shares = position.shares if position else 0
                exec_order.status = OrderStatus.REJECTED
                exec_order.rejected_reason = (
                    f"Insufficient shares: need {order.shares}, have {current_shares}"
                )
                logger.warning("Order rejected: %s", exec_order.rejected_reason)
                return False

        return True

    def _execute_order(self, exec_order: ExecutionOrder) -> None:
        """Execute order and update positions."""
        order = exec_order.order
        symbol = order.symbol
        base_price = self._current_prices[symbol]

        # Apply slippage
        if order.action == OrderAction.BUY:
            # Buy at slightly higher price (unfavorable)
            fill_price = base_price * (1 + self.slippage_pct)
        else:
            # Sell at slightly lower price (unfavorable)
            fill_price = base_price * (1 - self.slippage_pct)

        # Calculate commission
        commission = self._calculate_commission(order.shares)

        # Create fill
        fill = Fill(
            order_id=exec_order.order_id,
            symbol=symbol,
            shares=order.shares,
            price=fill_price,
            commission=commission,
            timestamp=self._current_time,
        )
        self._fills.append(fill)

        # Update order status
        exec_order.status = OrderStatus.FILLED
        exec_order.filled_qty = order.shares
        exec_order.filled_avg_price = fill_price
        exec_order.commission = commission
        exec_order.filled_at = self._current_time

        # Update cash and positions
        if order.action == OrderAction.BUY:
            total_cost = fill.value + commission
            self._cash -= total_cost
            self._update_position_buy(symbol, order.shares, fill_price)
            logger.info(
                "BUY %d %s @ $%.2f (cost: $%.2f, commission: $%.2f)",
                order.shares,
                symbol,
                fill_price,
                total_cost,
                commission,
            )
        else:
            total_proceeds = fill.value - commission
            self._cash += total_proceeds
            self._update_position_sell(symbol, order.shares, fill_price)
            logger.info(
                "SELL %d %s @ $%.2f (proceeds: $%.2f, commission: $%.2f)",
                order.shares,
                symbol,
                fill_price,
                total_proceeds,
                commission,
            )

        # Store order
        self._orders[exec_order.order_id] = exec_order

    def _calculate_buy_cost(self, shares: int, price: float) -> float:
        """Calculate total cost to buy shares including slippage and commission."""
        fill_price = price * (1 + self.slippage_pct)
        commission = self._calculate_commission(shares)
        return shares * fill_price + commission

    def _calculate_commission(self, shares: int) -> float:
        """Calculate commission for an order."""
        commission = shares * self.commission_per_share
        return max(commission, self.commission_min)

    def _update_position_buy(self, symbol: str, shares: int, price: float) -> None:
        """Update position after buy."""
        if symbol in self._positions:
            position = self._positions[symbol]
            # Calculate new average cost
            total_shares = position.shares + shares
            total_cost = position.shares * position.avg_cost + shares * price
            position.avg_cost = total_cost / total_shares
            position.shares = total_shares
        else:
            self._positions[symbol] = Position(
                symbol=symbol,
                shares=shares,
                avg_cost=price,
            )

    def _update_position_sell(self, symbol: str, shares: int, price: float) -> None:
        """Update position after sell."""
        position = self._positions[symbol]

        # Calculate realized P&L
        cost_basis = shares * position.avg_cost
        proceeds = shares * price
        realized_pnl = proceeds - cost_basis
        position.realized_pnl += realized_pnl

        # Update shares
        position.shares -= shares

        # Remove position if fully closed
        if position.shares == 0:
            del self._positions[symbol]

    def get_order_status(self, order_ids: List[str]) -> List[ExecutionOrder]:
        """Get status of orders by ID."""
        return [self._orders[oid] for oid in order_ids if oid in self._orders]

    def cancel_orders(self, order_ids: List[str]) -> Dict[str, bool]:
        """Cancel orders (not applicable in backtesting - all orders fill instantly)."""
        # In backtesting, orders fill instantly, so cancellation is not meaningful
        return {oid: False for oid in order_ids}

    def get_positions(self) -> Dict[str, Position]:
        """Get current positions with updated market values."""
        # Update market values and unrealized P&L
        for symbol, position in self._positions.items():
            if symbol in self._current_prices:
                current_price = self._current_prices[symbol]
                position.market_value = position.shares * current_price
                position.unrealized_pnl = position.market_value - position.cost_basis

        return self._positions.copy()

    def get_account_info(self) -> AccountInfo:
        """Get account balance and status."""
        positions_value = sum(
            pos.shares * self._current_prices.get(pos.symbol, pos.avg_cost)
            for pos in self._positions.values()
        )

        return AccountInfo(
            cash=self._cash,
            portfolio_value=self._cash + positions_value,
            buying_power=self._cash,  # Simple: buying power = cash
            positions_value=positions_value,
            timestamp=self._current_time,
        )

    def get_fills(self) -> List[Fill]:
        """Get all fills."""
        return self._fills.copy()

    def get_all_orders(self) -> List[ExecutionOrder]:
        """Get all orders."""
        return list(self._orders.values())

    def reset(self) -> None:
        """Reset executor to initial state."""
        self._cash = self.initial_cash
        self._positions.clear()
        self._orders.clear()
        self._fills.clear()
        self._current_prices.clear()
        self._current_time = datetime.now()

        logger.info("BacktestExecutor reset to initial state")

    def get_performance_summary(self) -> Dict:
        """Get summary of backtest performance.

        Returns:
            Dict with performance metrics
        """
        account = self.get_account_info()

        total_return = (account.portfolio_value - self.initial_cash) / self.initial_cash
        total_commission = sum(f.commission for f in self._fills)

        # Count trades
        buy_fills = [f for f in self._fills if self._orders.get(f.order_id) and
                     self._orders[f.order_id].order.action == OrderAction.BUY]
        sell_fills = [f for f in self._fills if self._orders.get(f.order_id) and
                      self._orders[f.order_id].order.action == OrderAction.SELL]

        return {
            "initial_cash": self.initial_cash,
            "final_value": account.portfolio_value,
            "cash": account.cash,
            "positions_value": account.positions_value,
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "total_commission": total_commission,
            "num_trades": len(self._fills),
            "num_buys": len(buy_fills),
            "num_sells": len(sell_fills),
            "num_positions": len(self._positions),
        }
