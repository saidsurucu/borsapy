"""
Dividends command - Dividend history for a ticker.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import console, format_number, handle_error


def dividends(
    symbol: Annotated[str, typer.Argument(help="Stock ticker symbol")],
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get dividend history for a stock.

    Examples:
        borsapy dividends THYAO
        borsapy dividends GARAN -o csv
        borsapy dividends THYAO -o json
    """
    from rich.table import Table

    import borsapy as bp

    symbol = symbol.strip().upper()

    with console.status(f"[bold green]Fetching dividends for {symbol}..."):
        try:
            ticker = bp.Ticker(symbol)
            div_df = ticker.dividends

            if div_df is None or div_df.empty:
                console.print(f"[yellow]No dividend history found for {symbol}[/yellow]")
                raise typer.Exit(0)

        except Exception as e:
            handle_error(e, symbol)
            raise typer.Exit(1) from None

    # Output
    if output == "json":
        output_json(div_df)
    elif output == "csv":
        output_csv(div_df)
    else:
        table = Table(
            title=f"{symbol} Dividend History",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Date", style="bold")
        table.add_column("Gross Rate", justify="right")
        table.add_column("Net Rate", justify="right")
        table.add_column("Amount", justify="right")
        table.add_column("Total Dividend", justify="right")

        for idx, row in div_df.iterrows():
            date_str = (
                idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
            )
            table.add_row(
                date_str,
                format_number(row.get("GrossRate", row.get("gross_rate"))),
                format_number(row.get("NetRate", row.get("net_rate"))),
                format_number(row.get("Amount", row.get("amount"))),
                format_number(row.get("TotalDividend", row.get("total_dividend")), 0),
            )

        output_table(table)
