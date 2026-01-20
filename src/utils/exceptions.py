"""Custom exceptions for AI Trader.

This module defines the exception hierarchy for the application.
"""


class AITraderError(Exception):
    """Base exception for all AI Trader errors.

    All custom exceptions in the application should inherit from this class.
    """

    pass


class ConfigurationError(AITraderError):
    """Raised when configuration is invalid or missing.

    Examples:
        - Missing required configuration keys
        - Invalid configuration values
        - Configuration file not found
    """

    pass


class DataError(AITraderError):
    """Base exception for data layer errors.

    Parent class for all data-related exceptions.
    """

    pass


class DataProviderError(DataError):
    """Raised when data provider fails to fetch data.

    Examples:
        - API rate limit exceeded
        - Network connection failed
        - Invalid API credentials
    """

    pass


class DataQualityError(DataError):
    """Raised when data quality checks fail.

    Examples:
        - Missing or incomplete data
        - Data outside expected range
        - Inconsistent data (e.g., high < low)
    """

    pass


class StorageError(DataError):
    """Raised when database operations fail.

    Examples:
        - Database connection failed
        - SQL query failed
        - Data integrity constraint violated
    """

    pass


class PortfolioError(AITraderError):
    """Base exception for portfolio layer errors.

    Parent class for all portfolio-related exceptions.
    """

    pass


class AllocationError(PortfolioError):
    """Raised when portfolio allocation fails.

    Examples:
        - Invalid signal values
        - No investable signals
        - Configuration constraint violation
    """

    pass


class InsufficientFundsError(PortfolioError):
    """Raised when there are insufficient funds for an operation.

    Examples:
        - Not enough cash to execute buy orders
        - Portfolio value is zero or negative
    """

    pass


class RebalanceError(PortfolioError):
    """Raised when rebalancing calculation fails.

    Examples:
        - Missing price data for symbol
        - Invalid current position data
    """

    pass


class RiskError(AITraderError):
    """Base exception for risk layer errors.

    Parent class for all risk-related exceptions.
    """

    pass


class RiskViolationError(RiskError):
    """Raised when a risk rule is violated and cannot be auto-adjusted.

    Examples:
        - Position size exceeds absolute maximum
        - Total exposure cannot be reduced to limit
    """

    pass


class RiskConfigError(RiskError):
    """Raised when risk configuration is invalid.

    Examples:
        - Invalid risk thresholds
        - Conflicting risk parameters
    """

    pass


class CircuitBreakerError(RiskError):
    """Raised when circuit breaker is triggered.

    Examples:
        - Single-day loss exceeds threshold
        - Maximum drawdown exceeded
    """

    pass
