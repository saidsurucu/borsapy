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
from borsapy.cli.utils import IndexType, ScanInterval, console, handle_error


def scan(
    condition: Annotated[str, typer.Argument(help="Scan condition (e.g., 'rsi < 30', 'close > sma_50')")],
    index: Annotated[
        IndexType,
        typer.Option("--index", "-x", help="Index to scan"),
    ] = "XU030",
    interval: Annotated[
        ScanInterval,
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

    SUPPORTED FIELDS:

      Price: price, close, open, high, low, volume, change_percent, market_cap

      RSI: rsi, rsi_7, rsi_14

      SMA: sma_5, sma_10, sma_20, sma_30, sma_50, sma_100, sma_200

      EMA: ema_5, ema_10, ema_12, ema_20, ema_26, ema_50, ema_100, ema_200

      MACD: macd, signal, histogram

      Stochastic: stoch_k, stoch_d

      Other: adx, bb_upper, bb_middle, bb_lower, atr, cci, wr

    OPERATORS:

      Comparison: <, >, <=, >=, ==

      Logical: and, or

      Crossover: crosses_above, crosses_below, crosses

      Percent: above_pct, below_pct (e.g., "close above_pct sma_50 1.05")

    Examples:
        borsapy scan "rsi < 30" --index XU030
        borsapy scan "close > sma_50" --index XU100
        borsapy scan "rsi < 30 and volume > 1000000"
        borsapy scan "macd > signal" --interval 1h
        borsapy scan "sma_20 crosses_above sma_50" --index XBANK
        borsapy scan "change_percent > 3"
    """
    import borsapy as bp

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
