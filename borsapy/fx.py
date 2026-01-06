"""FX class for forex and commodity data - yfinance-like API."""

from datetime import datetime
from typing import Any

import pandas as pd

from borsapy._providers.dovizcom import get_dovizcom_provider


def banks() -> list[str]:
    """
    Get list of supported banks for exchange rates.

    Returns:
        List of bank codes.

    Examples:
        >>> import borsapy as bp
        >>> bp.banks()
        ['akbank', 'albaraka', 'alternatifbank', 'anadolubank', ...]
    """
    return get_dovizcom_provider().get_banks()


class FX:
    """
    A yfinance-like interface for forex and commodity data.

    Supported assets:
    - Currencies: USD, EUR, GBP, JPY, CHF, CAD, AUD
    - Precious Metals: gram-altin, gumus, ons, XAG-USD, XPT-USD, XPD-USD
    - Energy: BRENT, WTI
    - Fuel: diesel, gasoline, lpg

    Examples:
        >>> import borsapy as bp
        >>> usd = bp.FX("USD")
        >>> usd.current
        {'symbol': 'USD', 'last': 34.85, ...}
        >>> usd.history(period="1mo")
                         Open    High     Low   Close
        Date
        2024-12-01    34.50   34.80   34.40   34.75
        ...

        >>> gold = bp.FX("gram-altin")
        >>> gold.current
        {'symbol': 'gram-altin', 'last': 2850.50, ...}
    """

    def __init__(self, asset: str):
        """
        Initialize an FX object.

        Args:
            asset: Asset code (USD, EUR, gram-altin, BRENT, etc.)
        """
        self._asset = asset
        self._provider = get_dovizcom_provider()
        self._current_cache: dict[str, Any] | None = None

    @property
    def asset(self) -> str:
        """Return the asset code."""
        return self._asset

    @property
    def symbol(self) -> str:
        """Return the asset code (alias for asset)."""
        return self._asset

    @property
    def current(self) -> dict[str, Any]:
        """
        Get current price information.

        Returns:
            Dictionary with current market data:
            - symbol: Asset code
            - last: Last price
            - open: Opening price
            - high: Day high
            - low: Day low
            - update_time: Last update timestamp
        """
        if self._current_cache is None:
            self._current_cache = self._provider.get_current(self._asset)
        return self._current_cache

    @property
    def info(self) -> dict[str, Any]:
        """Alias for current property (yfinance compatibility)."""
        return self.current

    @property
    def bank_rates(self) -> pd.DataFrame:
        """
        Get exchange rates from all banks.

        Returns:
            DataFrame with columns: bank, bank_name, currency, buy, sell, spread

        Examples:
            >>> usd = FX("USD")
            >>> usd.bank_rates
                      bank        bank_name currency      buy     sell  spread
            0       akbank           Akbank      USD  41.6610  44.1610    5.99
            1      garanti     Garanti BBVA      USD  41.7000  44.2000    5.99
            ...
        """
        return self._provider.get_bank_rates(self._asset)

    def bank_rate(self, bank: str) -> dict[str, Any]:
        """
        Get exchange rate from a specific bank.

        Args:
            bank: Bank code (akbank, garanti, isbank, ziraat, etc.)

        Returns:
            Dictionary with keys: bank, currency, buy, sell, spread

        Examples:
            >>> usd = FX("USD")
            >>> usd.bank_rate("akbank")
            {'bank': 'akbank', 'currency': 'USD', 'buy': 41.6610, 'sell': 44.1610, 'spread': 5.99}
        """
        return self._provider.get_bank_rates(self._asset, bank=bank)

    @staticmethod
    def banks() -> list[str]:
        """
        Get list of supported banks.

        Returns:
            List of bank codes.

        Examples:
            >>> FX.banks()
            ['akbank', 'albaraka', 'alternatifbank', 'anadolubank', ...]
        """
        from borsapy._providers.dovizcom import get_dovizcom_provider

        return get_dovizcom_provider().get_banks()

    def history(
        self,
        period: str = "1mo",
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> pd.DataFrame:
        """
        Get historical OHLC data.

        Args:
            period: How much data to fetch. Valid periods:
                    1d, 5d, 1mo, 3mo, 6mo, 1y.
                    Ignored if start is provided.
            start: Start date (string or datetime).
            end: End date (string or datetime). Defaults to today.

        Returns:
            DataFrame with columns: Open, High, Low, Close.
            Index is the Date.

        Examples:
            >>> fx = FX("USD")
            >>> fx.history(period="1mo")  # Last month
            >>> fx.history(start="2024-01-01", end="2024-06-30")  # Date range
        """
        start_dt = self._parse_date(start) if start else None
        end_dt = self._parse_date(end) if end else None

        return self._provider.get_history(
            asset=self._asset,
            period=period,
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
        return f"FX('{self._asset}')"
