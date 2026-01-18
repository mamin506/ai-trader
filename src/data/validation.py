"""Data validation module for ensuring market data quality."""

import pandas as pd
import numpy as np
from typing import List, Optional

from src.utils.logging import get_logger
from src.utils.exceptions import DataQualityError

logger = get_logger(__name__)


class DataValidator:
    """Validator for market data quality."""

    REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]

    @classmethod
    def validate(
        cls,
        df: pd.DataFrame,
        symbol: str,
        expected_days: Optional[pd.DatetimeIndex] = None
    ) -> None:
        """Run all validation checks.

        Args:
            df: DataFrame to validate
            symbol: Ticker symbol for logging
            expected_days: Optional list of expected trading days for continuity check

        Raises:
            DataQualityError: If validation fails critically
        """
        if df is None or df.empty:
            raise DataQualityError(f"Data is empty for {symbol}")

        cls.validate_schema(df, symbol)
        cls.validate_integrity(df, symbol)

        if expected_days is not None:
            cls.validate_continuity(df, expected_days, symbol)

        cls.detect_anomalies(df, symbol)

    @classmethod
    def validate_schema(cls, df: pd.DataFrame, symbol: str) -> None:
        """Check for required columns."""
        missing = [col for col in cls.REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise DataQualityError(f"Missing columns for {symbol}: {missing}")

    @classmethod
    def validate_integrity(cls, df: pd.DataFrame, symbol: str) -> None:
        """Check data integrity rules."""
        # Rule 1: No negative prices
        if (df[["open", "high", "low", "close"]] <= 0).any().any():
            raise DataQualityError(f"Found non-positive prices for {symbol}")

        # Rule 2: High >= max(Open, Close)
        # Allow for small floating point errors
        epsilon = 1e-6
        if (df["high"] < df[["open", "close"]].max(axis=1) - epsilon).any():
            invalid_rows = df[df["high"] < df[["open", "close"]].max(axis=1) - epsilon]
            logger.warning(
                "High price integrity check failed for %s at %s. Found %d violations.",
                symbol,
                invalid_rows.index[0],
                len(invalid_rows)
            )
            # Depending on strictness, we might raise or just warn.
            # For now, let's strictly validate but maybe just warn for minor issues?
            # The user asked for "Fail-Safe", so blocking invalid data is safer.
            raise DataQualityError(f"High price integrity check failed for {symbol}")

        # Rule 3: Low <= min(Open, Close)
        if (df["low"] > df[["open", "close"]].min(axis=1) + epsilon).any():
             raise DataQualityError(f"Low price integrity check failed for {symbol}")

        # Rule 4: Volume >= 0
        if (df["volume"] < 0).any():
             raise DataQualityError(f"Found negative volume for {symbol}")

    @classmethod
    def validate_continuity(
        cls,
        df: pd.DatetimeIndex | pd.DataFrame,
        expected_days: pd.DatetimeIndex,
        symbol: str
    ) -> None:
        """Check for missing trading days."""
        actual_days = df.index if isinstance(df, pd.DataFrame) else df

        # Find expected days that are missing in actual data
        # We only check for days that fall within the actual data's range
        # (or should we strictly enforce the requested range?
        # Usually provided data is what we got, checking holes IN it)

        # Restrict expected days to the range covered by actual data (or requested range?)
        # Generally we care about gaps *within* the range we got.
        if len(actual_days) == 0:
            return

        start, end = actual_days[0], actual_days[-1]
        relevant_expected = expected_days[(expected_days >= start) & (expected_days <= end)]

        missing = relevant_expected.difference(actual_days)

        if not missing.empty:
            # If missing days > threshold (e.g., 0 for strictness), raise error
            # For backtesting, missing data is fatal.
            first_missing = missing[0]
            logger.error("Missing trading day for %s: %s. Total missing: %d", symbol, first_missing, len(missing))
            raise DataQualityError(f"Missing {len(missing)} trading days for {symbol} (e.g. {first_missing})")

    @classmethod
    def detect_anomalies(cls, df: pd.DataFrame, symbol: str) -> None:
        """Detect potential anomalies (warnings only)."""
        # Spike detection: Check for > 20% single day move
        # (Close - PrevClose) / PrevClose
        returns = df["close"].pct_change().abs()
        spikes = returns[returns > 0.20]

        if not spikes.empty:
            logger.warning(
                "Detected price spikes (>20%%) for %s at dates: %s",
                symbol,
                spikes.index.tolist()
            )
            # We don't raise Error here, just warn, as per design
