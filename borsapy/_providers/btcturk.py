"""BtcTurk provider for cryptocurrency data."""

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL
from borsapy.exceptions import APIError, DataNotAvailableError


class BtcTurkProvider(BaseProvider):
    """
    Provider for cryptocurrency data from BtcTurk.

    Provides:
    - Real-time ticker data for crypto pairs
    - Historical OHLC data
    """

    BASE_URL = "https://api.btcturk.com/api/v2"
    GRAPH_API_URL = "https://graph-api.btcturk.com"

    # Resolution mapping (minutes)
    RESOLUTION_MAP = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
        "1wk": 10080,
    }

    def get_ticker(self, pair: str) -> dict[str, Any]:
        """
        Get current ticker data for a crypto pair.

        Args:
            pair: Trading pair (e.g., "BTCTRY", "ETHTRY", "BTCUSDT")

        Returns:
            Dictionary with ticker data.
        """
        pair = pair.upper()

        cache_key = f"btcturk:ticker:{pair}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            url = f"{self.BASE_URL}/ticker"
            params = {"pairSymbol": pair}

            response = self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if not data.get("success", False):
                raise APIError(f"API error: {data.get('message', 'Unknown')}")

            ticker_data = data.get("data", [])
            if not ticker_data:
                raise DataNotAvailableError(f"No data for pair: {pair}")

            ticker = ticker_data[0] if isinstance(ticker_data, list) else ticker_data

            result = {
                "symbol": ticker.get("pair"),
                "last": float(ticker.get("last", 0)),
                "open": float(ticker.get("open", 0)),
                "high": float(ticker.get("high", 0)),
                "low": float(ticker.get("low", 0)),
                "bid": float(ticker.get("bid", 0)),
                "ask": float(ticker.get("ask", 0)),
                "volume": float(ticker.get("volume", 0)),
                "change": float(ticker.get("daily", 0)),
                "change_percent": float(ticker.get("dailyPercent", 0)),
                "timestamp": ticker.get("timestamp"),
            }

            self._cache_set(cache_key, result, TTL.REALTIME_PRICE)
            return result

        except Exception as e:
            raise APIError(f"Failed to fetch ticker for {pair}: {e}") from e

    def get_history(
        self,
        pair: str,
        period: str = "1mo",
        interval: str = "1d",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Get historical OHLC data for a crypto pair.

        Args:
            pair: Trading pair (e.g., "BTCTRY", "ETHTRY")
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y)
            interval: Data interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1wk)
            start: Start date
            end: End date

        Returns:
            DataFrame with OHLCV data.
        """
        pair = pair.upper()

        # Calculate time range
        end_dt = end or datetime.now()
        if start:
            start_dt = start
        else:
            days = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}.get(period, 30)
            start_dt = end_dt - timedelta(days=days)

        from_ts = int(start_dt.timestamp())
        to_ts = int(end_dt.timestamp())

        cache_key = f"btcturk:history:{pair}:{interval}:{from_ts}:{to_ts}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            # Get resolution in minutes
            resolution = self.RESOLUTION_MAP.get(interval, 1440)

            url = f"{self.GRAPH_API_URL}/v1/klines/history"
            params = {
                "symbol": pair,
                "resolution": resolution,
                "from": from_ts,
                "to": to_ts,
            }

            response = self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Graph API returns TradingView format
            status = data.get("s", "error")
            if status != "ok":
                raise DataNotAvailableError(f"No data available for {pair}")

            # Parse TradingView format
            timestamps = data.get("t", [])
            opens = data.get("o", [])
            highs = data.get("h", [])
            lows = data.get("l", [])
            closes = data.get("c", [])
            volumes = data.get("v", [])

            records = []
            for i in range(len(timestamps)):
                records.append(
                    {
                        "Date": datetime.fromtimestamp(timestamps[i]),
                        "Open": float(opens[i]) if i < len(opens) else 0.0,
                        "High": float(highs[i]) if i < len(highs) else 0.0,
                        "Low": float(lows[i]) if i < len(lows) else 0.0,
                        "Close": float(closes[i]) if i < len(closes) else 0.0,
                        "Volume": float(volumes[i]) if i < len(volumes) else 0.0,
                    }
                )

            df = pd.DataFrame(records)
            if not df.empty:
                df.set_index("Date", inplace=True)
                df.sort_index(inplace=True)

            self._cache_set(cache_key, df, TTL.OHLCV_HISTORY)
            return df

        except Exception as e:
            raise APIError(f"Failed to fetch history for {pair}: {e}") from e

    def get_pairs(self, quote: str = "TRY") -> list[str]:
        """
        Get list of available trading pairs.

        Args:
            quote: Quote currency filter (TRY, USDT, BTC)

        Returns:
            List of trading pair symbols.
        """
        cache_key = f"btcturk:pairs:{quote}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            url = f"{self.BASE_URL}/ticker"
            response = self._client.get(url)
            response.raise_for_status()
            data = response.json()

            if not data.get("success", False):
                return []

            pairs = []
            quote_upper = quote.upper()
            for ticker in data.get("data", []):
                pair = ticker.get("pair", "")
                if pair.endswith(quote_upper):
                    pairs.append(pair)

            self._cache_set(cache_key, pairs, TTL.COMPANY_LIST)
            return pairs

        except Exception:
            return []


# Singleton
_provider: BtcTurkProvider | None = None


def get_btcturk_provider() -> BtcTurkProvider:
    """Get singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = BtcTurkProvider()
    return _provider
