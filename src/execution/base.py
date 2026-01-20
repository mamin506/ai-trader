"""Abstract base class for order execution.

This module defines the contract for order execution across different modes:
- Backtesting: Historical simulation
- Paper trading: Real-time simulation (Phase 2)
- Live trading: Production execution (Phase 3)

Key Principle: Abstract the execution mechanism to support multiple modes
through a unified interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from src.portfolio.base import Order


class OrderStatus(Enum):
    """Order lifecycle states."""

    PENDING = "pending"  # Created, not yet submitted
    SUBMITTED = "submitted"  # Sent to broker/executor
    PARTIALLY_FILLED = "partially_filled"  # Partial execution
    FILLED = "filled"  # Fully executed
    REJECTED = "rejected"  # Broker rejected
    CANCELLED = "cancelled"  # User/system cancellation
    EXPIRED = "expired"  # Order expired (e.g., day order at market close)


class OrderType(Enum):
    """Order types supported by the system."""

    MARKET = "market"  # Execute at current market price
    LIMIT = "limit"  # Execute only at specified price or better
    STOP = "stop"  # Trigger market order when stop price reached
    STOP_LIMIT = "stop_limit"  # Trigger limit order when stop price reached


class TimeInForce(Enum):
    """Order duration/validity."""

    DAY = "day"  # Valid for current trading day only
    GTC = "gtc"  # Good-til-cancelled
    IOC = "ioc"  # Immediate-or-cancel
    FOK = "fok"  # Fill-or-kill


@dataclass
class ExecutionOrder:
    """Order with execution details.

    Extends the basic Order from Portfolio layer with execution-specific fields.

    Attributes:
        order_id: Unique identifier for this order
        order: Original Order from Portfolio layer
        order_type: Market, limit, stop, etc.
        limit_price: Price for limit orders
        stop_price: Trigger price for stop orders
        time_in_force: Order duration
        status: Current order status
        filled_qty: Number of shares filled
        filled_avg_price: Average fill price
        commission: Commission charged
        submitted_at: When order was submitted
        filled_at: When order was fully filled
        rejected_reason: Reason for rejection (if rejected)
    """

    order_id: str
    order: Order
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    filled_avg_price: float = 0.0
    commission: float = 0.0
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    rejected_reason: str = ""

    @property
    def is_complete(self) -> bool:
        """Check if order is in a terminal state."""
        return self.status in (
            OrderStatus.FILLED,
            OrderStatus.REJECTED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
        )

    @property
    def remaining_qty(self) -> int:
        """Calculate unfilled quantity."""
        return self.order.shares - self.filled_qty

    @property
    def fill_ratio(self) -> float:
        """Calculate fill percentage."""
        if self.order.shares == 0:
            return 0.0
        return self.filled_qty / self.order.shares


@dataclass
class Fill:
    """Represents a single fill (partial or complete execution).

    Attributes:
        order_id: ID of the order this fill belongs to
        symbol: Ticker symbol
        shares: Number of shares in this fill
        price: Execution price
        commission: Commission for this fill
        timestamp: When fill occurred
    """

    order_id: str
    symbol: str
    shares: int
    price: float
    commission: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def value(self) -> float:
        """Calculate total value of this fill."""
        return self.shares * self.price


@dataclass
class Position:
    """Current position in a security.

    Attributes:
        symbol: Ticker symbol
        shares: Number of shares held (positive = long, negative = short)
        avg_cost: Average cost per share
        market_value: Current market value
        unrealized_pnl: Unrealized profit/loss
        realized_pnl: Realized profit/loss from closed trades
    """

    symbol: str
    shares: int
    avg_cost: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    @property
    def cost_basis(self) -> float:
        """Calculate total cost basis."""
        return abs(self.shares) * self.avg_cost


@dataclass
class AccountInfo:
    """Account balance and status information.

    Attributes:
        cash: Available cash balance
        portfolio_value: Total portfolio value (cash + positions)
        buying_power: Available buying power
        positions_value: Total value of all positions
        timestamp: When this snapshot was taken
    """

    cash: float
    portfolio_value: float
    buying_power: float
    positions_value: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class OrderExecutor(ABC):
    """Abstract base class for order execution.

    All execution modes (backtest, paper, live) implement this interface.
    This allows the Portfolio and Risk layers to be execution-mode agnostic.

    Example:
        >>> executor = BacktestExecutor(config)
        >>> orders = [Order(action=OrderAction.BUY, symbol='AAPL', shares=100, ...)]
        >>> results = executor.submit_orders(orders)
        >>> for result in results:
        ...     print(f"{result.order_id}: {result.status.value}")
    """

    @abstractmethod
    def submit_orders(self, orders: List[Order]) -> List[ExecutionOrder]:
        """Submit a batch of orders for execution.

        Args:
            orders: List of Order objects from Portfolio Manager

        Returns:
            List of ExecutionOrder objects with execution status

        Note:
            For backtesting, orders are filled immediately.
            For live/paper trading, orders are submitted and status
            should be checked via get_order_status().
        """
        pass

    @abstractmethod
    def get_order_status(self, order_ids: List[str]) -> List[ExecutionOrder]:
        """Query status of submitted orders.

        Args:
            order_ids: List of order IDs to query

        Returns:
            List of ExecutionOrder objects with current status
        """
        pass

    @abstractmethod
    def cancel_orders(self, order_ids: List[str]) -> Dict[str, bool]:
        """Cancel pending orders.

        Args:
            order_ids: List of order IDs to cancel

        Returns:
            Dict mapping order_id to success (True) or failure (False)
        """
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """Get current positions.

        Returns:
            Dict mapping symbol to Position object
        """
        pass

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """Get account balance and status.

        Returns:
            AccountInfo with cash, portfolio value, etc.
        """
        pass

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            Position if held, None otherwise
        """
        positions = self.get_positions()
        return positions.get(symbol)

    def get_open_orders(self) -> List[ExecutionOrder]:
        """Get all orders that are not in a terminal state.

        Returns:
            List of open ExecutionOrder objects
        """
        # Default implementation - subclasses may override for efficiency
        return []
