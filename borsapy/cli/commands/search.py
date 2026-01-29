"""
Search command - Symbol search.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import (
    OutputFormat,
    create_search_table,
    output_csv,
    output_json,
    output_table,
)
from borsapy.cli.utils import console, handle_error


def search(
    query: Annotated[str, typer.Argument(help="Search query")],
    search_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Filter by type: stock, crypto, forex, index"),
    ] = None,
    exchange: Annotated[
        str | None,
        typer.Option("--exchange", "-e", help="Filter by exchange (e.g., BIST, NASDAQ)"),
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
    Search for symbols by name or keyword.

    Examples:
        borsapy search banka
        borsapy search THY
        borsapy search BTC --type crypto
        borsapy search gold --type forex
        borsapy search XU --type index
        borsapy search GARAN --exchange BIST
    """
    import borsapy as bp

    with console.status(f"[bold green]Searching '{query}'..."):
        try:
            # Use appropriate search function based on type
            if search_type == "crypto":
                results = bp.search_crypto(query)
            elif search_type == "forex":
                results = bp.search_forex(query)
            elif search_type == "index":
                results = bp.search_index(query)
            elif search_type == "stock" or exchange == "BIST":
                results = bp.search_bist(query)
            else:
                # General search
                results = bp.search(query, type=search_type, exchange=exchange, full_info=True)

            # Normalize results to list of dicts
            if isinstance(results, list):
                if results and isinstance(results[0], str):
                    # Simple list of symbols
                    results = [{"symbol": s} for s in results]
            else:
                results = [{"symbol": results}]

            results = results[:limit]

        except Exception as e:
            handle_error(e)
            raise typer.Exit(1) from None

    if not results:
        console.print(f"[yellow]No results found for '{query}'[/yellow]")
        raise typer.Exit(0)

    # Output
    if output == "json":
        output_json(results)
    elif output == "csv":
        import pandas as pd

        output_csv(pd.DataFrame(results))
    else:
        output_table(create_search_table(results))
