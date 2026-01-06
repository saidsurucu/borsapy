"""EconomicCalendar class for economic events - yfinance-like API."""

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from borsapy._providers.dovizcom_calendar import get_calendar_provider


class EconomicCalendar:
    """
    A yfinance-like interface for economic calendar data.

    Data source: doviz.com

    Examples:
        >>> import borsapy as bp
        >>> cal = bp.EconomicCalendar()
        >>> cal.events(period="1w")  # This week's events
                         Date      Time Country  Importance              Event Actual Forecast Previous
        0 2024-01-15  10:00:00  Türkiye        high  Enflasyon (YoY)  64.77%   65.00%   61.98%
        ...

        >>> cal.today()  # Today's events
        >>> cal.events(country="TR", importance="high")  # High importance TR events
    """

    # Valid country codes
    COUNTRIES = ["TR", "US", "EU", "DE", "GB", "JP", "CN", "FR", "IT", "CA", "AU", "CH"]

    def __init__(self):
        """Initialize EconomicCalendar."""
        self._provider = get_calendar_provider()

    def events(
        self,
        period: str = "1w",
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        country: str | list[str] | None = None,
        importance: str | None = None,
    ) -> pd.DataFrame:
        """
        Get economic calendar events.

        Args:
            period: How much data to fetch. Valid periods: 1d, 1w, 2w, 1mo.
                    Ignored if start is provided.
            start: Start date (string or datetime).
            end: End date (string or datetime). Defaults to start + period.
            country: Country code(s) to filter by (TR, US, EU, etc.).
                     Can be a single code or list of codes.
                     Defaults to ['TR', 'US'].
            importance: Filter by importance level ('low', 'mid', 'high').

        Returns:
            DataFrame with columns: Date, Time, Country, Importance, Event,
                                    Actual, Forecast, Previous, Period.

        Examples:
            >>> cal = EconomicCalendar()
            >>> cal.events(period="1w")  # Next 7 days
            >>> cal.events(country="TR", importance="high")  # High importance TR events
            >>> cal.events(country=["TR", "US", "EU"])  # Multiple countries
            >>> cal.events(start="2024-01-01", end="2024-01-31")  # Date range
        """
        # Parse dates
        start_dt = self._parse_date(start) if start else None
        end_dt = self._parse_date(end) if end else None

        # If no start, use today
        if start_dt is None:
            start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # If no end, calculate from period
        if end_dt is None:
            days = {"1d": 1, "1w": 7, "2w": 14, "1mo": 30}.get(period, 7)
            end_dt = start_dt + timedelta(days=days)

        # Parse country parameter
        countries = self._parse_countries(country)

        # Fetch events
        events = self._provider.get_economic_calendar(
            start=start_dt,
            end=end_dt,
            countries=countries,
            importance=importance,
        )

        # Convert to DataFrame
        if not events:
            return pd.DataFrame(
                columns=[
                    "Date",
                    "Time",
                    "Country",
                    "Importance",
                    "Event",
                    "Actual",
                    "Forecast",
                    "Previous",
                    "Period",
                ]
            )

        df = pd.DataFrame(events)

        # Rename columns
        df = df.rename(
            columns={
                "date": "Date",
                "time": "Time",
                "country": "Country",
                "importance": "Importance",
                "event": "Event",
                "actual": "Actual",
                "forecast": "Forecast",
                "previous": "Previous",
                "period": "Period",
            }
        )

        # Drop internal columns
        if "country_code" in df.columns:
            df = df.drop(columns=["country_code"])

        # Reorder columns
        column_order = [
            "Date",
            "Time",
            "Country",
            "Importance",
            "Event",
            "Actual",
            "Forecast",
            "Previous",
            "Period",
        ]
        df = df[[c for c in column_order if c in df.columns]]

        return df

    def today(
        self,
        country: str | list[str] | None = None,
        importance: str | None = None,
    ) -> pd.DataFrame:
        """
        Get today's economic events.

        Args:
            country: Country code(s) to filter by.
            importance: Filter by importance level.

        Returns:
            DataFrame with today's economic events.
        """
        return self.events(period="1d", country=country, importance=importance)

    def this_week(
        self,
        country: str | list[str] | None = None,
        importance: str | None = None,
    ) -> pd.DataFrame:
        """
        Get this week's economic events.

        Args:
            country: Country code(s) to filter by.
            importance: Filter by importance level.

        Returns:
            DataFrame with this week's economic events.
        """
        return self.events(period="1w", country=country, importance=importance)

    def this_month(
        self,
        country: str | list[str] | None = None,
        importance: str | None = None,
    ) -> pd.DataFrame:
        """
        Get this month's economic events.

        Args:
            country: Country code(s) to filter by.
            importance: Filter by importance level.

        Returns:
            DataFrame with this month's economic events.
        """
        return self.events(period="1mo", country=country, importance=importance)

    def high_importance(
        self,
        period: str = "1w",
        country: str | list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Get high importance events only.

        Args:
            period: Time period (1d, 1w, 2w, 1mo).
            country: Country code(s) to filter by.

        Returns:
            DataFrame with high importance events.
        """
        return self.events(period=period, country=country, importance="high")

    @staticmethod
    def countries() -> list[str]:
        """
        Get list of supported country codes.

        Returns:
            List of country codes.

        Examples:
            >>> EconomicCalendar.countries()
            ['TR', 'US', 'EU', 'DE', 'GB', 'JP', 'CN', ...]
        """
        return EconomicCalendar.COUNTRIES.copy()

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

    def _parse_countries(self, country: str | list[str] | None) -> list[str]:
        """Parse country parameter to list of codes."""
        if country is None:
            return ["TR", "US"]
        if isinstance(country, str):
            return [country.upper()]
        return [c.upper() for c in country]

    def __repr__(self) -> str:
        return "EconomicCalendar()"


def economic_calendar(
    period: str = "1w",
    country: str | list[str] | None = None,
    importance: str | None = None,
) -> pd.DataFrame:
    """
    Get economic calendar events (convenience function).

    Args:
        period: Time period (1d, 1w, 2w, 1mo). Defaults to 1w.
        country: Country code(s) to filter by. Defaults to ['TR', 'US'].
        importance: Filter by importance level ('low', 'mid', 'high').

    Returns:
        DataFrame with economic events.

    Examples:
        >>> import borsapy as bp
        >>> bp.economic_calendar()  # This week, TR + US
        >>> bp.economic_calendar(country="TR", importance="high")
    """
    cal = EconomicCalendar()
    return cal.events(period=period, country=country, importance=importance)
