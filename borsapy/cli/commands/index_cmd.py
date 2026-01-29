"""
Index command - BIST market index data and components.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import (
    console,
    format_change,
    format_number,
    get_change_color,
    handle_error,
)


def index(
    symbol: Annotated[
        str | None,
        typer.Argument(help="Index symbol (e.g., XU030, XU100, XBANK)"),
    ] = None,
    symbols_only: Annotated[
        bool,
        typer.Option("--symbols", "-s", help="Show only component symbols"),
    ] = False,
    list_indices: Annotated[
        bool,
        typer.Option("--list", "-l", help="List popular indices (29)"),
    ] = False,
    all_indices: Annotated[
        bool,
        typer.Option("--all", "-a", help="List all BIST indices (79)"),
    ] = False,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get BIST market index data and components.

    Examples:
        borsapy index XU030               # Index info + components
        borsapy index XU100 --symbols     # Just component symbols
        borsapy index --list              # Popular indices (29)
        borsapy index --all               # All BIST indices (79)
        borsapy index XU030 -o json
    """
    from rich.panel import Panel
    from rich.table import Table

    import borsapy as bp

    with console.status("[bold green]Fetching index data..."):
        try:
            if list_indices:
                # Show popular indices
                indices_data = bp.indices(detailed=True)

                if output == "json":
                    output_json(indices_data)
                elif output == "csv":
                    import pandas as pd

                    output_csv(pd.DataFrame(indices_data))
                else:
                    table = Table(
                        title="BIST Market Indices (Popular)",
                        show_header=True,
                        header_style="bold cyan",
                    )
                    table.add_column("Symbol", style="bold")
                    table.add_column("Name")
                    table.add_column("Stocks", justify="right")

                    for idx in indices_data:
                        table.add_row(
                            str(idx.get("symbol", "-")),
                            str(idx.get("name", "-")),
                            str(idx.get("count", "-")),
                        )

                    output_table(table)
                    console.print(f"\n[dim]Total: {len(indices_data)} indices[/dim]")
                return

            if all_indices:
                # Show all BIST indices
                all_data = bp.all_indices()

                if output == "json":
                    output_json(all_data)
                elif output == "csv":
                    import pandas as pd

                    output_csv(pd.DataFrame(all_data))
                else:
                    table = Table(
                        title="All BIST Indices",
                        show_header=True,
                        header_style="bold cyan",
                    )
                    table.add_column("Symbol", style="bold")
                    table.add_column("Name")
                    table.add_column("Stocks", justify="right")

                    for idx in all_data:
                        table.add_row(
                            str(idx.get("symbol", "-")),
                            str(idx.get("name", "-")),
                            str(idx.get("count", "-")),
                        )

                    output_table(table)
                    console.print(f"\n[dim]Total: {len(all_data)} indices[/dim]")
                return

            if not symbol:
                console.print(
                    "[yellow]Please provide an index symbol or use --list/--all[/yellow]"
                )
                raise typer.Exit(1)

            # Show specific index
            symbol = symbol.strip().upper()
            idx = bp.Index(symbol)
            info = idx.info
            components = idx.components

            if symbols_only:
                # Just output component symbols
                symbols_list = idx.component_symbols

                if output == "json":
                    output_json(symbols_list)
                elif output == "csv":
                    print(",".join(symbols_list))
                else:
                    console.print(" ".join(symbols_list))
                return

            if output == "json":
                output_json({
                    "info": info,
                    "components": components,
                })
            elif output == "csv":
                import pandas as pd

                output_csv(pd.DataFrame(components))
            else:
                # Rich output
                change = info.get("change")
                change_pct = info.get("change_percent")
                color = get_change_color(change)

                # Index info panel
                header = (
                    f"[bold]Value:[/bold] {format_number(info.get('last'))}\n"
                    f"[bold]Change:[/bold] [{color}]{format_change(change)}[/{color}]\n"
                    f"[bold]Change %:[/bold] [{color}]{format_number(change_pct)}%[/{color}]\n"
                    f"[bold]Components:[/bold] {len(components)} stocks"
                )
                console.print(
                    Panel(
                        header,
                        title=f"{symbol} - {info.get('name', symbol)}",
                        border_style="cyan",
                    )
                )

                # Components table
                if components:
                    table = Table(
                        title="Index Components",
                        show_header=True,
                        header_style="bold cyan",
                    )
                    table.add_column("#", style="dim")
                    table.add_column("Symbol", style="bold")
                    table.add_column("Name")

                    for i, comp in enumerate(components, 1):
                        table.add_row(
                            str(i),
                            str(comp.get("symbol", "-")),
                            str(comp.get("name", "-"))[:40],
                        )

                    output_table(table)

        except Exception as e:
            handle_error(e, symbol if symbol else None)
            raise typer.Exit(1) from None
