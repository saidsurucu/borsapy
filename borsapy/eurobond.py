"""Turkish sovereign Eurobond data.

Provides access to Turkish government bonds issued in foreign currencies
(USD and EUR denominated).

Examples:
    >>> import borsapy as bp

    # Get single Eurobond by ISIN
    >>> bond = bp.Eurobond("US900123DG28")
    >>> bond.isin                     # "US900123DG28"
    >>> bond.maturity                 # datetime(2033, 1, 19)
    >>> bond.currency                 # "USD"
    >>> bond.bid_yield                # 6.55
    >>> bond.ask_yield                # 6.24
    >>> bond.info                     # All data as dict

    # List all Eurobonds
    >>> bp.eurobonds()                # DataFrame with all Eurobonds
    >>> bp.eurobonds(currency="USD")  # Only USD bonds
    >>> bp.eurobonds(currency="EUR")  # Only EUR bonds
"""

from datetime import date as date_type
from datetime import datetime, timedelta

import pandas as pd

from borsapy._providers.ziraat_eurobond import get_eurobond_provider
from borsapy.exceptions import DataNotAvailableError

_PERIOD_DAYS = {
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 365 * 2,
    "3y": 365 * 3,
    "5y": 365 * 5,
    "10y": 365 * 10,
    "ytd": None,  # handled separately
    "max": 365 * 15,
}


def _parse_date_arg(value: str | datetime | date_type) -> date_type:
    """Parse start/end argument (accepts str YYYY-MM-DD, datetime, or date)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date_type):
        return value
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {value!r}")


class Eurobond:
    """Single Turkish sovereign Eurobond interface.

    Provides access to bond data including prices, yields,
    maturity, and other characteristics.

    Attributes:
        isin: ISIN code of the bond.
        maturity: Maturity date.
        days_to_maturity: Days until maturity.
        currency: Bond currency (USD or EUR).
        bid_price: Bid price (buying price).
        bid_yield: Bid yield (buying yield).
        ask_price: Ask price (selling price).
        ask_yield: Ask yield (selling yield).
        info: All bond data as dictionary.

    Examples:
        >>> bond = Eurobond("US900123DG28")
        >>> bond.bid_yield
        6.55
        >>> bond.currency
        'USD'
    """

    def __init__(self, isin: str):
        """Initialize Eurobond by ISIN.

        Args:
            isin: ISIN code (e.g., "US900123DG28").

        Raises:
            DataNotAvailableError: If bond not found.
        """
        self._isin = isin.upper()
        self._provider = get_eurobond_provider()
        self._data_cache: dict | None = None

    @property
    def _data(self) -> dict:
        """Lazy-loaded bond data."""
        if self._data_cache is None:
            self._data_cache = self._provider.get_eurobond(self._isin)
            if self._data_cache is None:
                raise DataNotAvailableError(f"Eurobond not found: {self._isin}")
        return self._data_cache

    @property
    def isin(self) -> str:
        """ISIN code of the bond."""
        return self._data["isin"]

    @property
    def maturity(self) -> datetime | None:
        """Maturity date of the bond."""
        return self._data.get("maturity")

    @property
    def days_to_maturity(self) -> int:
        """Number of days until maturity."""
        return self._data.get("days_to_maturity", 0)

    @property
    def currency(self) -> str:
        """Bond currency (USD or EUR)."""
        return self._data.get("currency", "")

    @property
    def bid_price(self) -> float | None:
        """Bid price (buying price)."""
        return self._data.get("bid_price")

    @property
    def bid_yield(self) -> float | None:
        """Bid yield (buying yield) as percentage."""
        return self._data.get("bid_yield")

    @property
    def ask_price(self) -> float | None:
        """Ask price (selling price)."""
        return self._data.get("ask_price")

    @property
    def ask_yield(self) -> float | None:
        """Ask yield (selling yield) as percentage."""
        return self._data.get("ask_yield")

    @property
    def info(self) -> dict:
        """All bond data as dictionary.

        Returns:
            Dict with all bond attributes.
        """
        return self._data.copy()

    def history(
        self,
        period: str | None = None,
        start: str | datetime | date_type | None = None,
        end: str | datetime | date_type | None = None,
        skip_weekends: bool = True,
    ) -> pd.DataFrame:
        """Fetch daily historical bid/ask prices and yields.

        Args:
            period: Lookback window ending today. One of 1mo, 3mo, 6mo, 1y,
                2y, 3y, 5y, 10y, ytd, max. Ignored if ``start`` is given.
            start: Start date (str "YYYY-MM-DD", datetime, or date).
            end: End date, defaults to today.
            skip_weekends: Skip Sat/Sun (API returns zeros on weekends).

        Returns:
            DataFrame indexed by Date with columns: bid_price, bid_yield,
            ask_price, ask_yield, days_to_maturity. Holidays and suspended
            trading days (bid_price == 0) are dropped.

        Examples:
            >>> bond = bp.Eurobond("US900123DG28")
            >>> bond.history(period="1y")
            >>> bond.history(start="2021-08-16", end="2026-03-11")

        Note:
            Long ranges perform one HTTP request per business day against the
            Ziraat Bank API — expect ~30 seconds per year of data on a cold
            cache. Subsequent calls hit the per-date cache.
        """
        today = datetime.now().date()

        # Resolve end
        end_d = _parse_date_arg(end) if end else today

        # Resolve start
        if start:
            start_d = _parse_date_arg(start)
        elif period:
            if period == "ytd":
                start_d = date_type(today.year, 1, 1)
            elif period in _PERIOD_DAYS:
                start_d = end_d - timedelta(days=_PERIOD_DAYS[period])
            else:
                raise ValueError(
                    f"Unknown period {period!r}. Use start= or one of: "
                    f"{', '.join(sorted(_PERIOD_DAYS))}"
                )
        else:
            # Default to 1 month
            start_d = end_d - timedelta(days=30)

        rows = self._provider.get_history(
            self._isin, start_d, end_d, skip_weekends=skip_weekends
        )

        columns = [
            "bid_price",
            "bid_yield",
            "ask_price",
            "ask_yield",
            "days_to_maturity",
        ]
        if not rows:
            return pd.DataFrame(columns=columns, index=pd.DatetimeIndex([], name="Date"))

        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["date"])
        df = df.drop(columns=["date"]).set_index("Date")
        return df[columns]

    def __repr__(self) -> str:
        """String representation."""
        try:
            maturity_year = self.maturity.year if self.maturity else "?"
            return f"Eurobond({self._isin}, {self.currency}, {maturity_year}, yield={self.bid_yield}%)"
        except DataNotAvailableError:
            return f"Eurobond({self._isin})"


def eurobonds(currency: str | None = None) -> pd.DataFrame:
    """Get all Turkish sovereign Eurobonds as DataFrame.

    Args:
        currency: Optional filter by currency ("USD" or "EUR").

    Returns:
        DataFrame with columns: isin, maturity, days_to_maturity,
        currency, bid_price, bid_yield, ask_price, ask_yield.

    Examples:
        >>> import borsapy as bp
        >>> bp.eurobonds()                # All Eurobonds
        >>> bp.eurobonds(currency="USD")  # USD bonds only
        >>> bp.eurobonds(currency="EUR")  # EUR bonds only
    """
    provider = get_eurobond_provider()
    data = provider.get_eurobonds(currency=currency)

    if not data:
        return pd.DataFrame(
            columns=[
                "isin",
                "maturity",
                "days_to_maturity",
                "currency",
                "bid_price",
                "bid_yield",
                "ask_price",
                "ask_yield",
            ]
        )

    df = pd.DataFrame(data)
    df = df.sort_values("maturity")
    return df
