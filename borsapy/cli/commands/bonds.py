"""
Bonds command - Turkish government bond yields.
"""

from typing import Annotated, Literal

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import (
    console,
    format_change,
    format_number,
    get_change_color,
    handle_error,
)

BondMaturity = Literal["2Y", "5Y", "10Y"]


def bonds(
    maturity: Annotated[
        BondMaturity | None,
        typer.Argument(help="Bond maturity"),
    ] = None,
    risk_free: Annotated[
        bool,
        typer.Option("--risk-free", "-r", help="Show only risk-free rate (10Y yield)"),
    ] = False,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get Turkish government bond yields.

    Examples:
        borsapy bonds              # All bonds
        borsapy bonds 10Y          # 10-year bond details
        borsapy bonds --risk-free  # Risk-free rate for DCF
        borsapy bonds -o json
    """
    from rich.panel import Panel
    from rich.table import Table

    import borsapy as bp

    with console.status("[bold green]Fetching bond yields..."):
        try:
            if risk_free:
                # Show just the risk-free rate
                rf = bp.risk_free_rate()
                if rf is None:
                    console.print("[yellow]Could not fetch risk-free rate[/yellow]")
                    raise typer.Exit(1)

                if output == "json":
                    output_json({"risk_free_rate": rf, "rate_percent": rf * 100})
                else:
                    console.print(
                        Panel(
                            f"[bold]10Y Bond Yield:[/bold] {rf * 100:.2f}%\n"
                            f"[bold]As decimal:[/bold] {rf:.4f}",
                            title="Risk-Free Rate",
                            border_style="cyan",
                        )
                    )
                return

            if maturity:
                # Show single bond details
                bond = bp.Bond(maturity)
                info = bond.info

                if output == "json":
                    output_json(info)
                else:
                    change = info.get("change")
                    change_pct = info.get("change_pct")
                    color = get_change_color(change)

                    content = (
                        f"[bold]Name:[/bold] {info.get('name', '-')}\n"
                        f"[bold]Yield:[/bold] {format_number(info.get('yield'))}%\n"
                        f"[bold]Change:[/bold] [{color}]{format_change(change)}[/{color}]\n"
                        f"[bold]Change %:[/bold] [{color}]{format_number(change_pct)}%[/{color}]"
                    )
                    console.print(
                        Panel(content, title=f"{maturity} Bond", border_style="cyan")
                    )
                return

            # Show all bonds
            df = bp.bonds()

            if df is None or df.empty:
                console.print("[yellow]Could not fetch bond yields[/yellow]")
                raise typer.Exit(1)

        except Exception as e:
            handle_error(e)
            raise typer.Exit(1) from None

    # Output all bonds
    if output == "json":
        output_json(df)
    elif output == "csv":
        output_csv(df)
    else:
        table = Table(
            title="Turkish Government Bond Yields",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Maturity", style="bold")
        table.add_column("Name")
        table.add_column("Yield", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("Change %", justify="right")

        for _, row in df.iterrows():
            change = row.get("change")
            change_pct = row.get("change_pct")
            color = get_change_color(change)

            table.add_row(
                str(row.get("maturity", "-")),
                str(row.get("name", "-")),
                f"{format_number(row.get('yield'))}%",
                f"[{color}]{format_change(change)}[/{color}]",
                f"[{color}]{format_number(change_pct)}%[/{color}]",
            )

        output_table(table)
