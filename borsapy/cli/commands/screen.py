"""
Screen command - Stock/fund screening.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import (
    OutputFormat,
    create_screen_table,
    output_csv,
    output_json,
    output_table,
)
from borsapy.cli.utils import console, handle_error


def screen(
    template: Annotated[
        str | None,
        typer.Option("--template", "-T", help="Use a preset template (high_dividend, low_pe, growth, value)"),
    ] = None,
    sector: Annotated[
        str | None,
        typer.Option("--sector", "-s", help="Filter by sector"),
    ] = None,
    index: Annotated[
        str | None,
        typer.Option("--index", "-x", help="Filter by index (XU030, XU100, etc.)"),
    ] = None,
    market_cap_min: Annotated[
        float | None,
        typer.Option("--mcap-min", help="Minimum market cap (in millions TL)"),
    ] = None,
    market_cap_max: Annotated[
        float | None,
        typer.Option("--mcap-max", help="Maximum market cap (in millions TL)"),
    ] = None,
    pe_min: Annotated[
        float | None,
        typer.Option("--pe-min", help="Minimum P/E ratio"),
    ] = None,
    pe_max: Annotated[
        float | None,
        typer.Option("--pe-max", help="Maximum P/E ratio"),
    ] = None,
    pb_min: Annotated[
        float | None,
        typer.Option("--pb-min", help="Minimum P/B ratio"),
    ] = None,
    pb_max: Annotated[
        float | None,
        typer.Option("--pb-max", help="Maximum P/B ratio"),
    ] = None,
    dividend_min: Annotated[
        float | None,
        typer.Option("--div-min", help="Minimum dividend yield (%)"),
    ] = None,
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
    Screen stocks based on fundamental criteria.

    Templates:
        high_dividend - Stocks with dividend yield > 5%
        low_pe - Stocks with P/E < 10
        growth - High revenue growth stocks
        value - Low P/E and P/B stocks

    Examples:
        borsapy screen --template high_dividend
        borsapy screen --pe-max 10 --div-min 3
        borsapy screen --sector Bankacılık
        borsapy screen --index XU030 --pe-max 15
        borsapy screen --mcap-min 1000 --pe-max 10
    """
    import borsapy as bp

    with console.status("[bold green]Screening stocks..."):
        try:
            # Build screener
            screener = bp.Screener()

            # Apply template
            if template:
                if template == "high_dividend":
                    screener.add_filter("dividend_yield", min=5)
                elif template == "low_pe":
                    screener.add_filter("pe_ratio", max=10)
                elif template == "growth":
                    screener.add_filter("revenue_growth", min=20)
                elif template == "value":
                    screener.add_filter("pe_ratio", max=12)
                    screener.add_filter("pb_ratio", max=1.5)
                else:
                    console.print(f"[yellow]Unknown template: {template}[/yellow]")

            # Apply filters
            if sector:
                screener.set_sector(sector)
            if index:
                screener.set_index(index)
            if market_cap_min:
                screener.add_filter("market_cap", min=market_cap_min)
            if market_cap_max:
                screener.add_filter("market_cap", max=market_cap_max)
            if pe_min:
                screener.add_filter("pe_ratio", min=pe_min)
            if pe_max:
                screener.add_filter("pe_ratio", max=pe_max)
            if pb_min:
                screener.add_filter("pb_ratio", min=pb_min)
            if pb_max:
                screener.add_filter("pb_ratio", max=pb_max)
            if dividend_min:
                screener.add_filter("dividend_yield", min=dividend_min)

            results = screener.run()

            if results is None or (hasattr(results, "empty") and results.empty):
                console.print("[yellow]No stocks match the criteria[/yellow]")
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
        output_table(create_screen_table(results))
        count = len(results) if hasattr(results, "__len__") else "?"
        console.print(f"\n[dim]Found {count} matches[/dim]")
