"""
Targets command - Analyst price targets and recommendations.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import OutputFormat, output_json
from borsapy.cli.utils import (
    console,
    format_number,
    format_percent,
    get_change_color,
    handle_error,
)


def targets(
    symbol: Annotated[str, typer.Argument(help="Stock symbol (e.g., THYAO, GARAN)")],
    recommendations: Annotated[
        bool,
        typer.Option(
            "--recommendations", "-r", help="Show buy/sell recommendations"
        ),
    ] = False,
    summary: Annotated[
        bool,
        typer.Option("--summary", "-s", help="Show recommendation summary breakdown"),
    ] = False,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get analyst price targets and recommendations for a stock.

    Data sourced from hedeffiyat.com.tr for Turkish analyst coverage.

    Examples:
        borsapy targets THYAO                    # Price target summary
        borsapy targets THYAO --recommendations  # AL/TUT/SAT recommendation
        borsapy targets THYAO --summary          # Analyst breakdown
        borsapy targets THYAO -o json
    """
    from rich.panel import Panel

    import borsapy as bp

    symbol = symbol.strip().upper()

    with console.status(f"[bold green]Fetching analyst data for {symbol}..."):
        try:
            ticker = bp.Ticker(symbol)

            if summary:
                # Show recommendation summary (strongBuy, buy, hold, sell, strongSell)
                rec_summary = ticker.recommendations_summary

                if not rec_summary:
                    console.print(
                        f"[yellow]No recommendation summary found for {symbol}[/yellow]"
                    )
                    raise typer.Exit(0)

                if output == "json":
                    output_json(rec_summary)
                else:
                    lines = []
                    total = sum(rec_summary.values())

                    for rating, count in rec_summary.items():
                        pct = (count / total * 100) if total > 0 else 0
                        bar_len = int(pct / 5)  # Scale to 20 chars max
                        bar = "█" * bar_len

                        # Color based on rating
                        if rating in ("strongBuy", "buy"):
                            color = "green"
                        elif rating in ("strongSell", "sell"):
                            color = "red"
                        else:
                            color = "yellow"

                        lines.append(
                            f"[{color}]{rating:12}[/{color}] [{color}]{bar:20}[/{color}] {count} ({pct:.0f}%)"
                        )

                    content = "\n".join(lines)
                    console.print(
                        Panel(
                            content,
                            title=f"{symbol} Recommendation Summary",
                            border_style="cyan",
                        )
                    )
                    console.print(f"\n[dim]Total analysts: {total}[/dim]")
                return

            if recommendations:
                # Show buy/sell recommendation
                rec = ticker.recommendations

                if not rec:
                    console.print(
                        f"[yellow]No recommendations found for {symbol}[/yellow]"
                    )
                    raise typer.Exit(0)

                if output == "json":
                    output_json(rec)
                else:
                    recommendation = rec.get("recommendation", "-")
                    target = rec.get("target_price")
                    upside = rec.get("upside_potential")

                    # Color the recommendation
                    rec_lower = recommendation.lower()
                    if "al" in rec_lower or "buy" in rec_lower:
                        rec_color = "green"
                    elif "sat" in rec_lower or "sell" in rec_lower:
                        rec_color = "red"
                    else:
                        rec_color = "yellow"

                    # Color the upside
                    upside_color = get_change_color(upside)

                    content = (
                        f"[bold]Recommendation:[/bold] [{rec_color}]{recommendation}[/{rec_color}]\n"
                        f"[bold]Target Price:[/bold] {format_number(target)} TL\n"
                        f"[bold]Upside Potential:[/bold] [{upside_color}]{format_percent(upside)}[/{upside_color}]"
                    )
                    console.print(
                        Panel(
                            content,
                            title=f"{symbol} Analyst Recommendation",
                            border_style="cyan",
                        )
                    )
                return

            # Default: show price targets
            targets_data = ticker.analyst_price_targets

            if not targets_data:
                console.print(
                    f"[yellow]No price targets found for {symbol}[/yellow]"
                )
                raise typer.Exit(0)

            if output == "json":
                output_json(targets_data)
            else:
                current = targets_data.get("current")
                low = targets_data.get("low")
                high = targets_data.get("high")
                mean = targets_data.get("mean")
                median = targets_data.get("median")
                analysts = targets_data.get("numberOfAnalysts", 0)

                # Calculate upside to mean target
                upside = None
                if current and mean:
                    upside = ((mean - current) / current) * 100
                upside_color = get_change_color(upside)

                content = (
                    f"[bold]Current Price:[/bold] {format_number(current)} TL\n\n"
                    f"[bold cyan]Target Prices[/bold cyan]\n"
                    f"[bold]Low:[/bold] {format_number(low)} TL\n"
                    f"[bold]Mean:[/bold] {format_number(mean)} TL\n"
                    f"[bold]Median:[/bold] {format_number(median)} TL\n"
                    f"[bold]High:[/bold] {format_number(high)} TL\n\n"
                    f"[bold]Upside to Mean:[/bold] [{upside_color}]{format_percent(upside)}[/{upside_color}]\n"
                    f"[bold]Analyst Coverage:[/bold] {analysts} analysts"
                )
                console.print(
                    Panel(
                        content,
                        title=f"{symbol} Analyst Price Targets",
                        border_style="cyan",
                    )
                )

        except Exception as e:
            handle_error(e, symbol)
            raise typer.Exit(1) from None
