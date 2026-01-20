"""FX class for forex and commodity data - yfinance-like API."""

from datetime import datetime
from typing import Any

import pandas as pd

from borsapy._providers.canlidoviz import get_canlidoviz_provider
from borsapy._providers.dovizcom import get_dovizcom_provider
from borsapy._providers.tradingview import get_tradingview_provider
from borsapy.technical import TechnicalMixin


# TradingView symbol mapping for currencies (asset -> (exchange, symbol))
# Note: Only pairs that are verified to work on TradingView free tier
TV_CURRENCY_MAP = {
    # Major currencies -> TRY pairs (verified working)
    "USD": ("FX", "USDTRY"),
    "EUR": ("FX", "EURTRY"),
    "GBP": ("PEPPERSTONE", "GBPTRY"),
    "JPY": ("FX", "TRYJPY"),  # Inverse pair (TRY/JPY)
    # Note: CHF, CAD, AUD, NZD etc. TRY pairs not available on TradingView
    # Use daily data from canlidoviz for these currencies
}

# TradingView symbol mapping for precious metals and commodities
TV_COMMODITY_MAP = {
    # Precious metals (USD prices)
    "ons-altin": ("OANDA", "XAUUSD"),
    "XAU": ("OANDA", "XAUUSD"),
    "XAG": ("OANDA", "XAGUSD"),
    "XAG-USD": ("OANDA", "XAGUSD"),
    "XPT": ("OANDA", "XPTUSD"),
    "XPT-USD": ("OANDA", "XPTUSD"),
    "XPD": ("OANDA", "XPDUSD"),
    "XPD-USD": ("OANDA", "XPDUSD"),
    # Energy
    "BRENT": ("TVC", "UKOIL"),
    "WTI": ("TVC", "USOIL"),
}


def banks() -> list[str]:
    """
    Get list of supported banks for exchange rates.

    Returns:
        List of bank codes.

    Examples:
        >>> import borsapy as bp
        >>> bp.banks()
        ['akbank', 'albaraka', 'alternatifbank', 'anadolubank', ...]
    """
    return get_dovizcom_provider().get_banks()


def metal_institutions() -> list[str]:
    """
    Get list of supported precious metal assets for institution rates.

    Returns:
        List of asset codes that support institution_rates.

    Examples:
        >>> import borsapy as bp
        >>> bp.metal_institutions()
        ['gram-altin', 'gram-gumus', 'gram-platin', 'ons-altin']
    """
    return get_dovizcom_provider().get_metal_institutions()


class FX(TechnicalMixin):
    """
    A yfinance-like interface for forex and commodity data.

    Supported assets:
    - Currencies: USD, EUR, GBP, JPY, CHF, CAD, AUD (+ 58 more via canlidoviz)
    - Precious Metals: gram-altin, gumus, ons-altin, gram-platin, XAG-USD, XPT-USD, XPD-USD
    - Energy: BRENT

    Examples:
        >>> import borsapy as bp
        >>> usd = bp.FX("USD")
        >>> usd.current
        {'symbol': 'USD', 'last': 34.85, ...}
        >>> usd.history(period="1mo")
                         Open    High     Low   Close
        Date
        2024-12-01    34.50   34.80   34.40   34.75
        ...

        >>> gold = bp.FX("gram-altin")
        >>> gold.current
        {'symbol': 'gram-altin', 'last': 2850.50, ...}
    """

    def __init__(self, asset: str):
        """
        Initialize an FX object.

        Args:
            asset: Asset code (USD, EUR, gram-altin, BRENT, etc.)
        """
        self._asset = asset
        self._canlidoviz = get_canlidoviz_provider()
        self._dovizcom = get_dovizcom_provider()
        self._tradingview = get_tradingview_provider()
        self._current_cache: dict[str, Any] | None = None

    def _use_canlidoviz(self) -> bool:
        """Check if canlidoviz should be used for this asset."""
        asset_upper = self._asset.upper()
        # Currencies
        if asset_upper in self._canlidoviz.CURRENCY_IDS:
            return True
        # Metals supported by canlidoviz (TRY prices)
        if self._asset in self._canlidoviz.METAL_IDS:
            return True
        # Energy supported by canlidoviz (USD prices)
        if asset_upper in self._canlidoviz.ENERGY_IDS:
            return True
        # Commodities supported by canlidoviz (USD prices)
        if asset_upper in self._canlidoviz.COMMODITY_IDS:
            return True
        return False

    def _get_tradingview_symbol(self) -> tuple[str, str] | None:
        """Get TradingView exchange and symbol for this asset.

        Returns:
            Tuple of (exchange, symbol) or None if not supported.
        """
        asset_upper = self._asset.upper()

        # Check currency map first
        if asset_upper in TV_CURRENCY_MAP:
            return TV_CURRENCY_MAP[asset_upper]

        # Check commodity map
        if self._asset in TV_COMMODITY_MAP:
            return TV_COMMODITY_MAP[self._asset]
        if asset_upper in TV_COMMODITY_MAP:
            return TV_COMMODITY_MAP[asset_upper]

        return None

    @property
    def asset(self) -> str:
        """Return the asset code."""
        return self._asset

    @property
    def symbol(self) -> str:
        """Return the asset code (alias for asset)."""
        return self._asset

    @property
    def current(self) -> dict[str, Any]:
        """
        Get current price information.

        Returns:
            Dictionary with current market data:
            - symbol: Asset code
            - last: Last price
            - open: Opening price
            - high: Day high
            - low: Day low
            - update_time: Last update timestamp
        """
        if self._current_cache is None:
            if self._use_canlidoviz():
                self._current_cache = self._canlidoviz.get_current(self._asset)
            else:
                try:
                    self._current_cache = self._dovizcom.get_current(self._asset)
                except Exception:
                    # Fallback to bank_rates for currencies not supported by APIs
                    self._current_cache = self._current_from_bank_rates()
        return self._current_cache

    def _current_from_bank_rates(self) -> dict[str, Any]:
        """Calculate current price from bank rates as fallback."""
        from datetime import datetime

        rates = self._dovizcom.get_bank_rates(self._asset)
        if rates.empty:
            raise ValueError(f"No data available for {self._asset}")

        # Calculate average mid price from all banks
        mids = (rates["buy"] + rates["sell"]) / 2
        avg_mid = float(mids.mean())

        return {
            "symbol": self._asset,
            "last": avg_mid,
            "open": avg_mid,
            "high": float(rates["sell"].max()),
            "low": float(rates["buy"].min()),
            "update_time": datetime.now(),
            "source": "bank_rates_avg",
        }

    @property
    def info(self) -> dict[str, Any]:
        """Alias for current property (yfinance compatibility)."""
        return self.current

    @property
    def bank_rates(self) -> pd.DataFrame:
        """
        Get exchange rates from all banks.

        Returns:
            DataFrame with columns: bank, bank_name, currency, buy, sell, spread

        Examples:
            >>> usd = FX("USD")
            >>> usd.bank_rates
                      bank        bank_name currency      buy     sell  spread
            0       akbank           Akbank      USD  41.6610  44.1610    5.99
            1      garanti     Garanti BBVA      USD  41.7000  44.2000    5.99
            ...
        """
        return self._dovizcom.get_bank_rates(self._asset)

    def bank_rate(self, bank: str) -> dict[str, Any]:
        """
        Get exchange rate from a specific bank.

        Args:
            bank: Bank code (akbank, garanti, isbank, ziraat, etc.)

        Returns:
            Dictionary with keys: bank, currency, buy, sell, spread

        Examples:
            >>> usd = FX("USD")
            >>> usd.bank_rate("akbank")
            {'bank': 'akbank', 'currency': 'USD', 'buy': 41.6610, 'sell': 44.1610, 'spread': 5.99}
        """
        return self._dovizcom.get_bank_rates(self._asset, bank=bank)

    @staticmethod
    def banks() -> list[str]:
        """
        Get list of supported banks.

        Returns:
            List of bank codes.

        Examples:
            >>> FX.banks()
            ['akbank', 'albaraka', 'alternatifbank', 'anadolubank', ...]
        """
        from borsapy._providers.dovizcom import get_dovizcom_provider

        return get_dovizcom_provider().get_banks()

    @property
    def institution_rates(self) -> pd.DataFrame:
        """
        Get precious metal rates from all institutions (kuyumcular, bankalar).

        Only available for precious metals: gram-altin, gram-gumus, ons-altin,
        gram-platin

        Returns:
            DataFrame with columns: institution, institution_name, asset, buy, sell, spread

        Examples:
            >>> gold = FX("gram-altin")
            >>> gold.institution_rates
                   institution  institution_name       asset      buy     sell  spread
            0      altinkaynak       Altınkaynak  gram-altin  6315.00  6340.00    0.40
            1           akbank            Akbank  gram-altin  6310.00  6330.00    0.32
            ...
        """
        return self._dovizcom.get_metal_institution_rates(self._asset)

    def institution_rate(self, institution: str) -> dict[str, Any]:
        """
        Get precious metal rate from a specific institution.

        Args:
            institution: Institution slug (kapalicarsi, altinkaynak, akbank, etc.)

        Returns:
            Dictionary with keys: institution, institution_name, asset, buy, sell, spread

        Examples:
            >>> gold = FX("gram-altin")
            >>> gold.institution_rate("akbank")
            {'institution': 'akbank', 'institution_name': 'Akbank', 'asset': 'gram-altin',
             'buy': 6310.00, 'sell': 6330.00, 'spread': 0.32}
        """
        return self._dovizcom.get_metal_institution_rates(self._asset, institution=institution)

    @staticmethod
    def metal_institutions() -> list[str]:
        """
        Get list of supported precious metal assets for institution rates.

        Returns:
            List of asset codes that support institution_rates.

        Examples:
            >>> FX.metal_institutions()
            ['gram-altin', 'gram-gumus', 'gram-platin', 'ons-altin']
        """
        from borsapy._providers.dovizcom import get_dovizcom_provider

        return get_dovizcom_provider().get_metal_institutions()

    def history(
        self,
        period: str = "1mo",
        interval: str = "1d",
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> pd.DataFrame:
        """
        Get historical OHLC data.

        Args:
            period: How much data to fetch. Valid periods:
                    1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max.
                    Ignored if start is provided.
            interval: Data interval. Valid intervals:
                    1m, 5m, 15m, 30m, 1h, 4h, 1d, 1wk, 1mo.
                    Note: Intraday intervals (1m-4h) use TradingView.
                    Daily and above use canlidoviz/dovizcom.
            start: Start date (string or datetime).
            end: End date (string or datetime). Defaults to today.

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume.
            Index is the Date.

        Examples:
            >>> fx = FX("USD")
            >>> fx.history(period="1mo")  # Last month daily
            >>> fx.history(period="1d", interval="1m")  # Today's minute data
            >>> fx.history(period="5d", interval="1h")  # 5 days hourly
            >>> fx.history(start="2024-01-01", end="2024-06-30")  # Date range
        """
        start_dt = self._parse_date(start) if start else None
        end_dt = self._parse_date(end) if end else None

        # Use TradingView for intraday intervals
        intraday_intervals = ("1m", "5m", "15m", "30m", "1h", "4h")
        if interval in intraday_intervals:
            tv_info = self._get_tradingview_symbol()
            if tv_info is None:
                raise ValueError(
                    f"Intraday data not available for {self._asset}. "
                    f"Supported currencies: {list(TV_CURRENCY_MAP.keys())}"
                )

            exchange, symbol = tv_info
            return self._tradingview.get_history(
                symbol=symbol,
                period=period,
                interval=interval,
                start=start_dt,
                end=end_dt,
                exchange=exchange,
            )

        # Use canlidoviz/dovizcom for daily and above
        if self._use_canlidoviz():
            return self._canlidoviz.get_history(
                asset=self._asset,
                period=period,
                start=start_dt,
                end=end_dt,
            )
        else:
            return self._dovizcom.get_history(
                asset=self._asset,
                period=period,
                start=start_dt,
                end=end_dt,
            )

    def institution_history(
        self,
        institution: str,
        period: str = "1mo",
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> pd.DataFrame:
        """
        Get historical OHLC data from a specific institution.

        Supports both precious metals and currencies.

        Args:
            institution: Institution slug (akbank, kapalicarsi, harem, etc.)
            period: How much data to fetch. Valid periods:
                    1d, 5d, 1mo, 3mo, 6mo, 1y.
                    Ignored if start is provided.
            start: Start date (string or datetime).
            end: End date (string or datetime). Defaults to today.

        Returns:
            DataFrame with columns: Open, High, Low, Close.
            Index is the Date.
            Note: Banks typically return only Close values (Open/High/Low = 0).

        Examples:
            >>> # Metal history
            >>> gold = FX("gram-altin")
            >>> gold.institution_history("akbank", period="1mo")
            >>> gold.institution_history("kapalicarsi", start="2024-01-01")

            >>> # Currency history
            >>> usd = FX("USD")
            >>> usd.institution_history("akbank", period="1mo")
            >>> usd.institution_history("garanti-bbva", period="5d")
        """
        start_dt = self._parse_date(start) if start else None
        end_dt = self._parse_date(end) if end else None

        # Use canlidoviz for currencies and precious metals (bank-specific rates)
        asset_upper = self._asset.upper()
        use_canlidoviz = (
            asset_upper in self._canlidoviz.CURRENCY_IDS
            or self._asset in ("gram-altin", "gumus", "gram-platin")
        )

        if use_canlidoviz:
            # Check if canlidoviz has bank ID for this asset
            try:
                return self._canlidoviz.get_history(
                    asset=self._asset,
                    period=period,
                    start=start_dt,
                    end=end_dt,
                    institution=institution,
                )
            except Exception:
                # Fall back to dovizcom if canlidoviz doesn't support this bank
                pass

        # Use dovizcom for other metals and unsupported banks
        return self._dovizcom.get_institution_history(
            asset=self._asset,
            institution=institution,
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
        return f"FX('{self._asset}')"
