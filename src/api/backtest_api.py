"""User-friendly API for Backtesting.

This module provides a simplified interface for running backtests
and analyzing results.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from src.api.data_api import DataAPI
from src.orchestration.backtest_orchestrator import (
    BacktestConfig,
    BacktestOrchestrator,
    BacktestResult,
)
from src.strategy.base import Strategy
from src.strategy.ma_crossover import MACrossoverStrategy
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BacktestAPI:
    """User-friendly API for running backtests.

    Provides a high-level interface for backtesting trading strategies
    with historical data.

    Example:
        >>> api = BacktestAPI()
        >>> result = api.run_ma_crossover(
        ...     symbols=['AAPL', 'MSFT'],
        ...     start_date='2024-01-01',
        ...     end_date='2024-12-31',
        ...     fast_period=10,
        ...     slow_period=30,
        ... )
        >>> print(api.format_results(result))
    """

    def __init__(self, data_api: Optional[DataAPI] = None):
        """Initialize BacktestAPI.

        Args:
            data_api: DataAPI instance for fetching data (creates new one if not provided)
        """
        self.data_api = data_api or DataAPI()
        logger.info("BacktestAPI initialized")

    def run_backtest(
        self,
        strategy: Strategy,
        symbols: List[str],
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        initial_cash: float = 100000.0,
        slippage_pct: float = 0.001,
        commission_per_share: float = 0.0,
        rebalance_frequency: str = "daily",
        max_positions: int = 10,
        max_position_size: float = 0.25,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> BacktestResult:
        """Run a backtest with a custom strategy.

        Args:
            strategy: Trading strategy to backtest
            symbols: List of ticker symbols
            start_date: Backtest start date
            end_date: Backtest end date
            initial_cash: Starting capital
            slippage_pct: Slippage percentage
            commission_per_share: Commission per share
            rebalance_frequency: 'daily', 'weekly', or 'monthly'
            max_positions: Maximum number of positions
            max_position_size: Maximum weight per position
            price_data: Pre-loaded price data (fetches if not provided)

        Returns:
            BacktestResult with performance metrics
        """
        # Parse dates
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")

        # Fetch price data if not provided
        if price_data is None:
            price_data = self._fetch_price_data(symbols, start_date, end_date)

        # Create config
        config = BacktestConfig(
            initial_cash=initial_cash,
            slippage_pct=slippage_pct,
            commission_per_share=commission_per_share,
            rebalance_frequency=rebalance_frequency,
            max_positions=max_positions,
            max_position_size=max_position_size,
        )

        # Create orchestrator and run
        orchestrator = BacktestOrchestrator(strategy, config)
        return orchestrator.run(price_data)

    def run_ma_crossover(
        self,
        symbols: List[str],
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        fast_period: int = 10,
        slow_period: int = 30,
        initial_cash: float = 100000.0,
        slippage_pct: float = 0.001,
        commission_per_share: float = 0.0,
        rebalance_frequency: str = "daily",
        max_positions: int = 10,
        max_position_size: float = 0.25,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> BacktestResult:
        """Run a backtest with MA Crossover strategy.

        Args:
            symbols: List of ticker symbols
            start_date: Backtest start date
            end_date: Backtest end date
            fast_period: Fast MA period
            slow_period: Slow MA period
            initial_cash: Starting capital
            slippage_pct: Slippage percentage
            commission_per_share: Commission per share
            rebalance_frequency: 'daily', 'weekly', or 'monthly'
            max_positions: Maximum number of positions
            max_position_size: Maximum weight per position
            price_data: Pre-loaded price data (fetches if not provided)

        Returns:
            BacktestResult with performance metrics

        Example:
            >>> api = BacktestAPI()
            >>> result = api.run_ma_crossover(
            ...     symbols=['AAPL', 'MSFT', 'GOOGL'],
            ...     start_date='2024-01-01',
            ...     end_date='2024-06-30',
            ...     fast_period=10,
            ...     slow_period=30,
            ... )
        """
        strategy = MACrossoverStrategy(
            {"fast_period": fast_period, "slow_period": slow_period}
        )

        return self.run_backtest(
            strategy=strategy,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            slippage_pct=slippage_pct,
            commission_per_share=commission_per_share,
            rebalance_frequency=rebalance_frequency,
            max_positions=max_positions,
            max_position_size=max_position_size,
            price_data=price_data,
        )

    def _fetch_price_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch price data for symbols."""
        price_data = {}
        for symbol in symbols:
            try:
                df = self.data_api.get_daily_bars(
                    symbol,
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                )
                if df is not None and not df.empty:
                    price_data[symbol] = df
                    logger.info("Fetched %d bars for %s", len(df), symbol)
            except Exception as e:
                logger.warning("Failed to fetch data for %s: %s", symbol, e)

        return price_data

    def format_results(self, result: BacktestResult) -> str:
        """Format backtest results as a readable string.

        Args:
            result: BacktestResult from a backtest run

        Returns:
            Formatted string with performance metrics
        """
        lines = [
            "=" * 70,
            "BACKTEST RESULTS",
            "=" * 70,
            f"Period: {result.start_date.strftime('%Y-%m-%d')} to {result.end_date.strftime('%Y-%m-%d')}",
            f"Duration: {(result.end_date - result.start_date).days} days",
            "-" * 70,
            "PERFORMANCE METRICS",
            "-" * 70,
            f"Initial Value:      ${result.initial_value:>15,.2f}",
            f"Final Value:        ${result.final_value:>15,.2f}",
            f"Total Return:       {result.total_return_pct:>15.2f}%",
            f"Annualized Return:  {result.annualized_return * 100:>15.2f}%",
            f"Max Drawdown:       {result.max_drawdown * 100:>15.2f}%",
        ]

        if result.sharpe_ratio is not None:
            lines.append(f"Sharpe Ratio:       {result.sharpe_ratio:>15.2f}")
        else:
            lines.append("Sharpe Ratio:              N/A")

        lines.extend(
            [
                "-" * 70,
                "TRADE STATISTICS",
                "-" * 70,
                f"Total Trades:       {result.num_trades:>15}",
                f"Win Rate:           {result.win_rate * 100:>15.2f}%",
            ]
        )

        lines.extend(
            [
                "-" * 70,
                "CONFIGURATION",
                "-" * 70,
                f"Initial Cash:       ${result.config.initial_cash:>14,.2f}",
                f"Slippage:           {result.config.slippage_pct * 100:>15.3f}%",
                f"Commission/Share:   ${result.config.commission_per_share:>14.4f}",
                f"Rebalance:          {result.config.rebalance_frequency:>15}",
                f"Max Positions:      {result.config.max_positions:>15}",
                f"Max Position Size:  {result.config.max_position_size * 100:>15.1f}%",
                "=" * 70,
            ]
        )

        return "\n".join(lines)

    def get_equity_curve(self, result: BacktestResult) -> pd.DataFrame:
        """Get equity curve from backtest result.

        Args:
            result: BacktestResult from a backtest run

        Returns:
            DataFrame with daily portfolio values
        """
        return result.equity_curve.copy()

    def get_trades(self, result: BacktestResult) -> pd.DataFrame:
        """Get trades from backtest result.

        Args:
            result: BacktestResult from a backtest run

        Returns:
            DataFrame with all trades
        """
        if not result.trades:
            return pd.DataFrame()
        return pd.DataFrame(result.trades)

    def get_daily_returns(self, result: BacktestResult) -> pd.Series:
        """Get daily returns from backtest result.

        Args:
            result: BacktestResult from a backtest run

        Returns:
            Series with daily returns
        """
        return result.daily_returns.copy()

    def calculate_buy_and_hold_return(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        initial_cash: float = 100000.0,
    ) -> Dict[str, float]:
        """Calculate buy-and-hold return for a symbol.

        This simulates buying the symbol on day 1 and holding until the end.

        Args:
            symbol: Ticker symbol
            start_date: Start date
            end_date: End date
            initial_cash: Starting capital

        Returns:
            Dict with buy-and-hold metrics
        """
        # Parse dates
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")

        # Fetch price data
        price_data = self._fetch_price_data([symbol], start_date, end_date)

        if symbol not in price_data or price_data[symbol].empty:
            raise ValueError(f"No data available for {symbol}")

        df = price_data[symbol]

        # Get first and last close prices
        first_price = df.iloc[0]['close']
        last_price = df.iloc[-1]['close']

        # Calculate shares bought on day 1
        shares = initial_cash / first_price

        # Calculate final value
        final_value = shares * last_price

        # Calculate returns
        total_return = (final_value - initial_cash) / initial_cash
        num_days = (df.index[-1] - df.index[0]).days
        years = num_days / 365.25
        annualized_return = (final_value / initial_cash) ** (1 / years) - 1 if years > 0 else 0

        # Calculate daily returns
        daily_returns = df['close'].pct_change().dropna()

        # Calculate Sharpe ratio (assuming risk-free rate = 0)
        if len(daily_returns) > 1:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5) if daily_returns.std() > 0 else None
        else:
            sharpe_ratio = None

        # Calculate max drawdown
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdown.min())

        return {
            'symbol': symbol,
            'initial_cash': initial_cash,
            'final_value': final_value,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'annualized_return': annualized_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'num_days': num_days,
            'first_price': first_price,
            'last_price': last_price,
            'shares': shares,
            'start_date': df.index[0],
            'end_date': df.index[-1],
        }

    def compare_results(
        self,
        results: Dict[str, BacktestResult],
    ) -> pd.DataFrame:
        """Compare multiple backtest results.

        Args:
            results: Dict mapping name to BacktestResult

        Returns:
            DataFrame comparing key metrics
        """
        comparison_data = []
        for name, result in results.items():
            comparison_data.append(
                {
                    "Strategy": name,
                    "Total Return (%)": result.total_return_pct,
                    "Annualized Return (%)": result.annualized_return * 100,
                    "Max Drawdown (%)": result.max_drawdown * 100,
                    "Sharpe Ratio": result.sharpe_ratio,
                    "Num Trades": result.num_trades,
                    "Win Rate (%)": result.win_rate * 100,
                }
            )

        return pd.DataFrame(comparison_data).set_index("Strategy")

    def format_comparison(self, results: Dict[str, BacktestResult]) -> str:
        """Format comparison of multiple backtest results.

        Args:
            results: Dict mapping name to BacktestResult

        Returns:
            Formatted comparison string
        """
        df = self.compare_results(results)

        lines = [
            "=" * 90,
            "STRATEGY COMPARISON",
            "=" * 90,
        ]

        # Header
        header = f"{'Strategy':<20} {'Return':>12} {'Ann. Ret':>12} {'Max DD':>10} {'Sharpe':>10} {'Trades':>8}"
        lines.append(header)
        lines.append("-" * 90)

        # Data rows
        for name in df.index:
            row = df.loc[name]
            sharpe_str = f"{row['Sharpe Ratio']:.2f}" if pd.notna(row["Sharpe Ratio"]) else "N/A"
            lines.append(
                f"{name:<20} {row['Total Return (%)']:>11.2f}% {row['Annualized Return (%)']:>11.2f}% "
                f"{row['Max Drawdown (%)']:>9.2f}% {sharpe_str:>10} {int(row['Num Trades']):>8}"
            )

        lines.append("=" * 90)
        return "\n".join(lines)
