"""Multi-ticker functions and classes - yfinance-like API."""

from datetime import datetime

import pandas as pd

from borsapy._providers.paratic import get_paratic_provider
from borsapy.ticker import Ticker


class Tickers:
    """
    Container for multiple Ticker objects.

    Examples:
        >>> import borsapy as bp
        >>> tickers = bp.Tickers("THYAO GARAN AKBNK")
        >>> tickers.tickers["THYAO"].info
        >>> tickers.symbols
        ['THYAO', 'GARAN', 'AKBNK']

        >>> tickers = bp.Tickers(["THYAO", "GARAN", "AKBNK"])
        >>> for symbol, ticker in tickers:
        ...     print(symbol, ticker.info['last'])
    """

    def __init__(self, symbols: str | list[str]):
        """
        Initialize Tickers with multiple symbols.

        Args:
            symbols: Space-separated string or list of symbols.
                     Example: "THYAO GARAN AKBNK" or ["THYAO", "GARAN", "AKBNK"]
        """
        if isinstance(symbols, str):
            self._symbols = [s.strip().upper() for s in symbols.split() if s.strip()]
        else:
            self._symbols = [s.strip().upper() for s in symbols if s.strip()]

        self._tickers: dict[str, Ticker] = {}
        for symbol in self._symbols:
            self._tickers[symbol] = Ticker(symbol)

    @property
    def symbols(self) -> list[str]:
        """Return list of symbols."""
        return self._symbols.copy()

    @property
    def tickers(self) -> dict[str, Ticker]:
        """Return dictionary of Ticker objects keyed by symbol."""
        return self._tickers

    def history(
        self,
        period: str = "1mo",
        interval: str = "1d",
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        group_by: str = "column",
    ) -> pd.DataFrame:
        """
        Get historical data for all tickers.

        Args:
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, etc.)
            interval: Data interval (1d, 1wk, 1mo)
            start: Start date
            end: End date
            group_by: How to group columns ('column' or 'ticker')

        Returns:
            DataFrame with multi-level columns.
        """
        return download(
            self._symbols,
            period=period,
            interval=interval,
            start=start,
            end=end,
            group_by=group_by,
        )

    def __iter__(self):
        """Iterate over (symbol, ticker) pairs."""
        return iter(self._tickers.items())

    def __len__(self) -> int:
        """Return number of tickers."""
        return len(self._tickers)

    def __getitem__(self, symbol: str) -> Ticker:
        """Get ticker by symbol."""
        symbol = symbol.upper()
        if symbol not in self._tickers:
            raise KeyError(f"Symbol not found: {symbol}")
        return self._tickers[symbol]

    def __repr__(self) -> str:
        return f"Tickers({self._symbols})"


def download(
    tickers: str | list[str],
    period: str = "1mo",
    interval: str = "1d",
    start: datetime | str | None = None,
    end: datetime | str | None = None,
    group_by: str = "column",
    progress: bool = True,
) -> pd.DataFrame:
    """
    Download historical data for multiple tickers.

    Similar to yfinance.download(), this function fetches OHLCV data
    for multiple stocks and returns a DataFrame with multi-level columns.

    Args:
        tickers: Space-separated string or list of symbols.
                 Example: "THYAO GARAN AKBNK" or ["THYAO", "GARAN"]
        period: Data period. Valid values:
                1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max.
                Ignored if start is provided.
        interval: Data interval. Valid values:
                  1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo.
        start: Start date (string YYYY-MM-DD or datetime).
        end: End date (string YYYY-MM-DD or datetime). Defaults to today.
        group_by: How to group the output columns:
                  - 'column': MultiIndex (Price, Symbol) - default
                  - 'ticker': MultiIndex (Symbol, Price)
        progress: Show progress (not implemented, for yfinance compatibility).

    Returns:
        DataFrame with OHLCV data.
        - If single ticker: Simple columns (Open, High, Low, Close, Volume)
        - If multiple tickers: MultiIndex columns based on group_by

    Examples:
        >>> import borsapy as bp

        # Single ticker (returns simple DataFrame)
        >>> bp.download("THYAO", period="1mo")
                         Open    High     Low   Close    Volume
        Date
        2024-12-01    265.00  268.00  264.00  267.50  12345678

        # Multiple tickers (returns MultiIndex DataFrame)
        >>> bp.download(["THYAO", "GARAN"], period="1mo")
                           Open                 High          ...
                          THYAO   GARAN        THYAO   GARAN
        Date
        2024-12-01       265.00  45.50        268.00   46.20

        # With date range
        >>> bp.download("THYAO GARAN AKBNK", start="2024-01-01", end="2024-06-30")

        # Group by ticker
        >>> bp.download(["THYAO", "GARAN"], group_by="ticker")
                          THYAO                      GARAN
                           Open    High  Low Close   Open    High
        Date
        2024-12-01       265.00  268.00  ...        45.50   46.20
    """
    # Parse symbols
    if isinstance(tickers, str):
        symbols = [s.strip().upper() for s in tickers.split() if s.strip()]
    else:
        symbols = [s.strip().upper() for s in tickers if s.strip()]

    if not symbols:
        raise ValueError("No symbols provided")

    # Parse dates
    start_dt = _parse_date(start) if start else None
    end_dt = _parse_date(end) if end else None

    provider = get_paratic_provider()

    # Fetch data for each symbol
    data_frames: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        try:
            df = provider.get_history(
                symbol=symbol,
                period=period,
                interval=interval,
                start=start_dt,
                end=end_dt,
            )
            if not df.empty:
                data_frames[symbol] = df
        except Exception:
            # Skip failed symbols silently (yfinance behavior)
            continue

    if not data_frames:
        return pd.DataFrame()

    # Single ticker - return simple DataFrame
    if len(symbols) == 1 and len(data_frames) == 1:
        return list(data_frames.values())[0]

    # Multiple tickers - create MultiIndex DataFrame
    if group_by == "ticker":
        # Group by ticker first: (THYAO, Open), (THYAO, High), ...
        result = pd.concat(data_frames, axis=1)
        # result columns are already (symbol, price)
    else:
        # Group by column first: (Open, THYAO), (Open, GARAN), ...
        result = pd.concat(data_frames, axis=1)
        # Swap levels to get (price, symbol)
        result = result.swaplevel(axis=1)
        result = result.sort_index(axis=1, level=0)

    return result


def _parse_date(date: str | datetime) -> datetime:
    """Parse a date string to datetime."""
    if isinstance(date, datetime):
        return date
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date, fmt)
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {date}")
