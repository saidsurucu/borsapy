"""Technical scanner for screening stocks based on technical conditions.

This module provides a TechnicalScanner class for screening multiple symbols
based on technical indicators and price conditions.

Examples:
    >>> import borsapy as bp

    # Simple scan
    >>> bp.scan("XU030", "rsi < 30")
    >>> bp.scan("XU100", "price > sma_50")

    # Compound conditions
    >>> bp.scan("XU030", "rsi < 30 and volume > 1000000")

    # Using TechnicalScanner class
    >>> scanner = bp.TechnicalScanner()
    >>> scanner.set_universe("XU030")
    >>> scanner.add_condition("rsi < 30")
    >>> results = scanner.run()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

import numpy as np
import pandas as pd

from borsapy.condition import ConditionParser, ParseError
from borsapy.technical import (
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_obv,
    calculate_rsi,
    calculate_sma,
    calculate_stochastic,
    calculate_vwap,
)

if TYPE_CHECKING:
    pass

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


class TechnicalScanner:
    """Scanner for technical analysis conditions across multiple symbols.

    Supports batch scanning with conditions based on quote data (price, volume)
    and technical indicators (RSI, SMA, EMA, MACD, Bollinger Bands, etc.).

    Examples:
        >>> scanner = TechnicalScanner()
        >>> scanner.set_universe("XU030")
        >>> scanner.add_condition("rsi < 30", name="oversold")
        >>> scanner.add_condition("volume > 1000000", name="high_vol")
        >>> results = scanner.run()
        >>> print(results)
    """

    def __init__(self, realtime: bool = False) -> None:
        """Initialize scanner.

        Args:
            realtime: If True, use streaming for real-time scanning (not yet implemented)
        """
        self._realtime = realtime
        self._symbols: list[str] = []
        self._conditions: dict[str, ConditionParser] = {}
        self._data_period = "3mo"
        self._interval = "1d"
        self._results: list[ScanResult] = []
        self._on_match_callback: Callable[[str, dict[str, Any]], None] | None = None
        self._on_complete_callback: Callable[[list[ScanResult]], None] | None = None

    def set_universe(self, symbols: str | list[str]) -> "TechnicalScanner":
        """Set the universe of symbols to scan.

        Args:
            symbols: Index symbol (e.g., "XU030") or list of stock symbols

        Returns:
            Self for method chaining
        """
        if isinstance(symbols, str):
            # Check if it's an index
            if symbols.upper().startswith("X"):
                from borsapy.index import Index

                try:
                    idx = Index(symbols.upper())
                    self._symbols = idx.component_symbols
                except Exception:
                    # Not a valid index, treat as single symbol
                    self._symbols = [symbols.upper()]
            else:
                self._symbols = [symbols.upper()]
        else:
            self._symbols = [s.upper() for s in symbols]
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

        Args:
            condition: Condition string (e.g., "rsi < 30")
            name: Optional name for the condition

        Returns:
            Self for method chaining

        Raises:
            ParseError: If condition syntax is invalid
        """
        parser = ConditionParser(condition)
        cond_name = name or condition
        self._conditions[cond_name] = parser
        return self

    def remove_condition(self, name: str) -> "TechnicalScanner":
        """Remove a condition by name.

        Args:
            name: Condition name to remove

        Returns:
            Self for method chaining
        """
        if name in self._conditions:
            del self._conditions[name]
        return self

    def clear_conditions(self) -> "TechnicalScanner":
        """Clear all conditions.

        Returns:
            Self for method chaining
        """
        self._conditions.clear()
        return self

    def set_data_period(self, period: str = "3mo") -> "TechnicalScanner":
        """Set the historical data period for indicator calculation.

        Args:
            period: Period for history data (e.g., "1mo", "3mo", "1y")

        Returns:
            Self for method chaining
        """
        self._data_period = period
        return self

    def set_interval(self, interval: str = "1d") -> "TechnicalScanner":
        """Set the data interval.

        Args:
            interval: Interval for data (e.g., "1d", "1h")

        Returns:
            Self for method chaining
        """
        self._interval = interval
        return self

    def on_match(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Set callback for when a symbol matches conditions (real-time mode).

        Args:
            callback: Function taking (symbol, data) arguments
        """
        self._on_match_callback = callback

    def on_scan_complete(self, callback: Callable[[list[ScanResult]], None]) -> None:
        """Set callback for when scan completes.

        Args:
            callback: Function taking list of ScanResults
        """
        self._on_complete_callback = callback

    def run(self) -> pd.DataFrame:
        """Execute the scan and return results as DataFrame.

        Returns:
            DataFrame with columns: symbol, plus indicator columns,
            plus conditions_met column

        Examples:
            >>> scanner = TechnicalScanner()
            >>> scanner.set_universe("XU030")
            >>> scanner.add_condition("rsi < 30")
            >>> df = scanner.run()
            >>> print(df[['symbol', 'rsi', 'price', 'conditions_met']])
        """
        from borsapy.ticker import Ticker
        from borsapy._providers.tradingview import get_tradingview_provider

        self._results = []
        tv_provider = get_tradingview_provider()

        # Collect all required indicators
        all_indicators = self._collect_required_indicators()

        for symbol in self._symbols:
            try:
                result = self._scan_symbol(symbol, all_indicators, tv_provider)
                if result is not None:
                    self._results.append(result)
            except Exception as e:
                # Log error but continue with other symbols
                import warnings

                warnings.warn(f"Error scanning {symbol}: {e}")
                continue

        # Invoke callback if set
        if self._on_complete_callback:
            self._on_complete_callback(self._results)

        return self.to_dataframe()

    def _collect_required_indicators(self) -> dict[str, list[int]]:
        """Collect all required indicators from all conditions."""
        all_indicators: dict[str, list[int]] = {}
        for parser in self._conditions.values():
            for ind, periods in parser.required_indicators().items():
                if ind not in all_indicators:
                    all_indicators[ind] = []
                for p in periods:
                    if p not in all_indicators[ind]:
                        all_indicators[ind].append(p)
        return all_indicators

    def _scan_symbol(
        self,
        symbol: str,
        indicators: dict[str, list[int]],
        tv_provider: Any,
    ) -> ScanResult | None:
        """Scan a single symbol."""
        from borsapy.ticker import Ticker

        # Get quote data
        try:
            quote = tv_provider.get_quote(symbol)
        except Exception:
            return None

        # Get historical data for indicators
        try:
            ticker = Ticker(symbol)
            history = ticker.history(period=self._data_period, interval=self._interval)
        except Exception:
            history = pd.DataFrame()

        # Build data dict with quote fields
        data: dict[str, Any] = {
            "symbol": symbol,
            "price": quote.get("last"),
            "last": quote.get("last"),
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "volume": quote.get("volume"),
            "change_percent": quote.get("change_percent"),
            "market_cap": quote.get("market_cap"),
            "bid": quote.get("bid"),
            "ask": quote.get("ask"),
        }

        # Calculate indicators and add to history
        if not history.empty:
            history = self._add_indicators_to_history(history, indicators)
            # Add latest indicator values to data
            self._add_latest_indicators(data, history, indicators)

        # Evaluate conditions
        conditions_met = []
        for name, parser in self._conditions.items():
            try:
                if parser.evaluate(data, history):
                    conditions_met.append(name)
            except Exception:
                continue

        # Only include if at least one condition met
        if not conditions_met:
            return None

        # Invoke match callback
        if self._on_match_callback:
            self._on_match_callback(symbol, data)

        return ScanResult(
            symbol=symbol,
            data=data,
            conditions_met=conditions_met,
            timestamp=datetime.now(),
        )

    def _add_indicators_to_history(
        self, df: pd.DataFrame, indicators: dict[str, list[int]]
    ) -> pd.DataFrame:
        """Add indicator columns to history DataFrame."""
        result = df.copy()

        for ind, periods in indicators.items():
            if ind == "rsi":
                for period in periods:
                    result[f"RSI_{period}"] = calculate_rsi(df, period)
            elif ind == "sma":
                for period in periods:
                    result[f"SMA_{period}"] = calculate_sma(df, period)
            elif ind == "ema":
                for period in periods:
                    result[f"EMA_{period}"] = calculate_ema(df, period)
            elif ind == "macd" or ind == "macd_signal" or ind == "macd_histogram":
                macd_df = calculate_macd(df)
                result["MACD"] = macd_df["MACD"]
                result["Signal"] = macd_df["Signal"]
                result["Histogram"] = macd_df["Histogram"]
            elif ind == "bb":
                for period in periods:
                    bb_df = calculate_bollinger_bands(df, period)
                    result["BB_Upper"] = bb_df["BB_Upper"]
                    result["BB_Middle"] = bb_df["BB_Middle"]
                    result["BB_Lower"] = bb_df["BB_Lower"]
            elif ind == "adx":
                for period in periods:
                    result[f"ADX_{period}"] = calculate_adx(df, period)
            elif ind == "atr":
                for period in periods:
                    result[f"ATR_{period}"] = calculate_atr(df, period)
            elif ind == "stoch":
                stoch_df = calculate_stochastic(df)
                result["Stoch_K"] = stoch_df["Stoch_K"]
                result["Stoch_D"] = stoch_df["Stoch_D"]
            elif ind == "obv":
                result["OBV"] = calculate_obv(df)
            elif ind == "vwap":
                result["VWAP"] = calculate_vwap(df)

        return result

    def _add_latest_indicators(
        self,
        data: dict[str, Any],
        history: pd.DataFrame,
        indicators: dict[str, list[int]],
    ) -> None:
        """Add latest indicator values to data dict."""
        if history.empty:
            return

        for ind, periods in indicators.items():
            if ind == "rsi":
                for period in periods:
                    col = f"RSI_{period}"
                    if col in history.columns:
                        data[f"rsi_{period}"] = float(history[col].iloc[-1])
                        if period == 14:
                            data["rsi"] = data[f"rsi_{period}"]
            elif ind == "sma":
                for period in periods:
                    col = f"SMA_{period}"
                    if col in history.columns:
                        data[f"sma_{period}"] = float(history[col].iloc[-1])
            elif ind == "ema":
                for period in periods:
                    col = f"EMA_{period}"
                    if col in history.columns:
                        data[f"ema_{period}"] = float(history[col].iloc[-1])
            elif ind in ("macd", "macd_signal", "macd_histogram"):
                if "MACD" in history.columns:
                    data["macd"] = float(history["MACD"].iloc[-1])
                if "Signal" in history.columns:
                    data["signal"] = float(history["Signal"].iloc[-1])
                if "Histogram" in history.columns:
                    data["histogram"] = float(history["Histogram"].iloc[-1])
            elif ind == "bb":
                if "BB_Upper" in history.columns:
                    data["bb_upper"] = float(history["BB_Upper"].iloc[-1])
                if "BB_Middle" in history.columns:
                    data["bb_middle"] = float(history["BB_Middle"].iloc[-1])
                if "BB_Lower" in history.columns:
                    data["bb_lower"] = float(history["BB_Lower"].iloc[-1])
            elif ind == "adx":
                for period in periods:
                    col = f"ADX_{period}"
                    if col in history.columns:
                        data[f"adx_{period}"] = float(history[col].iloc[-1])
                        if period == 14:
                            data["adx"] = data[f"adx_{period}"]
            elif ind == "atr":
                for period in periods:
                    col = f"ATR_{period}"
                    if col in history.columns:
                        data[f"atr_{period}"] = float(history[col].iloc[-1])
                        if period == 14:
                            data["atr"] = data[f"atr_{period}"]
            elif ind == "stoch":
                if "Stoch_K" in history.columns:
                    data["stoch_k"] = float(history["Stoch_K"].iloc[-1])
                if "Stoch_D" in history.columns:
                    data["stoch_d"] = float(history["Stoch_D"].iloc[-1])
            elif ind == "obv":
                if "OBV" in history.columns:
                    data["obv"] = float(history["OBV"].iloc[-1])
            elif ind == "vwap":
                if "VWAP" in history.columns:
                    data["vwap"] = float(history["VWAP"].iloc[-1])

    @property
    def results(self) -> list[ScanResult]:
        """Get list of scan results."""
        return self._results

    def to_dataframe(self) -> pd.DataFrame:
        """Convert results to DataFrame.

        Returns:
            DataFrame with scan results
        """
        if not self._results:
            return pd.DataFrame()

        rows = []
        for result in self._results:
            row = result.data.copy()
            row["conditions_met"] = result.conditions_met
            row["timestamp"] = result.timestamp
            rows.append(row)

        return pd.DataFrame(rows)

    def __repr__(self) -> str:
        return (
            f"TechnicalScanner(symbols={len(self._symbols)}, "
            f"conditions={len(self._conditions)})"
        )


def scan(
    symbols: str | list[str],
    condition: str,
    period: str = "3mo",
    interval: str = "1d",
) -> pd.DataFrame:
    """Convenience function for quick technical scanning.

    Args:
        symbols: Index symbol (e.g., "XU030") or list of stock symbols
        condition: Condition string (e.g., "rsi < 30")
        period: Historical data period for indicators
        interval: Data interval

    Returns:
        DataFrame with matching symbols and their data

    Examples:
        >>> import borsapy as bp
        >>> bp.scan("XU030", "rsi < 30")
        >>> bp.scan(["THYAO", "GARAN"], "price > sma_50")
        >>> bp.scan("XU100", "rsi < 30 and volume > 1000000")
    """
    scanner = TechnicalScanner()
    scanner.set_universe(symbols)
    scanner.add_condition(condition)
    scanner.set_data_period(period)
    scanner.set_interval(interval)
    return scanner.run()
