"""
Watch command - Real-time monitoring.
"""

import time
from typing import Annotated

import typer
from rich.live import Live
from rich.table import Table

from borsapy.cli.utils import (
    console,
    format_change,
    format_number,
    format_percent,
    get_change_color,
    handle_error,
    validate_symbols,
)


def create_watch_table(quotes: dict[str, dict]) -> Table:
    """Create a live-updating price table."""
    table = Table(title="Live Prices", show_header=True, header_style="bold cyan")
    table.add_column("Symbol", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Bid", justify="right")
    table.add_column("Ask", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("Change %", justify="right")
    table.add_column("Volume", justify="right")

    for symbol, q in quotes.items():
        if q is None:
            table.add_row(symbol, "[dim]waiting...[/dim]", "", "", "", "", "")
            continue

        change = q.get("change")
        change_pct = q.get("change_percent")
        color = get_change_color(change)

        table.add_row(
            symbol,
            format_number(q.get("last")),
            format_number(q.get("bid")),
            format_number(q.get("ask")),
            f"[{color}]{format_change(change)}[/{color}]",
            f"[{color}]{format_percent(change_pct)}[/{color}]",
            format_number(q.get("volume"), 0),
        )

    return table


def watch(
    symbols: Annotated[list[str], typer.Argument(help="Symbols to watch")],
    interval: Annotated[
        float,
        typer.Option("--interval", "-i", help="Update interval in seconds"),
    ] = 1.0,
    duration: Annotated[
        int | None,
        typer.Option("--duration", "-d", help="Duration in seconds (infinite if not set)"),
    ] = None,
) -> None:
    """
    Watch real-time prices using TradingView WebSocket streaming.

    Press Ctrl+C to stop.

    Examples:
        borsapy watch THYAO GARAN ASELS
        borsapy watch THYAO --interval 0.5
        borsapy watch THYAO GARAN --duration 60
    """
    import borsapy as bp

    symbols = validate_symbols(symbols)
    if not symbols:
        raise typer.BadParameter("At least one symbol is required")

    console.print(f"[bold green]Starting watch for {', '.join(symbols)}...[/bold green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    # Initialize stream
    try:
        stream = bp.TradingViewStream()
        stream.connect()

        # Subscribe to all symbols
        for symbol in symbols:
            stream.subscribe(symbol)

        # Wait for initial quotes
        console.print("[dim]Waiting for initial data...[/dim]")
        time.sleep(2)

        # Initialize quotes dict
        quotes = dict.fromkeys(symbols)

        start_time = time.time()

        with Live(create_watch_table(quotes), refresh_per_second=2, console=console) as live:
            try:
                while True:
                    # Update quotes
                    for symbol in symbols:
                        quote = stream.get_quote(symbol)
                        if quote:
                            quotes[symbol] = quote

                    live.update(create_watch_table(quotes))

                    # Check duration
                    if duration and (time.time() - start_time) >= duration:
                        break

                    time.sleep(interval)

            except KeyboardInterrupt:
                pass

    except Exception as e:
        handle_error(e)
        raise typer.Exit(1) from None
    finally:
        try:
            stream.disconnect()
        except Exception:
            pass

    console.print("\n[bold green]Watch stopped[/bold green]")
