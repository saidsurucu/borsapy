"""Technical analysis indicators for borsapy.

This module provides technical analysis indicators for stocks, FX, crypto, and indices.
Indicators can be used via:
1. Pure functions: calculate_sma(df), calculate_rsi(df), etc.
2. TechnicalAnalyzer class: ta = TechnicalAnalyzer(df); ta.rsi()
3. Asset class methods (via TechnicalMixin): stock.rsi(), stock.macd()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    pass

__all__ = [
    "TechnicalAnalyzer",
    "TechnicalMixin",
    "calculate_sma",
    "calculate_ema",
    "calculate_tilson_t3",
    "calculate_rsi",
    "calculate_macd",
    "calculate_bollinger_bands",
    "calculate_atr",
    "calculate_stochastic",
    "calculate_obv",
    "calculate_vwap",
    "calculate_adx",
    "calculate_supertrend",
    "add_indicators",
]


# =============================================================================
# Pure Functions - Calculate individual indicators
# =============================================================================


def _get_price_column(df: pd.DataFrame, column: str = "Close") -> str:
    """Get the price column name, falling back to 'Price' for Fund data."""
    if column in df.columns:
        return column
    # Fund data uses "Price" instead of "Close"
    if column == "Close" and "Price" in df.columns:
        return "Price"
    return column


def calculate_sma(
    df: pd.DataFrame, period: int = 20, column: str = "Close"
) -> pd.Series:
    """Calculate Simple Moving Average (SMA).

    Args:
        df: DataFrame with price data
        period: Number of periods for moving average
        column: Column name to use for calculation

    Returns:
        Series with SMA values
    """
    col = _get_price_column(df, column)
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, name=f"SMA_{period}")
    return df[col].rolling(window=period, min_periods=1).mean()


def calculate_ema(
    df: pd.DataFrame, period: int = 20, column: str = "Close"
) -> pd.Series:
    """Calculate Exponential Moving Average (EMA).

    Args:
        df: DataFrame with price data
        period: Number of periods for moving average
        column: Column name to use for calculation

    Returns:
        Series with EMA values
    """
    col = _get_price_column(df, column)
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, name=f"EMA_{period}")
    return df[col].ewm(span=period, adjust=False).mean()


def calculate_tilson_t3(
    df: pd.DataFrame,
    period: int = 5,
    vfactor: float = 0.7,
    column: str = "Close",
) -> pd.Series:
    """Calculate Tilson T3 Moving Average.

    T3 is a triple-smoothed exponential moving average that reduces lag
    while maintaining smoothness. Developed by Tim Tilson.

    The T3 uses a volume factor (vfactor) to control the amount of
    smoothing vs responsiveness:
    - vfactor = 0: T3 behaves like a triple EMA
    - vfactor = 1: Maximum smoothing (may overshoot)
    - vfactor = 0.7: Tilson's recommended default

    Args:
        df: DataFrame with price data
        period: Number of periods for EMA calculations (default 5)
        vfactor: Volume factor for smoothing (0-1, default 0.7)
        column: Column name to use for calculation

    Returns:
        Series with T3 values

    Examples:
        >>> t3 = calculate_tilson_t3(df, period=5, vfactor=0.7)
        >>> # More responsive (less smooth)
        >>> t3_fast = calculate_tilson_t3(df, period=5, vfactor=0.5)
        >>> # More smooth (more lag)
        >>> t3_smooth = calculate_tilson_t3(df, period=5, vfactor=0.9)
    """
    col = _get_price_column(df, column)
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, name=f"T3_{period}")

    # Calculate coefficients
    c1 = -(vfactor**3)
    c2 = 3 * vfactor**2 + 3 * vfactor**3
    c3 = -6 * vfactor**2 - 3 * vfactor - 3 * vfactor**3
    c4 = 1 + 3 * vfactor + vfactor**3 + 3 * vfactor**2

    # Calculate 6 consecutive EMAs
    ema1 = df[col].ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    ema3 = ema2.ewm(span=period, adjust=False).mean()
    ema4 = ema3.ewm(span=period, adjust=False).mean()
    ema5 = ema4.ewm(span=period, adjust=False).mean()
    ema6 = ema5.ewm(span=period, adjust=False).mean()

    # T3 = c1*e6 + c2*e5 + c3*e4 + c4*e3
    t3 = c1 * ema6 + c2 * ema5 + c3 * ema4 + c4 * ema3

    return t3.rename(f"T3_{period}")


def calculate_rsi(
    df: pd.DataFrame, period: int = 14, column: str = "Close"
) -> pd.Series:
    """Calculate Relative Strength Index (RSI).

    RSI measures the speed and magnitude of price movements on a scale of 0-100.
    - RSI > 70: Overbought (potential sell signal)
    - RSI < 30: Oversold (potential buy signal)

    Args:
        df: DataFrame with price data
        period: Number of periods for RSI calculation (default 14)
        column: Column name to use for calculation

    Returns:
        Series with RSI values (0-100)
    """
    col = _get_price_column(df, column)
    if col not in df.columns or len(df) < period:
        return pd.Series(np.nan, index=df.index, name=f"RSI_{period}")

    delta = df[col].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    # Use Wilder's smoothing (same as TradingView)
    # Wilder's uses alpha=1/period, NOT span=period
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Handle division by zero
    rsi = rsi.replace([np.inf, -np.inf], np.nan)
    rsi = rsi.fillna(50.0)  # Neutral RSI when no movement

    return rsi.rename(f"RSI_{period}")


def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "Close",
) -> pd.DataFrame:
    """Calculate Moving Average Convergence Divergence (MACD).

    MACD shows the relationship between two moving averages of prices.
    - MACD Line: Fast EMA - Slow EMA
    - Signal Line: EMA of MACD Line
    - Histogram: MACD Line - Signal Line

    Args:
        df: DataFrame with price data
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line EMA period (default 9)
        column: Column name to use for calculation

    Returns:
        DataFrame with columns: MACD, Signal, Histogram
    """
    col = _get_price_column(df, column)
    if col not in df.columns:
        return pd.DataFrame(
            {"MACD": np.nan, "Signal": np.nan, "Histogram": np.nan},
            index=df.index,
        )

    ema_fast = df[col].ewm(span=fast, adjust=False).mean()
    ema_slow = df[col].ewm(span=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return pd.DataFrame(
        {"MACD": macd_line, "Signal": signal_line, "Histogram": histogram},
        index=df.index,
    )


def calculate_bollinger_bands(
    df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, column: str = "Close"
) -> pd.DataFrame:
    """Calculate Bollinger Bands.

    Bollinger Bands consist of a middle band (SMA) and two outer bands
    at standard deviation levels above and below the middle band.

    Args:
        df: DataFrame with price data
        period: Period for SMA and standard deviation
        std_dev: Number of standard deviations for bands
        column: Column name to use for calculation

    Returns:
        DataFrame with columns: Upper, Middle, Lower
    """
    col = _get_price_column(df, column)
    if col not in df.columns:
        return pd.DataFrame(
            {"BB_Upper": np.nan, "BB_Middle": np.nan, "BB_Lower": np.nan},
            index=df.index,
        )

    middle = df[col].rolling(window=period, min_periods=1).mean()
    std = df[col].rolling(window=period, min_periods=1).std()

    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    return pd.DataFrame(
        {"BB_Upper": upper, "BB_Middle": middle, "BB_Lower": lower},
        index=df.index,
    )


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR).

    ATR measures market volatility by decomposing the entire range of an asset
    price for that period.

    Args:
        df: DataFrame with High, Low, Close columns
        period: Period for ATR calculation

    Returns:
        Series with ATR values
    """
    required = ["High", "Low", "Close"]
    if not all(col in df.columns for col in required):
        return pd.Series(np.nan, index=df.index, name=f"ATR_{period}")

    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    # True Range components
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))

    # True Range is the maximum of the three
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # ATR uses Wilder's smoothing (same as TradingView)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()

    return atr.rename(f"ATR_{period}")


def calculate_stochastic(
    df: pd.DataFrame, k_period: int = 14, d_period: int = 3
) -> pd.DataFrame:
    """Calculate Stochastic Oscillator (%K and %D).

    The Stochastic Oscillator compares a closing price to a range of prices
    over a certain period of time.
    - %K > 80: Overbought
    - %K < 20: Oversold

    Args:
        df: DataFrame with High, Low, Close columns
        k_period: Period for %K calculation
        d_period: Period for %D (signal line)

    Returns:
        DataFrame with columns: Stoch_K, Stoch_D
    """
    required = ["High", "Low", "Close"]
    if not all(col in df.columns for col in required):
        return pd.DataFrame(
            {"Stoch_K": np.nan, "Stoch_D": np.nan},
            index=df.index,
        )

    # Calculate %K
    lowest_low = df["Low"].rolling(window=k_period, min_periods=1).min()
    highest_high = df["High"].rolling(window=k_period, min_periods=1).max()

    stoch_k = 100 * (df["Close"] - lowest_low) / (highest_high - lowest_low)
    stoch_k = stoch_k.replace([np.inf, -np.inf], np.nan).fillna(50.0)

    # %D is the SMA of %K
    stoch_d = stoch_k.rolling(window=d_period, min_periods=1).mean()

    return pd.DataFrame(
        {"Stoch_K": stoch_k, "Stoch_D": stoch_d},
        index=df.index,
    )


def calculate_obv(df: pd.DataFrame) -> pd.Series:
    """Calculate On-Balance Volume (OBV).

    OBV uses volume flow to predict changes in stock price.
    Rising OBV indicates positive volume pressure that can lead to higher prices.

    Args:
        df: DataFrame with Close and Volume columns

    Returns:
        Series with OBV values
    """
    required = ["Close", "Volume"]
    if not all(col in df.columns for col in required):
        return pd.Series(np.nan, index=df.index, name="OBV")

    # Direction: +1 if close > previous close, -1 if close < previous close, 0 if equal
    direction = np.sign(df["Close"].diff())
    direction.iloc[0] = 0  # First value has no direction

    # OBV is cumulative sum of signed volume
    obv = (direction * df["Volume"]).cumsum()

    return obv.rename("OBV")


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculate Volume Weighted Average Price (VWAP).

    VWAP gives the average price weighted by volume.
    It's often used as a trading benchmark.

    Args:
        df: DataFrame with High, Low, Close, Volume columns

    Returns:
        Series with VWAP values
    """
    required = ["High", "Low", "Close", "Volume"]
    if not all(col in df.columns for col in required):
        return pd.Series(np.nan, index=df.index, name="VWAP")

    # Typical Price
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3

    # Cumulative TP * Volume / Cumulative Volume
    cumulative_tp_vol = (typical_price * df["Volume"]).cumsum()
    cumulative_vol = df["Volume"].cumsum()

    vwap = cumulative_tp_vol / cumulative_vol
    vwap = vwap.replace([np.inf, -np.inf], np.nan)

    return vwap.rename("VWAP")


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average Directional Index (ADX).

    ADX measures the strength of a trend regardless of its direction.
    - ADX > 25: Strong trend
    - ADX < 20: Weak or no trend

    Args:
        df: DataFrame with High, Low, Close columns
        period: Period for ADX calculation

    Returns:
        Series with ADX values
    """
    required = ["High", "Low", "Close"]
    if not all(col in df.columns for col in required):
        return pd.Series(np.nan, index=df.index, name=f"ADX_{period}")

    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    # Calculate +DM and -DM
    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Smoothed values using Wilder's smoothing (same as TradingView)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)

    # DX and ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    dx = dx.replace([np.inf, -np.inf], np.nan).fillna(0)

    adx = dx.ewm(alpha=1 / period, adjust=False).mean()

    return adx.rename(f"ADX_{period}")


def calculate_supertrend(
    df: pd.DataFrame, atr_period: int = 10, multiplier: float = 3.0
) -> pd.DataFrame:
    """Calculate Supertrend indicator.

    Supertrend is a trend-following indicator based on ATR.
    - When price is above Supertrend line: Bullish (uptrend)
    - When price is below Supertrend line: Bearish (downtrend)

    Args:
        df: DataFrame with High, Low, Close columns
        atr_period: Period for ATR calculation (default: 10)
        multiplier: ATR multiplier for bands (default: 3.0)

    Returns:
        DataFrame with columns:
        - Supertrend: The Supertrend line value
        - Supertrend_Direction: 1 for bullish, -1 for bearish
        - Supertrend_Upper: Upper band
        - Supertrend_Lower: Lower band
    """
    required = ["High", "Low", "Close"]
    if not all(col in df.columns for col in required):
        return pd.DataFrame(
            {
                "Supertrend": np.nan,
                "Supertrend_Direction": np.nan,
                "Supertrend_Upper": np.nan,
                "Supertrend_Lower": np.nan,
            },
            index=df.index,
        )

    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    # Calculate ATR
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / atr_period, adjust=False).mean()

    # Calculate basic bands
    hl2 = (high + low) / 2
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)

    # Initialize arrays
    n = len(df)
    supertrend = np.zeros(n)
    direction = np.zeros(n)
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)

    # First value
    final_upper[0] = basic_upper.iloc[0]
    final_lower[0] = basic_lower.iloc[0]
    supertrend[0] = basic_upper.iloc[0]
    direction[0] = -1  # Start bearish

    # Calculate Supertrend
    for i in range(1, n):
        # Final Upper Band
        if basic_upper.iloc[i] < final_upper[i - 1] or close.iloc[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper.iloc[i]
        else:
            final_upper[i] = final_upper[i - 1]

        # Final Lower Band
        if basic_lower.iloc[i] > final_lower[i - 1] or close.iloc[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower.iloc[i]
        else:
            final_lower[i] = final_lower[i - 1]

        # Supertrend and Direction
        if supertrend[i - 1] == final_upper[i - 1]:
            # Was bearish
            if close.iloc[i] > final_upper[i]:
                supertrend[i] = final_lower[i]
                direction[i] = 1  # Bullish
            else:
                supertrend[i] = final_upper[i]
                direction[i] = -1  # Bearish
        else:
            # Was bullish
            if close.iloc[i] < final_lower[i]:
                supertrend[i] = final_upper[i]
                direction[i] = -1  # Bearish
            else:
                supertrend[i] = final_lower[i]
                direction[i] = 1  # Bullish

    return pd.DataFrame(
        {
            "Supertrend": supertrend,
            "Supertrend_Direction": direction,
            "Supertrend_Upper": final_upper,
            "Supertrend_Lower": final_lower,
        },
        index=df.index,
    )


# =============================================================================
# Convenience Function - Add all indicators to DataFrame
# =============================================================================


def add_indicators(
    df: pd.DataFrame,
    indicators: list[str] | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Add technical indicator columns to a DataFrame.

    Args:
        df: DataFrame with OHLCV data (Open, High, Low, Close, Volume)
        indicators: List of indicators to add. If None, adds all applicable.
            Options: 'sma', 'ema', 'rsi', 'macd', 'bollinger', 'atr',
                     'stochastic', 'obv', 'vwap', 'adx', 'supertrend'
        **kwargs: Additional arguments for specific indicators:
            - sma_period: SMA period (default 20)
            - ema_period: EMA period (default 12)
            - rsi_period: RSI period (default 14)
            - bb_period: Bollinger Bands period (default 20)
            - atr_period: ATR period (default 14)
            - adx_period: ADX period (default 14)
            - supertrend_period: Supertrend ATR period (default 10)
            - supertrend_multiplier: Supertrend ATR multiplier (default 3.0)

    Returns:
        DataFrame with indicator columns added
    """
    result = df.copy()

    # Default indicators based on available columns
    has_volume = "Volume" in df.columns
    has_hlc = all(col in df.columns for col in ["High", "Low", "Close"])

    if indicators is None:
        indicators = ["sma", "ema", "rsi", "macd", "bollinger"]
        if has_hlc:
            indicators.extend(["atr", "stochastic", "adx", "supertrend"])
        if has_volume:
            indicators.append("obv")
        if has_volume and has_hlc:
            indicators.append("vwap")

    # Get periods from kwargs
    sma_period = kwargs.get("sma_period", 20)
    ema_period = kwargs.get("ema_period", 12)
    rsi_period = kwargs.get("rsi_period", 14)
    bb_period = kwargs.get("bb_period", 20)
    atr_period = kwargs.get("atr_period", 14)
    adx_period = kwargs.get("adx_period", 14)
    supertrend_period = kwargs.get("supertrend_period", 10)
    supertrend_multiplier = kwargs.get("supertrend_multiplier", 3.0)

    # Add indicators
    for indicator in indicators:
        indicator = indicator.lower()

        if indicator == "sma":
            result[f"SMA_{sma_period}"] = calculate_sma(df, sma_period)
        elif indicator == "ema":
            result[f"EMA_{ema_period}"] = calculate_ema(df, ema_period)
        elif indicator == "rsi":
            result[f"RSI_{rsi_period}"] = calculate_rsi(df, rsi_period)
        elif indicator == "macd":
            macd_df = calculate_macd(df)
            result["MACD"] = macd_df["MACD"]
            result["MACD_Signal"] = macd_df["Signal"]
            result["MACD_Hist"] = macd_df["Histogram"]
        elif indicator == "bollinger":
            bb_df = calculate_bollinger_bands(df, bb_period)
            result["BB_Upper"] = bb_df["BB_Upper"]
            result["BB_Middle"] = bb_df["BB_Middle"]
            result["BB_Lower"] = bb_df["BB_Lower"]
        elif indicator == "atr" and has_hlc:
            result[f"ATR_{atr_period}"] = calculate_atr(df, atr_period)
        elif indicator == "stochastic" and has_hlc:
            stoch_df = calculate_stochastic(df)
            result["Stoch_K"] = stoch_df["Stoch_K"]
            result["Stoch_D"] = stoch_df["Stoch_D"]
        elif indicator == "obv" and has_volume:
            result["OBV"] = calculate_obv(df)
        elif indicator == "vwap" and has_volume and has_hlc:
            result["VWAP"] = calculate_vwap(df)
        elif indicator == "adx" and has_hlc:
            result[f"ADX_{adx_period}"] = calculate_adx(df, adx_period)
        elif indicator == "supertrend" and has_hlc:
            st_df = calculate_supertrend(df, supertrend_period, supertrend_multiplier)
            result["Supertrend"] = st_df["Supertrend"]
            result["Supertrend_Direction"] = st_df["Supertrend_Direction"]

    return result


# =============================================================================
# TechnicalAnalyzer Class
# =============================================================================


class TechnicalAnalyzer:
    """Technical analysis wrapper for OHLCV DataFrames.

    Provides easy access to technical indicators as methods and properties.

    Example:
        >>> df = stock.history(period="1y")
        >>> ta = TechnicalAnalyzer(df)
        >>> ta.rsi()  # Returns full RSI series
        >>> ta.latest  # Returns dict with latest values of all indicators
    """

    def __init__(self, df: pd.DataFrame) -> None:
        """Initialize with OHLCV DataFrame.

        Args:
            df: DataFrame with price data (must have at least 'Close' column)
        """
        self._df = df.copy()
        self._has_volume = "Volume" in df.columns
        self._has_hlc = all(col in df.columns for col in ["High", "Low", "Close"])

    def sma(self, period: int = 20) -> pd.Series:
        """Calculate Simple Moving Average."""
        return calculate_sma(self._df, period)

    def ema(self, period: int = 20) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return calculate_ema(self._df, period)

    def tilson_t3(self, period: int = 5, vfactor: float = 0.7) -> pd.Series:
        """Calculate Tilson T3 Moving Average."""
        return calculate_tilson_t3(self._df, period, vfactor)

    def rsi(self, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        return calculate_rsi(self._df, period)

    def macd(
        self, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> pd.DataFrame:
        """Calculate MACD (line, signal, histogram)."""
        return calculate_macd(self._df, fast, slow, signal)

    def bollinger_bands(
        self, period: int = 20, std_dev: float = 2.0
    ) -> pd.DataFrame:
        """Calculate Bollinger Bands (upper, middle, lower)."""
        return calculate_bollinger_bands(self._df, period, std_dev)

    def atr(self, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        return calculate_atr(self._df, period)

    def stochastic(self, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
        """Calculate Stochastic Oscillator (%K, %D)."""
        return calculate_stochastic(self._df, k_period, d_period)

    def obv(self) -> pd.Series:
        """Calculate On-Balance Volume."""
        return calculate_obv(self._df)

    def vwap(self) -> pd.Series:
        """Calculate Volume Weighted Average Price."""
        return calculate_vwap(self._df)

    def adx(self, period: int = 14) -> pd.Series:
        """Calculate Average Directional Index."""
        return calculate_adx(self._df, period)

    def supertrend(self, atr_period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
        """Calculate Supertrend indicator.

        Args:
            atr_period: Period for ATR calculation (default 10)
            multiplier: ATR multiplier for bands (default 3.0)

        Returns:
            DataFrame with Supertrend, Supertrend_Direction, Supertrend_Upper, Supertrend_Lower
        """
        return calculate_supertrend(self._df, atr_period, multiplier)

    def heikin_ashi(self) -> pd.DataFrame:
        """Calculate Heikin Ashi candlestick values.

        Returns:
            DataFrame with HA_Open, HA_High, HA_Low, HA_Close, Volume columns
        """
        from borsapy.charts import calculate_heikin_ashi

        return calculate_heikin_ashi(self._df)

    def all(self, **kwargs: Any) -> pd.DataFrame:
        """Get DataFrame with all applicable indicators added."""
        return add_indicators(self._df, **kwargs)

    @property
    def latest(self) -> dict[str, float]:
        """Get latest values of all applicable indicators.

        Returns:
            Dictionary with indicator names and their latest values
        """
        result: dict[str, float] = {}

        # Always available (need Close or Price)
        has_price = "Close" in self._df.columns or "Price" in self._df.columns
        if has_price and len(self._df) > 0:
            result["sma_20"] = float(self.sma(20).iloc[-1])
            result["sma_50"] = float(self.sma(50).iloc[-1])
            result["ema_12"] = float(self.ema(12).iloc[-1])
            result["ema_26"] = float(self.ema(26).iloc[-1])
            result["t3_5"] = float(self.tilson_t3(5).iloc[-1])
            result["rsi_14"] = float(self.rsi(14).iloc[-1])

            macd_df = self.macd()
            result["macd"] = float(macd_df["MACD"].iloc[-1])
            result["macd_signal"] = float(macd_df["Signal"].iloc[-1])
            result["macd_histogram"] = float(macd_df["Histogram"].iloc[-1])

            bb_df = self.bollinger_bands()
            result["bb_upper"] = float(bb_df["BB_Upper"].iloc[-1])
            result["bb_middle"] = float(bb_df["BB_Middle"].iloc[-1])
            result["bb_lower"] = float(bb_df["BB_Lower"].iloc[-1])

        # Need High, Low, Close
        if self._has_hlc and len(self._df) > 0:
            result["atr_14"] = float(self.atr(14).iloc[-1])
            result["adx_14"] = float(self.adx(14).iloc[-1])

            stoch_df = self.stochastic()
            result["stoch_k"] = float(stoch_df["Stoch_K"].iloc[-1])
            result["stoch_d"] = float(stoch_df["Stoch_D"].iloc[-1])

            st_df = self.supertrend()
            result["supertrend"] = float(st_df["Supertrend"].iloc[-1])
            result["supertrend_direction"] = float(st_df["Supertrend_Direction"].iloc[-1])

        # Need Volume
        if self._has_volume and len(self._df) > 0:
            result["obv"] = float(self.obv().iloc[-1])

        # Need HLC + Volume
        if self._has_hlc and self._has_volume and len(self._df) > 0:
            result["vwap"] = float(self.vwap().iloc[-1])

        # Round all values
        return {k: round(v, 4) if not np.isnan(v) else np.nan for k, v in result.items()}


# =============================================================================
# TechnicalMixin - Add to Asset Classes
# =============================================================================


class TechnicalMixin:
    """Mixin class to add technical analysis methods to asset classes.

    This mixin requires the class to have a `history()` method that returns
    a DataFrame with OHLC(V) data.

    Example:
        >>> class Ticker(TechnicalMixin):
        ...     def history(self, period): ...
        >>> stock = Ticker("THYAO")
        >>> stock.rsi()  # Returns latest RSI value
        >>> stock.technicals(period="1y")  # Returns TechnicalAnalyzer
    """

    def history(self, period: str = "1mo", **kwargs: Any) -> pd.DataFrame:
        """Must be implemented by the class using this mixin."""
        raise NotImplementedError("Subclass must implement history() method")

    def technicals(self, period: str = "1y", **kwargs: Any) -> TechnicalAnalyzer:
        """Get TechnicalAnalyzer for historical data.

        Args:
            period: History period (default "1y")
            **kwargs: Additional arguments for history()

        Returns:
            TechnicalAnalyzer instance for the historical data
        """
        df = self.history(period=period, **kwargs)
        return TechnicalAnalyzer(df)

    def history_with_indicators(
        self,
        period: str = "1mo",
        indicators: list[str] | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Get historical data with technical indicator columns.

        Args:
            period: History period (default "1mo")
            indicators: List of indicators to add (None = all applicable)
            **kwargs: Additional arguments for indicators

        Returns:
            DataFrame with OHLCV and indicator columns
        """
        df = self.history(period=period)
        return add_indicators(df, indicators, **kwargs)

    def rsi(self, interval: str = "1d", **kwargs: Any) -> float:
        """Get latest RSI value from TradingView.

        Args:
            interval: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1W, 1M)
            **kwargs: Ignored (for backwards compatibility)

        Returns:
            Latest RSI value (0-100)
        """
        try:
            signals = self.ta_signals(interval=interval)
            rsi = signals.get("oscillators", {}).get("values", {}).get("RSI")
            return round(float(rsi), 2) if rsi is not None else np.nan
        except (NotImplementedError, Exception):
            # Fallback to local calculation
            df = self.history(period="3mo")
            if df.empty:
                return np.nan
            rsi_series = calculate_rsi(df, 14)
            return round(float(rsi_series.iloc[-1]), 2)

    def sma(self, interval: str = "1d", sma_period: int = 20, **kwargs: Any) -> float:
        """Get latest SMA value from TradingView.

        Args:
            interval: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1W, 1M)
            sma_period: SMA period (5, 10, 20, 30, 50, 100, 200)
            **kwargs: Ignored (for backwards compatibility)

        Returns:
            Latest SMA value
        """
        try:
            signals = self.ta_signals(interval=interval)
            sma = signals.get("moving_averages", {}).get("values", {}).get(f"SMA{sma_period}")
            return round(float(sma), 2) if sma is not None else np.nan
        except (NotImplementedError, Exception):
            # Fallback to local calculation
            df = self.history(period="3mo")
            if df.empty:
                return np.nan
            sma_series = calculate_sma(df, sma_period)
            return round(float(sma_series.iloc[-1]), 2)

    def ema(self, interval: str = "1d", ema_period: int = 20, **kwargs: Any) -> float:
        """Get latest EMA value from TradingView.

        Args:
            interval: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1W, 1M)
            ema_period: EMA period (5, 10, 20, 30, 50, 100, 200)
            **kwargs: Ignored (for backwards compatibility)

        Returns:
            Latest EMA value
        """
        try:
            signals = self.ta_signals(interval=interval)
            ema = signals.get("moving_averages", {}).get("values", {}).get(f"EMA{ema_period}")
            return round(float(ema), 2) if ema is not None else np.nan
        except (NotImplementedError, Exception):
            # Fallback to local calculation
            df = self.history(period="3mo")
            if df.empty:
                return np.nan
            ema_series = calculate_ema(df, ema_period)
            return round(float(ema_series.iloc[-1]), 2)

    def tilson_t3(
        self, period: str = "3mo", t3_period: int = 5, vfactor: float = 0.7
    ) -> float:
        """Get latest Tilson T3 value.

        T3 is a triple-smoothed EMA that reduces lag while maintaining smoothness.

        Note: This indicator uses local calculation as it's not available
        in TradingView Scanner API.

        Args:
            period: History period to fetch (default "3mo")
            t3_period: T3 period (default 5)
            vfactor: Volume factor (0-1, default 0.7)

        Returns:
            Latest T3 value

        Examples:
            >>> stock = bp.Ticker("THYAO")
            >>> stock.tilson_t3()
            285.5
        """
        df = self.history(period=period)
        if df.empty:
            return np.nan
        t3_series = calculate_tilson_t3(df, t3_period, vfactor)
        return round(float(t3_series.iloc[-1]), 2)

    def macd(self, interval: str = "1d", **kwargs: Any) -> dict[str, float]:
        """Get latest MACD values from TradingView.

        Args:
            interval: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1W, 1M)
            **kwargs: Ignored (for backwards compatibility)

        Returns:
            Dictionary with 'macd', 'signal', 'histogram' keys
        """
        try:
            signals = self.ta_signals(interval=interval)
            osc_values = signals.get("oscillators", {}).get("values", {})
            macd = osc_values.get("MACD.macd")
            signal = osc_values.get("MACD.signal")
            if macd is not None and signal is not None:
                return {
                    "macd": round(float(macd), 4),
                    "signal": round(float(signal), 4),
                    "histogram": round(float(macd - signal), 4),
                }
            return {"macd": np.nan, "signal": np.nan, "histogram": np.nan}
        except (NotImplementedError, Exception):
            # Fallback to local calculation
            df = self.history(period="3mo")
            if df.empty:
                return {"macd": np.nan, "signal": np.nan, "histogram": np.nan}
            macd_df = calculate_macd(df, 12, 26, 9)
            return {
                "macd": round(float(macd_df["MACD"].iloc[-1]), 4),
                "signal": round(float(macd_df["Signal"].iloc[-1]), 4),
                "histogram": round(float(macd_df["Histogram"].iloc[-1]), 4),
            }

    def bollinger_bands(self, interval: str = "1d", **kwargs: Any) -> dict[str, float]:
        """Get latest Bollinger Bands values from TradingView.

        Args:
            interval: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1W, 1M)
            **kwargs: Ignored (for backwards compatibility)

        Returns:
            Dictionary with 'upper', 'middle', 'lower' keys
        """
        try:
            signals = self.ta_signals(interval=interval)
            ma_values = signals.get("moving_averages", {}).get("values", {})
            upper = ma_values.get("BB.upper")
            lower = ma_values.get("BB.lower")
            middle = ma_values.get("BB.middle")
            if upper is not None and lower is not None:
                return {
                    "upper": round(float(upper), 2),
                    "middle": round(float(middle), 2) if middle else round((upper + lower) / 2, 2),
                    "lower": round(float(lower), 2),
                }
            return {"upper": np.nan, "middle": np.nan, "lower": np.nan}
        except (NotImplementedError, Exception):
            # Fallback to local calculation
            df = self.history(period="3mo")
            if df.empty:
                return {"upper": np.nan, "middle": np.nan, "lower": np.nan}
            bb_df = calculate_bollinger_bands(df, 20, 2.0)
            return {
                "upper": round(float(bb_df["BB_Upper"].iloc[-1]), 2),
                "middle": round(float(bb_df["BB_Middle"].iloc[-1]), 2),
                "lower": round(float(bb_df["BB_Lower"].iloc[-1]), 2),
            }

    def atr(self, interval: str = "1d", **kwargs: Any) -> float:
        """Get latest ATR value from TradingView.

        Args:
            interval: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1W, 1M)
            **kwargs: Ignored (for backwards compatibility)

        Returns:
            Latest ATR value
        """
        try:
            signals = self.ta_signals(interval=interval)
            atr = signals.get("moving_averages", {}).get("values", {}).get("ATR")
            return round(float(atr), 4) if atr is not None else np.nan
        except (NotImplementedError, Exception):
            # Fallback to local calculation
            df = self.history(period="3mo")
            if df.empty:
                return np.nan
            atr_series = calculate_atr(df, 14)
            return round(float(atr_series.iloc[-1]), 4)

    def stochastic(self, interval: str = "1d", **kwargs: Any) -> dict[str, float]:
        """Get latest Stochastic Oscillator values from TradingView.

        Args:
            interval: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1W, 1M)
            **kwargs: Ignored (for backwards compatibility)

        Returns:
            Dictionary with 'k' and 'd' keys (0-100 scale)
        """
        try:
            signals = self.ta_signals(interval=interval)
            osc_values = signals.get("oscillators", {}).get("values", {})
            k = osc_values.get("Stoch.K")
            d = osc_values.get("Stoch.D")
            if k is not None and d is not None:
                return {
                    "k": round(float(k), 2),
                    "d": round(float(d), 2),
                }
            return {"k": np.nan, "d": np.nan}
        except (NotImplementedError, Exception):
            # Fallback to local calculation
            df = self.history(period="3mo")
            if df.empty:
                return {"k": np.nan, "d": np.nan}
            stoch_df = calculate_stochastic(df, 14, 3)
            return {
                "k": round(float(stoch_df["Stoch_K"].iloc[-1]), 2),
                "d": round(float(stoch_df["Stoch_D"].iloc[-1]), 2),
            }

    def obv(self, period: str = "3mo") -> float:
        """Get latest OBV value.

        Args:
            period: History period to fetch

        Returns:
            Latest OBV value
        """
        df = self.history(period=period)
        if df.empty:
            return np.nan
        obv_series = calculate_obv(df)
        return round(float(obv_series.iloc[-1]), 0)

    def vwap(self, interval: str = "1d", **kwargs: Any) -> float:
        """Get latest VWAP value from TradingView.

        Args:
            interval: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1W, 1M)
            **kwargs: Ignored (for backwards compatibility)

        Returns:
            Latest VWAP value
        """
        try:
            signals = self.ta_signals(interval=interval)
            vwap = signals.get("moving_averages", {}).get("values", {}).get("VWAP")
            return round(float(vwap), 2) if vwap is not None else np.nan
        except (NotImplementedError, Exception):
            # Fallback to local calculation
            df = self.history(period="3mo")
            if df.empty:
                return np.nan
            vwap_series = calculate_vwap(df)
            return round(float(vwap_series.iloc[-1]), 2)

    def adx(self, interval: str = "1d", **kwargs: Any) -> float:
        """Get latest ADX value from TradingView.

        Args:
            interval: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1W, 1M)
            **kwargs: Ignored (for backwards compatibility)

        Returns:
            Latest ADX value (0-100 scale)
        """
        try:
            signals = self.ta_signals(interval=interval)
            adx = signals.get("oscillators", {}).get("values", {}).get("ADX")
            return round(float(adx), 2) if adx is not None else np.nan
        except (NotImplementedError, Exception):
            # Fallback to local calculation
            df = self.history(period="3mo")
            if df.empty:
                return np.nan
            adx_series = calculate_adx(df, 14)
            return round(float(adx_series.iloc[-1]), 2)

    def heikin_ashi(self, period: str = "1mo") -> pd.DataFrame:
        """Get Heikin Ashi candlestick data.

        Heikin Ashi candles smooth price data and help identify trends.

        Args:
            period: History period to fetch (default "1mo")

        Returns:
            DataFrame with columns:
            - HA_Open: Heikin Ashi open price
            - HA_High: Heikin Ashi high price
            - HA_Low: Heikin Ashi low price
            - HA_Close: Heikin Ashi close price
            - Volume: Original volume (if available)

        Examples:
            >>> stock = bp.Ticker("THYAO")
            >>> ha = stock.heikin_ashi(period="1y")
            >>> print(ha.columns.tolist())
            ['HA_Open', 'HA_High', 'HA_Low', 'HA_Close', 'Volume']
        """
        from borsapy.charts import calculate_heikin_ashi

        df = self.history(period=period)
        if df.empty:
            return pd.DataFrame(columns=["HA_Open", "HA_High", "HA_Low", "HA_Close", "Volume"])
        return calculate_heikin_ashi(df)

    def _get_ta_symbol_info(self) -> tuple[str, str]:
        """Get TradingView symbol and screener for TA signals.

        Must be implemented by subclasses.

        Returns:
            Tuple of (tv_symbol, screener) where:
            - tv_symbol: Full TradingView symbol (e.g., "BIST:THYAO", "FX:USDTRY")
            - screener: Market screener (turkey, forex, crypto, america)

        Raises:
            NotImplementedError: If TA signals are not supported for this asset
        """
        raise NotImplementedError(
            f"TA signals not supported for {self.__class__.__name__}. "
            "Subclass must implement _get_ta_symbol_info() method."
        )

    def ta_signals(self, interval: str = "1d") -> dict[str, Any]:
        """Get TradingView technical analysis signals.

        Fetches buy/sell/neutral signals from TradingView Scanner API.
        This provides 11 oscillator indicators and up to 15 moving averages
        with their computed signals.

        Args:
            interval: Timeframe for analysis. Valid intervals:
                     1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1W, 1M

        Returns:
            Dictionary with structure:
            {
                "symbol": str,
                "exchange": str,
                "interval": str,
                "summary": {
                    "recommendation": str,  # STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
                    "buy": int,
                    "sell": int,
                    "neutral": int
                },
                "oscillators": {
                    "recommendation": str,
                    "buy": int,
                    "sell": int,
                    "neutral": int,
                    "compute": {"RSI": "NEUTRAL", "MACD": "BUY", ...},
                    "values": {"RSI": 48.95, "MACD.macd": 3.78, ...}
                },
                "moving_averages": {
                    "recommendation": str,
                    "buy": int,
                    "sell": int,
                    "neutral": int,
                    "compute": {"EMA20": "BUY", "SMA50": "SELL", ...},
                    "values": {"EMA20": 285.5, "SMA50": 278.2, ...}
                }
            }

        Examples:
            >>> stock = bp.Ticker("THYAO")
            >>> signals = stock.ta_signals()
            >>> signals['summary']['recommendation']
            'BUY'
            >>> signals['oscillators']['compute']['RSI']
            'NEUTRAL'
            >>> signals['oscillators']['values']['RSI']
            48.95

            >>> # Get hourly signals
            >>> signals_1h = stock.ta_signals(interval="1h")

        Raises:
            NotImplementedError: If TA signals not supported for this asset
            APIError: If TradingView API request fails
        """
        from borsapy._providers.tradingview_scanner import get_scanner_provider

        tv_symbol, screener = self._get_ta_symbol_info()
        return get_scanner_provider().get_ta_signals(tv_symbol, screener, interval)

    def ta_signals_all_timeframes(self) -> dict[str, dict[str, Any]]:
        """Get TradingView TA signals for all available timeframes.

        Fetches signals for 9 different timeframes in a single call.
        Useful for multi-timeframe analysis.

        Returns:
            Dictionary keyed by interval with ta_signals() result for each:
            {
                "1m": {...},
                "5m": {...},
                "15m": {...},
                "30m": {...},
                "1h": {...},
                "4h": {...},
                "1d": {...},
                "1W": {...},
                "1M": {...}
            }

        Examples:
            >>> stock = bp.Ticker("THYAO")
            >>> all_tf = stock.ta_signals_all_timeframes()
            >>> all_tf['1d']['summary']['recommendation']
            'BUY'
            >>> all_tf['1h']['summary']['recommendation']
            'STRONG_BUY'

        Raises:
            NotImplementedError: If TA signals not supported for this asset
            APIError: If TradingView API request fails
        """
        intervals = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1W", "1M"]
        result = {}
        for interval in intervals:
            try:
                result[interval] = self.ta_signals(interval)
            except Exception as e:
                # Include error info for failed intervals
                result[interval] = {"error": str(e)}
        return result

    def supertrend(
        self, period: str = "3mo", atr_period: int = 10, multiplier: float = 3.0
    ) -> dict[str, float]:
        """Get latest Supertrend values.

        Supertrend is a trend-following indicator based on ATR.
        - Direction = 1: Bullish (price above Supertrend line)
        - Direction = -1: Bearish (price below Supertrend line)

        Note: This indicator uses local calculation as it's not available
        in TradingView Scanner API.

        Args:
            period: History period to fetch (default "3mo")
            atr_period: Period for ATR calculation (default 10)
            multiplier: ATR multiplier for bands (default 3.0)

        Returns:
            Dictionary with keys:
            - value: Current Supertrend line value
            - direction: 1 (bullish) or -1 (bearish)
            - upper: Upper band value
            - lower: Lower band value

        Examples:
            >>> stock = bp.Ticker("THYAO")
            >>> st = stock.supertrend()
            >>> st['direction']  # 1 = bullish, -1 = bearish
            1
            >>> st['value']
            275.5
        """
        df = self.history(period=period)
        if df.empty:
            return {
                "value": np.nan,
                "direction": np.nan,
                "upper": np.nan,
                "lower": np.nan,
            }
        st_df = calculate_supertrend(df, atr_period, multiplier)
        return {
            "value": round(float(st_df["Supertrend"].iloc[-1]), 2),
            "direction": int(st_df["Supertrend_Direction"].iloc[-1]),
            "upper": round(float(st_df["Supertrend_Upper"].iloc[-1]), 2),
            "lower": round(float(st_df["Supertrend_Lower"].iloc[-1]), 2),
        }
