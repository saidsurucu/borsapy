"""
Compare command - Multi-ticker comparison.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import OutputFormat, create_compare_table, output_json, output_table
from borsapy.cli.utils import AssetType, console, get_asset, handle_error, validate_symbols


def compare(
    symbols: Annotated[list[str], typer.Argument(help="Symbols to compare (2-10)")],
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
    Compare multiple tickers side by side.

    Compares price, change, volume, market cap, P/E, P/B, dividend yield, and 52-week range.

    Examples:
        borsapy compare THYAO PGSUS TAVHL
        borsapy compare AKBNK GARAN ISCTR YKBNK
        borsapy compare USD EUR GBP --type fx
        borsapy compare THYAO GARAN --output json
    """
    symbols = validate_symbols(symbols)

    if len(symbols) < 2:
        raise typer.BadParameter("At least 2 symbols are required for comparison")
    if len(symbols) > 10:
        raise typer.BadParameter("Maximum 10 symbols for comparison")

    tickers = []
    with console.status("[bold green]Fetching data for comparison..."):
        for symbol in symbols:
            try:
                asset = get_asset(symbol, asset_type)

                # Build info dict from known keys safely
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
                        "regularMarketPrice", "regularMarketChangePercent",
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

                # Normalize field names
                normalized = {
                    "symbol": symbol,
                    "last": info.get("last", info.get("regularMarketPrice")),
                    "change": info.get("change"),
                    "change_percent": info.get("change_percent", info.get("regularMarketChangePercent")),
                    "volume": info.get("volume"),
                    "market_cap": info.get("market_cap", info.get("marketCap")),
                    "pe_ratio": info.get("pe_ratio", info.get("trailingPE")),
                    "price_to_book": info.get("price_to_book", info.get("priceToBook")),
                    "dividend_yield": info.get("dividend_yield", info.get("dividendYield")),
                    "high_52_week": info.get("high_52_week", info.get("fiftyTwoWeekHigh")),
                    "low_52_week": info.get("low_52_week", info.get("fiftyTwoWeekLow")),
                }
                tickers.append(normalized)

            except Exception as e:
                handle_error(e, symbol)
                tickers.append({"symbol": symbol, "error": str(e)})

    if not tickers:
        console.print("[yellow]No data found[/yellow]")
        raise typer.Exit(1) from None

    # Output
    if output == "json":
        output_json(tickers)
    else:
        output_table(create_compare_table(tickers))
