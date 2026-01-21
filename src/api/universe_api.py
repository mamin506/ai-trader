"""Universe API - High-level interface for universe selection.

This module provides a simple API for selecting and managing stock universes.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from src.data.storage.database import DatabaseManager
from src.universe.static_universe import StaticUniverseSelector

logger = logging.getLogger(__name__)


class UniverseAPI:
    """High-level API for universe selection.

    This API provides simple methods for:
    1. Selecting stocks based on filters and ranking
    2. Saving/loading universes to/from database
    3. Managing multiple named universes

    Example:
        >>> from src.api.universe_api import UniverseAPI
        >>>
        >>> api = UniverseAPI()
        >>>
        >>> # Select top 50 liquid stocks
        >>> symbols = api.select_universe(
        ...     name='liquid_50',
        ...     top_n=50,
        ...     min_price=10.0,
        ...     min_avg_volume=2_000_000,
        ...     save=True,
        ... )
        >>>
        >>> # Load saved universe
        >>> symbols = api.load_universe('liquid_50', date='2024-01-01')
    """

    def __init__(
        self,
        db_path: str = "data/market_data.db",
        cache_dir: Optional[Path] = None,
    ):
        """Initialize Universe API.

        Args:
            db_path: Path to SQLite database
            cache_dir: Directory for caching listings (default: data/universe)
        """
        self.db = DatabaseManager(db_path)

        if cache_dir is None:
            cache_dir = Path("data/universe")

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.debug("UniverseAPI initialized")

    def select_universe(
        self,
        name: str = "default",
        date: Optional[Union[str, datetime]] = None,
        top_n: int = 100,
        # Filter parameters
        exchanges: Optional[list[str]] = None,
        min_price: float = 5.0,
        max_price: Optional[float] = None,
        min_avg_volume: float = 1_000_000,
        min_market_cap: Optional[float] = None,
        max_market_cap: Optional[float] = None,
        # Save option
        save: bool = False,
    ) -> list[str]:
        """Select stocks for a universe.

        Args:
            name: Universe name (for saving/loading)
            date: Selection date (default: today)
            top_n: Maximum number of stocks to select
            exchanges: List of exchanges (default: ['NASDAQ', 'NYSE', 'NYSE ARCA'])
            min_price: Minimum stock price (default: $5)
            max_price: Maximum stock price (optional)
            min_avg_volume: Minimum average daily volume (default: 1M shares)
            min_market_cap: Minimum market cap (optional)
            max_market_cap: Maximum market cap (optional)
            save: Whether to save universe to database

        Returns:
            List of stock symbols

        Example:
            >>> api = UniverseAPI()
            >>> symbols = api.select_universe(
            ...     name='tech_liquid',
            ...     top_n=50,
            ...     min_price=20.0,
            ...     min_avg_volume=5_000_000,
            ...     save=True,
            ... )
        """
        # Parse date
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")

        # Create selector
        selector = StaticUniverseSelector(
            cache_dir=self.cache_dir,
            exchanges=exchanges,
            min_price=min_price,
            max_price=max_price,
            min_avg_volume=min_avg_volume,
            min_market_cap=min_market_cap,
            max_market_cap=max_market_cap,
        )

        # Select universe
        symbols = selector.select(date=date, top_n=top_n)

        # Save if requested
        if save:
            # Get metadata for ranking
            metadata_df = selector.get_universe_metadata(symbols, date)
            ranks = metadata_df["rank"].tolist() if "rank" in metadata_df.columns else None

            self.db.save_universe(
                name=name,
                symbols=symbols,
                date=date,
                ranks=ranks,
            )

            logger.info(
                f"Saved universe '{name}' with {len(symbols)} symbols"
            )

        return symbols

    def load_universe(
        self,
        name: str,
        date: Optional[Union[str, datetime]] = None,
    ) -> list[str]:
        """Load a saved universe from database.

        Args:
            name: Universe name
            date: Selection date (default: most recent)

        Returns:
            List of stock symbols

        Raises:
            ValueError: If universe not found

        Example:
            >>> api = UniverseAPI()
            >>> symbols = api.load_universe('liquid_50', date='2024-01-01')
        """
        # Parse date
        if date is None:
            # Get most recent date
            dates = self.db.get_universe_dates(name)
            if not dates:
                raise ValueError(f"No universe found with name '{name}'")
            date_str = dates[0]
            date = datetime.strptime(date_str, "%Y-%m-%d")
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")

        # Load from database
        df = self.db.load_universe(name, date)

        if df.empty:
            raise ValueError(
                f"Universe '{name}' not found for date {date.strftime('%Y-%m-%d')}"
            )

        symbols = df["symbol"].tolist()

        logger.info(
            f"Loaded universe '{name}' with {len(symbols)} symbols for {date.strftime('%Y-%m-%d')}"
        )

        return symbols

    def get_universe_dates(self, name: str) -> list[str]:
        """Get all dates for which a universe exists.

        Args:
            name: Universe name

        Returns:
            List of date strings (YYYY-MM-DD), sorted descending

        Example:
            >>> api = UniverseAPI()
            >>> dates = api.get_universe_dates('liquid_50')
            >>> print(dates)
            ['2024-03-15', '2024-03-01', '2024-02-15', ...]
        """
        return self.db.get_universe_dates(name)

    def refresh_listings_cache(self) -> int:
        """Refresh the cached stock listings from AlphaVantage.

        Returns:
            Number of listings fetched

        Example:
            >>> api = UniverseAPI()
            >>> count = api.refresh_listings_cache()
            >>> print(f"Fetched {count} stock listings")
        """
        from src.universe.providers.alphavantage import AlphaVantageProvider

        provider = AlphaVantageProvider(cache_dir=self.cache_dir)

        # Force refresh (ignore cache)
        df = provider.fetch_listings(use_cache=False)

        logger.info(f"Refreshed listings cache with {len(df)} listings")

        return len(df)
