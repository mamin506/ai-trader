#!/usr/bin/env python3
"""Universe selection CLI tool.

This script selects stocks for a trading universe based on filters like
liquidity, price, and market cap.

Examples:
    # Select top 50 liquid stocks
    python scripts/select_universe.py --name liquid_50 --top-n 50

    # Select with price filter
    python scripts/select_universe.py --name mid_price --min-price 20 --max-price 200

    # Select and save to database
    python scripts/select_universe.py --name my_universe --save

    # Load saved universe
    python scripts/select_universe.py --load liquid_50

    # Refresh stock listings cache
    python scripts/select_universe.py --refresh-cache
"""

import sys
from datetime import datetime

import click

sys.path.append(".")

from src.api.universe_api import UniverseAPI


@click.command()
@click.option("--name", default="default", help="Universe name")
@click.option("--load", "load_name", help="Load saved universe by name")
@click.option("--date", type=str, help="Selection date (YYYY-MM-DD)")
@click.option("--top-n", type=int, default=100, help="Number of stocks to select")
@click.option(
    "--exchange",
    multiple=True,
    help="Exchanges to include (e.g., NASDAQ, NYSE)",
)
@click.option("--min-price", type=float, default=5.0, help="Minimum stock price")
@click.option("--max-price", type=float, help="Maximum stock price")
@click.option(
    "--min-volume",
    type=float,
    default=1_000_000,
    help="Minimum average daily volume",
)
@click.option("--min-market-cap", type=float, help="Minimum market cap")
@click.option("--max-market-cap", type=float, help="Maximum market cap")
@click.option("--save", is_flag=True, help="Save universe to database")
@click.option("--refresh-cache", is_flag=True, help="Refresh stock listings cache")
def main(
    name,
    load_name,
    date,
    top_n,
    exchange,
    min_price,
    max_price,
    min_volume,
    min_market_cap,
    max_market_cap,
    save,
    refresh_cache,
):
    """Select stocks for a trading universe.

    By default, selects top N stocks from NASDAQ and NYSE based on liquidity.

    Examples:

        \b
        # Select top 50 most liquid stocks
        python scripts/select_universe.py --name liquid_50 --top-n 50 --save

        \b
        # Select stocks priced between $20-$200
        python scripts/select_universe.py --min-price 20 --max-price 200

        \b
        # Load saved universe
        python scripts/select_universe.py --load liquid_50

        \b
        # Refresh listings cache
        python scripts/select_universe.py --refresh-cache
    """
    api = UniverseAPI()

    # Refresh cache if requested
    if refresh_cache:
        click.echo("Refreshing stock listings cache...")
        count = api.refresh_listings_cache()
        click.echo(f"✓ Fetched {count} stock listings from AlphaVantage")
        return

    # Load universe if requested
    if load_name:
        click.echo(f"Loading universe '{load_name}'...")
        try:
            symbols = api.load_universe(load_name, date=date)
            click.echo(f"✓ Loaded {len(symbols)} symbols")
            click.echo()
            click.echo("Symbols:")
            for i, symbol in enumerate(symbols, 1):
                click.echo(f"  {i:3d}. {symbol}")
        except ValueError as e:
            click.echo(f"✗ Error: {e}")
            sys.exit(1)
        return

    # Select universe
    click.echo("=" * 70)
    click.echo("UNIVERSE SELECTION")
    click.echo("=" * 70)
    click.echo(f"Name:            {name}")
    click.echo(f"Top N:           {top_n}")
    click.echo(f"Min Price:       ${min_price:.2f}")
    if max_price:
        click.echo(f"Max Price:       ${max_price:.2f}")
    click.echo(f"Min Volume:      {min_volume:,.0f} shares/day")
    if exchange:
        click.echo(f"Exchanges:       {', '.join(exchange)}")
    else:
        click.echo(f"Exchanges:       NASDAQ, NYSE, NYSE ARCA (default)")
    click.echo("=" * 70)
    click.echo()

    try:
        click.echo("Selecting universe...")

        exchanges = list(exchange) if exchange else None

        symbols = api.select_universe(
            name=name,
            date=date,
            top_n=top_n,
            exchanges=exchanges,
            min_price=min_price,
            max_price=max_price,
            min_avg_volume=min_volume,
            min_market_cap=min_market_cap,
            max_market_cap=max_market_cap,
            save=save,
        )

        click.echo(f"✓ Selected {len(symbols)} stocks")
        click.echo()

        # Display symbols
        click.echo("=" * 70)
        click.echo("SELECTED SYMBOLS")
        click.echo("=" * 70)

        # Show in columns
        cols = 5
        for i in range(0, len(symbols), cols):
            row = symbols[i : i + cols]
            click.echo("  " + "  ".join(f"{s:6s}" for s in row))

        click.echo("=" * 70)
        click.echo()

        if save:
            click.echo(f"✓ Saved universe '{name}' to database")
            if date:
                click.echo(f"  Date: {date}")
            else:
                click.echo(f"  Date: {datetime.now().strftime('%Y-%m-%d')}")

    except Exception as e:
        click.echo(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
