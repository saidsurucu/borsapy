"""
Scan command - Technical scanning.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import (
    OutputFormat,
    create_scan_table,
    output_csv,
    output_json,
    output_table,
)
from borsapy.cli.utils import console, handle_error, parse_interval


def scan(
    condition: Annotated[str, typer.Argument(help="Scan condition (e.g., 'rsi < 30', 'close > sma_50')")],
    index: Annotated[
        str,
        typer.Option("--index", "-x", help="Index to scan (XU030, XU100, XBANK, etc.)"),
    ] = "XU030",
    interval: Annotated[
        str,
        typer.Option("--interval", "-i", help="Timeframe for indicators"),
    ] = "1d",
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum number of results"),
    ] = 20,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Scan for stocks matching technical conditions.

    Supported conditions:
        - rsi < 30, rsi > 70
        - close > sma_50, close < sma_200
        - macd > signal
        - volume > 1000000
        - change_percent > 3

    Compound conditions:
        - rsi < 30 and volume > 1000000

    Crossover conditions:
        - sma_20 crosses_above sma_50
        - macd crosses signal

    Examples:
        borsapy scan "rsi < 30" --index XU030
        borsapy scan "close > sma_50" --index XU100
        borsapy scan "rsi < 30 and volume > 1000000"
        borsapy scan "macd > signal" --interval 1h
        borsapy scan "change_percent > 3" --index XBANK
    """
    import borsapy as bp

    interval = parse_interval(interval)

    with console.status(f"[bold green]Scanning {index} for '{condition}'..."):
        try:
            results = bp.scan(index, condition, interval=interval)

            if results is None or (hasattr(results, "empty") and results.empty):
                console.print(f"[yellow]No stocks match '{condition}'[/yellow]")
                raise typer.Exit(0)

            # Limit results
            if hasattr(results, "head"):
                results = results.head(limit)

        except typer.Exit:
            raise
        except Exception as e:
            handle_error(e)
            raise typer.Exit(1) from None

    # Output
    if output == "json":
        output_json(results.to_dict(orient="records") if hasattr(results, "to_dict") else results)
    elif output == "csv":
        output_csv(results)
    else:
        output_table(create_scan_table(results))
        count = len(results) if hasattr(results, "__len__") else "?"
        console.print(f"\n[dim]Found {count} matches[/dim]")
