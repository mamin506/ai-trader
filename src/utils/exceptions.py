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
