"""
News command - KAP disclosures for a ticker.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import console, handle_error


def news(
    symbol: Annotated[str, typer.Argument(help="Stock ticker symbol")],
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Number of news items to show"),
    ] = 10,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get KAP disclosures (news) for a stock.

    Examples:
        borsapy news THYAO
        borsapy news THYAO -l 20
        borsapy news THYAO -o json
    """
    from rich.table import Table

    import borsapy as bp

    symbol = symbol.strip().upper()

    with console.status(f"[bold green]Fetching news for {symbol}..."):
        try:
            ticker = bp.Ticker(symbol)
            news_df = ticker.news

            if news_df is None or news_df.empty:
                console.print(f"[yellow]No news found for {symbol}[/yellow]")
                raise typer.Exit(0)

            # Limit results
            news_df = news_df.head(limit)

        except Exception as e:
            handle_error(e, symbol)
            raise typer.Exit(1) from None

    # Output
    if output == "json":
        output_json(news_df)
    elif output == "csv":
        output_csv(news_df)
    else:
        table = Table(
            title=f"{symbol} KAP Disclosures",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Date", style="bold")
        table.add_column("Title")
        table.add_column("URL", style="dim")

        for _, row in news_df.iterrows():
            date_val = row.get("Date", row.get("date", "-"))
            date_str = (
                date_val.strftime("%Y-%m-%d %H:%M")
                if hasattr(date_val, "strftime")
                else str(date_val)
            )
            title = str(row.get("Title", row.get("title", "-")))
            if len(title) > 60:
                title = title[:57] + "..."
            url = str(row.get("URL", row.get("url", "-")))
            if len(url) > 40:
                url = url[:37] + "..."

            table.add_row(date_str, title, url)

        output_table(table)
