"""Paratic provider for historical OHLCV data."""

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL
from borsapy.exceptions import APIError, DataNotAvailableError, TickerNotFoundError


class ParaticProvider(BaseProvider):
    """
    Provider for historical OHLCV data from Paratic.

    API: https://piyasa.paratic.com/API/g.php
    """

    BASE_URL = "https://piyasa.paratic.com/API/g.php"

    # Period mapping (yfinance-style to days)
    PERIOD_MAP = {
        "1d": 1,
        "5d": 5,
        "1mo": 30,
        "3mo": 90,
        "6mo": 180,
        "1y": 365,
        "2y": 730,
        "5y": 1825,
        "10y": 3650,
        "ytd": None,  # Special handling
        "max": 3650,  # 10 years max
    }

    # Interval mapping (minutes)
    INTERVAL_MAP = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "1d": 1440,
        "1wk": 10080,
        "1mo": 43200,
    }

    def get_quote(self, symbol: str) -> dict[str, Any]:
        """
        Get current quote for a symbol.

        Args:
            symbol: Stock symbol (e.g., "THYAO", "GARAN").

        Returns:
            Dictionary with current market data.
        """
        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        cache_key = f"paratic:quote:{symbol}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # Fetch latest data point
        end_dt = datetime.now()
        params = {
            "a": "d",
            "c": symbol,
            "p": 1440,  # Daily
            "from": "",
            "at": end_dt.strftime("%Y%m%d%H%M%S"),
            "group": "f",
        }

        try:
            response = self._get(self.BASE_URL, params=params)
            data = response.json()
        except Exception as e:
            raise APIError(f"Failed to fetch quote for {symbol}: {e}") from e

        if not data:
            raise TickerNotFoundError(symbol)

        # Get the latest data point
        latest = data[-1] if data else None
        if not latest:
            raise TickerNotFoundError(symbol)

        # Get previous day for change calculation
        prev = data[-2] if len(data) > 1 else None
        prev_close = float(prev.get("c", 0)) if prev else 0

        last = float(latest.get("c", 0))
        change = last - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        result = {
            "symbol": symbol,
            "last": last,
            "open": float(latest.get("o", 0)),
            "high": float(latest.get("h", 0)),
            "low": float(latest.get("l", 0)),
            "close": prev_close,
            "volume": int(latest.get("v", 0)),
            "change": round(change, 2),
            "change_percent": round(change_pct, 2),
            "update_time": datetime.fromtimestamp(latest.get("d", 0) / 1000),
        }

        self._cache_set(cache_key, result, TTL.REALTIME_PRICE)
        return result

    def get_history(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data for a symbol.

        Args:
            symbol: Stock symbol (e.g., "THYAO", "GARAN").
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max).
            interval: Data interval (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo).
            start: Start date (overrides period if provided).
            end: End date (defaults to now).

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume.
        """
        # Normalize symbol
        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        # Cache key
        cache_key = f"paratic:history:{symbol}:{period}:{interval}"
        if start:
            cache_key += f":{start.isoformat()}"
        if end:
            cache_key += f":{end.isoformat()}"

        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # Calculate date range
        end_dt = end or datetime.now()
        if start:
            start_dt = start
        else:
            days = self._get_period_days(period)
            start_dt = end_dt - timedelta(days=days)

        # Get interval in minutes
        interval_minutes = self.INTERVAL_MAP.get(interval, 1440)

        # Build API params
        params = {
            "a": "d",  # data type
            "c": symbol,
            "p": interval_minutes,
            "from": "",  # Start from beginning
            "at": end_dt.strftime("%Y%m%d%H%M%S"),
            "group": "f",
        }

        try:
            response = self._get(self.BASE_URL, params=params)
            data = response.json()
        except Exception as e:
            raise APIError(f"Failed to fetch data for {symbol}: {e}") from e

        if not data:
            raise DataNotAvailableError(f"No data available for {symbol}")

        # Parse response
        df = self._parse_response(data, start_dt, end_dt)

        # Cache result
        self._cache_set(cache_key, df, TTL.OHLCV_HISTORY)

        return df

    def _get_period_days(self, period: str) -> int:
        """Convert period string to number of days."""
        if period == "ytd":
            today = datetime.now()
            year_start = datetime(today.year, 1, 1)
            return (today - year_start).days

        days = self.PERIOD_MAP.get(period)
        if days is None:
            # Default to 30 days
            return 30
        return days

    def _parse_response(
        self,
        data: list[dict[str, Any]],
        start_dt: datetime,
        end_dt: datetime,
    ) -> pd.DataFrame:
        """
        Parse API response into DataFrame.

        Response format:
        [
            {"d": timestamp_ms, "o": open, "h": high, "l": low, "c": close, "v": volume, ...},
            ...
        ]
        """
        if not data:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

        records = []
        for item in data:
            try:
                timestamp_ms = item.get("d")
                if timestamp_ms is None:
                    continue

                dt = datetime.fromtimestamp(timestamp_ms / 1000)

                # Filter by date range
                if dt < start_dt or dt > end_dt:
                    continue

                records.append(
                    {
                        "Date": dt,
                        "Open": float(item.get("o", 0)),
                        "High": float(item.get("h", 0)),
                        "Low": float(item.get("l", 0)),
                        "Close": float(item.get("c", 0)),
                        "Volume": int(item.get("v", 0)),
                    }
                )
            except (TypeError, ValueError):
                continue

        if not records:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

        df = pd.DataFrame(records)
        df.set_index("Date", inplace=True)
        df.sort_index(inplace=True)

        return df


# Singleton instance
_provider: ParaticProvider | None = None


def get_paratic_provider() -> ParaticProvider:
    """Get the singleton Paratic provider instance."""
    global _provider
    if _provider is None:
        _provider = ParaticProvider()
    return _provider
