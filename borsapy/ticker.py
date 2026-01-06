"""Ticker class for stock data - yfinance-like API."""

from collections.abc import Iterator
from datetime import datetime, timedelta
from functools import cached_property
from typing import Any

import pandas as pd

from borsapy._providers.kap import get_kap_provider
from borsapy._providers.paratic import get_paratic_provider


class FastInfo:
    """
    Fast access to common ticker information.

    Similar to yfinance's FastInfo, provides quick access to
    frequently used data through a dict-like interface.

    Attributes:
        currency: Trading currency (TRY)
        exchange: Exchange name (BIST)
        timezone: Market timezone
        last_price: Last traded price
        open: Opening price
        day_high: Day's high
        day_low: Day's low
        previous_close: Previous close price
        volume: Trading volume (lot)
        amount: Trading volume (TL)
        market_cap: Market capitalization
        shares: Shares outstanding
        pe_ratio: Price/Earnings ratio (F/K)
        pb_ratio: Price/Book ratio (PD/DD)
        year_high: 52-week high
        year_low: 52-week low
        fifty_day_average: 50-day moving average
        two_hundred_day_average: 200-day moving average
    """

    _KEYS = [
        "currency",
        "exchange",
        "timezone",
        "last_price",
        "open",
        "day_high",
        "day_low",
        "previous_close",
        "volume",
        "amount",
        "market_cap",
        "shares",
        "pe_ratio",
        "pb_ratio",
        "year_high",
        "year_low",
        "fifty_day_average",
        "two_hundred_day_average",
        "free_float",
        "foreign_ratio",
    ]

    def __init__(self, ticker: "Ticker"):
        self._ticker = ticker
        self._data: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        """Load all fast info data."""
        if self._data is not None:
            return self._data

        # Get basic quote info
        info = self._ticker.info

        # Get company metrics from İş Yatırım
        try:
            metrics = self._ticker._get_isyatirim().get_company_metrics(
                self._ticker._symbol
            )
        except Exception:
            metrics = {}

        # Calculate 52-week high/low and moving averages from history
        year_high = None
        year_low = None
        fifty_day_avg = None
        two_hundred_day_avg = None

        try:
            hist = self._ticker.history(period="1y")
            if not hist.empty:
                year_high = float(hist["High"].max())
                year_low = float(hist["Low"].min())
                if len(hist) >= 50:
                    fifty_day_avg = float(hist["Close"].tail(50).mean())
                if len(hist) >= 200:
                    two_hundred_day_avg = float(hist["Close"].tail(200).mean())
        except Exception:
            pass

        # Calculate shares from market cap and price
        shares = None
        if metrics.get("market_cap") and info.get("last"):
            shares = int(metrics["market_cap"] / info["last"])

        self._data = {
            "currency": "TRY",
            "exchange": "BIST",
            "timezone": "Europe/Istanbul",
            "last_price": info.get("last"),
            "open": info.get("open"),
            "day_high": info.get("high"),
            "day_low": info.get("low"),
            "previous_close": info.get("close"),
            "volume": info.get("volume"),
            "amount": info.get("amount"),
            "market_cap": metrics.get("market_cap"),
            "shares": shares,
            "pe_ratio": metrics.get("pe_ratio"),
            "pb_ratio": metrics.get("pb_ratio"),
            "year_high": year_high,
            "year_low": year_low,
            "fifty_day_average": round(fifty_day_avg, 2) if fifty_day_avg else None,
            "two_hundred_day_average": (
                round(two_hundred_day_avg, 2) if two_hundred_day_avg else None
            ),
            "free_float": metrics.get("free_float"),
            "foreign_ratio": metrics.get("foreign_ratio"),
        }

        return self._data

    def keys(self) -> list[str]:
        """Return available keys."""
        return self._KEYS.copy()

    def __getitem__(self, key: str) -> Any:
        if key not in self._KEYS:
            raise KeyError(f"Invalid key '{key}'. Valid keys: {self._KEYS}")
        return self._load().get(key)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._KEYS:
            raise AttributeError(
                f"'{type(self).__name__}' has no attribute '{name}'. "
                f"Valid attributes: {self._KEYS}"
            )
        return self._load().get(name)

    def __iter__(self):
        return iter(self._load().items())

    def __repr__(self) -> str:
        data = self._load()
        items = [f"{k}={v!r}" for k, v in data.items() if v is not None]
        return f"FastInfo({', '.join(items)})"

    def todict(self) -> dict[str, Any]:
        """Return all data as a dictionary."""
        return self._load().copy()


class EnrichedInfo:
    """
    Lazy-loading info dictionary with yfinance-compatible field names.

    Provides dict-like access to ticker information with three lazy-loaded groups:
    - Basic fields (from Paratic quote): last, open, high, low, close, volume, amount
    - Extended fields (from İş Yatırım + calculations): marketCap, trailingPE, etc.
    - Dividend fields (calculated): dividendYield, exDividendDate

    yfinance aliases are supported for common field names:
    - regularMarketPrice, currentPrice -> last
    - regularMarketOpen -> open
    - regularMarketDayHigh -> high
    - regularMarketDayLow -> low
    - regularMarketPreviousClose -> close
    - regularMarketVolume -> volume

    Examples:
        >>> stock = Ticker("THYAO")
        >>> stock.info['last']  # Basic field - fast
        268.5
        >>> stock.info['marketCap']  # Extended field - lazy loaded
        370530000000
        >>> stock.info['regularMarketPrice']  # yfinance alias
        268.5
        >>> stock.info.get('dividendYield')  # Safe access
        1.28
        >>> stock.info.todict()  # Get all as regular dict
        {...}
    """

    _YFINANCE_ALIASES: dict[str, str] = {
        "regularMarketPrice": "last",
        "currentPrice": "last",
        "regularMarketOpen": "open",
        "regularMarketDayHigh": "high",
        "regularMarketDayLow": "low",
        "regularMarketPreviousClose": "close",
        "regularMarketVolume": "volume",
        "regularMarketChange": "change",
        "regularMarketChangePercent": "change_percent",
    }

    _BASIC_KEYS = [
        "symbol",
        "last",
        "open",
        "high",
        "low",
        "close",
        "volume",  # Lot bazında hacim
        "amount",  # TL bazında hacim
        "change",
        "change_percent",
        "update_time",
    ]

    _EXTENDED_KEYS = [
        "currency",
        "exchange",
        "timezone",
        "sector",
        "industry",
        "website",
        "marketCap",
        "sharesOutstanding",
        "trailingPE",
        "priceToBook",
        "enterpriseToEbitda",
        "netDebt",
        "floatShares",
        "foreignRatio",
        "fiftyTwoWeekHigh",
        "fiftyTwoWeekLow",
        "fiftyDayAverage",
        "twoHundredDayAverage",
        "longBusinessSummary",
    ]

    _DIVIDEND_KEYS = [
        "dividendYield",
        "exDividendDate",
        "trailingAnnualDividendRate",
        "trailingAnnualDividendYield",
    ]

    def __init__(self, ticker: "Ticker"):
        self._ticker = ticker
        self._basic_data: dict[str, Any] | None = None
        self._extended_data: dict[str, Any] | None = None
        self._dividend_data: dict[str, Any] | None = None

    def _load_basic(self) -> dict[str, Any]:
        """Load basic quote data from Paratic."""
        if self._basic_data is None:
            self._basic_data = self._ticker._paratic.get_quote(self._ticker._symbol)
        return self._basic_data

    def _load_extended(self) -> dict[str, Any]:
        """Load extended metrics from İş Yatırım + calculations."""
        if self._extended_data is not None:
            return self._extended_data

        basic = self._load_basic()

        # Get İş Yatırım metrics
        try:
            metrics = self._ticker._get_isyatirim().get_company_metrics(
                self._ticker._symbol
            )
        except Exception:
            metrics = {}

        # Calculate 52-week and moving averages
        year_high = year_low = fifty_avg = two_hundred_avg = None
        try:
            hist = self._ticker.history(period="1y")
            if not hist.empty:
                year_high = float(hist["High"].max())
                year_low = float(hist["Low"].min())
                if len(hist) >= 50:
                    fifty_avg = round(float(hist["Close"].tail(50).mean()), 2)
                if len(hist) >= 200:
                    two_hundred_avg = round(float(hist["Close"].tail(200).mean()), 2)
        except Exception:
            pass

        # Calculate shares
        shares = None
        if metrics.get("market_cap") and basic.get("last"):
            shares = int(metrics["market_cap"] / basic["last"])

        # Get company details from KAP (sector, market, website, businessSummary)
        try:
            kap_details = get_kap_provider().get_company_details(
                self._ticker._symbol
            )
        except Exception:
            kap_details = {}

        self._extended_data = {
            "currency": "TRY",
            "exchange": "BIST",
            "timezone": "Europe/Istanbul",
            "sector": kap_details.get("sector"),
            "industry": kap_details.get("sector"),  # KAP has single level
            "website": kap_details.get("website"),
            "marketCap": metrics.get("market_cap"),
            "sharesOutstanding": shares,
            "trailingPE": metrics.get("pe_ratio"),
            "priceToBook": metrics.get("pb_ratio"),
            "enterpriseToEbitda": metrics.get("ev_ebitda"),
            "netDebt": metrics.get("net_debt"),
            "floatShares": metrics.get("free_float"),
            "foreignRatio": metrics.get("foreign_ratio"),
            "fiftyTwoWeekHigh": year_high,
            "fiftyTwoWeekLow": year_low,
            "fiftyDayAverage": fifty_avg,
            "twoHundredDayAverage": two_hundred_avg,
            "longBusinessSummary": kap_details.get("businessSummary"),
        }

        return self._extended_data

    def _load_dividends(self) -> dict[str, Any]:
        """Load dividend-related fields."""
        if self._dividend_data is not None:
            return self._dividend_data

        self._dividend_data = {
            "dividendYield": None,
            "exDividendDate": None,
            "trailingAnnualDividendRate": None,
            "trailingAnnualDividendYield": None,
        }

        try:
            divs = self._ticker.dividends
            if divs.empty:
                return self._dividend_data

            # Last dividend date
            self._dividend_data["exDividendDate"] = divs.index[0]

            # Trailing annual dividend (sum of last 1 year)
            one_year_ago = datetime.now() - timedelta(days=365)
            annual_divs = divs[divs.index >= one_year_ago]
            annual_total = (
                annual_divs["Amount"].sum() if not annual_divs.empty else 0.0
            )

            self._dividend_data["trailingAnnualDividendRate"] = round(annual_total, 4)

            # Yield calculation
            basic = self._load_basic()
            current_price = basic.get("last", 0)
            if current_price and annual_total:
                yield_pct = (annual_total / current_price) * 100
                self._dividend_data["dividendYield"] = round(yield_pct, 2)
                self._dividend_data["trailingAnnualDividendYield"] = round(
                    yield_pct / 100, 4
                )

        except Exception:
            pass

        return self._dividend_data

    def _resolve_key(self, key: str) -> str:
        """Resolve yfinance alias to actual key."""
        return self._YFINANCE_ALIASES.get(key, key)

    def __getitem__(self, key: str) -> Any:
        resolved_key = self._resolve_key(key)

        # Try basic first (fastest)
        basic = self._load_basic()
        if resolved_key in basic:
            return basic[resolved_key]

        # Try extended
        extended = self._load_extended()
        if resolved_key in extended:
            return extended[resolved_key]

        # Try dividend fields
        dividend = self._load_dividends()
        if resolved_key in dividend:
            return dividend[resolved_key]

        raise KeyError(f"Key '{key}' not found in info")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value with optional default."""
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self) -> list[str]:
        """Return all available keys including yfinance aliases."""
        all_keys = (
            self._BASIC_KEYS
            + self._EXTENDED_KEYS
            + self._DIVIDEND_KEYS
            + list(self._YFINANCE_ALIASES.keys())
        )
        return all_keys

    def items(self) -> Iterator[tuple[str, Any]]:
        """Return all key-value pairs."""
        result = {}
        result.update(self._load_basic())
        result.update(self._load_extended())
        result.update(self._load_dividends())
        return iter(result.items())

    def values(self) -> Iterator[Any]:
        """Return all values."""
        result = {}
        result.update(self._load_basic())
        result.update(self._load_extended())
        result.update(self._load_dividends())
        return iter(result.values())

    def __iter__(self) -> Iterator[str]:
        """Iterate over keys."""
        return iter(self.keys())

    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        resolved_key = self._resolve_key(key)
        return (
            resolved_key in self._BASIC_KEYS
            or resolved_key in self._EXTENDED_KEYS
            or resolved_key in self._DIVIDEND_KEYS
            or key in self._YFINANCE_ALIASES
        )

    def __len__(self) -> int:
        """Return number of fields."""
        return (
            len(self._BASIC_KEYS) + len(self._EXTENDED_KEYS) + len(self._DIVIDEND_KEYS)
        )

    def __repr__(self) -> str:
        # Only show basic data to avoid triggering extended loads
        basic = self._load_basic()
        return f"EnrichedInfo({basic})"

    def todict(self) -> dict[str, Any]:
        """Return all data as a regular dictionary (triggers all loads)."""
        result = {}
        result.update(self._load_basic())
        result.update(self._load_extended())
        result.update(self._load_dividends())
        return result


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
        self._isin_provider = None  # Lazy load for ISIN lookup
        self._hedeffiyat = None  # Lazy load for analyst price targets

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

    def _get_isin_provider(self):
        """Lazy load ISIN provider."""
        if self._isin_provider is None:
            from borsapy._providers.isin import get_isin_provider

            self._isin_provider = get_isin_provider()
        return self._isin_provider

    def _get_hedeffiyat(self):
        """Lazy load hedeffiyat.com.tr provider for analyst price targets."""
        if self._hedeffiyat is None:
            from borsapy._providers.hedeffiyat import get_hedeffiyat_provider

            self._hedeffiyat = get_hedeffiyat_provider()
        return self._hedeffiyat

    @property
    def symbol(self) -> str:
        """Return the ticker symbol."""
        return self._symbol

    @property
    def fast_info(self) -> FastInfo:
        """
        Get fast access to common ticker information.

        Returns a FastInfo object with quick access to frequently used data:
        - currency, exchange, timezone
        - last_price, open, day_high, day_low, previous_close, volume
        - market_cap, shares, pe_ratio, pb_ratio
        - year_high, year_low (52-week)
        - fifty_day_average, two_hundred_day_average
        - free_float, foreign_ratio

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.fast_info.market_cap
            370530000000
            >>> stock.fast_info['pe_ratio']
            2.8
            >>> stock.fast_info.keys()
            ['currency', 'exchange', 'timezone', ...]
        """
        if not hasattr(self, "_fast_info"):
            self._fast_info = FastInfo(self)
        return self._fast_info

    @property
    def info(self) -> EnrichedInfo:
        """
        Get comprehensive ticker information with yfinance-compatible fields.

        Returns:
            EnrichedInfo object providing dict-like access to:

            Basic fields (always loaded, fast):
            - symbol, last, open, high, low, close, volume
            - change, change_percent, update_time

            yfinance aliases (map to basic fields):
            - regularMarketPrice, currentPrice -> last
            - regularMarketOpen -> open
            - regularMarketDayHigh -> high
            - regularMarketDayLow -> low
            - regularMarketPreviousClose -> close
            - regularMarketVolume -> volume

            Extended fields (lazy-loaded on access):
            - marketCap, trailingPE, priceToBook, enterpriseToEbitda
            - sharesOutstanding, fiftyTwoWeekHigh, fiftyTwoWeekLow
            - fiftyDayAverage, twoHundredDayAverage
            - floatShares, foreignRatio, netDebt
            - currency, exchange, timezone

            Dividend fields (lazy-loaded on access):
            - dividendYield, exDividendDate
            - trailingAnnualDividendRate, trailingAnnualDividendYield

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.info['last']  # Basic field - fast
            268.5
            >>> stock.info['marketCap']  # Extended field - fetches İş Yatırım
            370530000000
            >>> stock.info['trailingPE']  # yfinance compatible name
            2.8
            >>> stock.info.get('dividendYield')  # Safe access
            1.28
            >>> stock.info.todict()  # Get all as regular dict
            {...}
        """
        if not hasattr(self, "_enriched_info"):
            self._enriched_info = EnrichedInfo(self)
        return self._enriched_info

    def history(
        self,
        period: str = "1mo",
        interval: str = "1d",
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        actions: bool = False,
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
            actions: If True, include Dividends and Stock Splits columns.
                     Defaults to False.

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume.
            If actions=True, also includes Dividends and Stock Splits columns.
            Index is the Date.

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.history(period="1mo")  # Last month
            >>> stock.history(period="1y", interval="1wk")  # Weekly for 1 year
            >>> stock.history(start="2024-01-01", end="2024-06-30")  # Date range
            >>> stock.history(period="1y", actions=True)  # With dividends/splits
        """
        # Parse dates if strings
        start_dt = self._parse_date(start) if start else None
        end_dt = self._parse_date(end) if end else None

        df = self._paratic.get_history(
            symbol=self._symbol,
            period=period,
            interval=interval,
            start=start_dt,
            end=end_dt,
        )

        if actions and not df.empty:
            df = self._add_actions_to_history(df)

        return df

    def _add_actions_to_history(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Dividends and Stock Splits columns to historical data.

        Args:
            df: Historical OHLCV DataFrame.

        Returns:
            DataFrame with added Dividends and Stock Splits columns.
        """
        # Initialize columns with zeros
        df = df.copy()
        df["Dividends"] = 0.0
        df["Stock Splits"] = 0.0

        # Get dividends
        try:
            divs = self.dividends
            if not divs.empty:
                for div_date, row in divs.iterrows():
                    # Normalize dates for comparison
                    div_date_normalized = pd.Timestamp(div_date).normalize()
                    for idx in df.index:
                        idx_normalized = pd.Timestamp(idx).normalize()
                        if div_date_normalized == idx_normalized:
                            df.loc[idx, "Dividends"] = row.get("Amount", 0)
                            break
        except Exception:
            pass

        # Get stock splits (capital increases)
        try:
            splits = self.splits
            if not splits.empty:
                for split_date, row in splits.iterrows():
                    split_date_normalized = pd.Timestamp(split_date).normalize()
                    # Calculate split ratio
                    # BonusFromCapital + BonusFromDividend = total bonus percentage
                    bonus_pct = row.get("BonusFromCapital", 0) + row.get(
                        "BonusFromDividend", 0
                    )
                    if bonus_pct > 0:
                        # Convert percentage to split ratio (e.g., 20% bonus = 1.2 split)
                        split_ratio = 1 + (bonus_pct / 100)
                        for idx in df.index:
                            idx_normalized = pd.Timestamp(idx).normalize()
                            if split_date_normalized == idx_normalized:
                                df.loc[idx, "Stock Splits"] = split_ratio
                                break
        except Exception:
            pass

        return df

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

    def _calculate_ttm(self, quarterly_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate trailing twelve months (TTM) by summing last 4 quarters.

        Args:
            quarterly_df: DataFrame with quarterly data (columns in YYYYQN format).

        Returns:
            DataFrame with single TTM column containing summed values.
        """
        if quarterly_df.empty or len(quarterly_df.columns) < 4:
            return pd.DataFrame(columns=["TTM"])

        # First 4 columns = last 4 quarters (most recent first)
        last_4_quarters = quarterly_df.iloc[:, :4]

        # Convert to numeric, coercing errors to NaN
        numeric_df = last_4_quarters.apply(pd.to_numeric, errors="coerce")

        return numeric_df.sum(axis=1).to_frame(name="TTM")

    @cached_property
    def ttm_income_stmt(self) -> pd.DataFrame:
        """
        Get trailing twelve months (TTM) income statement.

        Calculates TTM by summing the last 4 quarters of income statement data.
        Useful for analyzing recent performance without waiting for annual reports.

        Returns:
            DataFrame with TTM column containing summed values for each line item.

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.ttm_income_stmt
                                            TTM
            Net Satışlar             4.5e+11
            Brüt Kar                 1.2e+11
            Faaliyet Karı            8.0e+10
            Net Kar                  3.0e+10
        """
        return self._calculate_ttm(self.quarterly_income_stmt)

    @cached_property
    def ttm_cashflow(self) -> pd.DataFrame:
        """
        Get trailing twelve months (TTM) cash flow statement.

        Calculates TTM by summing the last 4 quarters of cash flow data.

        Returns:
            DataFrame with TTM column containing summed values for each line item.

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.ttm_cashflow
                                                TTM
            İşletme Faaliyetlerinden Nakit    5.0e+10
            Yatırım Faaliyetlerinden Nakit   -2.0e+10
            Finansman Faaliyetlerinden Nakit -1.0e+10
        """
        return self._calculate_ttm(self.quarterly_cashflow)

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
    def recommendations_summary(self) -> dict[str, int]:
        """
        Get analyst recommendation summary with buy/hold/sell counts.

        Aggregates individual analyst recommendations from hedeffiyat.com.tr
        into yfinance-compatible categories.

        Returns:
            Dictionary with counts:
            - strongBuy: Strong buy recommendations
            - buy: Buy recommendations (includes "Endeks Üstü Getiri")
            - hold: Hold recommendations (includes "Nötr", "Endekse Paralel")
            - sell: Sell recommendations (includes "Endeks Altı Getiri")
            - strongSell: Strong sell recommendations

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.recommendations_summary
            {'strongBuy': 0, 'buy': 31, 'hold': 0, 'sell': 0, 'strongSell': 0}
        """
        return self._get_hedeffiyat().get_recommendations_summary(self._symbol)

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

    def get_news_content(self, disclosure_id: int | str) -> str | None:
        """
        Get full HTML content of a KAP disclosure by ID.

        Args:
            disclosure_id: KAP disclosure ID from news DataFrame URL.

        Returns:
            Raw HTML content or None if failed.

        Examples:
            >>> stock = Ticker("THYAO")
            >>> html = stock.get_news_content(1530826)
        """
        return self._get_kap().get_disclosure_content(disclosure_id)

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

    @cached_property
    def isin(self) -> str | None:
        """
        Get ISIN (International Securities Identification Number) code.

        ISIN is a 12-character alphanumeric code that uniquely identifies
        a security, standardized by ISO 6166.

        Returns:
            ISIN code string (e.g., "TRATHYAO91M5") or None if not found.

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.isin
            'TRATHYAO91M5'
        """
        return self._get_isin_provider().get_isin(self._symbol)

    @cached_property
    def analyst_price_targets(self) -> dict[str, float | int | None]:
        """
        Get analyst price target data from hedeffiyat.com.tr.

        Returns aggregated price target information from multiple analysts.

        Returns:
            Dictionary with:
            - current: Current stock price
            - low: Lowest analyst target price
            - high: Highest analyst target price
            - mean: Average target price
            - median: Median target price
            - numberOfAnalysts: Number of analysts covering the stock

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.analyst_price_targets
            {'current': 268.5, 'low': 388.0, 'high': 580.0, 'mean': 474.49,
             'median': 465.0, 'numberOfAnalysts': 19}
        """
        return self._get_hedeffiyat().get_price_targets(self._symbol)

    @cached_property
    def earnings_dates(self) -> pd.DataFrame:
        """
        Get upcoming earnings announcement dates.

        Derived from KAP calendar, showing expected financial report dates.
        Compatible with yfinance earnings_dates format.

        Returns:
            DataFrame with index as Earnings Date and columns:
            - EPS Estimate: Always None (not available for BIST)
            - Reported EPS: Always None (not available for BIST)
            - Surprise (%): Always None (not available for BIST)

        Examples:
            >>> stock = Ticker("THYAO")
            >>> stock.earnings_dates
                            EPS Estimate  Reported EPS  Surprise(%)
            Earnings Date
            2026-03-11           None          None         None
            2026-05-11           None          None         None
        """
        cal = self.calendar
        if cal.empty:
            return pd.DataFrame(
                columns=["EPS Estimate", "Reported EPS", "Surprise(%)"]
            )

        # Filter for financial reports only
        financial_reports = cal[
            cal["Subject"].str.contains("Finansal Rapor", case=False, na=False)
        ]

        if financial_reports.empty:
            return pd.DataFrame(
                columns=["EPS Estimate", "Reported EPS", "Surprise(%)"]
            )

        # Use EndDate as the earnings date (latest expected date)
        earnings_dates = []
        for _, row in financial_reports.iterrows():
            end_date = row.get("EndDate", "")
            if end_date:
                try:
                    # Parse Turkish date format (DD.MM.YYYY)
                    parsed = datetime.strptime(end_date, "%d.%m.%Y")
                    earnings_dates.append(parsed)
                except ValueError:
                    continue

        if not earnings_dates:
            return pd.DataFrame(
                columns=["EPS Estimate", "Reported EPS", "Surprise(%)"]
            )

        result = pd.DataFrame(
            {
                "EPS Estimate": [None] * len(earnings_dates),
                "Reported EPS": [None] * len(earnings_dates),
                "Surprise(%)": [None] * len(earnings_dates),
            },
            index=pd.DatetimeIndex(earnings_dates, name="Earnings Date"),
        )
        result = result.sort_index()
        return result

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
