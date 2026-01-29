"""
VIOP command - Turkish derivatives (futures and options) contracts.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import console, handle_error

# Month code to name mapping
MONTH_NAMES = {
    "F": "January",
    "G": "February",
    "H": "March",
    "J": "April",
    "K": "May",
    "M": "June",
    "N": "July",
    "Q": "August",
    "U": "September",
    "V": "October",
    "X": "November",
    "Z": "December",
}


def viop(
    base_symbol: Annotated[
        str | None,
        typer.Argument(help="Base futures symbol (e.g., XU030D, XAUTRY, USDTRY)"),
    ] = None,
    search_query: Annotated[
        str | None,
        typer.Option("--search", "-s", help="Search VIOP symbols by keyword"),
    ] = None,
    detail: Annotated[
        bool,
        typer.Option("--detail", "-d", help="Show detailed contract information"),
    ] = False,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get VIOP (Turkish derivatives) contract information.

    VIOP contracts include index futures, currency futures, commodity futures,
    and stock options traded on BIST.

    Contract format: Base + Month Code + Year (e.g., XU030DG2026)
    Month codes: F=Jan, G=Feb, H=Mar, J=Apr, K=May, M=Jun,
                 N=Jul, Q=Aug, U=Sep, V=Oct, X=Nov, Z=Dec

    Examples:
        borsapy viop XU030D              # BIST30 futures contracts
        borsapy viop XAUTRY              # Gold TRY futures
        borsapy viop XU030D --detail     # Detailed contract info
        borsapy viop --search gold       # Search VIOP symbols
        borsapy viop -o json
    """
    from rich.panel import Panel
    from rich.table import Table

    import borsapy as bp

    with console.status("[bold green]Fetching VIOP data..."):
        try:
            if search_query:
                # Search for VIOP symbols
                results = bp.search_viop(search_query)

                if not results:
                    console.print(
                        f"[yellow]No VIOP symbols found for '{search_query}'[/yellow]"
                    )
                    raise typer.Exit(0)

                if output == "json":
                    output_json(results)
                elif output == "csv":
                    print("\n".join(results))
                else:
                    table = Table(
                        title=f"VIOP Search Results: '{search_query}'",
                        show_header=True,
                        header_style="bold cyan",
                    )
                    table.add_column("Symbol", style="bold")
                    table.add_column("Type")

                    for sym in results:
                        # Determine type based on symbol pattern
                        sym_type = "Futures"
                        if sym.endswith("D") and len(sym) <= 8:
                            sym_type = "Base Symbol"
                        elif "!" in sym:
                            sym_type = "Continuous"

                        table.add_row(sym, sym_type)

                    output_table(table)
                    console.print(f"\n[dim]Found: {len(results)} symbols[/dim]")
                return

            if not base_symbol:
                console.print(
                    "[yellow]Please provide a base symbol or use --search[/yellow]"
                )
                console.print(
                    "\n[dim]Examples:\n"
                    "  borsapy viop XU030D     # BIST30 futures\n"
                    "  borsapy viop XAUTRY     # Gold TRY futures\n"
                    "  borsapy viop USDTRY     # USD/TRY futures\n"
                    "  borsapy viop --search gold[/dim]"
                )
                raise typer.Exit(1)

            # Normalize base symbol
            base_symbol = base_symbol.strip().upper()

            # Get contracts
            contracts = bp.viop_contracts(base_symbol, full_info=True)

            if not contracts:
                console.print(
                    f"[yellow]No contracts found for '{base_symbol}'[/yellow]"
                )
                raise typer.Exit(0)

        except Exception as e:
            handle_error(e, base_symbol if base_symbol else None)
            raise typer.Exit(1) from None

    # Output contracts
    if output == "json":
        output_json(contracts)
    elif output == "csv":
        import pandas as pd

        output_csv(pd.DataFrame(contracts))
    else:
        # Rich output
        console.print(
            Panel(
                f"[bold]Base Symbol:[/bold] {base_symbol}\n"
                f"[bold]Active Contracts:[/bold] {len(contracts)}",
                title=f"{base_symbol} Futures Contracts",
                border_style="cyan",
            )
        )

        table = Table(
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Contract", style="bold")
        table.add_column("Month")
        table.add_column("Year", justify="right")

        if detail:
            table.add_column("Exchange")
            table.add_column("Description")

        for contract in contracts:
            symbol = contract.get("symbol", "-")
            month_code = contract.get("month_code", "")
            month_name = MONTH_NAMES.get(month_code, month_code)
            year = contract.get("year", "-")

            if detail:
                table.add_row(
                    symbol,
                    month_name,
                    str(year),
                    contract.get("exchange", "-"),
                    contract.get("description", "-")[:30],
                )
            else:
                table.add_row(
                    symbol,
                    month_name,
                    str(year),
                )

        output_table(table)

        # Show month code legend
        console.print(
            "\n[dim]Month codes: F=Jan, G=Feb, H=Mar, J=Apr, K=May, M=Jun, "
            "N=Jul, Q=Aug, U=Sep, V=Oct, X=Nov, Z=Dec[/dim]"
        )
