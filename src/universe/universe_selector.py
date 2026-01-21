"""Abstract base class for universe selection.

This module defines the interface for stock universe selectors that filter
and rank stocks before strategy application.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import pandas as pd


class UniverseSelector(ABC):
    """Abstract base class for universe selection.

    A UniverseSelector takes a broad set of stocks and applies filtering
    and ranking criteria to produce a focused universe for trading.

    Typical workflow:
    1. Fetch all available stocks from a data source
    2. Apply filters (liquidity, market cap, price range, etc.)
    3. Rank remaining stocks by criteria (momentum, value, quality, etc.)
    4. Select top N stocks for the universe

    Subclasses must implement the select() method.
    """

    @abstractmethod
    def select(
        self,
        date: Optional[datetime] = None,
        top_n: int = 100,
    ) -> list[str]:
        """Select stocks for the universe.

        Args:
            date: Date for universe selection (default: today)
                  Used for historical backtesting to avoid look-ahead bias
            top_n: Maximum number of stocks to select

        Returns:
            List of stock symbols in the universe

        Raises:
            ValueError: If parameters are invalid
            DataFetchError: If data fetching fails
        """
        pass

    @abstractmethod
    def get_universe_metadata(
        self,
        symbols: list[str],
        date: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Get metadata for universe stocks.

        Args:
            symbols: List of stock symbols
            date: Date for metadata (default: today)

        Returns:
            DataFrame with columns:
                - symbol: Stock symbol
                - market_cap: Market capitalization
                - avg_volume: Average daily volume
                - price: Current price
                - rank: Ranking score (if applicable)
                - Additional provider-specific columns

        Raises:
            ValueError: If symbols list is empty
            DataFetchError: If data fetching fails
        """
        pass

    def filter_by_liquidity(
        self,
        df: pd.DataFrame,
        min_avg_volume: float = 1_000_000,
        min_dollar_volume: Optional[float] = None,
    ) -> pd.DataFrame:
        """Filter stocks by liquidity.

        Args:
            df: DataFrame with 'avg_volume' and 'price' columns
            min_avg_volume: Minimum average daily volume (shares)
            min_dollar_volume: Minimum average daily dollar volume (optional)

        Returns:
            Filtered DataFrame
        """
        filtered = df[df["avg_volume"] >= min_avg_volume].copy()

        if min_dollar_volume is not None:
            if "price" not in df.columns:
                raise ValueError(
                    "DataFrame must have 'price' column for dollar volume filter"
                )
            filtered["dollar_volume"] = (
                filtered["avg_volume"] * filtered["price"]
            )
            filtered = filtered[
                filtered["dollar_volume"] >= min_dollar_volume
            ]

        return filtered

    def filter_by_market_cap(
        self,
        df: pd.DataFrame,
        min_market_cap: Optional[float] = None,
        max_market_cap: Optional[float] = None,
    ) -> pd.DataFrame:
        """Filter stocks by market capitalization.

        Args:
            df: DataFrame with 'market_cap' column
            min_market_cap: Minimum market cap (dollars)
            max_market_cap: Maximum market cap (dollars)

        Returns:
            Filtered DataFrame
        """
        if "market_cap" not in df.columns:
            raise ValueError(
                "DataFrame must have 'market_cap' column"
            )

        filtered = df.copy()

        if min_market_cap is not None:
            filtered = filtered[filtered["market_cap"] >= min_market_cap]

        if max_market_cap is not None:
            filtered = filtered[filtered["market_cap"] <= max_market_cap]

        return filtered

    def filter_by_price(
        self,
        df: pd.DataFrame,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> pd.DataFrame:
        """Filter stocks by price.

        Args:
            df: DataFrame with 'price' column
            min_price: Minimum price (dollars)
            max_price: Maximum price (dollars)

        Returns:
            Filtered DataFrame
        """
        if "price" not in df.columns:
            raise ValueError("DataFrame must have 'price' column")

        filtered = df.copy()

        if min_price is not None:
            filtered = filtered[filtered["price"] >= min_price]

        if max_price is not None:
            filtered = filtered[filtered["price"] <= max_price]

        return filtered

    def filter_by_exchange(
        self,
        df: pd.DataFrame,
        exchanges: list[str],
    ) -> pd.DataFrame:
        """Filter stocks by exchange.

        Args:
            df: DataFrame with 'exchange' column
            exchanges: List of exchange names (e.g., ['NASDAQ', 'NYSE'])

        Returns:
            Filtered DataFrame
        """
        if "exchange" not in df.columns:
            raise ValueError("DataFrame must have 'exchange' column")

        return df[df["exchange"].isin(exchanges)].copy()
