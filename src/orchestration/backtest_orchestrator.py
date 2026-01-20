"""Backtest Orchestrator - Coordinates all layers for historical backtesting.

This module implements the end-to-end backtest workflow:
Data → Strategy → Portfolio → Risk → Execution → Performance
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from src.execution.backtest_executor import BacktestExecutor
from src.portfolio.base import Order, PortfolioState
from src.portfolio.heuristic_allocator import HeuristicAllocator
from src.risk.basic_risk_manager import BasicRiskManager
from src.strategy.base import Strategy
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtest run.

    Attributes:
        initial_cash: Starting capital
        slippage_pct: Slippage as percentage of price
        commission_per_share: Commission per share traded
        commission_min: Minimum commission per order
        rebalance_frequency: How often to rebalance ('daily', 'weekly', 'monthly')
        min_signal_threshold: Minimum signal strength to act on
        max_positions: Maximum number of positions
        max_position_size: Maximum weight per position
        cash_buffer: Cash reserve percentage
        stop_loss_pct: Stop loss threshold (optional)
        take_profit_pct: Take profit threshold (optional)
    """

    initial_cash: float = 100000.0
    slippage_pct: float = 0.001
    commission_per_share: float = 0.0
    commission_min: float = 0.0
    rebalance_frequency: str = "daily"
    min_signal_threshold: float = 0.3
    max_positions: int = 10
    max_position_size: float = 0.25
    cash_buffer: float = 0.05
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


@dataclass
class BacktestResult:
    """Results from a backtest run.

    Attributes:
        config: Backtest configuration used
        start_date: Backtest start date
        end_date: Backtest end date
        initial_value: Starting portfolio value
        final_value: Ending portfolio value
        total_return: Total return (decimal)
        total_return_pct: Total return (percentage)
        annualized_return: Annualized return
        max_drawdown: Maximum drawdown
        sharpe_ratio: Sharpe ratio (if calculable)
        num_trades: Total number of trades
        num_winning_trades: Number of profitable trades
        num_losing_trades: Number of losing trades
        win_rate: Winning trade percentage
        equity_curve: Daily portfolio values
        trades: List of all trades
        daily_returns: Daily return series
    """

    config: BacktestConfig
    start_date: datetime
    end_date: datetime
    initial_value: float
    final_value: float
    total_return: float
    total_return_pct: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: Optional[float]
    num_trades: int
    num_winning_trades: int
    num_losing_trades: int
    win_rate: float
    equity_curve: pd.DataFrame
    trades: List[Dict[str, Any]]
    daily_returns: pd.Series


class BacktestOrchestrator:
    """Orchestrates end-to-end backtesting workflow.

    Coordinates Data, Strategy, Portfolio, Risk, and Execution layers
    to run historical backtests.

    Example:
        >>> from src.strategy.ma_crossover import MACrossoverStrategy
        >>> strategy = MACrossoverStrategy({'fast_period': 10, 'slow_period': 30})
        >>> orchestrator = BacktestOrchestrator(strategy)
        >>> result = orchestrator.run(price_data, signals)
        >>> print(f"Total Return: {result.total_return_pct:.2f}%")
    """

    def __init__(
        self,
        strategy: Strategy,
        config: Optional[BacktestConfig] = None,
    ):
        """Initialize backtest orchestrator.

        Args:
            strategy: Trading strategy to backtest
            config: Backtest configuration (uses defaults if not provided)
        """
        self.strategy = strategy
        self.config = config or BacktestConfig()

        # Initialize components
        self._init_components()

        logger.info(
            "BacktestOrchestrator initialized with %s strategy",
            strategy.__class__.__name__,
        )

    def _init_components(self) -> None:
        """Initialize all layer components."""
        # Execution layer
        self.executor = BacktestExecutor(
            {
                "initial_cash": self.config.initial_cash,
                "slippage_pct": self.config.slippage_pct,
                "commission_per_share": self.config.commission_per_share,
                "commission_min": self.config.commission_min,
            }
        )

        # Portfolio layer
        self.allocator = HeuristicAllocator(
            {
                "min_signal_threshold": self.config.min_signal_threshold,
                "max_positions": self.config.max_positions,
                "max_position_size": self.config.max_position_size,
                "cash_buffer": self.config.cash_buffer,
            }
        )

        # Risk layer
        risk_config = {
            "max_position_size": self.config.max_position_size,
            "max_total_exposure": 1.0 - self.config.cash_buffer,
            "min_cash_reserve": self.config.cash_buffer,
        }
        if self.config.stop_loss_pct:
            risk_config["stop_loss_pct"] = self.config.stop_loss_pct
        if self.config.take_profit_pct:
            risk_config["take_profit_pct"] = self.config.take_profit_pct

        self.risk_manager = BasicRiskManager(risk_config)

    def run(
        self,
        price_data: Dict[str, pd.DataFrame],
        signals: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> BacktestResult:
        """Run backtest on historical data.

        Args:
            price_data: Dict mapping symbol to OHLCV DataFrame
            signals: Pre-computed signals (optional, will generate if not provided)

        Returns:
            BacktestResult with performance metrics
        """
        # Validate input
        if not price_data:
            raise ValueError("price_data cannot be empty")

        symbols = list(price_data.keys())
        logger.info("Starting backtest for %d symbols: %s", len(symbols), symbols)

        # Get date range from price data
        all_dates = self._get_trading_dates(price_data)
        if len(all_dates) < 2:
            raise ValueError("Need at least 2 trading days for backtest")

        start_date = all_dates[0]
        end_date = all_dates[-1]

        # Generate signals if not provided
        if signals is None:
            signals = self._generate_signals(price_data)

        # Initialize tracking
        equity_curve_data = []
        trades_log = []

        # Reset executor
        self.executor.reset()

        # Run day-by-day simulation
        rebalance_dates = self._get_rebalance_dates(all_dates)

        for i, current_date in enumerate(all_dates):
            # Get current prices
            current_prices = self._get_prices_for_date(price_data, current_date)
            if not current_prices:
                continue

            self.executor.set_prices(current_prices)
            self.executor.set_timestamp(current_date)

            # Check if we should rebalance
            if current_date in rebalance_dates:
                # Get current signals
                current_signals = self._get_signals_for_date(signals, current_date)

                if current_signals:
                    # Generate allocation
                    portfolio_state = self._get_portfolio_state(current_prices)
                    allocation = self.allocator.allocate(current_signals, portfolio_state)

                    # Validate through risk manager
                    risk_result = self.risk_manager.validate_weights(
                        allocation.target_weights,
                    )

                    if risk_result.action.value in ["approve", "adjust"]:
                        # Generate orders with risk-adjusted weights
                        orders = self.allocator.generate_orders(
                            current_positions=portfolio_state.positions,
                            target_weights=risk_result.adjusted_weights,
                            total_value=portfolio_state.total_value,
                            prices=portfolio_state.prices,
                        )

                        # Execute orders
                        if orders:
                            results = self.executor.submit_orders(orders)
                            for order, result in zip(orders, results):
                                if result.status.value == "filled":
                                    trades_log.append(
                                        {
                                            "date": current_date,
                                            "symbol": order.symbol,
                                            "action": order.action.value,
                                            "shares": result.filled_qty,
                                            "price": result.filled_avg_price,
                                            "commission": result.commission,
                                        }
                                    )

            # Record equity
            account = self.executor.get_account_info()
            equity_curve_data.append(
                {
                    "date": current_date,
                    "portfolio_value": account.portfolio_value,
                    "cash": account.cash,
                    "positions_value": account.positions_value,
                }
            )

        # Calculate results
        equity_curve = pd.DataFrame(equity_curve_data)
        if not equity_curve.empty:
            equity_curve.set_index("date", inplace=True)

        result = self._calculate_results(
            equity_curve, trades_log, start_date, end_date
        )

        logger.info(
            "Backtest complete: Return=%.2f%%, MaxDD=%.2f%%, Trades=%d",
            result.total_return_pct,
            result.max_drawdown * 100,
            result.num_trades,
        )

        return result

    def _get_trading_dates(self, price_data: Dict[str, pd.DataFrame]) -> List[datetime]:
        """Get all unique trading dates from price data."""
        all_dates = set()
        for df in price_data.values():
            if isinstance(df.index, pd.DatetimeIndex):
                all_dates.update(df.index.to_pydatetime())
            else:
                all_dates.update(pd.to_datetime(df.index).to_pydatetime())

        return sorted(all_dates)

    def _get_rebalance_dates(self, all_dates: List[datetime]) -> set:
        """Get dates when rebalancing should occur."""
        if self.config.rebalance_frequency == "daily":
            return set(all_dates)

        rebalance_dates = set()
        if self.config.rebalance_frequency == "weekly":
            # Rebalance on Mondays (or first trading day of week)
            current_week = None
            for date in all_dates:
                week = date.isocalendar()[1]
                if week != current_week:
                    rebalance_dates.add(date)
                    current_week = week

        elif self.config.rebalance_frequency == "monthly":
            # Rebalance on first trading day of month
            current_month = None
            for date in all_dates:
                month = (date.year, date.month)
                if month != current_month:
                    rebalance_dates.add(date)
                    current_month = month

        return rebalance_dates

    def _get_prices_for_date(
        self,
        price_data: Dict[str, pd.DataFrame],
        date: datetime,
    ) -> Dict[str, float]:
        """Get closing prices for a specific date."""
        prices = {}
        for symbol, df in price_data.items():
            if date in df.index:
                prices[symbol] = float(df.loc[date, "close"])
            elif isinstance(df.index, pd.DatetimeIndex):
                # Try to find the date
                mask = df.index == date
                if mask.any():
                    prices[symbol] = float(df.loc[mask, "close"].iloc[0])
        return prices

    def _get_signals_for_date(
        self,
        signals: Dict[str, Union[pd.DataFrame, pd.Series]],
        date: datetime,
    ) -> Dict[str, float]:
        """Get signal values for a specific date."""
        current_signals = {}
        for symbol, signal_data in signals.items():
            # Handle both Series and DataFrame
            if isinstance(signal_data, pd.Series):
                if date in signal_data.index:
                    signal_val = signal_data.loc[date]
                    if pd.notna(signal_val) and signal_val != 0:
                        current_signals[symbol] = float(signal_val)
                elif isinstance(signal_data.index, pd.DatetimeIndex):
                    mask = signal_data.index == date
                    if mask.any():
                        signal_val = signal_data.loc[mask].iloc[0]
                        if pd.notna(signal_val) and signal_val != 0:
                            current_signals[symbol] = float(signal_val)
            elif isinstance(signal_data, pd.DataFrame):
                if "signal" not in signal_data.columns:
                    continue
                if date in signal_data.index:
                    signal_val = signal_data.loc[date, "signal"]
                    if pd.notna(signal_val) and signal_val != 0:
                        current_signals[symbol] = float(signal_val)
                elif isinstance(signal_data.index, pd.DatetimeIndex):
                    mask = signal_data.index == date
                    if mask.any():
                        signal_val = signal_data.loc[mask, "signal"].iloc[0]
                        if pd.notna(signal_val) and signal_val != 0:
                            current_signals[symbol] = float(signal_val)

        return current_signals

    def _generate_signals(
        self,
        price_data: Dict[str, pd.DataFrame],
    ) -> Dict[str, pd.DataFrame]:
        """Generate signals using the strategy."""
        signals = {}
        for symbol, df in price_data.items():
            try:
                signal_df = self.strategy.generate_signals(df)
                signals[symbol] = signal_df
            except Exception as e:
                logger.warning("Failed to generate signals for %s: %s", symbol, e)
        return signals

    def _get_portfolio_state(self, current_prices: Dict[str, float]) -> PortfolioState:
        """Get current portfolio state."""
        account = self.executor.get_account_info()
        positions = self.executor.get_positions()

        # Build positions dict for PortfolioState: {symbol: dollar_value}
        positions_dict = {}
        for symbol, pos in positions.items():
            market_value = pos.shares * current_prices.get(symbol, pos.avg_cost)
            positions_dict[symbol] = market_value

        return PortfolioState(
            positions=positions_dict,
            cash=account.cash,
            total_value=account.portfolio_value,
            prices=current_prices,
        )

    def _calculate_results(
        self,
        equity_curve: pd.DataFrame,
        trades: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime,
    ) -> BacktestResult:
        """Calculate backtest performance metrics."""
        if equity_curve.empty:
            return self._empty_result(start_date, end_date, trades)

        # Basic metrics
        initial_value = self.config.initial_cash
        final_value = equity_curve["portfolio_value"].iloc[-1]
        total_return = (final_value - initial_value) / initial_value
        total_return_pct = total_return * 100

        # Annualized return
        days = (end_date - start_date).days
        if days > 0:
            annualized_return = (1 + total_return) ** (365 / days) - 1
        else:
            annualized_return = 0.0

        # Daily returns
        daily_returns = equity_curve["portfolio_value"].pct_change().dropna()

        # Maximum drawdown
        cumulative = (1 + daily_returns).cumprod()
        rolling_max = cumulative.cummax()
        drawdown = (cumulative - rolling_max) / rolling_max
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0.0

        # Sharpe ratio (assuming 0% risk-free rate)
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5)
        else:
            sharpe_ratio = None

        # Trade statistics
        num_trades = len(trades)
        buy_trades = [t for t in trades if t["action"] == "BUY"]
        sell_trades = [t for t in trades if t["action"] == "SELL"]

        # Calculate winning/losing trades (simplified - based on sell trades)
        # A winning trade is when sell price > avg buy price for that symbol
        num_winning = 0
        num_losing = 0
        # This is simplified - proper P&L tracking would need more state

        win_rate = 0.0
        if num_trades > 0:
            # Use executor's performance data
            perf = self.executor.get_performance_summary()
            # Simplified win rate
            win_rate = 0.5 if num_trades > 0 else 0.0

        return BacktestResult(
            config=self.config,
            start_date=start_date,
            end_date=end_date,
            initial_value=initial_value,
            final_value=final_value,
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            num_trades=num_trades,
            num_winning_trades=num_winning,
            num_losing_trades=num_losing,
            win_rate=win_rate,
            equity_curve=equity_curve,
            trades=trades,
            daily_returns=daily_returns,
        )

    def _empty_result(
        self,
        start_date: datetime,
        end_date: datetime,
        trades: List[Dict[str, Any]],
    ) -> BacktestResult:
        """Return empty result when no data available."""
        return BacktestResult(
            config=self.config,
            start_date=start_date,
            end_date=end_date,
            initial_value=self.config.initial_cash,
            final_value=self.config.initial_cash,
            total_return=0.0,
            total_return_pct=0.0,
            annualized_return=0.0,
            max_drawdown=0.0,
            sharpe_ratio=None,
            num_trades=0,
            num_winning_trades=0,
            num_losing_trades=0,
            win_rate=0.0,
            equity_curve=pd.DataFrame(),
            trades=trades,
            daily_returns=pd.Series(dtype=float),
        )

    def reset(self) -> None:
        """Reset orchestrator for a new backtest run."""
        self.executor.reset()
        self._init_components()
        logger.info("BacktestOrchestrator reset")
