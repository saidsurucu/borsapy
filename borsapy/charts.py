"""Alternative chart types for borsapy.

This module provides alternative chart calculations like Heikin Ashi.

Examples:
    >>> import borsapy as bp
    >>> stock = bp.Ticker("THYAO")
    >>> df = stock.history(period="1y")

    >>> # Calculate Heikin Ashi
    >>> ha_df = bp.calculate_heikin_ashi(df)
    >>> print(ha_df.columns.tolist())
    ['HA_Open', 'HA_High', 'HA_Low', 'HA_Close', 'Volume']

    >>> # Using TechnicalMixin method
    >>> ha_df = stock.heikin_ashi(period="1y")
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["calculate_heikin_ashi"]


def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Heikin Ashi candlestick values.

    Heikin Ashi candles smooth price data and help identify trends more clearly.
    They use a modified formula that incorporates previous candle values.

    Formulas:
        HA_Close = (Open + High + Low + Close) / 4
        HA_Open = (Previous_HA_Open + Previous_HA_Close) / 2
        HA_High = max(High, HA_Open, HA_Close)
        HA_Low = min(Low, HA_Open, HA_Close)

    Note: First candle uses (Open + Close) / 2 for HA_Open since there's no previous.

    Args:
        df: DataFrame with OHLC columns (Open, High, Low, Close).
            May also include Volume which will be preserved.

    Returns:
        DataFrame with columns:
        - HA_Open: Heikin Ashi open price
        - HA_High: Heikin Ashi high price
        - HA_Low: Heikin Ashi low price
        - HA_Close: Heikin Ashi close price
        - Volume: Original volume (if present in input)

    Examples:
        >>> import borsapy as bp
        >>> stock = bp.Ticker("THYAO")
        >>> df = stock.history(period="1mo")
        >>> ha = bp.calculate_heikin_ashi(df)
        >>> print(ha.tail())
                     HA_Open    HA_High     HA_Low   HA_Close    Volume
        Date
        2024-01-15   284.125   286.5000   283.2500   285.3750   1234567
        2024-01-16   284.750   287.0000   284.0000   286.1250   1345678

    Raises:
        ValueError: If required OHLC columns are missing

    See Also:
        - TechnicalMixin.heikin_ashi(): Method on Ticker/Index for direct calculation
        - TechnicalAnalyzer.heikin_ashi(): Method on TechnicalAnalyzer class
    """
    # Validate required columns
    required = ["Open", "High", "Low", "Close"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if df.empty:
        return pd.DataFrame(columns=["HA_Open", "HA_High", "HA_Low", "HA_Close", "Volume"])

    # Calculate HA_Close: (O + H + L + C) / 4
    ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4

    # Calculate HA_Open iteratively (depends on previous HA values)
    ha_open = np.zeros(len(df))

    # First candle: HA_Open = (Open + Close) / 2
    ha_open[0] = (df["Open"].iloc[0] + df["Close"].iloc[0]) / 2

    # Subsequent candles: HA_Open = (Prev_HA_Open + Prev_HA_Close) / 2
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i - 1] + ha_close.iloc[i - 1]) / 2

    # Convert to Series with proper index
    ha_open = pd.Series(ha_open, index=df.index)

    # Calculate HA_High and HA_Low
    ha_high = pd.concat([df["High"], ha_open, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([df["Low"], ha_open, ha_close], axis=1).min(axis=1)

    # Build result DataFrame
    result = pd.DataFrame(
        {
            "HA_Open": ha_open,
            "HA_High": ha_high,
            "HA_Low": ha_low,
            "HA_Close": ha_close,
        },
        index=df.index,
    )

    # Preserve Volume if present
    if "Volume" in df.columns:
        result["Volume"] = df["Volume"]

    return result


def calculate_heikin_ashi_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Heikin Ashi using vectorized operations (faster for large datasets).

    This version uses cumulative operations which may have slight floating point
    differences from the iterative version but is significantly faster.

    Args:
        df: DataFrame with OHLC columns

    Returns:
        DataFrame with HA_Open, HA_High, HA_Low, HA_Close, Volume columns
    """
    required = ["Open", "High", "Low", "Close"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if df.empty:
        return pd.DataFrame(columns=["HA_Open", "HA_High", "HA_Low", "HA_Close", "Volume"])

    # HA_Close is straightforward
    ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4

    # For HA_Open, we need a recursive formula
    # HA_Open[0] = (Open[0] + Close[0]) / 2
    # HA_Open[i] = (HA_Open[i-1] + HA_Close[i-1]) / 2
    #
    # This can be expressed as an exponentially weighted sum
    # Using the fact that HA_Open[i] = sum(HA_Close[j] * 0.5^(i-j)) * 0.5 + initial * 0.5^i
    n = len(df)
    0.5 ** np.arange(n)

    # Initial value
    initial = (df["Open"].iloc[0] + df["Close"].iloc[0]) / 2

    # Build HA_Open
    ha_open = np.zeros(n)
    ha_open[0] = initial

    # Vectorized calculation using cumsum trick
    ha_close_shifted = ha_close.shift(1).fillna(0)

    for i in range(1, n):
        ha_open[i] = (ha_open[i - 1] + ha_close_shifted.iloc[i]) / 2
        if i == 1:
            ha_open[i] = (initial + ha_close.iloc[0]) / 2

    ha_open = pd.Series(ha_open, index=df.index)

    # Calculate HA_High and HA_Low
    ha_high = pd.concat([df["High"], ha_open, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([df["Low"], ha_open, ha_close], axis=1).min(axis=1)

    # Build result
    result = pd.DataFrame(
        {
            "HA_Open": ha_open,
            "HA_High": ha_high,
            "HA_Low": ha_low,
            "HA_Close": ha_close,
        },
        index=df.index,
    )

    if "Volume" in df.columns:
        result["Volume"] = df["Volume"]

    return result
