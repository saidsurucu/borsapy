"""Ticker class for stock data - yfinance-like API."""

from datetime import datetime
from functools import cached_property
from typing import Any

import pandas as pd

from borsapy._providers.paratic import get_paratic_provider


class Ticker:
    """
    A yfinance-like interface for Turkish stock data.

    Examples:
        >>> import borsapy as bp
        >>> stock = bp.Ticker("THYAO")
        >>> stock.info
        {'symbol': 'THYAO', 'last': 268.5, ...}
        >>> stock.history(period="1mo")
                         Open    High     Low   Close    Volume
        Date
        2024-12-01    265.00  268.00  264.00  267.50  12345678
        ...
    """

    def __init__(self, symbol: str):
        """
        Initialize a Ticker object.

        Args:
            symbol: Stock symbol (e.g., "THYAO", "GARAN", "ASELS").
                    The ".IS" or ".E" suffix is optional and will be removed.
        """
        self._symbol = symbol.upper().replace(".IS", "").replace(".E", "")
        self._paratic = get_paratic_provider()
        self._isyatirim = None  # Lazy load for financial statements
        self._info_cache: dict[str, Any] | None = None

    def _get_isyatirim(self):
        """Lazy load İş Yatırım provider for financial statements."""
        if self._isyatirim is None:
            from borsapy._providers.isyatirim import get_isyatirim_provider

            self._isyatirim = get_isyatirim_provider()
        return self._isyatirim

    @property
    def symbol(self) -> str:
        """Return the ticker symbol."""
        return self._symbol

    @property
    def info(self) -> dict[str, Any]:
        """
        Get current quote information.

        Returns:
            Dictionary with current market data:
            - symbol: Stock symbol
            - last: Last traded price
            - open: Opening price
            - high: Day high
            - low: Day low
            - close: Previous close
            - volume: Trading volume
            - change: Price change
            - change_percent: Percent change
            - update_time: Last update timestamp
        """
        if self._info_cache is None:
            self._info_cache = self._paratic.get_quote(self._symbol)
        return self._info_cache

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
                    1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max.
                    Ignored if start is provided.
            interval: Data granularity. Valid intervals:
                      1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo.
            start: Start date (string or datetime).
            end: End date (string or datetime). Defaults to today.

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume.
            Index is the Date.

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.history(period="1mo")  # Last month
            >>> stock.history(period="1y", interval="1wk")  # Weekly for 1 year
            >>> stock.history(start="2024-01-01", end="2024-06-30")  # Date range
        """
        # Parse dates if strings
        start_dt = self._parse_date(start) if start else None
        end_dt = self._parse_date(end) if end else None

        return self._paratic.get_history(
            symbol=self._symbol,
            period=period,
            interval=interval,
            start=start_dt,
            end=end_dt,
        )

    @cached_property
    def balance_sheet(self) -> pd.DataFrame:
        """
        Get annual balance sheet data.

        Returns:
            DataFrame with balance sheet items as rows and years as columns.
        """
        return self._get_isyatirim().get_financial_statements(
            symbol=self._symbol,
            statement_type="balance_sheet",
            quarterly=False,
        )

    @cached_property
    def quarterly_balance_sheet(self) -> pd.DataFrame:
        """
        Get quarterly balance sheet data.

        Returns:
            DataFrame with balance sheet items as rows and quarters as columns.
        """
        return self._get_isyatirim().get_financial_statements(
            symbol=self._symbol,
            statement_type="balance_sheet",
            quarterly=True,
        )

    @cached_property
    def income_stmt(self) -> pd.DataFrame:
        """
        Get annual income statement data.

        Returns:
            DataFrame with income statement items as rows and years as columns.
        """
        return self._get_isyatirim().get_financial_statements(
            symbol=self._symbol,
            statement_type="income_stmt",
            quarterly=False,
        )

    @cached_property
    def quarterly_income_stmt(self) -> pd.DataFrame:
        """
        Get quarterly income statement data.

        Returns:
            DataFrame with income statement items as rows and quarters as columns.
        """
        return self._get_isyatirim().get_financial_statements(
            symbol=self._symbol,
            statement_type="income_stmt",
            quarterly=True,
        )

    @cached_property
    def cashflow(self) -> pd.DataFrame:
        """
        Get annual cash flow statement data.

        Returns:
            DataFrame with cash flow items as rows and years as columns.
        """
        return self._get_isyatirim().get_financial_statements(
            symbol=self._symbol,
            statement_type="cashflow",
            quarterly=False,
        )

    @cached_property
    def quarterly_cashflow(self) -> pd.DataFrame:
        """
        Get quarterly cash flow statement data.

        Returns:
            DataFrame with cash flow items as rows and quarters as columns.
        """
        return self._get_isyatirim().get_financial_statements(
            symbol=self._symbol,
            statement_type="cashflow",
            quarterly=True,
        )

    def _parse_date(self, date: str | datetime) -> datetime:
        """Parse a date string to datetime."""
        if isinstance(date, datetime):
            return date
        # Try common formats
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"]:
            try:
                return datetime.strptime(date, fmt)
            except ValueError:
                continue
        raise ValueError(f"Could not parse date: {date}")

    def __repr__(self) -> str:
        return f"Ticker('{self._symbol}')"
