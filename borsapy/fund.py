"""Fund class for mutual fund data - yfinance-like API."""

from datetime import datetime
from typing import Any

import pandas as pd

from borsapy._providers.tefas import get_tefas_provider


class Fund:
    """
    A yfinance-like interface for mutual fund data from TEFAS.

    Examples:
        >>> import borsapy as bp
        >>> fund = bp.Fund("AAK")
        >>> fund.info
        {'fund_code': 'AAK', 'name': 'Ak Portföy...', 'price': 1.234, ...}
        >>> fund.history(period="1mo")
                         Price      FundSize  Investors
        Date
        2024-12-01      1.200  150000000.0       5000
        ...

        >>> fund = bp.Fund("TTE")
        >>> fund.info['return_1y']
        45.67
    """

    def __init__(self, fund_code: str):
        """
        Initialize a Fund object.

        Args:
            fund_code: TEFAS fund code (e.g., "AAK", "TTE", "YAF")
        """
        self._fund_code = fund_code.upper()
        self._provider = get_tefas_provider()
        self._info_cache: dict[str, Any] | None = None

    @property
    def fund_code(self) -> str:
        """Return the fund code."""
        return self._fund_code

    @property
    def symbol(self) -> str:
        """Return the fund code (alias)."""
        return self._fund_code

    @property
    def info(self) -> dict[str, Any]:
        """
        Get detailed fund information.

        Returns:
            Dictionary with fund details:
            - fund_code: TEFAS fund code
            - name: Fund full name
            - date: Last update date
            - price: Current unit price
            - fund_size: Total fund size (TRY)
            - investor_count: Number of investors
            - founder: Fund founder company
            - manager: Fund manager company
            - fund_type: Fund type
            - category: Fund category
            - risk_value: Risk rating (1-7)
            - return_1m, return_3m, return_6m: Period returns
            - return_ytd: Year-to-date return
            - return_1y, return_3y, return_5y: Annual returns
            - daily_return: Daily return
        """
        if self._info_cache is None:
            self._info_cache = self._provider.get_fund_detail(self._fund_code)
        return self._info_cache

    @property
    def detail(self) -> dict[str, Any]:
        """Alias for info property."""
        return self.info

    @property
    def performance(self) -> dict[str, Any]:
        """
        Get fund performance metrics only.

        Returns:
            Dictionary with performance data:
            - daily_return: Daily return
            - return_1m, return_3m, return_6m: Period returns
            - return_ytd: Year-to-date return
            - return_1y, return_3y, return_5y: Annual returns
        """
        info = self.info
        return {
            "daily_return": info.get("daily_return"),
            "return_1m": info.get("return_1m"),
            "return_3m": info.get("return_3m"),
            "return_6m": info.get("return_6m"),
            "return_ytd": info.get("return_ytd"),
            "return_1y": info.get("return_1y"),
            "return_3y": info.get("return_3y"),
            "return_5y": info.get("return_5y"),
        }

    def history(
        self,
        period: str = "1mo",
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> pd.DataFrame:
        """
        Get historical price data.

        Args:
            period: How much data to fetch. Valid periods:
                    1d, 5d, 1mo, 3mo, 6mo, 1y.
                    Ignored if start is provided.
            start: Start date (string or datetime).
            end: End date (string or datetime). Defaults to now.

        Returns:
            DataFrame with columns: Price, FundSize, Investors.
            Index is the Date.

        Examples:
            >>> fund = Fund("AAK")
            >>> fund.history(period="1mo")  # Last month
            >>> fund.history(period="1y")  # Last year
            >>> fund.history(start="2024-01-01", end="2024-06-30")  # Date range
        """
        start_dt = self._parse_date(start) if start else None
        end_dt = self._parse_date(end) if end else None

        return self._provider.get_history(
            fund_code=self._fund_code,
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
        return f"Fund('{self._fund_code}')"


def search_funds(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """
    Search for funds by name or code.

    Args:
        query: Search query (fund code or name)
        limit: Maximum number of results

    Returns:
        List of matching funds with fund_code, name, fund_type, return_1y.

    Examples:
        >>> import borsapy as bp
        >>> bp.search_funds("ak portföy")
        [{'fund_code': 'AAK', 'name': 'Ak Portföy...', ...}, ...]
        >>> bp.search_funds("TTE")
        [{'fund_code': 'TTE', 'name': 'Türkiye...', ...}]
    """
    provider = get_tefas_provider()
    return provider.search(query, limit)
