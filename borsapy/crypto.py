"""Crypto class for cryptocurrency data - yfinance-like API."""

from datetime import datetime
from typing import Any

import pandas as pd

from borsapy._providers.btcturk import get_btcturk_provider


class Crypto:
    """
    A yfinance-like interface for cryptocurrency data from BtcTurk.

    Examples:
        >>> import borsapy as bp
        >>> btc = bp.Crypto("BTCTRY")
        >>> btc.current
        {'symbol': 'BTCTRY', 'last': 3500000.0, ...}
        >>> btc.history(period="1mo")
                             Open       High        Low      Close      Volume
        Date
        2024-12-01   3400000.0  3550000.0  3380000.0  3500000.0   1234.5678
        ...

        >>> eth = bp.Crypto("ETHTRY")
        >>> eth.current['last']
        125000.0
    """

    def __init__(self, pair: str):
        """
        Initialize a Crypto object.

        Args:
            pair: Trading pair (e.g., "BTCTRY", "ETHTRY", "BTCUSDT").
                  Common pairs: BTCTRY, ETHTRY, XRPTRY, DOGETRY, SOLTRY
        """
        self._pair = pair.upper()
        self._provider = get_btcturk_provider()
        self._current_cache: dict[str, Any] | None = None

    @property
    def pair(self) -> str:
        """Return the trading pair."""
        return self._pair

    @property
    def symbol(self) -> str:
        """Return the trading pair (alias)."""
        return self._pair

    @property
    def current(self) -> dict[str, Any]:
        """
        Get current ticker information.

        Returns:
            Dictionary with current market data:
            - symbol: Trading pair
            - last: Last traded price
            - open: Opening price
            - high: 24h high
            - low: 24h low
            - bid: Best bid price
            - ask: Best ask price
            - volume: 24h volume
            - change: Price change
            - change_percent: Percent change
        """
        if self._current_cache is None:
            self._current_cache = self._provider.get_ticker(self._pair)
        return self._current_cache

    @property
    def info(self) -> dict[str, Any]:
        """Alias for current property (yfinance compatibility)."""
        return self.current

    def history(
        self,
        period: str = "1mo",
        interval: str = "1d",
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data.

        Args:
            period: How much data to fetch. Valid periods:
                    1d, 5d, 1mo, 3mo, 6mo, 1y.
                    Ignored if start is provided.
            interval: Data granularity. Valid intervals:
                      1m, 5m, 15m, 30m, 1h, 4h, 1d, 1wk.
            start: Start date (string or datetime).
            end: End date (string or datetime). Defaults to now.

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume.
            Index is the Date.

        Examples:
            >>> crypto = Crypto("BTCTRY")
            >>> crypto.history(period="1mo")  # Last month
            >>> crypto.history(period="1y", interval="1wk")  # Weekly for 1 year
            >>> crypto.history(start="2024-01-01", end="2024-06-30")  # Date range
        """
        start_dt = self._parse_date(start) if start else None
        end_dt = self._parse_date(end) if end else None

        return self._provider.get_history(
            pair=self._pair,
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
        return f"Crypto('{self._pair}')"


def crypto_pairs(quote: str = "TRY") -> list[str]:
    """
    Get list of available cryptocurrency trading pairs.

    Args:
        quote: Quote currency filter (TRY, USDT, BTC)

    Returns:
        List of available trading pair symbols.

    Examples:
        >>> import borsapy as bp
        >>> bp.crypto_pairs()
        ['BTCTRY', 'ETHTRY', 'XRPTRY', ...]
        >>> bp.crypto_pairs("USDT")
        ['BTCUSDT', 'ETHUSDT', ...]
    """
    provider = get_btcturk_provider()
    return provider.get_pairs(quote)
