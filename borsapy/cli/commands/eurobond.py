"""
Eurobond command - Turkish sovereign Eurobond data.
"""

from typing import Annotated, Literal

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import console, format_number, handle_error

EurobondCurrency = Literal["USD", "EUR"]


def eurobond(
    isin: Annotated[
        str | None,
        typer.Argument(help="ISIN code for single Eurobond details"),
    ] = None,
    currency: Annotated[
        EurobondCurrency | None,
        typer.Option("--currency", "-c", help="Filter by currency: USD, EUR"),
    ] = None,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get Turkish sovereign Eurobond data.

    Eurobonds are Turkish government bonds issued in foreign currencies (USD/EUR).

    Examples:
        borsapy eurobond                      # All Eurobonds
        borsapy eurobond US900123DG28         # Single Eurobond details
        borsapy eurobond --currency USD       # USD bonds only
        borsapy eurobond --currency EUR       # EUR bonds only
        borsapy eurobond -o json
    """
    from rich.panel import Panel
    from rich.table import Table

    import borsapy as bp

    with console.status("[bold green]Fetching Eurobond data..."):
        try:
            if isin:
                # Show single Eurobond details
                bond = bp.Eurobond(isin)
                info = bond.info

                if output == "json":
                    output_json(info)
                else:
                    maturity_str = (
                        info.get("maturity").strftime("%Y-%m-%d")
                        if info.get("maturity")
                        else "-"
                    )
                    content = (
                        f"[bold]ISIN:[/bold] {info.get('isin', '-')}\n"
                        f"[bold]Currency:[/bold] {info.get('currency', '-')}\n"
                        f"[bold]Maturity:[/bold] {maturity_str}\n"
                        f"[bold]Days to Maturity:[/bold] {info.get('days_to_maturity', '-')}\n"
                        f"\n[bold cyan]Prices[/bold cyan]\n"
                        f"[bold]Bid Price:[/bold] {format_number(info.get('bid_price'))}\n"
                        f"[bold]Ask Price:[/bold] {format_number(info.get('ask_price'))}\n"
                        f"\n[bold cyan]Yields[/bold cyan]\n"
                        f"[bold]Bid Yield:[/bold] {format_number(info.get('bid_yield'))}%\n"
                        f"[bold]Ask Yield:[/bold] {format_number(info.get('ask_yield'))}%"
                    )
                    console.print(
                        Panel(content, title=f"Eurobond {isin}", border_style="cyan")
                    )
                return

            # Show all Eurobonds
            df = bp.eurobonds(currency=currency)

            if df is None or df.empty:
                console.print("[yellow]No Eurobonds found[/yellow]")
                raise typer.Exit(1)

        except Exception as e:
            handle_error(e)
            raise typer.Exit(1) from None

    # Output all Eurobonds
    if output == "json":
        output_json(df)
    elif output == "csv":
        output_csv(df)
    else:
        title = "Turkish Sovereign Eurobonds"
        if currency:
            title += f" ({currency})"

        table = Table(
            title=title,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("ISIN", style="bold")
        table.add_column("Currency")
        table.add_column("Maturity")
        table.add_column("Days", justify="right")
        table.add_column("Bid Yield", justify="right")
        table.add_column("Ask Yield", justify="right")

        for _, row in df.iterrows():
            maturity = row.get("maturity")
            maturity_str = (
                maturity.strftime("%Y-%m-%d") if hasattr(maturity, "strftime") else "-"
            )

            table.add_row(
                str(row.get("isin", "-")),
                str(row.get("currency", "-")),
                maturity_str,
                str(row.get("days_to_maturity", "-")),
                f"{format_number(row.get('bid_yield'))}%",
                f"{format_number(row.get('ask_yield'))}%",
            )

        output_table(table)
        console.print(f"\n[dim]Total: {len(df)} Eurobonds[/dim]")
