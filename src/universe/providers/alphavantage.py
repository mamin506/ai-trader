"""AlphaVantage provider for stock listings.

This module fetches the complete list of US-listed stocks and ETFs from
AlphaVantage's LISTING_STATUS API endpoint.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from src.utils.exceptions import DataProviderError

logger = logging.getLogger(__name__)


class AlphaVantageProvider:
    """Provider for fetching stock listings from AlphaVantage.

    AlphaVantage provides a free endpoint for getting all US-listed securities.
    The data is updated daily and includes stocks and ETFs from major exchanges.

    API Endpoint: https://www.alphavantage.co/query?function=LISTING_STATUS

    Note: The 'demo' API key works for this endpoint without rate limits.
    """

    API_URL = "https://www.alphavantage.co/query"
    DEFAULT_API_KEY = "demo"

    def __init__(
        self,
        api_key: str = DEFAULT_API_KEY,
        cache_dir: Optional[Path] = None,
    ):
        """Initialize AlphaVantage provider.

        Args:
            api_key: AlphaVantage API key (default: 'demo' works for listings)
            cache_dir: Directory to cache downloaded listings (optional)
        """
        self.api_key = api_key
        self.cache_dir = cache_dir

        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

        logger.debug("AlphaVantage provider initialized")

    def fetch_listings(
        self,
        use_cache: bool = True,
        max_cache_age_days: int = 1,
    ) -> pd.DataFrame:
        """Fetch all US stock and ETF listings.

        Args:
            use_cache: Whether to use cached data if available
            max_cache_age_days: Maximum age of cache in days before refetching

        Returns:
            DataFrame with columns:
                - symbol: Ticker symbol
                - name: Company name
                - exchange: Exchange (NASDAQ, NYSE, etc.)
                - assetType: Stock or ETF
                - ipoDate: IPO date
                - delistingDate: Delisting date (if applicable)
                - status: Active or Delisted

        Raises:
            DataProviderError: If API request fails
        """
        # Check cache first
        if use_cache and self.cache_dir:
            cached_df = self._load_from_cache(max_cache_age_days)
            if cached_df is not None:
                logger.info(
                    "Loaded %d listings from cache", len(cached_df)
                )
                return cached_df

        # Fetch from API
        logger.info("Fetching stock listings from AlphaVantage...")

        try:
            params = {
                "function": "LISTING_STATUS",
                "apikey": self.api_key,
            }

            response = requests.get(self.API_URL, params=params, timeout=30)
            response.raise_for_status()

            # Parse CSV response
            from io import StringIO

            df = pd.read_csv(StringIO(response.text))

            logger.info("Fetched %d listings from AlphaVantage", len(df))

            # Save to cache
            if self.cache_dir:
                self._save_to_cache(df)

            return df

        except requests.RequestException as e:
            raise DataProviderError(
                f"Failed to fetch listings from AlphaVantage: {e}"
            ) from e
        except pd.errors.ParserError as e:
            raise DataProviderError(
                f"Failed to parse AlphaVantage response: {e}"
            ) from e

    def _load_from_cache(
        self, max_age_days: int
    ) -> Optional[pd.DataFrame]:
        """Load listings from cache if available and fresh.

        Args:
            max_age_days: Maximum cache age in days

        Returns:
            DataFrame if cache is valid, None otherwise
        """
        if not self.cache_dir:
            return None

        cache_file = self.cache_dir / "alphavantage_listings.csv"

        if not cache_file.exists():
            return None

        # Check cache age
        cache_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        age_days = (datetime.now() - cache_mtime).days

        if age_days > max_age_days:
            logger.debug(
                "Cache is %d days old (max: %d), refetching",
                age_days,
                max_age_days,
            )
            return None

        # Load cache
        try:
            df = pd.read_csv(cache_file)
            logger.debug("Loaded %d listings from cache", len(df))
            return df
        except Exception as e:
            logger.warning("Failed to load cache: %s", e)
            return None

    def _save_to_cache(self, df: pd.DataFrame) -> None:
        """Save listings to cache.

        Args:
            df: DataFrame to cache
        """
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / "alphavantage_listings.csv"

        try:
            df.to_csv(cache_file, index=False)
            logger.debug("Saved %d listings to cache", len(df))
        except Exception as e:
            logger.warning("Failed to save cache: %s", e)

    def get_active_stocks(
        self,
        exchanges: Optional[list[str]] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Get active stocks (excluding ETFs and delisted).

        Args:
            exchanges: List of exchanges to include (e.g., ['NASDAQ', 'NYSE'])
                      If None, includes all major exchanges
            use_cache: Whether to use cached listings

        Returns:
            DataFrame with active stocks only
        """
        df = self.fetch_listings(use_cache=use_cache)

        # Filter for active stocks
        df = df[
            (df["assetType"] == "Stock")
            & (df["status"] == "Active")
        ].copy()

        # Filter by exchange if specified
        if exchanges:
            df = df[df["exchange"].isin(exchanges)]

        return df

    def get_active_etfs(
        self,
        exchanges: Optional[list[str]] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Get active ETFs (excluding stocks and delisted).

        Args:
            exchanges: List of exchanges to include
            use_cache: Whether to use cached listings

        Returns:
            DataFrame with active ETFs only
        """
        df = self.fetch_listings(use_cache=use_cache)

        # Filter for active ETFs
        df = df[
            (df["assetType"] == "ETF")
            & (df["status"] == "Active")
        ].copy()

        # Filter by exchange if specified
        if exchanges:
            df = df[df["exchange"].isin(exchanges)]

        return df
