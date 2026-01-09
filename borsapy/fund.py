"""Fund class for mutual fund data - yfinance-like API."""

from datetime import datetime
from typing import Any

import numpy as np
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

    @property
    def allocation(self) -> pd.DataFrame:
        """
        Get current portfolio allocation (asset breakdown) for last 7 days.

        For longer periods, use allocation_history() method.

        Returns:
            DataFrame with columns: Date, asset_type, asset_name, weight.

        Examples:
            >>> fund = Fund("AAK")
            >>> fund.allocation
                             Date asset_type         asset_name  weight
            0 2024-12-20         HS        Hisse Senedi   45.32
            1 2024-12-20         DB        Devlet Bonusu  30.15
            ...
        """
        return self._provider.get_allocation(self._fund_code)

    def allocation_history(
        self,
        period: str = "1mo",
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> pd.DataFrame:
        """
        Get historical portfolio allocation (asset breakdown).

        Note: TEFAS API supports maximum ~100 days (3 months) of data.

        Args:
            period: How much data to fetch. Valid periods:
                    1d, 5d, 1mo, 3mo (max ~100 days).
                    Ignored if start is provided.
            start: Start date (string or datetime).
            end: End date (string or datetime). Defaults to today.

        Returns:
            DataFrame with columns: Date, asset_type, asset_name, weight.

        Examples:
            >>> fund = Fund("AAK")
            >>> fund.allocation_history(period="1mo")  # Last month
            >>> fund.allocation_history(period="3mo")  # Last 3 months (max)
            >>> fund.allocation_history(start="2024-10-01", end="2024-12-31")
        """
        start_dt = self._parse_date(start) if start else None
        end_dt = self._parse_date(end) if end else None

        # If no start date, calculate from period
        if start_dt is None:
            from datetime import timedelta
            end_dt = end_dt or datetime.now()
            days = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90}.get(period, 30)
            # Cap at 100 days (API limit)
            days = min(days, 100)
            start_dt = end_dt - timedelta(days=days)

        return self._provider.get_allocation(
            fund_code=self._fund_code,
            start=start_dt,
            end=end_dt,
        )

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

    def sharpe_ratio(self, period: str = "1y", risk_free_rate: float | None = None) -> float:
        """
        Calculate the Sharpe ratio for the fund.

        Sharpe Ratio = (Rp - Rf) / σp
        Where:
        - Rp = Annualized return of the fund
        - Rf = Risk-free rate (default: 10Y government bond yield)
        - σp = Annualized standard deviation of returns

        Args:
            period: Period for calculation ("1y", "3y", "5y"). Default is "1y".
            risk_free_rate: Annual risk-free rate as decimal (e.g., 0.28 for 28%).
                           If None, uses current 10Y bond yield from bp.risk_free_rate().

        Returns:
            Sharpe ratio as float. Higher is better (>1 good, >2 very good, >3 excellent).

        Examples:
            >>> fund = bp.Fund("YAY")
            >>> fund.sharpe_ratio()  # 1-year Sharpe with current risk-free rate
            0.85

            >>> fund.sharpe_ratio(period="3y")  # 3-year Sharpe
            1.23

            >>> fund.sharpe_ratio(risk_free_rate=0.25)  # Custom risk-free rate
            0.92
        """
        metrics = self.risk_metrics(period=period, risk_free_rate=risk_free_rate)
        return metrics.get("sharpe_ratio", np.nan)

    def risk_metrics(
        self,
        period: str = "1y",
        risk_free_rate: float | None = None,
    ) -> dict[str, Any]:
        """
        Calculate comprehensive risk metrics for the fund.

        Args:
            period: Period for calculation ("1y", "3y", "5y"). Default is "1y".
            risk_free_rate: Annual risk-free rate as decimal (e.g., 0.28 for 28%).
                           If None, uses current 10Y bond yield.

        Returns:
            Dictionary with risk metrics:
            - annualized_return: Annualized return (%)
            - annualized_volatility: Annualized standard deviation (%)
            - sharpe_ratio: Risk-adjusted return (Rp - Rf) / σp
            - sortino_ratio: Downside risk-adjusted return
            - max_drawdown: Maximum peak-to-trough decline (%)
            - risk_free_rate: Risk-free rate used (%)
            - trading_days: Number of trading days in the period

        Examples:
            >>> fund = bp.Fund("YAY")
            >>> metrics = fund.risk_metrics()
            >>> print(f"Sharpe: {metrics['sharpe_ratio']:.2f}")
            >>> print(f"Max Drawdown: {metrics['max_drawdown']:.1f}%")
        """
        # Get historical data
        df = self.history(period=period)

        if df.empty or len(df) < 20:
            return {
                "annualized_return": np.nan,
                "annualized_volatility": np.nan,
                "sharpe_ratio": np.nan,
                "sortino_ratio": np.nan,
                "max_drawdown": np.nan,
                "risk_free_rate": np.nan,
                "trading_days": 0,
            }

        # Calculate daily returns
        prices = df["Price"]
        daily_returns = prices.pct_change().dropna()
        trading_days = len(daily_returns)

        # Annualization factor (trading days per year)
        annualization_factor = 252

        # Annualized return
        total_return = (prices.iloc[-1] / prices.iloc[0]) - 1
        years = trading_days / annualization_factor
        annualized_return = ((1 + total_return) ** (1 / years) - 1) * 100

        # Annualized volatility
        daily_volatility = daily_returns.std()
        annualized_volatility = daily_volatility * np.sqrt(annualization_factor) * 100

        # Get risk-free rate
        if risk_free_rate is None:
            try:
                from borsapy.bond import risk_free_rate as get_rf_rate
                rf = get_rf_rate() * 100  # Returns decimal like 0.28, convert to %
            except Exception:
                rf = 30.0  # Fallback: approximate Turkish 10Y yield
        else:
            rf = risk_free_rate * 100  # Convert decimal to percentage

        # Sharpe Ratio
        if annualized_volatility > 0:
            sharpe = (annualized_return - rf) / annualized_volatility
        else:
            sharpe = np.nan

        # Sortino Ratio (uses downside deviation)
        negative_returns = daily_returns[daily_returns < 0]
        if len(negative_returns) > 0:
            downside_deviation = negative_returns.std() * np.sqrt(annualization_factor) * 100
            if downside_deviation > 0:
                sortino = (annualized_return - rf) / downside_deviation
            else:
                sortino = np.nan
        else:
            sortino = np.inf  # No negative returns

        # Maximum Drawdown
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.cummax()
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = drawdowns.min() * 100  # Negative percentage

        return {
            "annualized_return": round(annualized_return, 2),
            "annualized_volatility": round(annualized_volatility, 2),
            "sharpe_ratio": round(sharpe, 2) if not np.isnan(sharpe) else np.nan,
            "sortino_ratio": round(sortino, 2) if not np.isnan(sortino) and not np.isinf(sortino) else sortino,
            "max_drawdown": round(max_drawdown, 2),
            "risk_free_rate": round(rf, 2),
            "trading_days": trading_days,
        }

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


def screen_funds(
    fund_type: str = "YAT",
    founder: str | None = None,
    min_return_1m: float | None = None,
    min_return_3m: float | None = None,
    min_return_6m: float | None = None,
    min_return_ytd: float | None = None,
    min_return_1y: float | None = None,
    min_return_3y: float | None = None,
    limit: int = 50,
) -> pd.DataFrame:
    """
    Screen funds based on fund type and return criteria.

    Args:
        fund_type: Fund type filter:
            - "YAT": Investment Funds (Yatırım Fonları) - default
            - "EMK": Pension Funds (Emeklilik Fonları)
        founder: Filter by fund management company code (e.g., "AKP", "GPY", "ISP")
        min_return_1m: Minimum 1-month return (%)
        min_return_3m: Minimum 3-month return (%)
        min_return_6m: Minimum 6-month return (%)
        min_return_ytd: Minimum year-to-date return (%)
        min_return_1y: Minimum 1-year return (%)
        min_return_3y: Minimum 3-year return (%)
        limit: Maximum number of results (default: 50)

    Returns:
        DataFrame with funds matching the criteria, sorted by 1-year return.

    Examples:
        >>> import borsapy as bp
        >>> bp.screen_funds(fund_type="EMK")  # All pension funds
           fund_code                    name  return_1y  ...

        >>> bp.screen_funds(min_return_1y=50)  # Funds with >50% 1Y return
           fund_code                    name  return_1y  ...

        >>> bp.screen_funds(fund_type="EMK", min_return_ytd=20)
           fund_code                    name  return_ytd  ...
    """
    provider = get_tefas_provider()
    results = provider.screen_funds(
        fund_type=fund_type,
        founder=founder,
        min_return_1m=min_return_1m,
        min_return_3m=min_return_3m,
        min_return_6m=min_return_6m,
        min_return_ytd=min_return_ytd,
        min_return_1y=min_return_1y,
        min_return_3y=min_return_3y,
        limit=limit,
    )

    if not results:
        return pd.DataFrame(columns=["fund_code", "name", "fund_type", "return_1y"])

    return pd.DataFrame(results)


def compare_funds(fund_codes: list[str]) -> dict[str, Any]:
    """
    Compare multiple funds side by side.

    Args:
        fund_codes: List of TEFAS fund codes to compare (max 10)

    Returns:
        Dictionary with:
        - funds: List of fund details with performance metrics
        - rankings: Ranking by different criteria (by_return_1y, by_return_ytd, by_size, by_risk_asc)
        - summary: Aggregate statistics (avg_return_1y, best/worst returns, total_size)

    Examples:
        >>> import borsapy as bp
        >>> result = bp.compare_funds(["AAK", "TTE", "YAF"])
        >>> result['rankings']['by_return_1y']
        ['TTE', 'YAF', 'AAK']

        >>> result['summary']
        {'fund_count': 3, 'avg_return_1y': 45.2, 'best_return_1y': 72.1, ...}

        >>> for fund in result['funds']:
        ...     print(f"{fund['fund_code']}: {fund['return_1y']}%")
        AAK: 32.5%
        TTE: 72.1%
        YAF: 31.0%
    """
    provider = get_tefas_provider()
    return provider.compare_funds(fund_codes)
