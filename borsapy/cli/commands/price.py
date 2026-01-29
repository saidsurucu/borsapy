"""
Price command - Quick multi-symbol price lookup.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import (
    OutputFormat,
    create_price_table,
    output_csv,
    output_json,
    output_table,
)
from borsapy.cli.utils import (
    AssetType,
    console,
    get_asset,
    handle_error,
    validate_symbols,
)


def price(
    symbols: Annotated[list[str], typer.Argument(help="One or more symbols to look up")],
    asset_type: Annotated[
        AssetType | None,
        typer.Option("--type", "-t", help="Asset type (auto-detected if not specified)"),
    ] = None,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Quick price lookup for one or more symbols.

    Examples:
        borsapy price THYAO
        borsapy price THYAO GARAN ASELS
        borsapy price USD EUR --type fx
        borsapy price BTCTRY --type crypto
        borsapy price THYAO --output json
    """

    symbols = validate_symbols(symbols)
    if not symbols:
        raise typer.BadParameter("At least one symbol is required")

    quotes = []
    with console.status("[bold green]Fetching prices..."):
        for symbol in symbols:
            try:
                asset = get_asset(symbol, asset_type)

                # Get price data - prefer info over fast_info for complete data
                quote_data = {"symbol": symbol.upper()}

                if hasattr(asset, "info"):
                    info = asset.info
                    quote_data.update({
                        "last": info.get("last", info.get("regularMarketPrice")),
                        "change": info.get("change"),
                        "change_percent": info.get("change_percent"),
                        "volume": info.get("volume"),
                    })
                elif hasattr(asset, "fast_info"):
                    fi = asset.fast_info
                    quote_data.update({
                        "last": getattr(fi, "last_price", None),
                        "change": getattr(fi, "change", None),
                        "change_percent": getattr(fi, "change_percent", None),
                        "volume": getattr(fi, "volume", None),
                    })
                elif hasattr(asset, "current"):
                    current = asset.current
                    quote_data.update({
                        "last": current.get("last", current.get("buying")),
                        "change": current.get("change"),
                        "change_percent": current.get("change_percent"),
                        "volume": current.get("volume"),
                    })

                quotes.append(quote_data)
            except Exception as e:
                handle_error(e, symbol)
                quotes.append({"symbol": symbol.upper(), "last": None, "error": str(e)})

    if not quotes:
        console.print("[yellow]No data found[/yellow]")
        raise typer.Exit(1) from None

    # Output
    if output == "json":
        output_json(quotes)
    elif output == "csv":
        import pandas as pd

        output_csv(pd.DataFrame(quotes))
    else:
        output_table(create_price_table(quotes))
