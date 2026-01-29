"""Portfolio management for borsapy.

A yfinance-like interface for managing multi-asset portfolios with
stocks, forex, crypto, and mutual funds.

Examples:
    >>> import borsapy as bp
    >>> portfolio = bp.Portfolio()
    >>> portfolio.add("THYAO", shares=100, cost=280.0)
    >>> portfolio.add("gram-altin", shares=10, asset_type="fx")
    >>> portfolio.add("YAY", shares=1000, asset_type="fund")
    >>> portfolio.value  # Total portfolio value
    >>> portfolio.holdings  # DataFrame with all positions
    >>> portfolio.risk_metrics()  # Sharpe, Sortino, Beta, Alpha
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

import numpy as np
import pandas as pd

from borsapy.crypto import Crypto
from borsapy.fund import Fund
from borsapy.fx import FX
from borsapy.index import Index
from borsapy.technical import TechnicalMixin
from borsapy.ticker import Ticker

# 65 supported currencies from canlidoviz.py
FX_CURRENCIES = {
    # Major
    "USD", "EUR", "GBP", "CHF", "CAD", "AUD", "JPY", "NZD", "SGD", "HKD", "TWD",
    # European
    "DKK", "SEK", "NOK", "PLN", "CZK", "HUF", "RON", "BGN", "HRK", "RSD", "BAM",
    "MKD", "ALL", "MDL", "UAH", "BYR", "ISK",
    # Middle East & Africa
    "AED", "SAR", "QAR", "KWD", "BHD", "OMR", "JOD", "IQD", "IRR", "LBP", "SYP",
    "EGP", "LYD", "TND", "DZD", "MAD", "ZAR", "ILS",
    # Asia & Pacific
    "CNY", "INR", "PKR", "LKR", "IDR", "MYR", "THB", "PHP", "KRW", "KZT", "AZN", "GEL",
    # Americas
    "MXN", "BRL", "ARS", "CLP", "COP", "PEN", "UYU", "CRC",
    # Other
    "RUB", "DVZSP1",
}

# Precious metals and commodities
FX_METALS = {
    "gram-altin", "ceyrek-altin", "yarim-altin", "tam-altin",
    "cumhuriyet-altin", "ata-altin", "ons-altin", "gram-gumus", "gram-platin",
}

FX_COMMODITIES = {"BRENT", "XAG-USD", "XPT-USD", "XPD-USD"}


AssetType = Literal["stock", "fx", "crypto", "fund"]


@dataclass
class Holding:
    """Single holding in a portfolio."""

    symbol: str
    shares: float
    cost_per_share: float | None
    asset_type: AssetType
    purchase_date: date | None = None


def _detect_asset_type(symbol: str) -> AssetType:
    """Auto-detect asset type from symbol.

    Detection rules:
    - FX: 65 currency codes + metals + commodities
    - Crypto: *TRY pattern (6+ chars) -> BTCTRY, ETHTRY
    - Fund/Stock: Ambiguous - defaults to stock

    Args:
        symbol: Asset symbol.

    Returns:
        Detected asset type.
    """
    upper = symbol.upper()

    # Currency check
    if upper in FX_CURRENCIES or symbol in FX_METALS or upper in FX_COMMODITIES:
        return "fx"

    # Crypto check (BTCTRY, ETHTRY, etc.)
    if symbol.endswith("TRY") and len(symbol) > 5:
        return "crypto"

    # Default to stock (user can override with asset_type="fund")
    return "stock"


def _get_asset(symbol: str, asset_type: AssetType) -> Ticker | FX | Crypto | Fund:
    """Get asset instance by type.

    Args:
        symbol: Asset symbol.
        asset_type: Asset type.

    Returns:
        Asset instance.
    """
    if asset_type == "fx":
        return FX(symbol)
    elif asset_type == "crypto":
        return Crypto(symbol)
    elif asset_type == "fund":
        return Fund(symbol)
    return Ticker(symbol)


class Portfolio(TechnicalMixin):
    """
    Multi-asset portfolio management with performance tracking and risk metrics.

    Supports 4 asset types:
    - stock: BIST stocks via Ticker class
    - fx: Currencies, metals, commodities via FX class
    - crypto: Cryptocurrencies via Crypto class
    - fund: TEFAS mutual funds via Fund class

    Examples:
        >>> import borsapy as bp
        >>> p = bp.Portfolio()
        >>> p.add("THYAO", shares=100, cost=280)
        >>> p.add("gram-altin", shares=5, asset_type="fx")
        >>> p.add("YAY", shares=500, asset_type="fund")
        >>> p.set_benchmark("XU100")
        >>> print(p.holdings)
        >>> print(f"Value: {p.value:,.2f} TL")
        >>> print(f"Sharpe: {p.risk_metrics()['sharpe_ratio']:.2f}")
    """

    def __init__(self, benchmark: str = "XU100"):
        """
        Initialize an empty portfolio.

        Args:
            benchmark: Index symbol for beta/alpha calculations.
                       Default is XU100 (BIST 100).
        """
        self._holdings: dict[str, Holding] = {}
        self._asset_cache: dict[str, Ticker | FX | Crypto | Fund] = {}
        self._benchmark = benchmark

    # === Asset Management ===

    def add(
        self,
        symbol: str,
        shares: float,
        cost: float | None = None,
        asset_type: str | None = None,
        purchase_date: str | date | datetime | None = None,
    ) -> "Portfolio":
        """
        Add an asset to the portfolio.

        Args:
            symbol: Asset symbol (THYAO, USD, BTCTRY, AAK, etc.)
            shares: Number of shares/units.
            cost: Cost per share/unit. If None, uses current price.
            asset_type: Asset type override. Auto-detected if None.
                        Valid values: "stock", "fx", "crypto", "fund"
            purchase_date: Date when the asset was purchased.
                          Accepts string (YYYY-MM-DD), date, or datetime.
                          If None, defaults to today.

        Returns:
            Self for method chaining.

        Examples:
            >>> p = Portfolio()
            >>> p.add("THYAO", shares=100, cost=280)  # Stock with cost
            >>> p.add("GARAN", shares=200)  # Stock at current price
            >>> p.add("gram-altin", shares=5, asset_type="fx")  # Metal
            >>> p.add("YAY", shares=500, asset_type="fund")  # Mutual fund
            >>> p.add("ASELS", shares=50, cost=120, purchase_date="2024-01-15")
        """
        symbol = symbol.upper() if asset_type != "fx" else symbol

        # Detect or validate asset type
        if asset_type is None:
            detected_type = _detect_asset_type(symbol)
        else:
            detected_type = asset_type  # type: ignore

        # Get current price if cost not provided
        if cost is None:
            asset = self._get_or_create_asset(symbol, detected_type)
            cost = self._get_current_price(asset)

        # Parse purchase_date
        parsed_date: date | None = None
        if purchase_date is not None:
            if isinstance(purchase_date, str):
                parsed_date = datetime.strptime(purchase_date, "%Y-%m-%d").date()
            elif isinstance(purchase_date, datetime):
                parsed_date = purchase_date.date()
            elif isinstance(purchase_date, date):
                parsed_date = purchase_date
        else:
            parsed_date = date.today()

        self._holdings[symbol] = Holding(
            symbol=symbol,
            shares=shares,
            cost_per_share=cost,
            asset_type=detected_type,
            purchase_date=parsed_date,
        )

        return self

    def remove(self, symbol: str) -> "Portfolio":
        """
        Remove an asset from the portfolio.

        Args:
            symbol: Asset symbol to remove.

        Returns:
            Self for method chaining.
        """
        symbol_upper = symbol.upper()

        # Try both original and uppercase
        if symbol in self._holdings:
            del self._holdings[symbol]
            self._asset_cache.pop(symbol, None)
        elif symbol_upper in self._holdings:
            del self._holdings[symbol_upper]
            self._asset_cache.pop(symbol_upper, None)

        return self

    def update(
        self,
        symbol: str,
        shares: float | None = None,
        cost: float | None = None,
    ) -> "Portfolio":
        """
        Update an existing holding.

        Args:
            symbol: Asset symbol.
            shares: New share count. If None, keeps existing.
            cost: New cost per share. If None, keeps existing.

        Returns:
            Self for method chaining.
        """
        if symbol not in self._holdings:
            symbol = symbol.upper()
        if symbol not in self._holdings:
            raise KeyError(f"Symbol {symbol} not in portfolio")

        holding = self._holdings[symbol]
        if shares is not None:
            holding.shares = shares
        if cost is not None:
            holding.cost_per_share = cost

        return self

    def clear(self) -> "Portfolio":
        """
        Remove all holdings from the portfolio.

        Returns:
            Self for method chaining.
        """
        self._holdings.clear()
        self._asset_cache.clear()
        return self

    def set_benchmark(self, index: str) -> "Portfolio":
        """
        Set the benchmark index for beta/alpha calculations.

        Args:
            index: Index symbol (XU100, XU030, XK030, etc.)

        Returns:
            Self for method chaining.
        """
        self._benchmark = index
        return self

    # === Properties ===

    @property
    def holdings(self) -> pd.DataFrame:
        """
        Get all holdings as a DataFrame.

        Returns:
            DataFrame with columns:
            - symbol: Asset symbol
            - shares: Number of shares
            - cost: Cost per share
            - current_price: Current price
            - value: Current value (shares * price)
            - weight: Portfolio weight (%)
            - pnl: Profit/loss (TL)
            - pnl_pct: Profit/loss (%)
            - asset_type: Asset type
            - purchase_date: Date when asset was purchased
            - holding_days: Number of days since purchase
        """
        if not self._holdings:
            return pd.DataFrame(
                columns=[
                    "symbol", "shares", "cost", "current_price",
                    "value", "weight", "pnl", "pnl_pct", "asset_type",
                    "purchase_date", "holding_days"
                ]
            )

        rows = []
        total_value = self.value
        today = date.today()

        for symbol, holding in self._holdings.items():
            asset = self._get_or_create_asset(symbol, holding.asset_type)
            current_price = self._get_current_price(asset)
            value = holding.shares * current_price
            cost_basis = (holding.shares * holding.cost_per_share) if holding.cost_per_share else 0
            pnl = value - cost_basis if cost_basis else 0
            pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0
            weight = (value / total_value * 100) if total_value else 0

            # Calculate holding days
            holding_days = None
            if holding.purchase_date:
                holding_days = (today - holding.purchase_date).days

            rows.append({
                "symbol": symbol,
                "shares": holding.shares,
                "cost": holding.cost_per_share,
                "current_price": current_price,
                "value": value,
                "weight": round(weight, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "asset_type": holding.asset_type,
                "purchase_date": holding.purchase_date,
                "holding_days": holding_days,
            })

        return pd.DataFrame(rows)

    @property
    def symbols(self) -> list[str]:
        """Get list of symbols in portfolio."""
        return list(self._holdings.keys())

    @property
    def value(self) -> float:
        """Get total portfolio value in TL."""
        total = 0.0
        for symbol, holding in self._holdings.items():
            asset = self._get_or_create_asset(symbol, holding.asset_type)
            price = self._get_current_price(asset)
            total += holding.shares * price
        return total

    @property
    def cost(self) -> float:
        """Get total portfolio cost basis in TL."""
        total = 0.0
        for holding in self._holdings.values():
            if holding.cost_per_share:
                total += holding.shares * holding.cost_per_share
        return total

    @property
    def pnl(self) -> float:
        """Get total profit/loss in TL."""
        return self.value - self.cost

    @property
    def pnl_pct(self) -> float:
        """Get total profit/loss as percentage."""
        cost = self.cost
        if cost == 0:
            return 0.0
        return (self.pnl / cost) * 100

    @property
    def weights(self) -> dict[str, float]:
        """Get portfolio weights as dictionary."""
        total_value = self.value
        if total_value == 0:
            return {}

        result = {}
        for symbol, holding in self._holdings.items():
            asset = self._get_or_create_asset(symbol, holding.asset_type)
            price = self._get_current_price(asset)
            value = holding.shares * price
            result[symbol] = round(value / total_value, 4)
        return result

    # === Performance ===

    def history(self, period: str = "1y") -> pd.DataFrame:
        """
        Get historical portfolio value based on current holdings.

        Note: Uses current share counts - does not track historical trades.
        When purchase_date is set for a holding, only data from that date
        onwards is included in the portfolio value calculation.

        Args:
            period: Period for historical data (1d, 5d, 1mo, 3mo, 6mo, 1y).

        Returns:
            DataFrame with columns: Value, Daily_Return.
            Index is Date.
        """
        if not self._holdings:
            return pd.DataFrame(columns=["Value", "Daily_Return"])

        all_prices = {}
        for symbol, holding in self._holdings.items():
            asset = self._get_or_create_asset(symbol, holding.asset_type)
            try:
                hist = asset.history(period=period)
                if hist.empty:
                    continue

                # Filter by purchase_date if set
                if holding.purchase_date:
                    # Handle both timezone-aware and timezone-naive indices
                    if hasattr(hist.index, 'tz') and hist.index.tz is not None:
                        hist = hist[hist.index.date >= holding.purchase_date]
                    else:
                        hist = hist[hist.index >= pd.Timestamp(holding.purchase_date)]

                if hist.empty:
                    continue

                # Use Close for stocks/index, Price for funds
                price_col = "Close" if "Close" in hist.columns else "Price"
                all_prices[symbol] = hist[price_col] * holding.shares
            except Exception:
                continue

        if not all_prices:
            return pd.DataFrame(columns=["Value", "Daily_Return"])

        df = pd.DataFrame(all_prices)
        df = df.dropna(how="all")
        df["Value"] = df.sum(axis=1)
        df["Daily_Return"] = df["Value"].pct_change()
        return df[["Value", "Daily_Return"]]

    @property
    def performance(self) -> dict[str, float]:
        """
        Get portfolio performance summary.

        Returns:
            Dictionary with:
            - total_return: Total return (%)
            - annualized_return: Annualized return (%)
            - total_value: Current value (TL)
            - total_cost: Total cost (TL)
            - total_pnl: Profit/loss (TL)
        """
        return {
            "total_return": self.pnl_pct,
            "annualized_return": np.nan,  # Calculated in risk_metrics
            "total_value": self.value,
            "total_cost": self.cost,
            "total_pnl": self.pnl,
        }

    # === Risk Metrics ===

    def risk_metrics(
        self,
        period: str = "1y",
        risk_free_rate: float | None = None,
    ) -> dict[str, Any]:
        """
        Calculate comprehensive risk metrics.

        Args:
            period: Period for calculation (1y, 3mo, 6mo).
            risk_free_rate: Annual risk-free rate as decimal (e.g., 0.28 for 28%).
                           If None, uses current 10Y bond yield.

        Returns:
            Dictionary with:
            - annualized_return: Annualized return (%)
            - annualized_volatility: Annualized volatility (%)
            - sharpe_ratio: Risk-adjusted return
            - sortino_ratio: Downside risk-adjusted return
            - max_drawdown: Maximum drawdown (%)
            - beta: Beta vs benchmark
            - alpha: Alpha vs benchmark (%)
            - risk_free_rate: Risk-free rate used (%)
            - trading_days: Number of trading days
        """
        df = self.history(period=period)

        if df.empty or len(df) < 20:
            return {
                "annualized_return": np.nan,
                "annualized_volatility": np.nan,
                "sharpe_ratio": np.nan,
                "sortino_ratio": np.nan,
                "max_drawdown": np.nan,
                "beta": np.nan,
                "alpha": np.nan,
                "risk_free_rate": np.nan,
                "trading_days": 0,
            }

        daily_returns = df["Daily_Return"].dropna()
        trading_days = len(daily_returns)
        annualization = 252

        # Annualized return
        total_return = (df["Value"].iloc[-1] / df["Value"].iloc[0]) - 1
        years = trading_days / annualization
        ann_return = ((1 + total_return) ** (1 / years) - 1) * 100

        # Annualized volatility
        daily_volatility = daily_returns.std()
        ann_volatility = daily_volatility * np.sqrt(annualization) * 100

        # Get risk-free rate
        if risk_free_rate is None:
            try:
                from borsapy.bond import risk_free_rate as get_rf_rate
                rf = get_rf_rate() * 100  # Convert to percentage
            except Exception:
                rf = 30.0  # Fallback
        else:
            rf = risk_free_rate * 100

        # Sharpe Ratio
        if ann_volatility > 0:
            sharpe = (ann_return - rf) / ann_volatility
        else:
            sharpe = np.nan

        # Sortino Ratio (downside deviation)
        negative_returns = daily_returns[daily_returns < 0]
        if len(negative_returns) > 0:
            downside_deviation = negative_returns.std() * np.sqrt(annualization) * 100
            if downside_deviation > 0:
                sortino = (ann_return - rf) / downside_deviation
            else:
                sortino = np.nan
        else:
            sortino = np.inf  # No negative returns

        # Maximum Drawdown
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.cummax()
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = drawdowns.min() * 100

        # Beta and Alpha (vs benchmark)
        beta = np.nan
        alpha = np.nan

        try:
            bench = Index(self._benchmark)
            bench_hist = bench.history(period=period)
            if not bench_hist.empty:
                bench_returns = bench_hist["Close"].pct_change().dropna()

                # Align dates
                common_dates = daily_returns.index.intersection(bench_returns.index)
                if len(common_dates) >= 20:
                    port_ret = daily_returns.loc[common_dates]
                    bench_ret = bench_returns.loc[common_dates]

                    # Beta = Cov(Rp, Rm) / Var(Rm)
                    covariance = port_ret.cov(bench_ret)
                    variance = bench_ret.var()
                    if variance > 0:
                        beta = covariance / variance

                        # Alpha = Rp - Rf - Beta * (Rm - Rf)
                        bench_total = (bench_hist["Close"].iloc[-1] / bench_hist["Close"].iloc[0]) - 1
                        bench_ann = ((1 + bench_total) ** (1 / years) - 1) * 100
                        alpha = ann_return - rf - beta * (bench_ann - rf)
        except Exception:
            pass

        return {
            "annualized_return": round(ann_return, 2),
            "annualized_volatility": round(ann_volatility, 2),
            "sharpe_ratio": round(sharpe, 2) if not np.isnan(sharpe) else np.nan,
            "sortino_ratio": round(sortino, 2) if not np.isnan(sortino) and not np.isinf(sortino) else sortino,
            "max_drawdown": round(max_drawdown, 2),
            "beta": round(beta, 2) if not np.isnan(beta) else np.nan,
            "alpha": round(alpha, 2) if not np.isnan(alpha) else np.nan,
            "risk_free_rate": round(rf, 2),
            "trading_days": trading_days,
        }

    def sharpe_ratio(self, period: str = "1y") -> float:
        """
        Calculate Sharpe ratio.

        Args:
            period: Period for calculation.

        Returns:
            Sharpe ratio.
        """
        return self.risk_metrics(period=period).get("sharpe_ratio", np.nan)

    def sortino_ratio(self, period: str = "1y") -> float:
        """
        Calculate Sortino ratio.

        Args:
            period: Period for calculation.

        Returns:
            Sortino ratio.
        """
        return self.risk_metrics(period=period).get("sortino_ratio", np.nan)

    def beta(self, benchmark: str | None = None, period: str = "1y") -> float:
        """
        Calculate beta vs benchmark.

        Args:
            benchmark: Benchmark index. Uses portfolio default if None.
            period: Period for calculation.

        Returns:
            Beta coefficient.
        """
        if benchmark:
            old_bench = self._benchmark
            self._benchmark = benchmark
            result = self.risk_metrics(period=period).get("beta", np.nan)
            self._benchmark = old_bench
            return result
        return self.risk_metrics(period=period).get("beta", np.nan)

    def correlation_matrix(self, period: str = "1y") -> pd.DataFrame:
        """
        Calculate correlation matrix between holdings.

        Args:
            period: Period for calculation.

        Returns:
            DataFrame with correlation coefficients.
        """
        if len(self._holdings) < 2:
            return pd.DataFrame()

        returns_dict = {}
        for symbol, holding in self._holdings.items():
            try:
                asset = self._get_or_create_asset(symbol, holding.asset_type)
                hist = asset.history(period=period)
                if hist.empty:
                    continue
                price_col = "Close" if "Close" in hist.columns else "Price"
                returns_dict[symbol] = hist[price_col].pct_change()
            except Exception:
                continue

        if len(returns_dict) < 2:
            return pd.DataFrame()

        df = pd.DataFrame(returns_dict).dropna()
        return df.corr()

    # === Import/Export ===

    def to_dict(self) -> dict[str, Any]:
        """
        Export portfolio to dictionary.

        Returns:
            Dictionary with portfolio data.
        """
        return {
            "benchmark": self._benchmark,
            "holdings": [
                {
                    "symbol": h.symbol,
                    "shares": h.shares,
                    "cost_per_share": h.cost_per_share,
                    "asset_type": h.asset_type,
                    "purchase_date": h.purchase_date.isoformat() if h.purchase_date else None,
                }
                for h in self._holdings.values()
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Portfolio":
        """
        Create portfolio from dictionary.

        Args:
            data: Dictionary with portfolio data.

        Returns:
            Portfolio instance.
        """
        portfolio = cls(benchmark=data.get("benchmark", "XU100"))
        for h in data.get("holdings", []):
            # Parse purchase_date from ISO string
            purchase_date = None
            if h.get("purchase_date"):
                purchase_date = date.fromisoformat(h["purchase_date"])

            portfolio.add(
                symbol=h["symbol"],
                shares=h["shares"],
                cost=h.get("cost_per_share"),
                asset_type=h.get("asset_type"),
                purchase_date=purchase_date,
            )
        return portfolio

    # === Private Methods ===

    def _get_or_create_asset(
        self, symbol: str, asset_type: AssetType
    ) -> Ticker | FX | Crypto | Fund:
        """Get or create asset instance from cache."""
        cache_key = f"{symbol}_{asset_type}"
        if cache_key not in self._asset_cache:
            self._asset_cache[cache_key] = _get_asset(symbol, asset_type)
        return self._asset_cache[cache_key]

    def _get_current_price(self, asset: Ticker | FX | Crypto | Fund) -> float:
        """Get current price from asset."""
        try:
            if isinstance(asset, Ticker):
                return asset.fast_info.last_price or 0
            elif isinstance(asset, Crypto):
                return asset.fast_info.last_price or 0
            elif isinstance(asset, FX):
                current = asset.current
                return current.get("last", 0) if current else 0
            elif isinstance(asset, Fund):
                info = asset.info
                return info.get("price", 0) if info else 0
        except Exception:
            pass
        return 0

    def __repr__(self) -> str:
        n = len(self._holdings)
        value = self.value
        return f"Portfolio({n} holdings, {value:,.2f} TL)"

    def __len__(self) -> int:
        return len(self._holdings)
