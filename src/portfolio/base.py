"""Abstract base class for portfolio management.

This module defines the contract for portfolio allocation and rebalancing.
The Portfolio Management Layer sits between Strategy Layer and Risk Management Layer.

Responsibilities:
- Signal aggregation: Collect signals for all securities
- Weight allocation: Determine target portfolio weights
- Cash management: Maintain appropriate cash buffer
- Rebalancing logic: Calculate position changes
- Order generation: Create executable orders
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import pandas as pd


class OrderAction(Enum):
    """Order action types."""

    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """Represents a trading order to be executed.

    Attributes:
        action: BUY or SELL
        symbol: Stock ticker symbol
        shares: Number of shares to trade
        estimated_value: Estimated dollar value of the order
        timestamp: When the order was generated
        reason: Why this order was generated (for logging/debugging)
    """

    action: OrderAction
    symbol: str
    shares: int
    estimated_value: float
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""

    def __post_init__(self):
        """Validate order fields."""
        if self.shares <= 0:
            raise ValueError(f"shares must be positive, got {self.shares}")
        if self.estimated_value < 0:
            raise ValueError(
                f"estimated_value must be non-negative, got {self.estimated_value}"
            )


@dataclass
class PortfolioState:
    """Represents current portfolio state.

    Attributes:
        positions: Current holdings {symbol: dollar_value}
        total_value: Total portfolio value including cash
        cash: Cash available
        prices: Latest prices {symbol: price}
        timestamp: When this state was captured
    """

    positions: Dict[str, float]
    total_value: float
    cash: float
    prices: Dict[str, float]
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate portfolio state."""
        if self.total_value < 0:
            raise ValueError(
                f"total_value must be non-negative, got {self.total_value}"
            )
        if self.cash < 0:
            raise ValueError(f"cash must be non-negative, got {self.cash}")


@dataclass
class AllocationResult:
    """Result of portfolio allocation calculation.

    Attributes:
        target_weights: Target allocation {symbol: weight} where weights sum to 1.0
        orders: List of orders to achieve target allocation
        metrics: Additional metrics (turnover, position count, etc.)
    """

    target_weights: Dict[str, float]
    orders: List[Order]
    metrics: Dict[str, float] = field(default_factory=dict)


class PortfolioManager(ABC):
    """Abstract interface for portfolio allocation.

    The Portfolio Manager translates trading signals into target portfolio weights
    and generates orders to rebalance from current to target positions.

    Design Principles:
    - Only invests in signals above threshold (filter weak signals)
    - Limits maximum number of positions
    - Allocates proportional to signal strength
    - Enforces single-position size limit
    - Maintains cash buffer

    Example:
        >>> manager = HeuristicAllocator(config)
        >>> signals = {'AAPL': 0.8, 'MSFT': 0.5, 'GOOGL': 0.2}
        >>> portfolio = PortfolioState(
        ...     positions={'MSFT': 10000},
        ...     total_value=100000,
        ...     cash=90000,
        ...     prices={'AAPL': 150, 'MSFT': 350, 'GOOGL': 140}
        ... )
        >>> result = manager.allocate(signals, portfolio)
        >>> print(result.target_weights)
        {'AAPL': 0.45, 'MSFT': 0.28, 'Cash': 0.27}
    """

    @abstractmethod
    def allocate(
        self,
        signals: Dict[str, float],
        portfolio: PortfolioState,
    ) -> AllocationResult:
        """Calculate target allocation and generate rebalancing orders.

        This is the main entry point for portfolio allocation. It takes
        trading signals and current portfolio state, returns target weights
        and orders to achieve them.

        Args:
            signals: Trading signals from Strategy Layer
                    {symbol: signal_value} where signal_value in [-1.0, 1.0]
                    Positive = buy, negative = sell, 0 = neutral
            portfolio: Current portfolio state (positions, cash, prices)

        Returns:
            AllocationResult containing:
            - target_weights: Target allocation percentages
            - orders: List of orders to execute
            - metrics: Performance metrics

        Example:
            >>> signals = {'AAPL': 0.8, 'MSFT': -0.5}
            >>> result = manager.allocate(signals, portfolio)
            >>> for order in result.orders:
            ...     print(f"{order.action.value} {order.shares} {order.symbol}")
        """
        pass

    @abstractmethod
    def calculate_target_weights(
        self,
        signals: Dict[str, float],
    ) -> Dict[str, float]:
        """Convert signals to target portfolio weights.

        This method contains the core allocation logic. Subclasses implement
        different algorithms (heuristic, risk parity, optimization).

        Args:
            signals: Trading signals {symbol: signal_value}

        Returns:
            Target weights {symbol: weight} where weights sum to 1.0
            Always includes 'Cash' key for cash allocation

        Example:
            >>> signals = {'AAPL': 0.8, 'MSFT': 0.5}
            >>> weights = manager.calculate_target_weights(signals)
            >>> print(weights)
            {'AAPL': 0.48, 'MSFT': 0.30, 'Cash': 0.22}
        """
        pass

    @abstractmethod
    def generate_orders(
        self,
        current_positions: Dict[str, float],
        target_weights: Dict[str, float],
        total_value: float,
        prices: Dict[str, float],
    ) -> List[Order]:
        """Generate orders to move from current to target positions.

        Calculates the difference between current holdings and target allocation,
        converts dollar differences to share quantities, and creates order objects.

        Args:
            current_positions: Current holdings {symbol: dollar_value}
            target_weights: Target allocation {symbol: weight}
            total_value: Total portfolio value
            prices: Current prices {symbol: price}

        Returns:
            List of Order objects to execute

        Example:
            >>> orders = manager.generate_orders(
            ...     current_positions={'MSFT': 10000},
            ...     target_weights={'AAPL': 0.25, 'MSFT': 0.15, 'Cash': 0.60},
            ...     total_value=100000,
            ...     prices={'AAPL': 150, 'MSFT': 350}
            ... )
        """
        pass

    def should_rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        threshold: float = 0.05,
    ) -> bool:
        """Check if rebalancing is needed based on drift threshold.

        Only rebalance if any position has drifted more than threshold
        from its target weight. This prevents excessive trading from
        small fluctuations.

        Args:
            current_weights: Current allocation {symbol: weight}
            target_weights: Target allocation {symbol: weight}
            threshold: Maximum allowed drift before rebalancing (default 5%)

        Returns:
            True if any position drifted more than threshold

        Example:
            >>> current = {'AAPL': 0.28, 'MSFT': 0.22, 'Cash': 0.50}
            >>> target = {'AAPL': 0.25, 'MSFT': 0.25, 'Cash': 0.50}
            >>> manager.should_rebalance(current, target, threshold=0.05)
            False  # Max drift is 3%, below 5% threshold
        """
        all_symbols = set(current_weights.keys()) | set(target_weights.keys())

        for symbol in all_symbols:
            current = current_weights.get(symbol, 0.0)
            target = target_weights.get(symbol, 0.0)
            drift = abs(current - target)
            if drift > threshold:
                return True

        return False

    def calculate_current_weights(
        self,
        portfolio: PortfolioState,
    ) -> Dict[str, float]:
        """Calculate current portfolio weights from positions.

        Args:
            portfolio: Current portfolio state

        Returns:
            Current weights {symbol: weight} including 'Cash'
        """
        if portfolio.total_value <= 0:
            return {"Cash": 1.0}

        weights = {}
        for symbol, value in portfolio.positions.items():
            weights[symbol] = value / portfolio.total_value

        weights["Cash"] = portfolio.cash / portfolio.total_value

        return weights
