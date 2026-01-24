"""Technical scanner using TradingView-native filtering.

This module provides a TechnicalScanner class for screening multiple symbols
based on technical indicators using TradingView's Scanner API.

The scanner supports conditions like:
- Simple comparisons: "rsi < 30", "price > 300"
- Field comparisons: "close > sma_50", "macd > signal"
- Compound conditions: "rsi < 30 and volume > 1M"
- Crossover detection: "sma_20 crosses_above sma_50"

Examples:
    >>> import borsapy as bp

    # Simple scan
    >>> bp.scan("XU030", "rsi < 30")
    >>> bp.scan("XU100", "price > sma_50")

    # Compound conditions
    >>> bp.scan("XU030", "rsi < 30 and volume > 1M")

    # Crossover
    >>> bp.scan("XU030", "sma_20 crosses_above sma_50")

    # Different timeframe
    >>> bp.scan("XU030", "rsi < 30", interval="1h")

    # Using TechnicalScanner class
    >>> scanner = bp.TechnicalScanner()
    >>> scanner.set_universe("XU030")
    >>> scanner.add_condition("rsi < 30")
    >>> results = scanner.run()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from borsapy._providers.tradingview_screener_native import get_tv_screener_provider

__all__ = ["TechnicalScanner", "ScanResult", "scan"]


@dataclass
class ScanResult:
    """Result of scanning a single symbol.

    Attributes:
        symbol: The stock symbol
        data: Dictionary with current values and indicators
        conditions_met: List of condition names that were satisfied
        timestamp: When the scan was performed
    """

    symbol: str
    data: dict[str, Any] = field(default_factory=dict)
    conditions_met: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


def scan(
    universe: str | list[str],
    condition: str,
    interval: str = "1d",
    limit: int = 100,
) -> pd.DataFrame:
    """Convenience function for quick technical scanning using TradingView API.

    This function provides a simple interface to scan stocks based on technical
    conditions. All filtering is done server-side by TradingView for fast results.

    Args:
        universe: Index symbol (e.g., "XU030", "XU100", "XBANK") or list of stock symbols
        condition: Condition string supporting:
            - Simple comparisons: "rsi < 30", "volume > 1M"
            - Field comparisons: "close > sma_50", "macd > signal"
            - Compound conditions: "rsi < 30 and close > sma_50"
            - Crossover: "sma_20 crosses_above sma_50", "macd crosses signal"
            - Percentage: "close above_pct sma_50 1.05", "close below_pct sma_50 0.95"
        interval: Timeframe for indicators ("1m", "5m", "15m", "30m", "1h", "4h", "1d", "1W", "1M")
        limit: Maximum number of results (default: 100)

    Returns:
        DataFrame with matching symbols and their indicator values

    Examples:
        >>> import borsapy as bp

        # RSI oversold
        >>> bp.scan("XU030", "rsi < 30")

        # Price above SMA50
        >>> bp.scan("XU100", "close > sma_50")

        # Compound condition
        >>> bp.scan("XU030", "rsi < 30 and volume > 1M")

        # MACD bullish
        >>> bp.scan("XU100", "macd > signal")

        # Golden cross
        >>> bp.scan("XU030", "sma_20 crosses_above sma_50")

        # MACD crosses signal line
        >>> bp.scan("XU030", "macd crosses signal")

        # Close 5% above SMA50
        >>> bp.scan("XU030", "close above_pct sma_50 1.05")

        # Hourly timeframe
        >>> bp.scan("XU030", "rsi < 30", interval="1h")

    Supported Fields:
        Price: price, close, open, high, low, volume, change_percent, market_cap
        RSI: rsi, rsi_7, rsi_14
        SMA: sma_5, sma_10, sma_20, sma_30, sma_50, sma_100, sma_200
        EMA: ema_5, ema_10, ema_12, ema_20, ema_26, ema_50, ema_100, ema_200
        MACD: macd, signal, histogram
        Stochastic: stoch_k, stoch_d
        ADX: adx
        Bollinger: bb_upper, bb_middle, bb_lower
        ATR: atr
        CCI: cci
        Williams %R: wr
    """
    scanner = TechnicalScanner()
    scanner.set_universe(universe)
    scanner.add_condition(condition)
    scanner.set_interval(interval)
    return scanner.run(limit=limit)


class TechnicalScanner:
    """Scanner for technical analysis conditions using TradingView API.

    Provides a fluent API for building and executing stock scans based on
    technical indicators. All filtering is done server-side by TradingView
    for optimal performance.

    Examples:
        >>> scanner = TechnicalScanner()
        >>> scanner.set_universe("XU030")
        >>> scanner.add_condition("rsi < 30", name="oversold")
        >>> scanner.add_condition("volume > 1M", name="high_vol")
        >>> results = scanner.run()
        >>> print(results)

    Supported Timeframes:
        "1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1W", "1M"
    """

    def __init__(self) -> None:
        """Initialize scanner."""
        self._provider = get_tv_screener_provider()
        self._symbols: list[str] = []
        self._conditions: list[str] = []
        self._condition_names: dict[str, str] = {}  # condition -> name
        self._interval: str = "1d"
        self._extra_columns: list[str] = []

    def set_universe(self, universe: str | list[str]) -> "TechnicalScanner":
        """Set the universe of symbols to scan.

        Args:
            universe: Index symbol (e.g., "XU030", "XU100", "XBANK") or list of stock symbols

        Returns:
            Self for method chaining

        Examples:
            >>> scanner.set_universe("XU030")  # BIST 30 components
            >>> scanner.set_universe(["THYAO", "GARAN", "ASELS"])  # Specific symbols
        """
        if isinstance(universe, str):
            # Check if it's an index
            if universe.upper().startswith("X"):
                from borsapy.index import Index

                try:
                    idx = Index(universe.upper())
                    self._symbols = idx.component_symbols
                except Exception:
                    # Not a valid index, treat as single symbol
                    self._symbols = [universe.upper()]
            else:
                self._symbols = [universe.upper()]
        else:
            self._symbols = [s.upper() for s in universe]
        return self

    def add_symbol(self, symbol: str) -> "TechnicalScanner":
        """Add a single symbol to the universe.

        Args:
            symbol: Stock symbol to add

        Returns:
            Self for method chaining
        """
        symbol = symbol.upper()
        if symbol not in self._symbols:
            self._symbols.append(symbol)
        return self

    def remove_symbol(self, symbol: str) -> "TechnicalScanner":
        """Remove a symbol from the universe.

        Args:
            symbol: Stock symbol to remove

        Returns:
            Self for method chaining
        """
        symbol = symbol.upper()
        if symbol in self._symbols:
            self._symbols.remove(symbol)
        return self

    def add_condition(
        self, condition: str, name: str | None = None
    ) -> "TechnicalScanner":
        """Add a scanning condition.

        Conditions are combined with AND logic. For OR logic, use the full
        condition string: "(rsi < 30 or rsi > 70)".

        Args:
            condition: Condition string (e.g., "rsi < 30", "close > sma_50")
            name: Optional name for the condition (for reporting)

        Returns:
            Self for method chaining

        Supported Syntax:
            - Simple: "rsi < 30", "volume > 1M"
            - Field comparison: "close > sma_50", "macd > signal"
            - Compound (AND): "rsi < 30 and volume > 1M"
            - Crossover: "sma_20 crosses_above sma_50"

        Examples:
            >>> scanner.add_condition("rsi < 30", name="oversold")
            >>> scanner.add_condition("volume > 1M", name="high_volume")
        """
        # Split by "and" for multiple conditions
        parts = [c.strip() for c in condition.lower().split(" and ")]

        for part in parts:
            if part and part not in self._conditions:
                self._conditions.append(part)
                cond_name = name if name and len(parts) == 1 else part
                self._condition_names[part] = cond_name

        return self

    def remove_condition(self, name_or_condition: str) -> "TechnicalScanner":
        """Remove a condition by name or condition string.

        Args:
            name_or_condition: Condition name or string to remove

        Returns:
            Self for method chaining
        """
        # Try to find by name
        for cond, cname in list(self._condition_names.items()):
            if cname == name_or_condition or cond == name_or_condition.lower():
                self._conditions.remove(cond)
                del self._condition_names[cond]
                break
        return self

    def clear_conditions(self) -> "TechnicalScanner":
        """Clear all conditions.

        Returns:
            Self for method chaining
        """
        self._conditions.clear()
        self._condition_names.clear()
        return self

    def set_interval(self, interval: str) -> "TechnicalScanner":
        """Set the data interval/timeframe for indicators.

        Args:
            interval: Timeframe for indicators:
                - "1m", "5m", "15m", "30m" (intraday minutes)
                - "1h", "2h", "4h" (intraday hours)
                - "1d" (daily, default)
                - "1W", "1wk" (weekly)
                - "1M", "1mo" (monthly)

        Returns:
            Self for method chaining
        """
        self._interval = interval
        return self

    def add_column(self, column: str) -> "TechnicalScanner":
        """Add extra column to retrieve in results.

        Args:
            column: Column name (e.g., "ema_200", "adx")

        Returns:
            Self for method chaining
        """
        if column not in self._extra_columns:
            self._extra_columns.append(column)
        return self

    def run(self, limit: int = 100) -> pd.DataFrame:
        """Execute the scan and return results.

        Args:
            limit: Maximum number of results

        Returns:
            DataFrame with matching symbols and their data.
            Columns include: symbol, close, volume, change, market_cap,
            plus any indicator columns used in conditions.

        Raises:
            ValueError: If no symbols or conditions are set
        """
        if not self._symbols:
            return pd.DataFrame()

        if not self._conditions:
            return pd.DataFrame()

        # Execute scan via provider
        df = self._provider.scan(
            symbols=self._symbols,
            conditions=self._conditions,
            columns=self._extra_columns,
            interval=self._interval,
            limit=limit,
        )

        # Add conditions_met column for compatibility
        if not df.empty:
            df["conditions_met"] = [list(self._condition_names.values())] * len(df)

        return df

    @property
    def symbols(self) -> list[str]:
        """Get current symbol universe."""
        return self._symbols.copy()

    @property
    def conditions(self) -> list[str]:
        """Get current conditions."""
        return self._conditions.copy()

    # Backward compatibility aliases
    def set_data_period(self, period: str = "3mo") -> "TechnicalScanner":
        """Deprecated: Period is not used with TradingView API."""
        import warnings

        warnings.warn(
            "set_data_period() is deprecated. TradingView API uses real-time data.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self

    @property
    def results(self) -> list[ScanResult]:
        """Deprecated: Use run() which returns DataFrame directly."""
        return []

    def to_dataframe(self) -> pd.DataFrame:
        """Deprecated: Use run() which returns DataFrame directly."""
        return self.run()

    def on_match(self, callback) -> None:
        """Deprecated: Callbacks not supported with batch API."""
        import warnings

        warnings.warn(
            "on_match() is deprecated. Use run() and iterate results.",
            DeprecationWarning,
            stacklevel=2,
        )

    def on_scan_complete(self, callback) -> None:
        """Deprecated: Callbacks not supported with batch API."""
        import warnings

        warnings.warn(
            "on_scan_complete() is deprecated. Use run() directly.",
            DeprecationWarning,
            stacklevel=2,
        )

    def __repr__(self) -> str:
        return (
            f"TechnicalScanner(symbols={len(self._symbols)}, "
            f"conditions={len(self._conditions)}, interval='{self._interval}')"
        )
