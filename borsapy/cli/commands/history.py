"""
History command - OHLCV data export.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import (
    OutputFormat,
    create_history_table,
    output_csv,
    output_json,
    output_table,
)
from borsapy.cli.utils import (
    AssetType,
    HistoryInterval,
    Period,
    console,
    get_asset,
    handle_error,
)


def history(
    symbol: Annotated[str, typer.Argument(help="Symbol to get history for")],
    period: Annotated[
        Period,
        typer.Option("--period", "-p", help="Time period"),
    ] = "1mo",
    interval: Annotated[
        HistoryInterval,
        typer.Option("--interval", "-i", help="Data interval"),
    ] = "1d",
    asset_type: Annotated[
        AssetType | None,
        typer.Option("--type", "-t", help="Asset type (auto-detected if not specified)"),
    ] = None,
    actions: Annotated[
        bool,
        typer.Option("--actions", "-a", help="Include dividends and stock splits"),
    ] = False,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get historical OHLCV data for a symbol.

    Data is written to stdout, so you can pipe it to a file:
        borsapy history THYAO --period 1y --output csv > thyao.csv

    Examples:
        borsapy history THYAO
        borsapy history THYAO --period 1y --interval 1d
        borsapy history THYAO --period 5d --interval 1h
        borsapy history USD --type fx --period 1mo
        borsapy history THYAO --actions  # Include dividends/splits
        borsapy history THYAO --output csv > data.csv
        borsapy history THYAO --output json
    """
    symbol = symbol.strip().upper()

    with console.status(f"[bold green]Fetching {symbol} history..."):
        try:
            asset = get_asset(symbol, asset_type)

            # Get history
            if hasattr(asset, "history"):
                if actions and hasattr(asset, "history"):
                    # Try with actions parameter
                    try:
                        df = asset.history(period=period, interval=interval, actions=True)
                    except TypeError:
                        # Fallback if actions not supported
                        df = asset.history(period=period, interval=interval)
                else:
                    df = asset.history(period=period, interval=interval)
            else:
                console.print(f"[red]History not available for {symbol}[/red]")
                raise typer.Exit(1) from None

            if df is None or df.empty:
                console.print(f"[yellow]No data found for {symbol}[/yellow]")
                raise typer.Exit(1) from None

        except typer.Exit:
            raise
        except Exception as e:
            handle_error(e, symbol)
            raise typer.Exit(1) from None

    # Output
    if output == "json":
        # Convert index to string for JSON
        df_json = df.copy()
        df_json.index = df_json.index.astype(str)
        output_json(df_json.to_dict(orient="index"))
    elif output == "csv":
        output_csv(df)
    else:
        output_table(create_history_table(df, symbol))
        console.print(f"\n[dim]Showing last 10 of {len(df)} rows. Use --output csv for full data.[/dim]")
