#!/usr/bin/env python3
"""Interactive data viewer CLI."""

import sys
import click
# Add src to path
sys.path.append(".")

from src.api.data_api import DataAPI

@click.group()
def cli():
    """AI Trader Data Viewer"""
    pass

@cli.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option("--days", default=30, help="Number of days to show")
@click.option("--plot/--no-plot", default=True, help="Show price chart")
def prices(symbols, days, plot):
    """View price data for symbols."""
    data_api = DataAPI()

    for symbol in symbols:
        click.echo(f"\nFetching data for {symbol}...")
        try:
            data = data_api.get_latest(symbol, days=days)
            if data.empty:
                click.echo(f"No data found for {symbol}")
                continue

            click.echo(data)

            if plot:
                # We haven't implemented plotting yet, so mostly a placeholder
                # or basic print
                click.echo(f"Plotting {symbol} (ASCII approximation):")
                # Simple ASCII sparkline if needed, or just a note
                click.echo(
                    "(Plotting library not fully integrated yet, check back later)"
                )

        except Exception as e:
            click.echo(f"Error fetching {symbol}: {e}")

@cli.command()
@click.argument("symbols", nargs=-1)
def update(symbols):
    """Update market data."""
    data_api = DataAPI()
    target_symbols = list(symbols) if symbols else None

    target_str = (
        target_symbols if target_symbols else "all configured symbols"
    )
    click.echo(f"Updating data for {target_str}...")
    try:
        data_api.update_data(target_symbols)
        click.echo("✓ Data updated successfully")
    except Exception as e:
        click.echo(f"Error updating data: {e}")

if __name__ == "__main__":
    cli()
