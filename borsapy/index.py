"""Index class for market index data - yfinance-like API."""

from datetime import datetime
from typing import Any

import pandas as pd

from borsapy._providers.paratic import get_paratic_provider

# Known market indices with their names
INDICES = {
    "XU100": "BIST 100",
    "XU050": "BIST 50",
    "XU030": "BIST 30",
    "XBANK": "BIST Banka",
    "XUSIN": "BIST Sınai",
    "XHOLD": "BIST Holding ve Yatırım",
    "XUTEK": "BIST Teknoloji",
    "XGIDA": "BIST Gıda",
    "XTRZM": "BIST Turizm",
    "XULAS": "BIST Ulaştırma",
    "XSGRT": "BIST Sigorta",
    "XMANA": "BIST Metal Ana",
    "XKMYA": "BIST Kimya",
    "XMADN": "BIST Maden",
    "XELKT": "BIST Elektrik",
    "XTEKS": "BIST Tekstil",
    "XILTM": "BIST İletişim",
    "XUMAL": "BIST Mali",
    "XUTUM": "BIST Tüm",
}


class Index:
    """
    A yfinance-like interface for Turkish market indices.

    Examples:
        >>> import borsapy as bp
        >>> xu100 = bp.Index("XU100")
        >>> xu100.info
        {'symbol': 'XU100', 'name': 'BIST 100', 'last': 9500.5, ...}
        >>> xu100.history(period="1mo")
                         Open      High       Low     Close      Volume
        Date
        2024-12-01    9400.00  9550.00  9380.00  9500.50  1234567890
        ...

        # Available indices
        >>> bp.indices()
        ['XU100', 'XU050', 'XU030', 'XBANK', ...]
    """

    def __init__(self, symbol: str):
        """
        Initialize an Index object.

        Args:
            symbol: Index symbol (e.g., "XU100", "XU030", "XBANK").
        """
        self._symbol = symbol.upper()
        self._paratic = get_paratic_provider()
        self._info_cache: dict[str, Any] | None = None

    @property
    def symbol(self) -> str:
        """Return the index symbol."""
        return self._symbol

    @property
    def info(self) -> dict[str, Any]:
        """
        Get current index information.

        Returns:
            Dictionary with index data:
            - symbol: Index symbol
            - name: Index full name
            - last: Current value
            - open: Opening value
            - high: Day high
            - low: Day low
            - close: Previous close
            - change: Value change
            - change_percent: Percent change
            - update_time: Last update timestamp
        """
        if self._info_cache is None:
            # Use Paratic API to get quote (same endpoint works for indices)
            quote = self._paratic.get_quote(self._symbol)
            quote["name"] = INDICES.get(self._symbol, self._symbol)
            quote["type"] = "index"
            self._info_cache = quote
        return self._info_cache

    def history(
        self,
        period: str = "1mo",
        interval: str = "1d",
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> pd.DataFrame:
        """
        Get historical index data.

        Args:
            period: How much data to fetch. Valid periods:
                    1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max.
                    Ignored if start is provided.
            interval: Data interval. Valid intervals:
                      1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo.
            start: Start date (string or datetime).
            end: End date (string or datetime). Defaults to today.

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume.
            Index is the Date.

        Examples:
            >>> idx = Index("XU100")
            >>> idx.history(period="1mo")  # Last month
            >>> idx.history(period="1y")  # Last year
            >>> idx.history(start="2024-01-01", end="2024-06-30")
        """
        # Parse dates
        start_dt = self._parse_date(start) if start else None
        end_dt = self._parse_date(end) if end else None

        # Use Paratic provider (same API works for indices)
        return self._paratic.get_history(
            symbol=self._symbol,
            period=period,
            interval=interval,
            start=start_dt,
            end=end_dt,
        )

    def _parse_date(self, date: str | datetime) -> datetime:
        """Parse a date string to datetime."""
        if isinstance(date, datetime):
            return date
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"]:
            try:
                return datetime.strptime(date, fmt)
            except ValueError:
                continue
        raise ValueError(f"Could not parse date: {date}")

    def __repr__(self) -> str:
        return f"Index('{self._symbol}')"


def indices() -> list[str]:
    """
    Get list of available market indices.

    Returns:
        List of index symbols.

    Examples:
        >>> import borsapy as bp
        >>> bp.indices()
        ['XU100', 'XU050', 'XU030', 'XBANK', 'XUSIN', ...]
    """
    return list(INDICES.keys())


def index(symbol: str) -> Index:
    """
    Get an Index object for the given symbol.

    This is a convenience function that creates an Index object.

    Args:
        symbol: Index symbol (e.g., "XU100", "XBANK").

    Returns:
        Index object.

    Examples:
        >>> import borsapy as bp
        >>> xu100 = bp.index("XU100")
        >>> xu100.history(period="1mo")
    """
    return Index(symbol)
