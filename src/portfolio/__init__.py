"""Portfolio Management Layer.

This layer is responsible for translating trading signals into target portfolio
allocations and generating rebalancing orders.

Components:
- PortfolioManager: Abstract interface for portfolio allocation
- HeuristicAllocator: Phase 1 rule-based allocator
- Order: Trade order data structure
- PortfolioState: Current portfolio state representation
"""

from src.portfolio.base import (
    AllocationResult,
    Order,
    OrderAction,
    PortfolioManager,
    PortfolioState,
)
from src.portfolio.heuristic_allocator import HeuristicAllocator

__all__ = [
    "PortfolioManager",
    "HeuristicAllocator",
    "Order",
    "OrderAction",
    "PortfolioState",
    "AllocationResult",
]
