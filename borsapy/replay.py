"""
Replay Mode for historical data backtesting.

This module provides generator-based replay of historical OHLCV data
for backtesting trading strategies.

Features:
- Memory efficient generator pattern
- Speed control (1x, 2x, 10x, 100x)
- Callback support for each candle
- Date filtering
- Progress tracking

Examples:
    >>> import borsapy as bp

    >>> # Basic replay
    >>> session = bp.create_replay("THYAO", period="6mo", speed=5.0)
    >>> for candle in session.replay():
    ...     print(f"{candle['timestamp']}: Close={candle['close']}")

    >>> # With callbacks
    >>> def on_candle(candle):
    ...     print(f"Progress: {candle['_index']}/{candle['_total']}")
    >>> session.on_candle(on_candle)
    >>> list(session.replay())  # Callbacks fire automatically

    >>> # Date filtering
    >>> for candle in session.replay_filtered(
    ...     start_date="2024-01-01",
    ...     end_date="2024-06-01"
    ... ):
    ...     pass
"""

from __future__ import annotations

import time
from collections.abc import Callable, Generator
from datetime import datetime
from typing import Any

import pandas as pd

__all__ = ["ReplaySession", "create_replay"]


class ReplaySession:
    """
    Replay historical market data for backtesting.

    Provides a generator-based interface for iterating over historical
    OHLCV candles with speed control and callback support.

    Attributes:
        symbol: The stock symbol being replayed.
        speed: Playback speed multiplier (1.0 = real-time).
        total_candles: Total number of candles in the dataset.

    Examples:
        Basic usage::

            session = ReplaySession("THYAO", df=historical_data, speed=10.0)
            for candle in session.replay():
                # Implement trading logic
                pass

        With callbacks::

            def my_callback(candle):
                print(f"Candle {candle['_index']}: {candle['close']}")

            session.on_candle(my_callback)
            list(session.replay())  # Callbacks fire for each candle
    """

    def __init__(
        self,
        symbol: str,
        df: pd.DataFrame | None = None,
        speed: float = 1.0,
        realtime_injection: bool = False,
    ):
        """
        Initialize ReplaySession.

        Args:
            symbol: Stock symbol (e.g., "THYAO")
            df: DataFrame with OHLCV data. Must have DatetimeIndex and
                columns: Open, High, Low, Close, Volume.
                If None, use create_replay() to load data automatically.
            speed: Playback speed multiplier.
                   1.0 = real-time (60s between daily candles)
                   2.0 = 2x speed (30s between daily candles)
                   100.0 = fast forward (0.6s between daily candles)
                   0.0 or negative = no delay (as fast as possible)
            realtime_injection: If True, candles are yielded at the
                               original time interval divided by speed.
                               If False, yields immediately with no delay.

        Raises:
            ValueError: If df is provided but missing required columns.
        """
        self.symbol = symbol.upper()
        self.speed = max(0.0, speed)
        self.realtime_injection = realtime_injection
        self._df: pd.DataFrame | None = df
        self._callbacks: list[Callable[[dict], None]] = []
        self._current_index = 0
        self._start_time: float | None = None

        # Validate DataFrame if provided
        if df is not None:
            self._validate_dataframe(df)

    def _validate_dataframe(self, df: pd.DataFrame) -> None:
        """Validate that DataFrame has required columns."""
        required = {"Open", "High", "Low", "Close"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")

    @property
    def total_candles(self) -> int:
        """Get total number of candles."""
        if self._df is None:
            return 0
        return len(self._df)

    @property
    def progress(self) -> float:
        """Get current replay progress (0.0 to 1.0)."""
        if self.total_candles == 0:
            return 0.0
        return self._current_index / self.total_candles

    def set_data(self, df: pd.DataFrame) -> None:
        """
        Set the DataFrame for replay.

        Args:
            df: DataFrame with OHLCV data.
        """
        self._validate_dataframe(df)
        self._df = df
        self._current_index = 0

    def on_candle(self, callback: Callable[[dict], None]) -> None:
        """
        Register callback for candle updates.

        Callback signature: callback(candle: dict)

        Args:
            callback: Function to call for each candle during replay.

        Example:
            >>> def my_handler(candle):
            ...     print(f"Price: {candle['close']}")
            >>> session.on_candle(my_handler)
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[dict], None]) -> None:
        """
        Remove a registered callback.

        Args:
            callback: The callback to remove.
        """
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    def _build_candle(self, idx: int) -> dict[str, Any]:
        """Build candle dict from DataFrame row."""
        if self._df is None:
            return {}

        row = self._df.iloc[idx]
        timestamp = self._df.index[idx]

        # Convert timestamp to datetime if needed
        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()

        candle = {
            "timestamp": timestamp,
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row.get("Volume", 0)) if "Volume" in row else 0,
            "_index": idx,
            "_total": len(self._df),
            "_progress": (idx + 1) / len(self._df),
        }

        return candle

    def _calculate_delay(self, current_idx: int) -> float:
        """Calculate delay between candles based on speed."""
        if not self.realtime_injection or self.speed <= 0:
            return 0.0

        if self._df is None or current_idx == 0:
            return 0.0

        # Calculate time difference between candles
        current_time = self._df.index[current_idx]
        prev_time = self._df.index[current_idx - 1]

        if isinstance(current_time, pd.Timestamp):
            current_time = current_time.to_pydatetime()
        if isinstance(prev_time, pd.Timestamp):
            prev_time = prev_time.to_pydatetime()

        time_diff = (current_time - prev_time).total_seconds()

        # Apply speed multiplier
        return time_diff / self.speed

    def replay(self) -> Generator[dict[str, Any], None, None]:
        """
        Generator that yields candles one by one.

        Yields candles from the dataset with optional time delay
        based on speed setting.

        Yields:
            Candle dict with keys:
            - timestamp: datetime of the candle
            - open: Open price
            - high: High price
            - low: Low price
            - close: Close price
            - volume: Trading volume
            - _index: Current candle index (0-based)
            - _total: Total number of candles
            - _progress: Progress ratio (0.0 to 1.0)

        Example:
            >>> for candle in session.replay():
            ...     print(f"{candle['timestamp']}: {candle['close']}")
        """
        if self._df is None or len(self._df) == 0:
            return

        self._current_index = 0
        self._start_time = time.time()

        for idx in range(len(self._df)):
            self._current_index = idx

            # Calculate and apply delay
            if idx > 0:
                delay = self._calculate_delay(idx)
                if delay > 0:
                    time.sleep(delay)

            # Build candle
            candle = self._build_candle(idx)

            # Fire callbacks
            for callback in self._callbacks:
                try:
                    callback(candle)
                except Exception:
                    pass  # Silently ignore callback errors

            yield candle

    def replay_filtered(
        self,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Generator that yields filtered candles.

        Filter candles by date range before replay.

        Args:
            start_date: Start date (inclusive). Can be string "YYYY-MM-DD"
                       or datetime object.
            end_date: End date (inclusive). Can be string "YYYY-MM-DD"
                     or datetime object.

        Yields:
            Filtered candle dicts (same format as replay()).

        Example:
            >>> for candle in session.replay_filtered(
            ...     start_date="2024-01-01",
            ...     end_date="2024-06-30"
            ... ):
            ...     # Process candle in date range
            ...     pass
        """
        if self._df is None or len(self._df) == 0:
            return

        # Parse dates
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)
        if isinstance(end_date, str):
            end_date = pd.to_datetime(end_date)

        # Filter DataFrame
        mask = pd.Series([True] * len(self._df), index=self._df.index)

        if start_date is not None:
            mask &= self._df.index >= start_date

        if end_date is not None:
            mask &= self._df.index <= end_date

        filtered_indices = self._df.index[mask]

        self._current_index = 0
        self._start_time = time.time()

        for i, idx in enumerate(filtered_indices):
            self._current_index = i

            # Get the position in original DataFrame
            original_idx = self._df.index.get_loc(idx)

            # Calculate and apply delay
            if i > 0:
                delay = self._calculate_delay(original_idx)
                if delay > 0:
                    time.sleep(delay)

            # Build candle
            candle = self._build_candle(original_idx)

            # Update filtered progress
            candle["_index"] = i
            candle["_total"] = len(filtered_indices)
            candle["_progress"] = (i + 1) / len(filtered_indices)

            # Fire callbacks
            for callback in self._callbacks:
                try:
                    callback(candle)
                except Exception:
                    pass

            yield candle

    def stats(self) -> dict[str, Any]:
        """
        Get replay statistics.

        Returns:
            Dict with statistics:
            - symbol: Stock symbol
            - total_candles: Total number of candles
            - current_index: Current position in replay
            - progress: Progress ratio (0.0 to 1.0)
            - speed: Playback speed multiplier
            - elapsed_time: Time elapsed since replay start (seconds)
            - start_date: First candle date
            - end_date: Last candle date

        Example:
            >>> print(session.stats())
            {'symbol': 'THYAO', 'total_candles': 252, ...}
        """
        stats = {
            "symbol": self.symbol,
            "total_candles": self.total_candles,
            "current_index": self._current_index,
            "progress": self.progress,
            "speed": self.speed,
            "realtime_injection": self.realtime_injection,
            "elapsed_time": (
                time.time() - self._start_time if self._start_time else 0.0
            ),
            "start_date": None,
            "end_date": None,
            "callbacks_registered": len(self._callbacks),
        }

        if self._df is not None and len(self._df) > 0:
            stats["start_date"] = self._df.index[0]
            stats["end_date"] = self._df.index[-1]

            if isinstance(stats["start_date"], pd.Timestamp):
                stats["start_date"] = stats["start_date"].to_pydatetime()
            if isinstance(stats["end_date"], pd.Timestamp):
                stats["end_date"] = stats["end_date"].to_pydatetime()

        return stats

    def reset(self) -> None:
        """Reset replay to beginning."""
        self._current_index = 0
        self._start_time = None


def create_replay(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
    speed: float = 1.0,
    realtime_injection: bool = False,
) -> ReplaySession:
    """
    Create a ReplaySession with historical data loaded automatically.

    Convenience function that loads historical data from TradingView
    and creates a ReplaySession.

    Args:
        symbol: Stock symbol (e.g., "THYAO", "GARAN")
        period: Historical period to load.
                Valid values: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max
        interval: Candle interval.
                  Valid values: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1wk, 1mo
        speed: Playback speed multiplier.
               1.0 = real-time
               10.0 = 10x speed
               0.0 = no delay (as fast as possible)
        realtime_injection: If True, delays between candles are based
                           on actual time intervals.

    Returns:
        ReplaySession with loaded data.

    Raises:
        ValueError: If symbol not found or no data available.

    Example:
        >>> session = bp.create_replay("THYAO", period="1y", speed=100)
        >>> for candle in session.replay():
        ...     print(candle['close'])
    """
    # Import here to avoid circular import
    from borsapy.ticker import Ticker

    # Load historical data
    ticker = Ticker(symbol)
    df = ticker.history(period=period, interval=interval)

    if df is None or len(df) == 0:
        raise ValueError(f"No historical data available for {symbol}")

    # Create session with loaded data
    session = ReplaySession(
        symbol=symbol,
        df=df,
        speed=speed,
        realtime_injection=realtime_injection,
    )

    return session
