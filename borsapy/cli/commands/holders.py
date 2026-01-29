"""
Holders command - Stock holder information (major holders and ETF holders).
"""

from typing import Annotated, Literal

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import console, format_number, handle_error

HolderType = Literal["major", "etf"]


def holders(
    symbol: Annotated[str, typer.Argument(help="Stock symbol (e.g., THYAO, ASELS)")],
    etf: Annotated[
        bool,
        typer.Option("--etf", "-e", help="Show ETF holders instead of major holders"),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Limit number of results"),
    ] = 20,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get holder information for a stock.

    Shows major shareholders or ETF holders that include this stock.

    Examples:
        borsapy holders THYAO             # Major holders
        borsapy holders ASELS --etf       # ETF holders
        borsapy holders THYAO --etf -n 10 # Top 10 ETF holders
        borsapy holders THYAO -o json
    """
    from rich.table import Table

    import borsapy as bp

    symbol = symbol.strip().upper()

    with console.status(f"[bold green]Fetching holder data for {symbol}..."):
        try:
            ticker = bp.Ticker(symbol)

            if etf:
                # ETF holders
                df = ticker.etf_holders

                if df is None or df.empty:
                    console.print(
                        f"[yellow]No ETF holders found for {symbol}[/yellow]"
                    )
                    raise typer.Exit(0)

                # Limit results
                df = df.head(limit)

                if output == "json":
                    output_json(df)
                elif output == "csv":
                    output_csv(df)
                else:
                    table = Table(
                        title=f"{symbol} ETF Holders",
                        show_header=True,
                        header_style="bold cyan",
                    )
                    table.add_column("ETF", style="bold")
                    table.add_column("Name")
                    table.add_column("Exchange")
                    table.add_column("Weight %", justify="right")
                    table.add_column("Position $", justify="right")
                    table.add_column("Issuer")

                    for _, row in df.iterrows():
                        weight = row.get("holding_weight_pct")
                        weight_str = f"{weight:.4f}%" if weight else "-"
                        position = row.get("market_cap_usd")
                        position_str = (
                            f"${position / 1e6:.1f}M" if position else "-"
                        )

                        table.add_row(
                            str(row.get("symbol", "-")),
                            str(row.get("name", "-"))[:35],
                            str(row.get("exchange", "-")),
                            weight_str,
                            position_str,
                            str(row.get("issuer", "-"))[:15],
                        )

                    output_table(table)

                    total_weight = df["holding_weight_pct"].sum()
                    console.print(
                        f"\n[dim]Total: {len(df)} ETFs, combined weight: {total_weight:.4f}%[/dim]"
                    )

            else:
                # Major holders
                df = ticker.major_holders

                if df is None or df.empty:
                    console.print(
                        f"[yellow]No major holders found for {symbol}[/yellow]"
                    )
                    raise typer.Exit(0)

                if output == "json":
                    output_json(df)
                elif output == "csv":
                    output_csv(df)
                else:
                    table = Table(
                        title=f"{symbol} Major Holders",
                        show_header=True,
                        header_style="bold cyan",
                    )
                    table.add_column("#", style="dim")
                    table.add_column("Holder", style="bold")
                    table.add_column("Percentage", justify="right")

                    for i, (_, row) in enumerate(df.head(limit).iterrows(), 1):
                        holder = row.get("holder_name", row.get("Holder", "-"))
                        pct = row.get("Percentage", row.get("percentage"))
                        pct_str = f"{format_number(pct)}%" if pct else "-"

                        table.add_row(
                            str(i),
                            str(holder)[:50],
                            pct_str,
                        )

                    output_table(table)

                    total = df["Percentage"].sum() if "Percentage" in df.columns else None
                    if total:
                        console.print(
                            f"\n[dim]Total disclosed: {format_number(total)}%[/dim]"
                        )

        except Exception as e:
            handle_error(e, symbol)
            raise typer.Exit(1) from None
