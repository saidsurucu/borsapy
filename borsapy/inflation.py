"""Inflation class for TCMB inflation data - yfinance-like API."""

from typing import Any

import pandas as pd

from borsapy._providers.tcmb import get_tcmb_provider


class Inflation:
    """
    A yfinance-like interface for Turkish inflation data from TCMB.

    Examples:
        >>> import borsapy as bp
        >>> inf = bp.Inflation()

        # Get latest inflation
        >>> inf.latest()
        {'date': '2024-11-01', 'yearly_inflation': 47.09, 'monthly_inflation': 2.24, ...}

        # Get TÜFE history
        >>> inf.tufe(limit=12)  # Last 12 months
                        YearMonth  YearlyInflation  MonthlyInflation
        Date
        2024-11-01      11-2024             47.09              2.24
        ...

        # Calculate inflation
        >>> inf.calculate(100000, "2020-01", "2024-01")
        {'initial_value': 100000, 'final_value': 342515.0, 'total_change': 242.52, ...}
    """

    def __init__(self):
        """Initialize an Inflation object."""
        self._provider = get_tcmb_provider()

    def latest(self, inflation_type: str = "tufe") -> dict[str, Any]:
        """
        Get the latest inflation data.

        Args:
            inflation_type: 'tufe' (CPI) or 'ufe' (PPI)

        Returns:
            Dictionary with latest inflation data:
            - date: Date string (YYYY-MM-DD)
            - year_month: Month-Year string
            - yearly_inflation: Year-over-year inflation rate
            - monthly_inflation: Month-over-month inflation rate
            - type: Inflation type (TUFE or UFE)
        """
        return self._provider.get_latest(inflation_type)

    def tufe(
        self,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Get TÜFE (Consumer Price Index) data.

        Args:
            start: Start date in YYYY-MM-DD format
            end: End date in YYYY-MM-DD format
            limit: Maximum number of records

        Returns:
            DataFrame with columns: YearMonth, YearlyInflation, MonthlyInflation.
            Index is the Date.

        Examples:
            >>> inf = Inflation()
            >>> inf.tufe(limit=6)  # Last 6 months
            >>> inf.tufe(start="2023-01-01", end="2023-12-31")  # 2023 data
        """
        return self._provider.get_data("tufe", start, end, limit)

    def ufe(
        self,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Get ÜFE (Producer Price Index) data.

        Args:
            start: Start date in YYYY-MM-DD format
            end: End date in YYYY-MM-DD format
            limit: Maximum number of records

        Returns:
            DataFrame with columns: YearMonth, YearlyInflation, MonthlyInflation.
            Index is the Date.

        Examples:
            >>> inf = Inflation()
            >>> inf.ufe(limit=6)  # Last 6 months
            >>> inf.ufe(start="2023-01-01", end="2023-12-31")  # 2023 data
        """
        return self._provider.get_data("ufe", start, end, limit)

    def calculate(
        self,
        amount: float,
        start: str,
        end: str,
    ) -> dict[str, Any]:
        """
        Calculate inflation-adjusted value between two dates.

        Uses TCMB's official inflation calculator API.

        Args:
            amount: Initial amount in TRY
            start: Start date in YYYY-MM format (e.g., "2020-01")
            end: End date in YYYY-MM format (e.g., "2024-01")

        Returns:
            Dictionary with:
            - start_date: Start date
            - end_date: End date
            - initial_value: Initial amount
            - final_value: Inflation-adjusted value
            - total_years: Total years elapsed
            - total_months: Total months elapsed
            - total_change: Total percentage change
            - avg_yearly_inflation: Average yearly inflation rate
            - start_cpi: CPI at start date
            - end_cpi: CPI at end date

        Examples:
            >>> inf = Inflation()
            >>> result = inf.calculate(100000, "2020-01", "2024-01")
            >>> print(f"100,000 TL in 2020 = {result['final_value']:,.0f} TL in 2024")
            100,000 TL in 2020 = 342,515 TL in 2024
        """
        start_year, start_month = self._parse_year_month(start)
        end_year, end_month = self._parse_year_month(end)

        return self._provider.calculate_inflation(
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
            basket_value=amount,
        )

    def _parse_year_month(self, date_str: str) -> tuple[int, int]:
        """Parse YYYY-MM format to (year, month) tuple."""
        try:
            parts = date_str.split("-")
            if len(parts) != 2:
                raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM")
            year = int(parts[0])
            month = int(parts[1])
            if not (1 <= month <= 12):
                raise ValueError(f"Invalid month: {month}")
            return year, month
        except Exception as e:
            raise ValueError(f"Could not parse date '{date_str}': {e}") from e

    def __repr__(self) -> str:
        return "Inflation()"
