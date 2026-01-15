"""Index class for market index data - yfinance-like API."""

from datetime import datetime
from typing import Any

import pandas as pd

from borsapy._providers.bist_index import get_bist_index_provider
from borsapy._providers.tradingview import get_tradingview_provider
from borsapy.technical import TechnicalMixin

# Known market indices with their names
INDICES = {
    # Main indices
    "XU100": "BIST 100",
    "XU050": "BIST 50",
    "XU030": "BIST 30",
    "XUTUM": "BIST Tüm",
    # Participation (Katılım) indices
    "XKTUM": "BIST Katılım Tüm",
    "XK100": "BIST Katılım 100",
    "XK050": "BIST Katılım 50",
    "XK030": "BIST Katılım 30",
    "XKTMT": "BIST Katılım Model Portföy",
    # Sector indices
    "XBANK": "BIST Banka",
    "XUSIN": "BIST Sınai",
    "XUMAL": "BIST Mali",
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
    # Thematic indices
    "XSRDK": "BIST Sürdürülebilirlik",
    "XKURY": "BIST Kurumsal Yönetim",
    "XYLDZ": "BIST Yıldız",
    "XBANA": "BIST Banka Dışı Likit 10",
    "XSPOR": "BIST Spor",
    "XGMYO": "BIST GYO",
    "XTUMY": "BIST Tüm-100",
    "XYORT": "BIST Yatırım Ortaklıkları",
    "XSDNZ": "BIST Seçme Divident",
}


class Index(TechnicalMixin):
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
        self._tradingview = get_tradingview_provider()
        self._bist_index = get_bist_index_provider()
        self._info_cache: dict[str, Any] | None = None
        self._components_cache: list[dict[str, Any]] | None = None

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
            # Use TradingView API to get quote (same endpoint works for indices)
            quote = self._tradingview.get_quote(self._symbol)
            quote["name"] = INDICES.get(self._symbol, self._symbol)
            quote["type"] = "index"
            self._info_cache = quote
        return self._info_cache

    @property
    def components(self) -> list[dict[str, Any]]:
        """
        Get constituent stocks of this index.

        Returns:
            List of component dicts with 'symbol' and 'name' keys.
            Empty list if index components are not available.

        Examples:
            >>> import borsapy as bp
            >>> xu030 = bp.Index("XU030")
            >>> xu030.components
            [{'symbol': 'AKBNK', 'name': 'AKBANK'}, ...]
            >>> len(xu030.components)
            30
        """
        if self._components_cache is None:
            self._components_cache = self._bist_index.get_components(self._symbol)
        return self._components_cache

    @property
    def component_symbols(self) -> list[str]:
        """
        Get just the ticker symbols of constituent stocks.

        Returns:
            List of stock symbols.

        Examples:
            >>> import borsapy as bp
            >>> xu030 = bp.Index("XU030")
            >>> xu030.component_symbols
            ['AKBNK', 'AKSA', 'AKSEN', ...]
        """
        return [c["symbol"] for c in self.components]

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

        # Use TradingView provider (same API works for indices)
        return self._tradingview.get_history(
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


def indices(detailed: bool = False) -> list[str] | list[dict[str, Any]]:
    """
    Get list of available market indices.

    Args:
        detailed: If True, return list of dicts with symbol, name, and count.
                  If False (default), return just the symbol list.

    Returns:
        List of index symbols, or list of dicts if detailed=True.

    Examples:
        >>> import borsapy as bp
        >>> bp.indices()
        ['XU100', 'XU050', 'XU030', 'XBANK', 'XUSIN', ...]
        >>> bp.indices(detailed=True)
        [{'symbol': 'XU100', 'name': 'BIST 100', 'count': 100}, ...]
    """
    if not detailed:
        return list(INDICES.keys())

    # Get component counts from provider
    provider = get_bist_index_provider()
    available = provider.get_available_indices()

    # Create lookup for counts
    count_map = {item["symbol"]: item["count"] for item in available}

    result = []
    for symbol, name in INDICES.items():
        result.append({
            "symbol": symbol,
            "name": name,
            "count": count_map.get(symbol, 0),
        })
    return result


def all_indices() -> list[dict[str, Any]]:
    """
    Get all indices from BIST with component counts.

    This returns all 79 indices available in the BIST data,
    not just the commonly used ones in indices().

    Returns:
        List of dicts with 'symbol', 'name', and 'count' keys.

    Examples:
        >>> import borsapy as bp
        >>> bp.all_indices()
        [{'symbol': 'X030C', 'name': 'BIST 30 Capped', 'count': 30}, ...]
    """
    provider = get_bist_index_provider()
    return provider.get_available_indices()


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
