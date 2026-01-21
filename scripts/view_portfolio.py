#!/usr/bin/env python3
"""Portfolio analysis and backtesting CLI tool.

This script provides comprehensive portfolio analysis capabilities:
- Run backtests with multiple strategies
- Compare strategy performance
- View portfolio allocation and rebalancing
- Analyze risk metrics

Examples:
    # Run MA Crossover backtest on multiple symbols
    python scripts/view_portfolio.py backtest AAPL MSFT GOOGL \\
        --strategy ma-crossover --start 2024-01-01 --end 2024-12-31

    # Run backtest with custom parameters
    python scripts/view_portfolio.py backtest AAPL MSFT \\
        --strategy ma-crossover -p fast_period=10 -p slow_period=30 \\
        --capital 100000 --rebalance weekly

    # Compare multiple strategy configurations
    python scripts/view_portfolio.py compare AAPL MSFT GOOGL \\
        --start 2024-01-01 --end 2024-12-31

    # View detailed backtest results with trades
    python scripts/view_portfolio.py backtest AAPL MSFT \\
        --strategy ma-crossover --show-trades --show-equity
"""

import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import click

# Add src to path
sys.path.append(".")

from src.api.backtest_api import BacktestAPI
from src.api.data_api import DataAPI
from src.strategy.ma_crossover import MACrossoverStrategy


def parse_params(param_list: tuple) -> Dict:
    """Parse parameter strings into a dictionary.

    Args:
        param_list: Tuple of "key=value" strings

    Returns:
        Dictionary of parameters with proper types
    """
    params = {}
    for param in param_list:
        if "=" not in param:
            click.echo(f"Warning: Invalid parameter '{param}', expected 'key=value'")
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
        strategy_name: Strategy identifier
        params: Strategy parameters

    Returns:
        Strategy instance
    """
    if strategy_name in ["ma-crossover", "ma_crossover", "mac"]:
        default_params = {
            "fast_period": 50,
            "slow_period": 200,
        }
        default_params.update(params)
        return MACrossoverStrategy(default_params)
    else:
        raise ValueError(
            f"Unknown strategy: {strategy_name}. "
            f"Available: ma-crossover"
        )


@click.group()
def cli():
    """AI Trader Portfolio Analysis Tool"""
    pass


@cli.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option("--strategy", default="ma-crossover", help="Strategy name")
@click.option("--start", type=str, help="Start date (YYYY-MM-DD)")
@click.option("--end", type=str, help="End date (YYYY-MM-DD)")
@click.option("--capital", type=float, default=100000.0, help="Initial capital")
@click.option("--param", "-p", multiple=True, help="Strategy parameter (key=value)")
@click.option("--rebalance", default="daily", help="Rebalance frequency: daily/weekly/monthly")
@click.option("--max-positions", type=int, default=10, help="Max number of positions")
@click.option("--show-trades", is_flag=True, help="Show all trades")
@click.option("--show-equity", is_flag=True, help="Show equity curve")
def backtest(
    symbols: tuple,
    strategy: str,
    start: Optional[str],
    end: Optional[str],
    capital: float,
    param: tuple,
    rebalance: str,
    max_positions: int,
    show_trades: bool,
    show_equity: bool,
):
    """Run backtest on portfolio of symbols.

    SYMBOLS: Stock ticker symbols (e.g., AAPL MSFT GOOGL)

    Examples:

        \b
        # Basic backtest
        python scripts/view_portfolio.py backtest AAPL MSFT GOOGL

        \b
        # Custom parameters
        python scripts/view_portfolio.py backtest AAPL MSFT \\
            -p fast_period=10 -p slow_period=30 --capital 50000
    """
    # Set default date range
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    if start is None:
        start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    # Header
    click.echo("=" * 70)
    click.echo("AI TRADER - PORTFOLIO BACKTEST")
    click.echo("=" * 70)
    click.echo(f"Strategy:      {strategy}")
    click.echo(f"Symbols:       {', '.join(symbols)}")
    click.echo(f"Period:        {start} to {end}")
    click.echo(f"Capital:       ${capital:,.2f}")
    click.echo(f"Rebalance:     {rebalance}")
    click.echo(f"Max Positions: {max_positions}")

    # Parse strategy parameters
    strategy_params = parse_params(param)
    if strategy_params:
        click.echo(f"Parameters:    {strategy_params}")
    click.echo("=" * 70)
    click.echo()

    try:
        # Initialize API
        click.echo("Initializing backtest engine...")
        api = BacktestAPI()

        # Get strategy
        strategy_instance = get_strategy(strategy, strategy_params)
        click.echo(f"✓ Strategy loaded: {strategy} with {strategy_instance.params}")
        click.echo()

        # Run backtest
        click.echo(f"Running backtest on {len(symbols)} symbols...")
        result = api.run_backtest(
            strategy=strategy_instance,
            symbols=list(symbols),
            start_date=start,
            end_date=end,
            initial_cash=capital,
            rebalance_frequency=rebalance,
            max_positions=max_positions,
        )

        click.echo("✓ Backtest complete")
        click.echo()

        # Display results
        click.echo(api.format_results(result))

        # Show trades if requested
        if show_trades:
            click.echo()
            click.echo("=" * 70)
            click.echo("TRADE HISTORY")
            click.echo("=" * 70)
            trades = api.get_trades(result)

            if trades.empty:
                click.echo("No trades executed")
            else:
                # Format trades nicely
                for idx, trade in trades.iterrows():
                    date_str = trade['date'].strftime('%Y-%m-%d') if hasattr(trade['date'], 'strftime') else str(trade['date'])
                    click.echo(
                        f"{date_str} | {trade['action']:4s} | {trade['symbol']:6s} | "
                        f"{trade['shares']:>6.0f} shares @ ${trade['price']:>8.2f}"
                    )

        # Show equity curve if requested
        if show_equity:
            click.echo()
            click.echo("=" * 70)
            click.echo("EQUITY CURVE (Last 10 Days)")
            click.echo("=" * 70)
            equity = api.get_equity_curve(result)

            if not equity.empty:
                # Show last 10 rows
                display_cols = ['portfolio_value', 'cash', 'positions_value']
                available_cols = [c for c in display_cols if c in equity.columns]

                click.echo(equity[available_cols].tail(10).to_string())
            else:
                click.echo("No equity data available")

    except Exception as e:
        click.echo(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option("--start", type=str, help="Start date (YYYY-MM-DD)")
@click.option("--end", type=str, help="End date (YYYY-MM-DD)")
@click.option("--capital", type=float, default=100000.0, help="Initial capital")
@click.option("--rebalance", default="weekly", help="Rebalance frequency")
def compare(
    symbols: tuple,
    start: Optional[str],
    end: Optional[str],
    capital: float,
    rebalance: str,
):
    """Compare multiple MA Crossover configurations.

    Tests different fast/slow MA period combinations and compares results.

    SYMBOLS: Stock ticker symbols

    Examples:

        \b
        # Compare strategies on tech stocks
        python scripts/view_portfolio.py compare AAPL MSFT GOOGL
    """
    # Set default date range
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    if start is None:
        start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    # Header
    click.echo("=" * 90)
    click.echo("AI TRADER - STRATEGY COMPARISON")
    click.echo("=" * 90)
    click.echo(f"Symbols:   {', '.join(symbols)}")
    click.echo(f"Period:    {start} to {end}")
    click.echo(f"Capital:   ${capital:,.2f}")
    click.echo(f"Rebalance: {rebalance}")
    click.echo("=" * 90)
    click.echo()

    # Define strategy configurations to compare
    configs = {
        "MA(10/30)": {"fast_period": 10, "slow_period": 30},
        "MA(20/50)": {"fast_period": 20, "slow_period": 50},
        "MA(50/200)": {"fast_period": 50, "slow_period": 200},
    }

    try:
        api = BacktestAPI()
        results = {}

        # Run backtest for each configuration
        for name, params in configs.items():
            click.echo(f"Testing {name}...")
            strategy = MACrossoverStrategy(params)

            result = api.run_backtest(
                strategy=strategy,
                symbols=list(symbols),
                start_date=start,
                end_date=end,
                initial_cash=capital,
                rebalance_frequency=rebalance,
            )

            results[name] = result
            click.echo(f"✓ {name} complete")

        click.echo()

        # Display comparison
        click.echo(api.format_comparison(results))

        # Show best performer
        click.echo()
        best_name = max(results.keys(), key=lambda x: results[x].total_return)
        best_return = results[best_name].total_return_pct

        click.echo(f"🏆 Best Performer: {best_name} ({best_return:.2f}%)")

    except Exception as e:
        click.echo(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
