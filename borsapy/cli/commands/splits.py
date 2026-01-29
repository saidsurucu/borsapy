"""
Splits command - Capital increases (stock splits) for a ticker.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import console, format_number, handle_error


def splits(
    symbol: Annotated[str, typer.Argument(help="Stock ticker symbol")],
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get capital increases (stock splits) for a stock.

    Shows bedelli (rights issue) and bedelsiz (bonus share) capital increases.

    Examples:
        borsapy splits THYAO
        borsapy splits KAYSE
        borsapy splits THYAO -o json
    """
    from rich.table import Table

    import borsapy as bp

    symbol = symbol.strip().upper()

    with console.status(f"[bold green]Fetching splits for {symbol}..."):
        try:
            ticker = bp.Ticker(symbol)
            splits_df = ticker.splits

            if splits_df is None or splits_df.empty:
                console.print(
                    f"[yellow]No capital increases found for {symbol}[/yellow]"
                )
                raise typer.Exit(0)

        except Exception as e:
            handle_error(e, symbol)
            raise typer.Exit(1) from None

    # Output
    if output == "json":
        output_json(splits_df)
    elif output == "csv":
        output_csv(splits_df)
    else:
        table = Table(
            title=f"{symbol} Capital Increases",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Date", style="bold")
        table.add_column("Capital", justify="right")
        table.add_column("Rights Issue", justify="right")
        table.add_column("Bonus (Capital)", justify="right")
        table.add_column("Bonus (Dividend)", justify="right")

        for idx, row in splits_df.iterrows():
            date_str = (
                idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
            )
            table.add_row(
                date_str,
                format_number(row.get("Capital", row.get("capital")), 0),
                format_number(row.get("RightsIssue", row.get("rights_issue"))),
                format_number(
                    row.get("BonusFromCapital", row.get("bonus_from_capital"))
                ),
                format_number(
                    row.get("BonusFromDividend", row.get("bonus_from_dividend"))
                ),
            )

        output_table(table)
