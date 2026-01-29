"""
Companies command - List BIST companies.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import console, handle_error


def companies(
    search: Annotated[
        str | None,
        typer.Option("--search", "-s", help="Search by name or ticker"),
    ] = None,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    List all BIST companies or search by name/ticker.

    Examples:
        borsapy companies
        borsapy companies --search banka
        borsapy companies -s THY
        borsapy companies -o json
    """
    from rich.table import Table

    import borsapy as bp

    with console.status("[bold green]Fetching companies..."):
        try:
            if search:
                df = bp.search_companies(search)
                title = f"BIST Companies matching '{search}'"
            else:
                df = bp.companies()
                title = "BIST Companies"

            if df is None or df.empty:
                if search:
                    console.print(f"[yellow]No companies found matching '{search}'[/yellow]")
                else:
                    console.print("[yellow]No companies found[/yellow]")
                raise typer.Exit(0)

        except Exception as e:
            handle_error(e)
            raise typer.Exit(1) from None

    # Output
    if output == "json":
        output_json(df)
    elif output == "csv":
        output_csv(df)
    else:
        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("Ticker", style="bold")
        table.add_column("Name")
        table.add_column("City")

        # Limit table output to 50 rows
        display_df = df.head(50) if len(df) > 50 else df
        for _, row in display_df.iterrows():
            name = str(row.get("name", "-"))
            if len(name) > 50:
                name = name[:47] + "..."
            table.add_row(
                str(row.get("ticker", "-")),
                name,
                str(row.get("city", "-")),
            )

        output_table(table)

        if len(df) > 50:
            console.print(
                f"[dim]Showing 50 of {len(df)} companies. Use -o csv or -o json for full list.[/dim]"
            )
