"""
Quote command - Detailed info for a single symbol.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import OutputFormat, create_quote_panel, output_json
from borsapy.cli.utils import AssetType, console, get_asset, handle_error


def quote(
    symbol: Annotated[str, typer.Argument(help="Symbol to look up")],
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
    Get detailed quote information for a symbol.

    Examples:
        borsapy quote THYAO
        borsapy quote USD --type fx
        borsapy quote BTCTRY --type crypto
        borsapy quote YAY --type fund
        borsapy quote THYAO --output json
    """
    symbol = symbol.strip().upper()

    with console.status(f"[bold green]Fetching {symbol}..."):
        try:
            asset = get_asset(symbol, asset_type)

            # Get detailed info - build dict from known keys
            info = {"symbol": symbol}

            if hasattr(asset, "info"):
                asset_info = asset.info
                # Extract known keys safely using get()
                known_keys = [
                    "last", "open", "high", "low", "close", "volume", "amount",
                    "change", "change_percent", "prev_close", "previousClose",
                    "name", "shortName", "longName",
                    "market_cap", "marketCap", "pe_ratio", "trailingPE",
                    "price_to_book", "priceToBook", "dividend_yield", "dividendYield",
                    "high_52_week", "fiftyTwoWeekHigh", "low_52_week", "fiftyTwoWeekLow",
                    "bid", "ask", "bid_size", "ask_size",
                    "regularMarketPrice", "regularMarketChangePercent",
                    "sector", "industry", "website",
                ]
                for key in known_keys:
                    try:
                        val = asset_info.get(key)
                        if val is not None:
                            info[key] = val
                    except Exception:
                        pass
            elif hasattr(asset, "current"):
                current = asset.current
                if isinstance(current, dict):
                    info.update(current)

        except Exception as e:
            handle_error(e, symbol)
            raise typer.Exit(1) from None

    # Output
    if output == "json":
        output_json(info)
    else:
        console.print(create_quote_panel(info))
