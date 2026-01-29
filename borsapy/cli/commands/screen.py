"""
Screen command - Stock/fund screening.
"""

from typing import Annotated, Literal

import typer

from borsapy.cli.formatters import (
    OutputFormat,
    create_screen_table,
    output_csv,
    output_json,
    output_table,
)
from borsapy.cli.utils import IndexType, console, handle_error

ScreenTemplate = Literal[
    "small_cap", "mid_cap", "large_cap",
    "high_dividend", "low_pe", "high_roe",
    "high_upside", "low_upside",
    "high_volume", "low_volume",
    "buy_recommendation", "sell_recommendation",
    "high_net_margin", "high_return", "high_foreign_ownership",
]

Recommendation = Literal["AL", "SAT", "TUT"]


def screen(
    template: Annotated[
        ScreenTemplate | None,
        typer.Option("--template", "-T", help="Use a preset template"),
    ] = None,
    sector: Annotated[
        str | None,
        typer.Option("--sector", "-s", help="Filter by sector (e.g., Bankacılık, Holding, Enerji)"),
    ] = None,
    index: Annotated[
        IndexType | None,
        typer.Option("--index", "-x", help="Filter by index"),
    ] = None,
    recommendation: Annotated[
        Recommendation | None,
        typer.Option("--rec", "-r", help="Filter by analyst recommendation"),
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
    roe_min: Annotated[
        float | None,
        typer.Option("--roe-min", help="Minimum return on equity (%)"),
    ] = None,
    upside_min: Annotated[
        float | None,
        typer.Option("--upside-min", help="Minimum upside potential (%)"),
    ] = None,
    foreign_min: Annotated[
        float | None,
        typer.Option("--foreign-min", help="Minimum foreign ownership (%)"),
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

    TEMPLATES (--template):

      Size: small_cap, mid_cap, large_cap

      Value: high_dividend, low_pe, high_roe

      Momentum: high_upside, low_upside, high_return

      Volume: high_volume, low_volume

      Analyst: buy_recommendation, sell_recommendation

      Other: high_net_margin, high_foreign_ownership

    FILTERS:

      Valuation: --pe-min/max, --pb-min/max

      Fundamentals: --div-min, --roe-min, --mcap-min/max

      Analyst: --upside-min, --rec (AL/SAT/TUT)

      Ownership: --foreign-min

    SECTORS (--sector):

      Bankacılık, Holding, Enerji, Gıda, İnşaat, Otomotiv, Perakende, Teknoloji, Telekomünikasyon, vb.

    Examples:
        borsapy screen --template high_dividend
        borsapy screen --template buy_recommendation --index XU030
        borsapy screen --pe-max 10 --div-min 3
        borsapy screen --sector Bankacılık --roe-min 15
        borsapy screen --index XU100 --upside-min 20
        borsapy screen --rec AL --mcap-min 1000
    """
    import borsapy as bp

    with console.status("[bold green]Screening stocks..."):
        try:
            # Build screener
            screener = bp.Screener()

            # Apply filters
            if sector:
                screener.set_sector(sector)
            if index:
                screener.set_index(index)
            if recommendation:
                screener.set_recommendation(recommendation)
            if market_cap_min or market_cap_max:
                screener.add_filter("market_cap", min=market_cap_min, max=market_cap_max)
            if pe_min or pe_max:
                screener.add_filter("pe", min=pe_min, max=pe_max)
            if pb_min or pb_max:
                screener.add_filter("pb", min=pb_min, max=pb_max)
            if dividend_min:
                screener.add_filter("dividend_yield", min=dividend_min)
            if roe_min:
                screener.add_filter("roe", min=roe_min)
            if upside_min:
                screener.add_filter("upside_potential", min=upside_min)
            if foreign_min:
                screener.add_filter("foreign_ratio", min=foreign_min)

            results = screener.run(template=template)

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
