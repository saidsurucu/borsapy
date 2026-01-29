"""
Shared utilities for borsapy CLI.
"""

from typing import Literal

import typer
from rich.console import Console

console = Console()
err_console = Console(stderr=True)

AssetType = Literal["stock", "fx", "crypto", "fund", "index"]


# Known FX currencies and commodities
FX_SYMBOLS = {
    "USD",
    "EUR",
    "GBP",
    "CHF",
    "CAD",
    "AUD",
    "JPY",
    "CNY",
    "RUB",
    "SAR",
    "AED",
    "NZD",
    "SEK",
    "NOK",
    "DKK",
    "PLN",
    "HUF",
    "CZK",
    "RON",
    "BGN",
    "INR",
    "KRW",
    "MXN",
    "BRL",
    "ZAR",
    "gram-altin",
    "ceyrek-altin",
    "yarim-altin",
    "tam-altin",
    "cumhuriyet-altin",
    "ons-altin",
    "gram-gumus",
    "gram-platin",
    "gram-paladyum",
    "BRENT",
    "WTI",
    "XAU",
    "XAG",
    "XPT",
    "XPD",
}

# Known index symbols
INDEX_SYMBOLS = {
    "XU100",
    "XU030",
    "XU050",
    "XBANK",
    "XUSIN",
    "XHOLD",
    "XGIDA",
    "XELKT",
    "XILTM",
    "XKMYA",
    "XMANA",
    "XMESY",
    "XTAST",
    "XTEKS",
    "XUHIZ",
    "XUMAL",
    "XUTEK",
    "XK030",
    "XK100",
    "XKURY",
    "XSIST",
    "XSPOR",
    "XYORT",
}


def detect_asset_type(symbol: str) -> AssetType:
    """
    Detect asset type from symbol pattern.

    Returns:
        AssetType: One of 'stock', 'fx', 'crypto', 'fund', 'index'
    """
    symbol_upper = symbol.upper()
    symbol_lower = symbol.lower()

    # Check for index
    if symbol_upper in INDEX_SYMBOLS:
        return "index"

    # Check for FX/commodity
    if symbol_upper in FX_SYMBOLS or symbol_lower in {s.lower() for s in FX_SYMBOLS}:
        return "fx"

    # Check for crypto pattern (ends with TRY and 6+ chars, or common crypto symbols)
    if (
        symbol_upper.endswith("TRY")
        and len(symbol) >= 6
        or symbol_upper.endswith("USDT")
        or symbol_upper in {"BTC", "ETH", "XRP", "BNB", "SOL", "ADA", "DOGE", "AVAX"}
    ):
        return "crypto"

    # Default to stock
    return "stock"


def get_asset(symbol: str, asset_type: AssetType | None = None):
    """
    Get the appropriate asset object for a symbol.

    Args:
        symbol: The symbol to look up
        asset_type: Override auto-detection

    Returns:
        Ticker, FX, Crypto, Fund, or Index object
    """
    import borsapy as bp

    if asset_type is None:
        asset_type = detect_asset_type(symbol)

    if asset_type == "stock":
        return bp.Ticker(symbol)
    elif asset_type == "fx":
        return bp.FX(symbol)
    elif asset_type == "crypto":
        return bp.Crypto(symbol)
    elif asset_type == "fund":
        return bp.Fund(symbol)
    elif asset_type == "index":
        return bp.Index(symbol)
    else:
        return bp.Ticker(symbol)


def format_number(value: float | int | None, decimal_places: int = 2) -> str:
    """Format a number with thousand separators and decimal places."""
    import math

    if value is None:
        return "-"
    # Check for NaN or infinity
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return "-"
    if isinstance(value, int) or value == int(value):
        return f"{int(value):,}"
    return f"{value:,.{decimal_places}f}"


def format_percent(value: float | None, decimal_places: int = 2) -> str:
    """Format a percentage value."""
    if value is None:
        return "-"
    return f"{value:+.{decimal_places}f}%"


def format_change(value: float | None, decimal_places: int = 2) -> str:
    """Format a change value with sign."""
    if value is None:
        return "-"
    return f"{value:+.{decimal_places}f}"


def get_change_color(value: float | None) -> str:
    """Get color for change value (green for positive, red for negative)."""
    if value is None:
        return "white"
    if value > 0:
        return "green"
    elif value < 0:
        return "red"
    return "white"


def handle_error(e: Exception, symbol: str | None = None) -> None:
    """Handle and display error to user."""
    if symbol:
        err_console.print(f"[red]Error for {symbol}:[/red] {e}")
    else:
        err_console.print(f"[red]Error:[/red] {e}")


def validate_symbols(symbols: list[str]) -> list[str]:
    """Validate and normalize symbol list."""
    return [s.strip().upper() for s in symbols if s.strip()]


def parse_period(period: str) -> str:
    """Validate and normalize period string."""
    valid_periods = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "3y", "5y", "max"}
    period_lower = period.lower()
    if period_lower not in valid_periods:
        raise typer.BadParameter(
            f"Invalid period '{period}'. Valid options: {', '.join(sorted(valid_periods))}"
        )
    return period_lower


def parse_interval(interval: str) -> str:
    """Validate and normalize interval string."""
    valid_intervals = {"1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1wk", "1mo"}
    interval_lower = interval.lower()
    if interval_lower not in valid_intervals:
        raise typer.BadParameter(
            f"Invalid interval '{interval}'. Valid options: {', '.join(sorted(valid_intervals))}"
        )
    return interval_lower
