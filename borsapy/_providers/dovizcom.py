"""Doviz.com provider for forex and commodity data."""

import re
import time
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL
from borsapy.exceptions import APIError, DataNotAvailableError


class DovizcomProvider(BaseProvider):
    """
    Provider for forex and commodity data from doviz.com.

    Supported assets:
    - Currencies: USD, EUR, GBP, JPY, CHF, CAD, AUD
    - Precious Metals: gram-altin, gumus, ons, XAG-USD, XPT-USD, XPD-USD
    - Energy: BRENT, WTI
    - Fuel: diesel, gasoline, lpg
    """

    BASE_URL = "https://api.doviz.com/api/v12"
    TOKEN_EXPIRY = 3600  # 1 hour

    FALLBACK_TOKEN = "3e75d7fabf1c50c8b962626dd0e5ea22d8000815e1b0920d0a26afd77fcd6609"

    SUPPORTED_ASSETS = {
        # Currencies
        "USD",
        "EUR",
        "GBP",
        "JPY",
        "CHF",
        "CAD",
        "AUD",
        # Precious Metals (TRY)
        "gram-altin",
        "gumus",
        # Precious Metals (USD)
        "ons",
        "XAG-USD",
        "XPT-USD",
        "XPD-USD",
        # Energy
        "BRENT",
        "WTI",
        # Fuel
        "diesel",
        "gasoline",
        "lpg",
    }

    FUEL_ASSETS = {"gasoline", "diesel", "lpg"}

    def __init__(self):
        super().__init__()
        self._token: str | None = None
        self._token_expiry: float = 0

    def _get_token(self) -> str:
        """Get valid Bearer token."""
        if self._token and time.time() < self._token_expiry:
            return self._token

        # Try to extract token from website
        try:
            token = self._extract_token()
            if token:
                self._token = token
                self._token_expiry = time.time() + self.TOKEN_EXPIRY
                return token
        except Exception:
            pass

        # Use fallback
        return self.FALLBACK_TOKEN

    def _extract_token(self) -> str | None:
        """Extract token from doviz.com website."""
        try:
            response = self._client.get("https://www.doviz.com/")
            html = response.text

            # Look for 64-char hex token
            patterns = [
                r'token["\']?\s*:\s*["\']([a-f0-9]{64})["\']',
                r"Bearer\s+([a-f0-9]{64})",
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    return match.group(1)

            return None
        except Exception:
            return None

    def _get_headers(self, asset: str) -> dict[str, str]:
        """Get request headers with token."""
        if asset in ["gram-altin", "gumus", "ons"]:
            origin = "https://altin.doviz.com"
        else:
            origin = "https://www.doviz.com"

        token = self._get_token()

        return {
            "Accept": "*/*",
            "Authorization": f"Bearer {token}",
            "Origin": origin,
            "Referer": f"{origin}/",
            "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
        }

    def get_current(self, asset: str) -> dict[str, Any]:
        """
        Get current price for an asset.

        Args:
            asset: Asset code (USD, EUR, gram-altin, BRENT, etc.)

        Returns:
            Dictionary with current price data.
        """
        asset = asset.upper() if asset.upper() in self.SUPPORTED_ASSETS else asset

        if asset not in self.SUPPORTED_ASSETS:
            raise DataNotAvailableError(
                f"Unsupported asset: {asset}. Supported: {sorted(self.SUPPORTED_ASSETS)}"
            )

        cache_key = f"dovizcom:current:{asset}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        try:
            if asset in self.FUEL_ASSETS:
                data = self._get_from_archive(asset, days=7)
            else:
                data = self._get_from_daily(asset)

            if not data:
                raise DataNotAvailableError(f"No data for {asset}")

            result = {
                "symbol": asset,
                "last": float(data.get("close", 0)),
                "open": float(data.get("open", 0)),
                "high": float(data.get("highest", 0)),
                "low": float(data.get("lowest", 0)),
                "update_time": self._parse_timestamp(data.get("update_date")),
            }

            self._cache_set(cache_key, result, TTL.FX_RATES)
            return result

        except Exception as e:
            raise APIError(f"Failed to fetch {asset}: {e}") from e

    def get_history(
        self,
        asset: str,
        period: str = "1mo",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Get historical data for an asset.

        Args:
            asset: Asset code.
            period: Period (1d, 5d, 1mo, 3mo, 6mo, 1y).
            start: Start date.
            end: End date.

        Returns:
            DataFrame with OHLC data.
        """
        asset = asset.upper() if asset.upper() in self.SUPPORTED_ASSETS else asset

        if asset not in self.SUPPORTED_ASSETS:
            raise DataNotAvailableError(f"Unsupported asset: {asset}")

        # Calculate date range
        end_dt = end or datetime.now()
        if start:
            start_dt = start
        else:
            days = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}.get(period, 30)
            start_dt = end_dt - timedelta(days=days)

        cache_key = f"dovizcom:history:{asset}:{start_dt.date()}:{end_dt.date()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            url = f"{self.BASE_URL}/assets/{asset}/archive"
            params = {
                "start": int(start_dt.timestamp()),
                "end": int(end_dt.timestamp()),
            }

            response = self._client.get(url, headers=self._get_headers(asset), params=params)
            response.raise_for_status()
            data = response.json()

            archive = data.get("data", {}).get("archive", [])

            records = []
            for item in archive:
                records.append(
                    {
                        "Date": self._parse_timestamp(item.get("update_date")),
                        "Open": float(item.get("open", 0)),
                        "High": float(item.get("highest", 0)),
                        "Low": float(item.get("lowest", 0)),
                        "Close": float(item.get("close", 0)),
                    }
                )

            df = pd.DataFrame(records)
            if not df.empty:
                df.set_index("Date", inplace=True)
                df.sort_index(inplace=True)

            self._cache_set(cache_key, df, TTL.OHLCV_HISTORY)
            return df

        except Exception as e:
            raise APIError(f"Failed to fetch history for {asset}: {e}") from e

    def _get_from_daily(self, asset: str) -> dict | None:
        """Get latest data from daily endpoint."""
        url = f"{self.BASE_URL}/assets/{asset}/daily"
        response = self._client.get(url, headers=self._get_headers(asset), params={"limit": 1})
        response.raise_for_status()
        data = response.json()

        archive = data.get("data", {}).get("archive", [])
        return archive[0] if archive else None

    def _get_from_archive(self, asset: str, days: int = 7) -> dict | None:
        """Get latest data from archive endpoint."""
        end_time = int(time.time())
        start_time = end_time - (days * 86400)

        url = f"{self.BASE_URL}/assets/{asset}/archive"
        params = {"start": start_time, "end": end_time}

        response = self._client.get(url, headers=self._get_headers(asset), params=params)
        response.raise_for_status()
        data = response.json()

        archive = data.get("data", {}).get("archive", [])
        return archive[-1] if archive else None

    def _parse_timestamp(self, ts: Any) -> datetime:
        """Parse timestamp to datetime."""
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts)
        if isinstance(ts, datetime):
            return ts
        return datetime.now()


# Singleton
_provider: DovizcomProvider | None = None


def get_dovizcom_provider() -> DovizcomProvider:
    """Get singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = DovizcomProvider()
    return _provider
