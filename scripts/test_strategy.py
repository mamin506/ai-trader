#!/usr/bin/env python3
"""Strategy testing CLI tool.

This script provides an easy way to test trading strategies from the command line.
You can specify the strategy, symbol, date range, and strategy parameters.

Examples:
    # Test MA Crossover on AAPL for 2024
    python scripts/test_strategy.py ma-crossover AAPL --start 2024-01-01 --end 2024-12-31

    # Test with custom MA periods
    python scripts/test_strategy.py ma-crossover AAPL --start 2024-01-01 --end 2024-12-31 \\
        --param fast_period=10 --param slow_period=30

    # Test with custom initial capital
    python scripts/test_strategy.py ma-crossover AAPL --start 2024-01-01 --end 2024-12-31 \\
        --capital 50000

    # Show strategy data with indicators
    python scripts/test_strategy.py ma-crossover AAPL --start 2024-01-01 --end 2024-12-31 \\
        --show-data

    # Just show signals without backtest
    python scripts/test_strategy.py ma-crossover AAPL --start 2024-01-01 --end 2024-12-31 \\
        --signals-only
"""

import sys
from datetime import datetime, timedelta
from typing import Dict, Optional

import click

# Add src to path
sys.path.append(".")

from src.api.data_api import DataAPI
from src.api.strategy_api import StrategyAPI
from src.strategy.ma_crossover import MACrossoverStrategy


def parse_params(param_list: tuple) -> Dict:
    """Parse parameter strings into a dictionary.

    Args:
        param_list: Tuple of "key=value" strings

    Returns:
        Dictionary of parameters with proper types

    Example:
        >>> parse_params(("fast_period=10", "slow_period=20"))
        {'fast_period': 10, 'slow_period': 20}
    """
    params = {}
    for param in param_list:
        if "=" not in param:
            click.echo(f"Warning: Invalid parameter format '{param}', expected 'key=value'")
            continue

        key, value = param.split("=", 1)

        # Try to convert to int, then float, otherwise keep as string
        try:
            params[key] = int(value)
        except ValueError:
            try:
                params[key] = float(value)
            except ValueError:
                params[key] = value

    return params


def get_strategy(strategy_name: str, params: Dict):
    """Get strategy instance by name.

    Args:
        strategy_name: Strategy identifier (e.g., 'ma-crossover')
        params: Strategy parameters

    Returns:
        Strategy instance

    Raises:
        ValueError: If strategy name is not recognized
    """
    if strategy_name in ["ma-crossover", "ma_crossover", "mac"]:
        # Set default parameters for MA Crossover
        default_params = {
            "fast_period": 20,
            "slow_period": 50,
            "min_required_rows": 60,
        }
        default_params.update(params)
        return MACrossoverStrategy(default_params)
    else:
        raise ValueError(
            f"Unknown strategy: {strategy_name}. "
            f"Available strategies: ma-crossover"
        )


@click.command()
@click.argument("strategy", type=str)
@click.argument("symbol", type=str)
@click.option(
    "--start",
    type=str,
    help="Start date (YYYY-MM-DD). Default: 1 year ago",
)
@click.option(
    "--end",
    type=str,
    help="End date (YYYY-MM-DD). Default: today",
)
@click.option(
    "--param",
    "-p",
    multiple=True,
    help="Strategy parameter (key=value). Can be specified multiple times.",
)
@click.option(
    "--capital",
    type=float,
    default=10000.0,
    help="Initial capital for backtest (default: $10,000)",
)
@click.option(
    "--signals-only",
    is_flag=True,
    help="Only show signals, skip backtest",
)
@click.option(
    "--show-data",
    is_flag=True,
    help="Show data with indicators (last 10 rows)",
)
def test_strategy(
    strategy: str,
    symbol: str,
    start: Optional[str],
    end: Optional[str],
    param: tuple,
    capital: float,
    signals_only: bool,
    show_data: bool,
):
    """Test a trading strategy on historical data.

    STRATEGY: Name of the strategy to test (e.g., 'ma-crossover')
    SYMBOL: Stock ticker symbol (e.g., 'AAPL', 'TSLA')

    Examples:

        \b
        # Test MA Crossover on AAPL for 2024
        python scripts/test_strategy.py ma-crossover AAPL --start 2024-01-01 --end 2024-12-31

        \b
        # Test with custom MA periods
        python scripts/test_strategy.py ma-crossover AAPL -p fast_period=10 -p slow_period=30

        \b
        # Show strategy data with indicators
        python scripts/test_strategy.py ma-crossover AAPL --show-data
    """
    # Set default date range if not provided
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    if start is None:
        start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    click.echo("=" * 70)
    click.echo(f"AI Trader - Strategy Testing Tool")
    click.echo("=" * 70)
    click.echo(f"Strategy:      {strategy}")
    click.echo(f"Symbol:        {symbol}")
    click.echo(f"Period:        {start} to {end}")
    click.echo(f"Initial Cap:   ${capital:,.2f}")

    # Parse strategy parameters
    strategy_params = parse_params(param)
    if strategy_params:
        click.echo(f"Parameters:    {strategy_params}")

    click.echo("=" * 70)
    click.echo()

    try:
        # Initialize APIs
        click.echo("Initializing APIs...")
        data_api = DataAPI()
        strategy_api = StrategyAPI(data_api=data_api)

        # Get strategy instance
        click.echo(f"Loading strategy: {strategy}...")
        strategy_instance = get_strategy(strategy, strategy_params)
        click.echo(f"✓ Strategy loaded with params: {strategy_instance.params}")
        click.echo()

        # Fetch data
        click.echo(f"Fetching historical data for {symbol}...")
        data = data_api.get_daily_bars(symbol, start, end)

        if data.empty:
            click.echo(f"✗ No data available for {symbol} in the specified period")
            return

        click.echo(f"✓ Fetched {len(data)} trading days")
        click.echo()

        # Validate data
        if not strategy_instance.validate_data(data):
            click.echo("✗ Data validation failed")
            click.echo(f"  - Strategy requires at least {strategy_instance.params.get('min_required_rows', 100)} rows")
            click.echo(f"  - Available: {len(data)} rows")
            click.echo()
            click.echo("Tip: Try a longer date range or adjust min_required_rows parameter")
            return

        # Generate signals
        click.echo("Generating trading signals...")
        signals = strategy_api.get_signals(symbol, strategy_instance, start, end)

        if signals.empty:
            click.echo("✗ No signals generated")
            return

        buy_signals = (signals == 1.0).sum()
        sell_signals = (signals == -1.0).sum()
        hold_signals = (signals == 0.0).sum()

        click.echo(f"✓ Generated {len(signals)} signals:")
        click.echo(f"  - Buy signals:  {buy_signals}")
        click.echo(f"  - Sell signals: {sell_signals}")
        click.echo(f"  - Hold signals: {hold_signals}")
        click.echo()

        # Show signal dates
        if buy_signals > 0 or sell_signals > 0:
            click.echo("Signal Timeline:")
            signal_dates = signals[signals != 0.0]
            for date, signal in signal_dates.items():
                signal_type = "BUY " if signal == 1.0 else "SELL"
                click.echo(f"  {date.strftime('%Y-%m-%d')} - {signal_type}")
            click.echo()

        # If signals-only flag, stop here
        if signals_only:
            click.echo("(Skipping backtest as --signals-only was specified)")
            return

        # Run backtest
        click.echo("-" * 70)
        click.echo("Running Backtest...")
        click.echo("-" * 70)

        results = strategy_api.backtest(symbol, strategy_instance, start, end, initial_capital=capital)

        # Display results
        click.echo()
        click.echo("BACKTEST RESULTS")
        click.echo("=" * 70)
        click.echo(f"Initial Capital:        ${results['initial_capital']:>12,.2f}")
        click.echo(f"Final Value:            ${results['final_value']:>12,.2f}")
        click.echo()
        click.echo(f"Strategy Return:        {results['total_return']:>12.2%}")
        click.echo(f"Buy & Hold Return:      {results['buy_and_hold_return']:>12.2%}")
        click.echo()

        # Calculate alpha (strategy return - buy & hold)
        alpha = results['total_return'] - results['buy_and_hold_return']
        alpha_str = f"+{alpha:.2%}" if alpha > 0 else f"{alpha:.2%}"
        click.echo(f"Alpha (vs Buy & Hold): {alpha_str:>13}")
        click.echo()

        click.echo(f"Total Trades:           {results['num_trades']:>12}")
        click.echo(f"Buy Signals:            {results['num_buy_signals']:>12}")
        click.echo(f"Sell Signals:           {results['num_sell_signals']:>12}")
        click.echo(f"Round Trips:            {results['num_round_trips']:>12}")
        click.echo("=" * 70)
        click.echo()

        # Performance interpretation
        if results['total_return'] > results['buy_and_hold_return']:
            click.echo("✓ Strategy OUTPERFORMED buy-and-hold")
        elif results['total_return'] < results['buy_and_hold_return']:
            click.echo("✗ Strategy UNDERPERFORMED buy-and-hold")
        else:
            click.echo("~ Strategy matched buy-and-hold performance")

        click.echo()

        # Show data with indicators if requested
        if show_data:
            click.echo("-" * 70)
            click.echo("Strategy Data (last 10 rows)")
            click.echo("-" * 70)
            strategy_data = strategy_api.get_strategy_data(symbol, strategy_instance, start, end)

            # Show relevant columns
            display_cols = [col for col in strategy_data.columns if col in
                          ['close', 'fast_ma', 'slow_ma', 'signal', 'volume']]

            click.echo(strategy_data[display_cols].tail(10).to_string())
            click.echo()

    except ValueError as e:
        click.echo(f"✗ Error: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_strategy()
