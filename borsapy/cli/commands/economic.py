"""
Economic command - Economic calendar.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import (
    OutputFormat,
    create_economic_table,
    output_csv,
    output_json,
    output_table,
)
from borsapy.cli.utils import console, handle_error


def economic(
    period: Annotated[
        str,
        typer.Option("--period", "-p", help="Time period (today, 1d, 1w, 1mo)"),
    ] = "1w",
    country: Annotated[
        str | None,
        typer.Option("--country", "-c", help="Filter by country (TR, US, EU, etc.)"),
    ] = None,
    importance: Annotated[
        str | None,
        typer.Option("--importance", "-i", help="Filter by importance (high, medium, low)"),
    ] = None,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Display economic calendar events.

    Examples:
        borsapy economic
        borsapy economic --period today
        borsapy economic --country TR
        borsapy economic --importance high
        borsapy economic --country TR --importance high
        borsapy economic --output json
    """
    import borsapy as bp

    # Map period aliases
    period_map = {
        "today": "1d",
        "tomorrow": "1d",
        "week": "1w",
        "month": "1mo",
    }
    period = period_map.get(period.lower(), period)

    with console.status("[bold green]Fetching economic calendar..."):
        try:
            cal = bp.EconomicCalendar()

            # Get events with filters
            events = cal.events(period=period, country=country, importance=importance)

            if events is None or (hasattr(events, "empty") and events.empty):
                console.print("[yellow]No events found[/yellow]")
                raise typer.Exit(0)

        except typer.Exit:
            raise
        except Exception as e:
            handle_error(e)
            raise typer.Exit(1) from None

    # Output
    if output == "json":
        output_json(events.to_dict(orient="records") if hasattr(events, "to_dict") else events)
    elif output == "csv":
        output_csv(events)
    else:
        output_table(create_economic_table(events))
        count = len(events) if hasattr(events, "__len__") else "?"
        console.print(f"\n[dim]Showing {min(30, count)} of {count} events[/dim]")
