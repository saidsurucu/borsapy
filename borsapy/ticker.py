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
        self._kap = None  # Lazy load for KAP disclosures
        self._info_cache: dict[str, Any] | None = None

    def _get_isyatirim(self):
        """Lazy load İş Yatırım provider for financial statements."""
        if self._isyatirim is None:
            from borsapy._providers.isyatirim import get_isyatirim_provider

            self._isyatirim = get_isyatirim_provider()
        return self._isyatirim

    def _get_kap(self):
        """Lazy load KAP provider for disclosures and calendar."""
        if self._kap is None:
            from borsapy._providers.kap import get_kap_provider

            self._kap = get_kap_provider()
        return self._kap

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
    def dividends(self) -> pd.DataFrame:
        """
        Get dividend history.

        Returns:
            DataFrame with dividend history:
            - Amount: Dividend per share (TL)
            - GrossRate: Gross dividend rate (%)
            - NetRate: Net dividend rate (%)
            - TotalDividend: Total dividend distributed (TL)

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.dividends
                           Amount  GrossRate  NetRate  TotalDividend
            Date
            2025-09-02     3.442    344.20   292.57  4750000000.0
            2025-06-16     3.442    344.20   292.57  4750000000.0
        """
        return self._get_isyatirim().get_dividends(self._symbol)

    @cached_property
    def splits(self) -> pd.DataFrame:
        """
        Get capital increase (split) history.

        Note: Turkish market uses capital increases instead of traditional splits.
        - RightsIssue: Paid capital increase (bedelli)
        - BonusFromCapital: Free shares from capital reserves (bedelsiz iç kaynak)
        - BonusFromDividend: Free shares from dividend (bedelsiz temettüden)

        Returns:
            DataFrame with capital increase history:
            - Capital: New capital after increase (TL)
            - RightsIssue: Rights issue rate (%)
            - BonusFromCapital: Bonus from capital (%)
            - BonusFromDividend: Bonus from dividend (%)

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.splits
                             Capital  RightsIssue  BonusFromCapital  BonusFromDividend
            Date
            2013-06-26  1380000000.0         0.0             15.00               0.0
            2011-07-11  1200000000.0         0.0              0.00              20.0
        """
        return self._get_isyatirim().get_capital_increases(self._symbol)

    @cached_property
    def actions(self) -> pd.DataFrame:
        """
        Get combined dividends and splits history.

        Returns:
            DataFrame with combined dividend and split actions:
            - Dividends: Dividend per share (TL) or 0
            - Splits: Combined split ratio (0 if no split)

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.actions
                         Dividends  Splits
            Date
            2025-09-02      3.442    0.0
            2013-06-26      0.000   15.0
        """
        dividends = self.dividends
        splits = self.splits

        # Merge on index (Date)
        if dividends.empty and splits.empty:
            return pd.DataFrame(columns=["Dividends", "Splits"])

        # Extract relevant columns
        div_series = dividends["Amount"] if not dividends.empty else pd.Series(dtype=float)
        split_series = (
            splits["BonusFromCapital"] + splits["BonusFromDividend"]
            if not splits.empty
            else pd.Series(dtype=float)
        )

        # Combine into single DataFrame
        result = pd.DataFrame({"Dividends": div_series, "Splits": split_series})
        result = result.fillna(0)
        result = result.sort_index(ascending=False)

        return result

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

    @cached_property
    def major_holders(self) -> pd.DataFrame:
        """
        Get major shareholders (ortaklık yapısı).

        Returns:
            DataFrame with shareholder names and percentages:
            - Index: Holder name
            - Percentage: Ownership percentage (%)

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.major_holders
                                     Percentage
            Holder
            Diğer                        50.88
            Türkiye Varlık Fonu          49.12
        """
        return self._get_isyatirim().get_major_holders(self._symbol)

    @cached_property
    def recommendations(self) -> dict:
        """
        Get analyst recommendations and target price.

        Returns:
            Dictionary with:
            - recommendation: Buy/Hold/Sell (AL/TUT/SAT)
            - target_price: Analyst target price (TL)
            - upside_potential: Expected upside (%)

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.recommendations
            {'recommendation': 'AL', 'target_price': 579.99, 'upside_potential': 116.01}
        """
        return self._get_isyatirim().get_recommendations(self._symbol)

    @cached_property
    def news(self) -> pd.DataFrame:
        """
        Get recent KAP (Kamuyu Aydınlatma Platformu) disclosures for the stock.

        Fetches directly from KAP - the official disclosure platform for
        publicly traded companies in Turkey.

        Returns:
            DataFrame with columns:
            - Date: Disclosure date and time
            - Title: Disclosure headline
            - URL: Link to full disclosure on KAP

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.news
                              Date                                         Title                                         URL
            0  29.12.2025 19:21:18  Haber ve Söylentilere İlişkin Açıklama  https://www.kap.org.tr/tr/Bildirim/1530826
            1  29.12.2025 16:11:36  Payların Geri Alınmasına İlişkin Bildirim  https://www.kap.org.tr/tr/Bildirim/1530656
        """
        return self._get_kap().get_disclosures(self._symbol)

    @cached_property
    def calendar(self) -> pd.DataFrame:
        """
        Get expected disclosure calendar for the stock from KAP.

        Returns upcoming expected disclosures like financial reports,
        annual reports, sustainability reports, and corporate governance reports.

        Returns:
            DataFrame with columns:
            - StartDate: Expected disclosure window start
            - EndDate: Expected disclosure window end
            - Subject: Type of disclosure (e.g., "Finansal Rapor")
            - Period: Report period (e.g., "Yıllık", "3 Aylık")
            - Year: Fiscal year

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.calendar
                  StartDate       EndDate               Subject   Period  Year
            0  01.01.2026  11.03.2026       Finansal Rapor   Yıllık  2025
            1  01.01.2026  11.03.2026    Faaliyet Raporu  Yıllık  2025
            2  01.04.2026  11.05.2026       Finansal Rapor  3 Aylık  2026
        """
        return self._get_kap().get_calendar(self._symbol)

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
