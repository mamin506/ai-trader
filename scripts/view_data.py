#!/usr/bin/env python3
"""Interactive data viewer CLI."""

import sys
import click
from datetime import datetime, timedelta

# Add src to path
sys.path.append(".")

from src.api.data_api import DataAPI


@click.group()
def cli():
    """AI Trader Data Viewer"""
    pass


@cli.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option("--days", type=int, help="Number of days from today (alternative to start/end)")
@click.option("--start", type=str, help="Start date (YYYY-MM-DD)")
@click.option("--end", type=str, help="End date (YYYY-MM-DD)")
@click.option("--plot/--no-plot", default=False, help="Show price chart")
def prices(symbols, days, start, end, plot):
    """View price data for symbols.

    Examples:
        # Last 30 days
        python scripts/view_data.py prices AAPL --days 30

        # Specific date range
        python scripts/view_data.py prices AAPL --start 2024-01-01 --end 2024-12-31

        # Multiple symbols
        python scripts/view_data.py prices AAPL MSFT GOOGL --days 10
    """
    data_api = DataAPI()

    # Parse date options
    if days:
        # Use days from today
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
    elif start and end:
        # Use explicit date range
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
        except ValueError as e:
            click.echo(f"Error: Invalid date format. Use YYYY-MM-DD. {e}")
            return
    elif start:
        # Start provided, use today as end
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.now()
        except ValueError as e:
            click.echo(f"Error: Invalid date format. Use YYYY-MM-DD. {e}")
            return
    else:
        # Default: last 30 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

    click.echo(f"Date range: {start_date.date()} to {end_date.date()}")

    for symbol in symbols:
        click.echo(f"\n{'='*60}")
        click.echo(f"Symbol: {symbol}")
        click.echo(f"{'='*60}")

        try:
            data = data_api.get_daily_bars(symbol, start=start_date, end=end_date)

            if data.empty:
                click.echo(f"No data found for {symbol}")
                continue

            click.echo(f"\nRows: {len(data)}")
            click.echo(f"Date range: {data.index[0].date()} to {data.index[-1].date()}")
            click.echo(f"\nFirst 5 rows:")
            click.echo(data.head().to_string())
            click.echo(f"\nLast 5 rows:")
            click.echo(data.tail().to_string())

            # Summary statistics
            click.echo(f"\nSummary:")
            click.echo(f"  Latest Close: ${data['close'].iloc[-1]:.2f}")
            click.echo(f"  High: ${data['high'].max():.2f}")
            click.echo(f"  Low: ${data['low'].min():.2f}")
            click.echo(f"  Avg Volume: {data['volume'].mean():,.0f}")

            if plot:
                # We haven't implemented plotting yet, so mostly a placeholder
                click.echo(f"\nPlotting {symbol} (ASCII approximation):")
                click.echo("(Plotting library not fully integrated yet, check back later)")

        except Exception as e:
            click.echo(f"Error fetching {symbol}: {e}")
            import traceback
            traceback.print_exc()


@cli.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option("--days", type=int, help="Number of days from today (alternative to start/end)")
@click.option("--start", type=str, help="Start date (YYYY-MM-DD)")
@click.option("--end", type=str, help="End date (YYYY-MM-DD)")
def update(symbols, days, start, end):
    """Update/fetch market data for symbols.

    Examples:
        # Update last 30 days
        python scripts/view_data.py update AAPL MSFT --days 30

        # Update specific date range
        python scripts/view_data.py update AAPL --start 2023-01-01 --end 2024-12-31

        # Update to today (from start)
        python scripts/view_data.py update AAPL --start 2024-01-01
    """
    data_api = DataAPI()

    # Parse date options
    if days:
        # Use days from today
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
    elif start and end:
        # Use explicit date range
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
        except ValueError as e:
            click.echo(f"Error: Invalid date format. Use YYYY-MM-DD. {e}")
            return
    elif start:
        # Start provided, use today as end
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.now()
        except ValueError as e:
            click.echo(f"Error: Invalid date format. Use YYYY-MM-DD. {e}")
            return
    else:
        # Default: last 365 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)

    click.echo(f"Updating data for: {', '.join(symbols)}")
    click.echo(f"Date range: {start_date.date()} to {end_date.date()}")

    for symbol in symbols:
        click.echo(f"\nFetching {symbol}...")
        try:
            data = data_api.get_daily_bars(symbol, start=start_date, end=end_date)

            if data.empty:
                click.echo(f"  No data found for {symbol}")
            else:
                click.echo(f"  ✓ Fetched {len(data)} rows")
                click.echo(f"    Date range: {data.index[0].date()} to {data.index[-1].date()}")

        except Exception as e:
            click.echo(f"  ✗ Error: {e}")

    click.echo("\n✓ Update complete")


if __name__ == "__main__":
    cli()
