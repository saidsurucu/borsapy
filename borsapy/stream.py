"""
TradingView Persistent WebSocket Streaming for real-time data.

This module provides a persistent WebSocket connection to TradingView
for low-latency, high-throughput market data streaming.

Performance targets:
- Connection time: <2s
- First quote: <500ms
- Cached quote: <1ms
- Update latency: <100ms

Based on: https://github.com/Mathieu2301/TradingView-API

Examples:
    >>> import borsapy as bp
    >>> stream = bp.TradingViewStream()
    >>> stream.connect()
    >>> stream.subscribe("THYAO")
    >>> quote = stream.get_quote("THYAO")
    >>> print(quote['last'])
    299.0
    >>> stream.disconnect()

    # Context manager usage
    >>> with bp.TradingViewStream() as stream:
    ...     stream.subscribe("THYAO")
    ...     while True:
    ...         quote = stream.get_quote("THYAO")
    ...         # Trading logic...

    # Pine Script indicators (streaming)
    >>> stream = bp.TradingViewStream()
    >>> stream.connect()
    >>> stream.subscribe_chart("THYAO", "1m")
    >>> stream.add_study("THYAO", "1m", "RSI")
    >>> stream.add_study("THYAO", "1m", "MACD")
    >>> rsi = stream.get_study("THYAO", "1m", "RSI")
    >>> print(rsi['value'])
    48.5
"""

from __future__ import annotations

import json
import logging
import random
import re
import string
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import websocket

from borsapy._providers.tradingview import get_tradingview_auth

logger = logging.getLogger(__name__)


# Quote fields to request from TradingView (46 fields)
QUOTE_FIELDS = [
    # Price data
    "lp",  # Last price
    "ch",  # Change
    "chp",  # Change percent
    "bid",  # Bid price
    "ask",  # Ask price
    "bid_size",  # Bid size
    "ask_size",  # Ask size
    "volume",  # Volume
    # OHLC
    "open_price",
    "high_price",
    "low_price",
    "prev_close_price",
    # Fundamentals
    "market_cap_basic",
    "price_earnings_ttm",
    "earnings_per_share_basic_ttm",
    "dividends_yield",
    "beta_1_year",
    # 52 week
    "high_52_week",
    "low_52_week",
    # Meta
    "description",
    "type",
    "exchange",
    "currency_code",
    "lp_time",
    "current_session",
    "status",
    "original_name",
    "short_name",
    # Additional
    "open_time",
    "close_time",
    "timezone",
    "regular_market_price",
    "regular_market_change",
    "regular_market_change_percent",
    "pre_market_price",
    "pre_market_change",
    "after_hours_price",
    "after_hours_change",
    "pricescale",
    "minmov",
    "minmove2",
    "fractional",
    "value_unit_id",
]


# Chart timeframe mapping (user-friendly -> TradingView format)
CHART_TIMEFRAMES = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "2h": "120",
    "4h": "240",
    "1d": "1D",
    "1wk": "1W",
    "1w": "1W",
    "1mo": "1M",
    "1M": "1M",
}


@dataclass
class PineStudy:
    """
    Pine Script study (indicator) configuration.

    Represents a TradingView indicator study attached to a chart session.

    Attributes:
        indicator_id: Full TradingView indicator ID (e.g., "STD;RSI")
        study_id: Unique study identifier within the session (e.g., "st1")
        symbol: Stock symbol (e.g., "THYAO")
        interval: Chart interval (e.g., "1m", "1d")
        inputs: User-provided input parameters
        metadata: Indicator metadata from Pine Facade API
        values: Latest computed indicator values
        ready: Whether the study has received initial data

    Examples:
        >>> study = PineStudy(
        ...     indicator_id="STD;RSI",
        ...     study_id="st1",
        ...     symbol="THYAO",
        ...     interval="1m",
        ...     inputs={"length": 14},
        ... )
    """

    indicator_id: str
    study_id: str
    symbol: str
    interval: str
    inputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)
    ready: bool = False


class StudySession:
    """
    Manages Pine Script studies (indicators) on a TradingViewStream.

    This class handles the lifecycle of TradingView indicator studies,
    including creation, data updates, and removal.

    Standard indicators (STD;*) don't require authentication.
    Custom indicators (PUB;*, USER;*) require TradingView auth.

    Supported standard indicators:
    - RSI: Relative Strength Index
    - MACD: Moving Average Convergence Divergence
    - BB (Bollinger): Bollinger Bands
    - EMA, SMA: Moving Averages
    - Stochastic: Stochastic Oscillator
    - ATR: Average True Range
    - ADX: Average Directional Index
    - OBV: On-Balance Volume
    - VWAP: Volume Weighted Average Price

    Examples:
        >>> stream = bp.TradingViewStream()
        >>> stream.connect()
        >>> stream.subscribe_chart("THYAO", "1m")
        >>> stream.add_study("THYAO", "1m", "RSI")
        >>> stream.add_study("THYAO", "1m", "MACD")
        >>> # Wait for data...
        >>> rsi = stream.get_study("THYAO", "1m", "RSI")
        >>> print(rsi['value'])
        48.5
    """

    def __init__(self, stream: TradingViewStream):
        """
        Initialize StudySession.

        Args:
            stream: Parent TradingViewStream instance
        """
        self._stream = stream
        # Storage: {symbol: {interval: {indicator_name: PineStudy}}}
        self._studies: dict[str, dict[str, dict[str, PineStudy]]] = {}
        self._study_counter = 0
        self._lock = threading.RLock()

        # Callbacks: {"symbol:interval:indicator": [callbacks]}
        self._callbacks: dict[str, list[Callable[[str, str, str, dict], None]]] = {}
        self._global_callbacks: list[Callable[[str, str, str, dict], None]] = []

        # Events for synchronization
        self._study_events: dict[str, threading.Event] = {}

        # Study ID to (symbol, interval, indicator) mapping
        self._study_id_map: dict[str, tuple[str, str, str]] = {}

        # Lazy-load pine facade provider
        self._pine_facade = None

    def _get_pine_facade(self):
        """Get Pine Facade provider (lazy-loaded)."""
        if self._pine_facade is None:
            from borsapy._providers.pine_facade import get_pine_facade_provider
            self._pine_facade = get_pine_facade_provider()
        return self._pine_facade

    def _normalize_indicator(self, indicator: str) -> tuple[str, str]:
        """
        Normalize indicator name to (display_name, indicator_id).

        Args:
            indicator: User-provided indicator name

        Returns:
            Tuple of (display_name, full_indicator_id)
        """
        from borsapy._providers.pine_facade import STANDARD_INDICATORS

        upper = indicator.upper()

        # Check if it's a standard indicator short name
        if upper in STANDARD_INDICATORS:
            return (upper, STANDARD_INDICATORS[upper])

        # Already full ID format
        if ";" in indicator:
            # Extract display name from ID
            parts = indicator.split(";")
            display = parts[1] if len(parts) > 1 else indicator
            return (display.upper(), indicator)

        # Assume it's a standard indicator
        return (upper, f"STD;{indicator}")

    def add(
        self,
        symbol: str,
        interval: str,
        indicator: str,
        **kwargs: Any,
    ) -> str:
        """
        Add a Pine indicator study to the chart.

        Args:
            symbol: Stock symbol (e.g., "THYAO")
            interval: Chart interval (e.g., "1m", "1d")
            indicator: Indicator name or ID. Examples:
                       - "RSI", "MACD", "BB" (standard)
                       - "STD;RSI" (full standard ID)
                       - "PUB;abc123" (community indicator)
            **kwargs: Indicator-specific parameters (e.g., length=14)

        Returns:
            Unique study ID

        Raises:
            ValueError: If chart not subscribed for symbol/interval
            AuthenticationError: If custom indicator requires auth

        Example:
            >>> stream.add_study("THYAO", "1m", "RSI")
            >>> stream.add_study("THYAO", "1m", "RSI", length=7)
            >>> stream.add_study("THYAO", "1m", "MACD")
        """
        symbol = symbol.upper()
        interval = interval.lower()

        # Check if chart is subscribed
        if not self._stream._chart_subscribed.get(symbol, set()).intersection({interval}):
            raise ValueError(
                f"Chart not subscribed for {symbol} {interval}. "
                "Call stream.subscribe_chart() first."
            )

        # Normalize indicator
        display_name, indicator_id = self._normalize_indicator(indicator)

        with self._lock:
            # Initialize nested dicts
            if symbol not in self._studies:
                self._studies[symbol] = {}
            if interval not in self._studies[symbol]:
                self._studies[symbol][interval] = {}

            # Check if already exists
            if display_name in self._studies[symbol][interval]:
                existing = self._studies[symbol][interval][display_name]
                return existing.study_id

            # Generate unique study ID
            self._study_counter += 1
            study_id = f"st{self._study_counter}"

            # Fetch indicator metadata
            try:
                metadata = self._get_pine_facade().get_indicator(indicator_id)
            except Exception as e:
                logger.warning(f"Failed to fetch indicator metadata: {e}")
                metadata = {}

            # Create study
            study = PineStudy(
                indicator_id=indicator_id,
                study_id=study_id,
                symbol=symbol,
                interval=interval,
                inputs=kwargs,
                metadata=metadata,
            )

            self._studies[symbol][interval][display_name] = study
            self._study_id_map[study_id] = (symbol, interval, display_name)

            # Create event for waiting
            event_key = f"{symbol}:{interval}:{display_name}"
            self._study_events[event_key] = threading.Event()

        # Send create_study message
        self._send_create_study(study)

        return study_id

    def remove(self, symbol: str, interval: str, indicator: str) -> None:
        """
        Remove a study from the chart.

        Args:
            symbol: Stock symbol
            interval: Chart interval
            indicator: Indicator name

        Example:
            >>> stream.remove_study("THYAO", "1m", "RSI")
        """
        symbol = symbol.upper()
        interval = interval.lower()
        display_name, _ = self._normalize_indicator(indicator)

        with self._lock:
            if symbol not in self._studies:
                return
            if interval not in self._studies[symbol]:
                return
            if display_name not in self._studies[symbol][interval]:
                return

            study = self._studies[symbol][interval].pop(display_name)

            # Clean up mappings
            if study.study_id in self._study_id_map:
                del self._study_id_map[study.study_id]

            event_key = f"{symbol}:{interval}:{display_name}"
            self._study_events.pop(event_key, None)
            self._callbacks.pop(event_key, None)

            # Clean up empty dicts
            if not self._studies[symbol][interval]:
                del self._studies[symbol][interval]
            if not self._studies[symbol]:
                del self._studies[symbol]

        # Send remove_study message
        self._send_remove_study(study)

    def get(
        self, symbol: str, interval: str, indicator: str
    ) -> dict[str, Any] | None:
        """
        Get latest study values.

        Args:
            symbol: Stock symbol
            interval: Chart interval
            indicator: Indicator name

        Returns:
            Dict of indicator values or None if not found/no data.
            Format depends on indicator type:
            - RSI: {"value": 48.5}
            - MACD: {"macd": 3.2, "signal": 2.8, "histogram": 0.4}
            - BB: {"upper": 296.8, "middle": 285.0, "lower": 273.2}

        Example:
            >>> rsi = stream.get_study("THYAO", "1m", "RSI")
            >>> print(rsi['value'])
            48.5
        """
        symbol = symbol.upper()
        interval = interval.lower()
        display_name, _ = self._normalize_indicator(indicator)

        with self._lock:
            if symbol not in self._studies:
                return None
            if interval not in self._studies[symbol]:
                return None
            if display_name not in self._studies[symbol][interval]:
                return None

            study = self._studies[symbol][interval][display_name]
            if not study.values:
                return None
            return study.values.copy()

    def get_all(self, symbol: str, interval: str) -> dict[str, dict[str, Any]]:
        """
        Get all study values for a symbol/interval.

        Args:
            symbol: Stock symbol
            interval: Chart interval

        Returns:
            Dict mapping indicator name to values dict.

        Example:
            >>> studies = stream.get_studies("THYAO", "1m")
            >>> print(studies['RSI']['value'])
            48.5
            >>> print(studies['MACD']['macd'])
            3.2
        """
        symbol = symbol.upper()
        interval = interval.lower()

        result = {}
        with self._lock:
            if symbol not in self._studies:
                return result
            if interval not in self._studies[symbol]:
                return result

            for name, study in self._studies[symbol][interval].items():
                if study.values:
                    result[name] = study.values.copy()

        return result

    def wait_for(
        self, symbol: str, interval: str, indicator: str, timeout: float = 10.0
    ) -> dict[str, Any]:
        """
        Wait for study data (blocking).

        Args:
            symbol: Stock symbol
            interval: Chart interval
            indicator: Indicator name
            timeout: Maximum wait time in seconds

        Returns:
            Study values dict

        Raises:
            TimeoutError: If data not received within timeout

        Example:
            >>> stream.add_study("THYAO", "1m", "RSI")
            >>> rsi = stream.studies.wait_for("THYAO", "1m", "RSI")
        """
        symbol = symbol.upper()
        interval = interval.lower()
        display_name, _ = self._normalize_indicator(indicator)

        # Check if already have data
        values = self.get(symbol, interval, indicator)
        if values:
            return values

        # Wait for data
        event_key = f"{symbol}:{interval}:{display_name}"
        with self._lock:
            if event_key not in self._study_events:
                self._study_events[event_key] = threading.Event()
            event = self._study_events[event_key]
            event.clear()

        if not event.wait(timeout=timeout):
            raise TimeoutError(
                f"Timeout waiting for study: {symbol} {interval} {indicator}"
            )

        values = self.get(symbol, interval, indicator)
        if values is None:
            raise TimeoutError(
                f"No study data received for {symbol} {interval} {indicator}"
            )
        return values

    def on_update(
        self,
        symbol: str,
        interval: str,
        indicator: str,
        callback: Callable[[str, str, str, dict], None],
    ) -> None:
        """
        Register callback for study updates.

        Callback signature: callback(symbol, interval, indicator, values)

        Args:
            symbol: Stock symbol
            interval: Chart interval
            indicator: Indicator name
            callback: Function to call on each update

        Example:
            >>> def on_rsi_update(symbol, interval, indicator, values):
            ...     print(f"{symbol} {indicator}: {values['value']}")
            >>> stream.studies.on_update("THYAO", "1m", "RSI", on_rsi_update)
        """
        symbol = symbol.upper()
        interval = interval.lower()
        display_name, _ = self._normalize_indicator(indicator)
        callback_key = f"{symbol}:{interval}:{display_name}"

        with self._lock:
            if callback_key not in self._callbacks:
                self._callbacks[callback_key] = []
            self._callbacks[callback_key].append(callback)

    def on_any_update(
        self, callback: Callable[[str, str, str, dict], None]
    ) -> None:
        """
        Register callback for any study update.

        Args:
            callback: Function to call on each update

        Example:
            >>> stream.studies.on_any_update(
            ...     lambda s, i, n, v: print(f"{s} {n}: {v}")
            ... )
        """
        self._global_callbacks.append(callback)

    def _send_create_study(self, study: PineStudy) -> None:
        """Send create_study WebSocket message."""
        # Build inputs for TradingView format
        tv_inputs = self._build_tv_inputs(study)

        # The study references the chart series
        # Format: create_study(session_id, study_id, "st1", "$prices", script_type, inputs)
        message = self._stream._create_message(
            "create_study",
            [
                self._stream._chart_session,
                study.study_id,
                "st1",
                "$prices",  # Data source (chart series)
                "Script@tv-scripting-101!",
                tv_inputs,
            ],
        )
        self._stream._send(message)

    def _send_remove_study(self, study: PineStudy) -> None:
        """Send remove_study WebSocket message."""
        message = self._stream._create_message(
            "remove_study",
            [self._stream._chart_session, study.study_id],
        )
        self._stream._send(message)

    def _build_tv_inputs(self, study: PineStudy) -> dict[str, Any]:
        """
        Build TradingView-format inputs for create_study.

        Converts user inputs to TradingView's expected format.
        """
        inputs = {
            "pineId": study.indicator_id,
            "pineVersion": "last",
        }

        # Get default inputs from metadata
        defaults = study.metadata.get("defaults", {})

        # Merge user inputs with defaults
        merged = {**defaults, **study.inputs}

        # Convert to TradingView format
        i = 0
        for _key, value in merged.items():
            # Determine type
            if isinstance(value, bool):
                tv_type = "boolean"
            elif isinstance(value, int):
                tv_type = "integer"
            elif isinstance(value, float):
                tv_type = "float"
            else:
                tv_type = "string"
                value = str(value)

            inputs[f"in_{i}"] = {
                "v": value,
                "f": True,
                "t": tv_type,
            }
            i += 1

        return inputs

    def handle_study_data(self, study_id: str, data: dict[str, Any]) -> None:
        """
        Handle incoming study data update.

        Called by TradingViewStream when study data is received.

        Args:
            study_id: Study identifier
            data: Raw study data from WebSocket
        """
        with self._lock:
            if study_id not in self._study_id_map:
                return

            symbol, interval, indicator = self._study_id_map[study_id]

            if symbol not in self._studies:
                return
            if interval not in self._studies[symbol]:
                return
            if indicator not in self._studies[symbol][interval]:
                return

            study = self._studies[symbol][interval][indicator]

            # Parse study values
            values = self._parse_study_values(study, data)
            if values:
                study.values = values
                study.ready = True

        # Fire callbacks
        if values:
            callback_key = f"{symbol}:{interval}:{indicator}"

            # Specific callbacks
            for callback in self._callbacks.get(callback_key, []):
                try:
                    callback(symbol, interval, indicator, values)
                except Exception as e:
                    logger.error(f"Study callback error: {e}")

            # Global callbacks
            for callback in self._global_callbacks:
                try:
                    callback(symbol, interval, indicator, values)
                except Exception as e:
                    logger.error(f"Global study callback error: {e}")

            # Signal waiting threads
            if callback_key in self._study_events:
                self._study_events[callback_key].set()

    def _parse_study_values(
        self, study: PineStudy, data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Parse raw study data into user-friendly values dict.

        Args:
            study: The PineStudy instance
            data: Raw data from WebSocket

        Returns:
            Parsed values dict
        """
        from borsapy._providers.pine_facade import INDICATOR_OUTPUTS

        values = {}

        # Get output mapping
        output_mapping = INDICATOR_OUTPUTS.get(study.indicator_id, {})

        # Extract values from data
        # Data format: {"st": [{"i": index, "v": [timestamp, val1, val2, ...]}]}
        st_data = data.get("st", data.get("s", []))
        if isinstance(st_data, list) and st_data:
            # Get latest data point
            latest = st_data[-1] if st_data else {}
            v = latest.get("v", [])

            if len(v) >= 2:
                # First value is timestamp, rest are plot values
                if output_mapping:
                    for plot_id, name in output_mapping.items():
                        # Extract plot index from plot_id (e.g., "plot_0" -> 0)
                        try:
                            idx = int(plot_id.split("_")[1]) + 1  # +1 for timestamp
                            if idx < len(v):
                                values[name] = v[idx]
                        except (ValueError, IndexError):
                            pass
                else:
                    # No mapping, just use first value
                    values["value"] = v[1] if len(v) > 1 else None

        return values

    def handle_study_loading(self, study_id: str) -> None:
        """Handle study_loading message."""
        logger.debug(f"Study loading: {study_id}")

    def handle_study_completed(self, study_id: str) -> None:
        """Handle study_completed message."""
        logger.debug(f"Study completed: {study_id}")

        # Mark study as ready
        with self._lock:
            if study_id in self._study_id_map:
                symbol, interval, indicator = self._study_id_map[study_id]
                if (
                    symbol in self._studies
                    and interval in self._studies[symbol]
                    and indicator in self._studies[symbol][interval]
                ):
                    self._studies[symbol][interval][indicator].ready = True

    def handle_study_error(self, study_id: str, error: str) -> None:
        """Handle study_error message."""
        logger.warning(f"Study error for {study_id}: {error}")


class TradingViewStream:
    """
    Persistent WebSocket connection for real-time TradingView data.

    Optimized for:
    - Low latency (~50-100ms)
    - High throughput (10-20 updates/sec)
    - Multiple symbol subscriptions
    - Automatic reconnection

    Attributes:
        is_connected: Whether the WebSocket is currently connected.
        subscribed_symbols: Set of currently subscribed symbols.

    Examples:
        Basic usage::

            stream = TradingViewStream()
            stream.connect()
            stream.subscribe("THYAO")
            quote = stream.get_quote("THYAO")

        With callbacks::

            def on_price_update(symbol, quote):
                print(f"{symbol}: {quote['last']}")

            stream.on_quote("THYAO", on_price_update)

        Context manager::

            with TradingViewStream() as stream:
                stream.subscribe("THYAO")
                # Trading logic...
    """

    WS_URL = "wss://data.tradingview.com/socket.io/websocket"
    ORIGIN = "https://www.tradingview.com"

    # Reconnection settings
    MAX_RECONNECT_ATTEMPTS = 10
    MAX_RECONNECT_DELAY = 30  # seconds
    HEARTBEAT_INTERVAL = 30  # seconds

    def __init__(self, auth_token: str | None = None):
        """
        Initialize TradingViewStream.

        Args:
            auth_token: Optional TradingView auth token for real-time data.
                        If not provided, uses unauthorized token (~15min delay).
        """
        self._ws: websocket.WebSocketApp | None = None
        self._ws_thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None

        # Connection state
        self._connected = threading.Event()
        self._should_reconnect = True
        self._reconnect_attempts = 0
        self._last_heartbeat_time = 0.0
        self._heartbeat_counter = 0

        # Session management
        self._quote_session: str | None = None
        self._chart_session: str | None = None
        self._auth_token = auth_token

        # Data storage (thread-safe)
        self._lock = threading.RLock()
        self._quotes: dict[str, dict[str, Any]] = {}  # symbol -> latest quote
        self._subscribed: set[str] = set()  # subscribed symbols
        self._pending_subscribes: set[str] = set()  # waiting for confirmation

        # Chart session data
        # Format: {symbol: {interval: [candles]}}
        self._chart_data: dict[str, dict[str, list[dict]]] = {}
        self._chart_subscribed: dict[str, set[str]] = {}  # symbol -> set of intervals
        self._chart_series_counter = 0  # Counter for unique series IDs
        self._chart_series_map: dict[str, tuple[str, str]] = {}  # series_id -> (symbol, interval)

        # Callbacks
        self._callbacks: dict[str, list[Callable[[str, dict], None]]] = {}
        self._global_callbacks: list[Callable[[str, dict], None]] = []
        # Chart callbacks: {f"{symbol}:{interval}": [callbacks]}
        self._chart_callbacks: dict[str, list[Callable[[str, str, dict], None]]] = {}
        self._global_chart_callbacks: list[Callable[[str, str, dict], None]] = []

        # Events for synchronization
        self._quote_events: dict[str, threading.Event] = {}
        self._chart_events: dict[str, threading.Event] = {}  # f"{symbol}:{interval}" -> Event

        # Pine Script studies session (lazy-loaded)
        self._study_session: StudySession | None = None

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected.is_set()

    @property
    def subscribed_symbols(self) -> set[str]:
        """Get set of currently subscribed symbols."""
        with self._lock:
            return self._subscribed.copy()

    def _get_auth_token(self) -> str:
        """Get auth token from credentials or use unauthorized."""
        if self._auth_token:
            return self._auth_token
        creds = get_tradingview_auth()
        if creds and creds.get("auth_token"):
            return creds["auth_token"]
        return "unauthorized_user_token"

    def _generate_session_id(self, prefix: str = "qs") -> str:
        """Generate random session ID like qs_abc123xyz."""
        chars = string.ascii_lowercase + string.digits
        suffix = "".join(random.choice(chars) for _ in range(12))
        return f"{prefix}_{suffix}"

    def _format_packet(self, data: str | dict) -> str:
        """Format data into TradingView packet format: ~m~{length}~m~{data}"""
        content = (
            json.dumps(data, separators=(",", ":"))
            if isinstance(data, dict)
            else data
        )
        return f"~m~{len(content)}~m~{content}"

    def _create_message(self, method: str, params: list) -> str:
        """Create a TradingView message."""
        msg = json.dumps({"m": method, "p": params}, separators=(",", ":"))
        return self._format_packet(msg)

    def _parse_packets(self, raw: str) -> list[dict | str]:
        """
        Parse TradingView packets from raw WebSocket message.

        Handles both JSON packets and heartbeat packets (~h~{number}).
        """
        packets: list[dict | str] = []

        # Find all packets using regex
        # Pattern: ~m~{length}~m~{content} or ~h~{number}
        pattern = r"~m~(\d+)~m~|~h~(\d+)"

        for match in re.finditer(pattern, raw):
            if match.group(2):  # Heartbeat
                packets.append(f"~h~{match.group(2)}")
            elif match.group(1):  # Data packet
                length = int(match.group(1))
                start = match.end()
                content = raw[start : start + length]
                try:
                    packets.append(json.loads(content))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse packet: {content[:100]}")

        return packets

    def _send(self, message: str) -> bool:
        """Send message to WebSocket (thread-safe)."""
        if self._ws and self.is_connected:
            try:
                self._ws.send(message)
                return True
            except Exception as e:
                logger.error(f"Send error: {e}")
                return False
        return False

    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        """Handle WebSocket connection opened."""
        logger.info("WebSocket connected")

        # Reset reconnection counter
        self._reconnect_attempts = 0

        # Generate new sessions
        self._quote_session = self._generate_session_id("qs")
        self._chart_session = self._generate_session_id("cs")

        # 1. Set auth token
        auth_token = self._get_auth_token()
        ws.send(self._create_message("set_auth_token", [auth_token]))

        # 2. Create quote session
        ws.send(self._create_message("quote_create_session", [self._quote_session]))

        # 3. Set quote fields
        ws.send(
            self._create_message("quote_set_fields", [self._quote_session, *QUOTE_FIELDS])
        )

        # 4. Create chart session
        ws.send(self._create_message("chart_create_session", [self._chart_session]))

        # Mark as connected
        self._connected.set()

        # Re-subscribe to existing symbols (for reconnection)
        with self._lock:
            for symbol in self._subscribed:
                self._send_subscribe(symbol)

            # Re-subscribe to chart data
            for symbol, intervals in self._chart_subscribed.items():
                for interval in intervals:
                    self._send_chart_subscribe(symbol, interval)

    def _on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        """Handle incoming WebSocket message."""
        packets = self._parse_packets(message)

        for packet in packets:
            # Handle heartbeat
            if isinstance(packet, str) and packet.startswith("~h~"):
                self._handle_heartbeat(packet)
                continue

            if not isinstance(packet, dict):
                continue

            method = packet.get("m")
            params = packet.get("p", [])

            if method == "qsd":
                # Quote data update
                self._handle_quote_data(params)

            elif method == "quote_completed":
                # Initial quote load complete
                if len(params) >= 2:
                    symbol = params[1]
                    logger.debug(f"Quote completed for {symbol}")
                    # Signal waiting threads
                    if symbol in self._quote_events:
                        self._quote_events[symbol].set()

            elif method == "critical_error":
                logger.error(f"TradingView critical error: {params}")

            elif method == "symbol_error":
                logger.warning(f"Symbol error: {params}")

            # Chart session messages
            elif method == "symbol_resolved":
                # Symbol successfully resolved for chart
                self._handle_symbol_resolved(params)

            elif method in ("timescale_update", "du"):
                # OHLCV data update
                self._handle_chart_data(params)

            elif method == "series_error":
                logger.warning(f"Chart series error: {params}")

            elif method == "series_completed":
                # Chart series load complete
                if len(params) >= 2:
                    session_id = params[0]
                    logger.debug(f"Series completed for session {session_id}")

            # Pine Script study messages
            elif method == "study_loading":
                # Study is loading
                if len(params) >= 2:
                    study_id = params[1]
                    if self._study_session:
                        self._study_session.handle_study_loading(study_id)

            elif method == "study_completed":
                # Study finished loading
                if len(params) >= 2:
                    study_id = params[1]
                    if self._study_session:
                        self._study_session.handle_study_completed(study_id)

            elif method == "study_error":
                # Study error
                if len(params) >= 3:
                    study_id = params[1]
                    error = params[2] if len(params) > 2 else "Unknown error"
                    if self._study_session:
                        self._study_session.handle_study_error(study_id, str(error))

    def _handle_heartbeat(self, packet: str) -> None:
        """Handle heartbeat packet by echoing it back."""
        self._last_heartbeat_time = time.time()
        # Echo heartbeat back to server
        self._send(self._format_packet(packet))
        logger.debug(f"Heartbeat: {packet}")

    def _handle_quote_data(self, params: list) -> None:
        """Handle quote data (qsd) packet."""
        if len(params) < 2 or not isinstance(params[1], dict):
            return

        data = params[1]
        symbol = data.get("n", "")  # Full symbol like "BIST:THYAO"
        status = data.get("s")  # "ok" or "error"
        values = data.get("v", {})

        if status != "ok" or not values:
            if status == "error":
                logger.warning(f"Quote error for {symbol}: {data}")
            return

        # Extract base symbol (remove exchange prefix)
        base_symbol = symbol.split(":")[-1] if ":" in symbol else symbol

        # Update quote cache
        with self._lock:
            if base_symbol not in self._quotes:
                self._quotes[base_symbol] = {}
            self._quotes[base_symbol].update(values)
            self._quotes[base_symbol]["_symbol"] = base_symbol
            self._quotes[base_symbol]["_full_symbol"] = symbol
            self._quotes[base_symbol]["_updated"] = time.time()

        # Fire callbacks
        quote = self._build_quote(base_symbol)

        # Symbol-specific callbacks
        for callback in self._callbacks.get(base_symbol, []):
            try:
                callback(base_symbol, quote)
            except Exception as e:
                logger.error(f"Callback error for {base_symbol}: {e}")

        # Global callbacks
        for callback in self._global_callbacks:
            try:
                callback(base_symbol, quote)
            except Exception as e:
                logger.error(f"Global callback error: {e}")

        # Signal waiting threads
        if base_symbol in self._quote_events:
            self._quote_events[base_symbol].set()

    def _build_quote(self, symbol: str) -> dict[str, Any]:
        """Build standardized quote dict from raw data."""
        with self._lock:
            raw = self._quotes.get(symbol, {})

        return {
            "symbol": symbol,
            "exchange": raw.get("exchange", "BIST"),
            "last": raw.get("lp"),
            "change": raw.get("ch"),
            "change_percent": raw.get("chp"),
            "open": raw.get("open_price"),
            "high": raw.get("high_price"),
            "low": raw.get("low_price"),
            "prev_close": raw.get("prev_close_price"),
            "volume": raw.get("volume"),
            "bid": raw.get("bid"),
            "ask": raw.get("ask"),
            "bid_size": raw.get("bid_size"),
            "ask_size": raw.get("ask_size"),
            "timestamp": raw.get("lp_time"),
            "description": raw.get("description"),
            "currency": raw.get("currency_code"),
            # Fundamentals
            "market_cap": raw.get("market_cap_basic"),
            "pe_ratio": raw.get("price_earnings_ttm"),
            "eps": raw.get("earnings_per_share_basic_ttm"),
            "dividend_yield": raw.get("dividends_yield"),
            "beta": raw.get("beta_1_year"),
            # 52 week
            "high_52_week": raw.get("high_52_week"),
            "low_52_week": raw.get("low_52_week"),
            # Meta
            "_updated": raw.get("_updated"),
            "_raw": raw,
        }

    def _handle_symbol_resolved(self, params: list) -> None:
        """Handle symbol_resolved message for chart session."""
        if len(params) < 2:
            return
        # params[0] = session_id, params[1] = symbol_info dict
        logger.debug(f"Symbol resolved: {params}")

    def _handle_chart_data(self, params: list) -> None:
        """Handle timescale_update or du (data update) messages."""
        if len(params) < 2:
            return

        session_id = params[0]
        data = params[1]

        if not isinstance(data, dict):
            return

        # Process each series in the response
        for series_key, series_data in data.items():
            # Handle Pine Script study data (keys like "st1", "st2", etc.)
            if series_key.startswith("st") and self._study_session:
                self._study_session.handle_study_data(series_key, series_data)
                continue

            if not series_key.startswith("$prices") and series_key != "s":
                # Look up the series mapping
                if series_key not in self._chart_series_map:
                    continue

            # Get symbol and interval from series map or use default
            symbol = None
            interval = None

            # Try to find series info
            for key, (sym, intv) in self._chart_series_map.items():
                if key in str(session_id) or series_key == "$prices":
                    symbol = sym
                    interval = intv
                    break

            if not symbol or not interval:
                # Try to extract from the first available mapping
                if self._chart_series_map:
                    first_key = next(iter(self._chart_series_map))
                    symbol, interval = self._chart_series_map[first_key]
                else:
                    continue

            # Extract candle data
            candles = []
            if isinstance(series_data, dict):
                bars = series_data.get("s", series_data.get("st", []))
                if isinstance(bars, list):
                    for bar in bars:
                        if isinstance(bar, dict) and "v" in bar:
                            v = bar["v"]
                            if len(v) >= 6:
                                candle = {
                                    "time": int(v[0]),
                                    "open": float(v[1]),
                                    "high": float(v[2]),
                                    "low": float(v[3]),
                                    "close": float(v[4]),
                                    "volume": float(v[5]) if v[5] else 0,
                                }
                                candles.append(candle)

            if candles:
                self._update_chart_data(symbol, interval, candles)

    def _update_chart_data(
        self, symbol: str, interval: str, candles: list[dict]
    ) -> None:
        """Update chart data cache and fire callbacks."""
        with self._lock:
            if symbol not in self._chart_data:
                self._chart_data[symbol] = {}
            if interval not in self._chart_data[symbol]:
                self._chart_data[symbol][interval] = []

            # Update or append candles
            existing = self._chart_data[symbol][interval]
            for candle in candles:
                # Check if we need to update the last candle or add new
                if existing and existing[-1]["time"] == candle["time"]:
                    existing[-1] = candle
                elif not existing or candle["time"] > existing[-1]["time"]:
                    existing.append(candle)

        # Fire callbacks
        callback_key = f"{symbol}:{interval}"
        latest_candle = candles[-1] if candles else None

        if latest_candle:
            # Symbol-specific callbacks
            for callback in self._chart_callbacks.get(callback_key, []):
                try:
                    callback(symbol, interval, latest_candle)
                except Exception as e:
                    logger.error(f"Chart callback error for {callback_key}: {e}")

            # Global chart callbacks
            for callback in self._global_chart_callbacks:
                try:
                    callback(symbol, interval, latest_candle)
                except Exception as e:
                    logger.error(f"Global chart callback error: {e}")

            # Signal waiting threads
            if callback_key in self._chart_events:
                self._chart_events[callback_key].set()

    def _send_chart_subscribe(self, symbol: str, interval: str, exchange: str = "BIST") -> None:
        """Send chart subscription messages."""
        tv_interval = CHART_TIMEFRAMES.get(interval, interval)
        tv_symbol = f"{exchange}:{symbol}"

        # Generate unique series ID
        self._chart_series_counter += 1
        series_id = f"ser_{self._chart_series_counter}"

        # Store mapping
        self._chart_series_map[series_id] = (symbol, interval)

        # 1. Resolve symbol with configuration
        symbol_config = json.dumps({
            "symbol": tv_symbol,
            "adjustment": "splits",
            "session": "regular",
        })
        self._send(
            self._create_message(
                "resolve_symbol",
                [self._chart_session, series_id, f"={symbol_config}"],
            )
        )

        # 2. Create series for OHLCV data
        self._send(
            self._create_message(
                "create_series",
                [
                    self._chart_session,
                    "$prices",  # Fixed price stream ID
                    "s1",  # Series index
                    series_id,  # Reference to resolved symbol
                    tv_interval,  # Timeframe
                    300,  # Number of bars
                ],
            )
        )

    def _send_chart_unsubscribe(self, symbol: str, interval: str) -> None:
        """Send chart unsubscription messages."""
        # Find and remove series
        series_to_remove = None
        for series_id, (sym, intv) in list(self._chart_series_map.items()):
            if sym == symbol and intv == interval:
                series_to_remove = series_id
                break

        if series_to_remove:
            self._send(
                self._create_message(
                    "remove_series", [self._chart_session, "$prices"]
                )
            )
            del self._chart_series_map[series_to_remove]

    def _on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        """Handle WebSocket error."""
        logger.error(f"WebSocket error: {error}")

    def _on_close(
        self,
        ws: websocket.WebSocketApp,
        close_status: int | None,
        close_msg: str | None,
    ) -> None:
        """Handle WebSocket close."""
        logger.info(f"WebSocket closed: {close_status} - {close_msg}")
        self._connected.clear()

        # Attempt reconnection if needed
        if self._should_reconnect:
            self._reconnect()

    def _reconnect(self) -> None:
        """Reconnect with exponential backoff."""
        if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
            logger.error("Max reconnection attempts reached")
            return

        # Calculate delay with exponential backoff
        delay = min(self.MAX_RECONNECT_DELAY, 2 ** self._reconnect_attempts)
        logger.info(f"Reconnecting in {delay}s (attempt {self._reconnect_attempts + 1})")

        self._reconnect_attempts += 1
        time.sleep(delay)

        # Reconnect
        self._start_websocket()

    def _start_websocket(self) -> None:
        """Start WebSocket connection in background thread."""
        self._ws = websocket.WebSocketApp(
            f"{self.WS_URL}?type=chart",
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            header={"Origin": self.ORIGIN},
        )

        self._ws_thread = threading.Thread(
            target=self._ws.run_forever,
            kwargs={"ping_interval": 0},  # We handle heartbeat ourselves
            daemon=True,
        )
        self._ws_thread.start()

    def _send_subscribe(self, symbol: str, exchange: str = "BIST") -> None:
        """Send subscribe message for symbol."""
        tv_symbol = f"{exchange}:{symbol}"
        self._send(
            self._create_message(
                "quote_add_symbols", [self._quote_session, tv_symbol]
            )
        )

    def _send_unsubscribe(self, symbol: str, exchange: str = "BIST") -> None:
        """Send unsubscribe message for symbol."""
        tv_symbol = f"{exchange}:{symbol}"
        self._send(
            self._create_message(
                "quote_remove_symbols", [self._quote_session, tv_symbol]
            )
        )

    # Public API

    def connect(self, timeout: float = 10.0) -> bool:
        """
        Establish persistent WebSocket connection.

        Args:
            timeout: Maximum time to wait for connection in seconds.

        Returns:
            True if connected successfully, False otherwise.

        Raises:
            TimeoutError: If connection times out.

        Example:
            >>> stream = TradingViewStream()
            >>> stream.connect()
            >>> print(stream.is_connected)
            True
        """
        if self.is_connected:
            return True

        self._should_reconnect = True
        self._start_websocket()

        # Wait for connection
        if not self._connected.wait(timeout=timeout):
            raise TimeoutError(f"Connection timed out after {timeout}s")

        return True

    def disconnect(self) -> None:
        """
        Close WebSocket connection and cleanup.

        Example:
            >>> stream.disconnect()
            >>> print(stream.is_connected)
            False
        """
        self._should_reconnect = False
        self._connected.clear()

        if self._ws:
            self._ws.close()
            self._ws = None

        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=2)

        # Clear state
        with self._lock:
            # Quote state
            self._quotes.clear()
            self._subscribed.clear()
            self._callbacks.clear()
            self._global_callbacks.clear()
            self._quote_events.clear()

            # Chart state
            self._chart_data.clear()
            self._chart_subscribed.clear()
            self._chart_series_map.clear()
            self._chart_callbacks.clear()
            self._global_chart_callbacks.clear()
            self._chart_events.clear()

        logger.info("Disconnected")

    def subscribe(self, symbol: str, exchange: str = "BIST") -> None:
        """
        Subscribe to symbol updates.

        Args:
            symbol: Stock symbol (e.g., "THYAO", "GARAN")
            exchange: Exchange name (default: "BIST")

        Example:
            >>> stream.subscribe("THYAO")
            >>> stream.subscribe("GARAN")
        """
        symbol = symbol.upper()

        with self._lock:
            if symbol in self._subscribed:
                return
            self._subscribed.add(symbol)
            self._quote_events[symbol] = threading.Event()

        if self.is_connected:
            self._send_subscribe(symbol, exchange)

    def unsubscribe(self, symbol: str, exchange: str = "BIST") -> None:
        """
        Unsubscribe from symbol.

        Args:
            symbol: Stock symbol
            exchange: Exchange name

        Example:
            >>> stream.unsubscribe("THYAO")
        """
        symbol = symbol.upper()

        with self._lock:
            self._subscribed.discard(symbol)
            self._quotes.pop(symbol, None)
            self._callbacks.pop(symbol, None)
            self._quote_events.pop(symbol, None)

        if self.is_connected:
            self._send_unsubscribe(symbol, exchange)

    # Chart Session API

    def subscribe_chart(
        self, symbol: str, interval: str = "1m", exchange: str = "BIST"
    ) -> None:
        """
        Subscribe to OHLCV candle updates for a symbol.

        Args:
            symbol: Stock symbol (e.g., "THYAO", "GARAN")
            interval: Candle interval. Valid values:
                      1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1wk, 1mo
            exchange: Exchange name (default: "BIST")

        Example:
            >>> stream.subscribe_chart("THYAO", "1m")
            >>> stream.subscribe_chart("GARAN", "1h")
        """
        symbol = symbol.upper()
        interval = interval.lower()

        # Validate interval
        if interval not in CHART_TIMEFRAMES:
            raise ValueError(
                f"Invalid interval '{interval}'. "
                f"Valid intervals: {list(CHART_TIMEFRAMES.keys())}"
            )

        with self._lock:
            if symbol not in self._chart_subscribed:
                self._chart_subscribed[symbol] = set()

            if interval in self._chart_subscribed[symbol]:
                return  # Already subscribed

            self._chart_subscribed[symbol].add(interval)

            # Initialize data storage
            if symbol not in self._chart_data:
                self._chart_data[symbol] = {}
            if interval not in self._chart_data[symbol]:
                self._chart_data[symbol][interval] = []

            # Create event for this subscription
            event_key = f"{symbol}:{interval}"
            self._chart_events[event_key] = threading.Event()

        if self.is_connected:
            self._send_chart_subscribe(symbol, interval, exchange)

    def unsubscribe_chart(
        self, symbol: str, interval: str, exchange: str = "BIST"
    ) -> None:
        """
        Unsubscribe from chart updates.

        Args:
            symbol: Stock symbol
            interval: Candle interval
            exchange: Exchange name

        Example:
            >>> stream.unsubscribe_chart("THYAO", "1m")
        """
        symbol = symbol.upper()
        interval = interval.lower()

        with self._lock:
            if symbol in self._chart_subscribed:
                self._chart_subscribed[symbol].discard(interval)
                if not self._chart_subscribed[symbol]:
                    del self._chart_subscribed[symbol]

            if symbol in self._chart_data and interval in self._chart_data[symbol]:
                del self._chart_data[symbol][interval]
                if not self._chart_data[symbol]:
                    del self._chart_data[symbol]

            event_key = f"{symbol}:{interval}"
            self._chart_events.pop(event_key, None)
            self._chart_callbacks.pop(event_key, None)

        if self.is_connected:
            self._send_chart_unsubscribe(symbol, interval)

    def get_candle(self, symbol: str, interval: str) -> dict[str, Any] | None:
        """
        Get latest cached candle (instant, ~1ms).

        Args:
            symbol: Stock symbol
            interval: Candle interval

        Returns:
            Candle dict or None if not subscribed/no data yet.
            Candle format:
            {
                "time": 1737123456,      # Unix timestamp
                "open": 285.0,           # Open price
                "high": 286.5,           # High price
                "low": 284.0,            # Low price
                "close": 285.5,          # Close price
                "volume": 123456         # Volume
            }

        Example:
            >>> candle = stream.get_candle("THYAO", "1m")
            >>> print(candle['close'])
            285.5
        """
        symbol = symbol.upper()
        interval = interval.lower()

        with self._lock:
            if symbol not in self._chart_data:
                return None
            if interval not in self._chart_data[symbol]:
                return None
            candles = self._chart_data[symbol][interval]
            if not candles:
                return None
            return candles[-1].copy()

    def get_candles(
        self, symbol: str, interval: str, count: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Get cached candles.

        Args:
            symbol: Stock symbol
            interval: Candle interval
            count: Number of candles to return (None = all)

        Returns:
            List of candle dicts, oldest first.

        Example:
            >>> candles = stream.get_candles("THYAO", "1m", count=10)
            >>> print(len(candles))
            10
        """
        symbol = symbol.upper()
        interval = interval.lower()

        with self._lock:
            if symbol not in self._chart_data:
                return []
            if interval not in self._chart_data[symbol]:
                return []
            candles = self._chart_data[symbol][interval]
            if count:
                return [c.copy() for c in candles[-count:]]
            return [c.copy() for c in candles]

    def wait_for_candle(
        self, symbol: str, interval: str, timeout: float = 5.0
    ) -> dict[str, Any]:
        """
        Wait for first candle (blocking).

        Useful after subscribing to ensure data is received.

        Args:
            symbol: Stock symbol
            interval: Candle interval
            timeout: Maximum wait time in seconds

        Returns:
            Candle dict

        Raises:
            TimeoutError: If candle not received within timeout.

        Example:
            >>> stream.subscribe_chart("THYAO", "1m")
            >>> candle = stream.wait_for_candle("THYAO", "1m")
        """
        symbol = symbol.upper()
        interval = interval.lower()

        # Check if already have data
        candle = self.get_candle(symbol, interval)
        if candle:
            return candle

        # Wait for data
        event_key = f"{symbol}:{interval}"
        with self._lock:
            if event_key not in self._chart_events:
                self._chart_events[event_key] = threading.Event()
            event = self._chart_events[event_key]
            event.clear()

        if not event.wait(timeout=timeout):
            raise TimeoutError(f"Timeout waiting for candle: {symbol} {interval}")

        candle = self.get_candle(symbol, interval)
        if candle is None:
            raise TimeoutError(f"No candle data received for {symbol} {interval}")
        return candle

    def on_candle(
        self,
        symbol: str,
        interval: str,
        callback: Callable[[str, str, dict], None],
    ) -> None:
        """
        Register callback for candle updates.

        Callback signature: callback(symbol: str, interval: str, candle: dict)

        Args:
            symbol: Stock symbol
            interval: Candle interval
            callback: Function to call on each update

        Example:
            >>> def on_candle_update(symbol, interval, candle):
            ...     print(f"{symbol} {interval}: O={candle['open']} C={candle['close']}")
            >>> stream.on_candle("THYAO", "1m", on_candle_update)
        """
        symbol = symbol.upper()
        interval = interval.lower()
        callback_key = f"{symbol}:{interval}"

        with self._lock:
            if callback_key not in self._chart_callbacks:
                self._chart_callbacks[callback_key] = []
            self._chart_callbacks[callback_key].append(callback)

    def on_any_candle(
        self, callback: Callable[[str, str, dict], None]
    ) -> None:
        """
        Register callback for all candle updates.

        Args:
            callback: Function to call on each update for any subscription.

        Example:
            >>> def on_any_update(symbol, interval, candle):
            ...     print(f"{symbol} {interval}: {candle['close']}")
            >>> stream.on_any_candle(on_any_update)
        """
        self._global_chart_callbacks.append(callback)

    def remove_candle_callback(
        self,
        symbol: str,
        interval: str,
        callback: Callable[[str, str, dict], None],
    ) -> None:
        """
        Remove a registered candle callback.

        Args:
            symbol: Stock symbol
            interval: Candle interval
            callback: The callback to remove
        """
        symbol = symbol.upper()
        interval = interval.lower()
        callback_key = f"{symbol}:{interval}"

        with self._lock:
            if callback_key in self._chart_callbacks:
                try:
                    self._chart_callbacks[callback_key].remove(callback)
                except ValueError:
                    pass

    @property
    def chart_subscriptions(self) -> dict[str, set[str]]:
        """Get current chart subscriptions.

        Returns:
            Dict mapping symbol to set of subscribed intervals.
        """
        with self._lock:
            return {
                sym: intervals.copy()
                for sym, intervals in self._chart_subscribed.items()
            }

    def get_quote(self, symbol: str) -> dict[str, Any] | None:
        """
        Get latest cached quote (instant, ~1ms).

        Args:
            symbol: Stock symbol

        Returns:
            Quote dict or None if not subscribed/no data yet.

        Example:
            >>> quote = stream.get_quote("THYAO")
            >>> print(quote['last'])
            299.0
        """
        symbol = symbol.upper()
        with self._lock:
            if symbol not in self._quotes:
                return None
        return self._build_quote(symbol)

    def wait_for_quote(
        self, symbol: str, timeout: float = 5.0
    ) -> dict[str, Any]:
        """
        Wait for first quote (blocking).

        Useful after subscribing to ensure data is received.

        Args:
            symbol: Stock symbol
            timeout: Maximum wait time in seconds

        Returns:
            Quote dict

        Raises:
            TimeoutError: If quote not received within timeout.

        Example:
            >>> stream.subscribe("THYAO")
            >>> quote = stream.wait_for_quote("THYAO")
        """
        symbol = symbol.upper()

        # Check if already have data
        quote = self.get_quote(symbol)
        if quote and quote.get("last") is not None:
            return quote

        # Wait for data
        with self._lock:
            if symbol not in self._quote_events:
                self._quote_events[symbol] = threading.Event()
            event = self._quote_events[symbol]
            event.clear()

        if not event.wait(timeout=timeout):
            raise TimeoutError(f"Timeout waiting for quote: {symbol}")

        quote = self.get_quote(symbol)
        if quote is None:
            raise TimeoutError(f"No quote data received for {symbol}")
        return quote

    def on_quote(
        self, symbol: str, callback: Callable[[str, dict], None]
    ) -> None:
        """
        Register callback for quote updates.

        Callback signature: callback(symbol: str, quote: dict)

        Args:
            symbol: Stock symbol
            callback: Function to call on each update

        Example:
            >>> def on_price_update(symbol, quote):
            ...     print(f"{symbol}: {quote['last']}")
            >>> stream.on_quote("THYAO", on_price_update)
        """
        symbol = symbol.upper()
        with self._lock:
            if symbol not in self._callbacks:
                self._callbacks[symbol] = []
            self._callbacks[symbol].append(callback)

    def on_any_quote(self, callback: Callable[[str, dict], None]) -> None:
        """
        Register callback for all quote updates.

        Args:
            callback: Function to call on each update for any symbol.

        Example:
            >>> def on_any_update(symbol, quote):
            ...     print(f"{symbol}: {quote['last']}")
            >>> stream.on_any_quote(on_any_update)
        """
        self._global_callbacks.append(callback)

    def remove_callback(
        self, symbol: str, callback: Callable[[str, dict], None]
    ) -> None:
        """
        Remove a registered callback.

        Args:
            symbol: Stock symbol
            callback: The callback to remove
        """
        symbol = symbol.upper()
        with self._lock:
            if symbol in self._callbacks:
                try:
                    self._callbacks[symbol].remove(callback)
                except ValueError:
                    pass

    def wait(self) -> None:
        """
        Block until disconnect.

        Useful for keeping the stream alive in main thread.

        Example:
            >>> stream.connect()
            >>> stream.subscribe("THYAO")
            >>> stream.on_quote("THYAO", my_callback)
            >>> stream.wait()  # Blocks forever
        """
        if self._ws_thread:
            self._ws_thread.join()

    # Context manager

    def __enter__(self) -> TradingViewStream:
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()

    # Pine Script Study API

    @property
    def studies(self) -> StudySession:
        """
        Access Pine Script study session.

        Returns:
            StudySession instance for managing indicators.

        Example:
            >>> stream.studies.add("THYAO", "1m", "RSI")
            >>> stream.studies.get("THYAO", "1m", "RSI")
        """
        if self._study_session is None:
            self._study_session = StudySession(self)
        return self._study_session

    def add_study(
        self,
        symbol: str,
        interval: str,
        indicator: str,
        **kwargs: Any,
    ) -> str:
        """
        Add a Pine indicator study (convenience method).

        Args:
            symbol: Stock symbol (e.g., "THYAO")
            interval: Chart interval (e.g., "1m", "1d")
            indicator: Indicator name. Examples:
                       - "RSI", "MACD", "BB" (standard)
                       - "STD;RSI" (full standard ID)
                       - "PUB;abc123" (community indicator)
            **kwargs: Indicator-specific parameters (e.g., length=14)

        Returns:
            Study ID

        Example:
            >>> stream.add_study("THYAO", "1m", "RSI")
            >>> stream.add_study("THYAO", "1m", "MACD")
        """
        return self.studies.add(symbol, interval, indicator, **kwargs)

    def remove_study(self, symbol: str, interval: str, indicator: str) -> None:
        """
        Remove a Pine indicator study (convenience method).

        Args:
            symbol: Stock symbol
            interval: Chart interval
            indicator: Indicator name

        Example:
            >>> stream.remove_study("THYAO", "1m", "RSI")
        """
        self.studies.remove(symbol, interval, indicator)

    def get_study(
        self, symbol: str, interval: str, indicator: str
    ) -> dict[str, Any] | None:
        """
        Get latest study values (convenience method).

        Args:
            symbol: Stock symbol
            interval: Chart interval
            indicator: Indicator name

        Returns:
            Dict of indicator values or None.

        Example:
            >>> rsi = stream.get_study("THYAO", "1m", "RSI")
            >>> print(rsi['value'])
            48.5
        """
        return self.studies.get(symbol, interval, indicator)

    def get_studies(self, symbol: str, interval: str) -> dict[str, dict[str, Any]]:
        """
        Get all study values for a symbol/interval (convenience method).

        Args:
            symbol: Stock symbol
            interval: Chart interval

        Returns:
            Dict mapping indicator name to values.

        Example:
            >>> studies = stream.get_studies("THYAO", "1m")
            >>> print(studies['RSI']['value'])
            48.5
        """
        return self.studies.get_all(symbol, interval)

    def on_study(
        self,
        symbol: str,
        interval: str,
        indicator: str,
        callback: Callable[[str, str, str, dict], None],
    ) -> None:
        """
        Register callback for study updates (convenience method).

        Callback signature: callback(symbol, interval, indicator, values)

        Args:
            symbol: Stock symbol
            interval: Chart interval
            indicator: Indicator name
            callback: Function to call on each update

        Example:
            >>> def on_rsi(symbol, interval, indicator, values):
            ...     print(f"{symbol} RSI: {values['value']}")
            >>> stream.on_study("THYAO", "1m", "RSI", on_rsi)
        """
        self.studies.on_update(symbol, interval, indicator, callback)

    def on_any_study(
        self, callback: Callable[[str, str, str, dict], None]
    ) -> None:
        """
        Register callback for any study update (convenience method).

        Args:
            callback: Function to call on each update.

        Example:
            >>> stream.on_any_study(
            ...     lambda s, i, n, v: print(f"{s} {n}: {v}")
            ... )
        """
        self.studies.on_any_update(callback)

    def wait_for_study(
        self, symbol: str, interval: str, indicator: str, timeout: float = 10.0
    ) -> dict[str, Any]:
        """
        Wait for study data (blocking convenience method).

        Args:
            symbol: Stock symbol
            interval: Chart interval
            indicator: Indicator name
            timeout: Maximum wait time in seconds

        Returns:
            Study values dict

        Raises:
            TimeoutError: If data not received within timeout

        Example:
            >>> stream.add_study("THYAO", "1m", "RSI")
            >>> rsi = stream.wait_for_study("THYAO", "1m", "RSI")
        """
        return self.studies.wait_for(symbol, interval, indicator, timeout)

    # Utility methods

    def get_all_quotes(self) -> dict[str, dict[str, Any]]:
        """
        Get all cached quotes.

        Returns:
            Dict mapping symbol to quote dict.
        """
        with self._lock:
            return {sym: self._build_quote(sym) for sym in self._quotes}

    def ping(self) -> float:
        """
        Measure round-trip latency.

        Returns:
            Latency in milliseconds.
        """
        if not self.is_connected:
            return -1

        start = time.time()
        # Send a heartbeat-like ping
        self._send(self._format_packet(f"~h~{self._heartbeat_counter}"))
        self._heartbeat_counter += 1
        elapsed = (time.time() - start) * 1000
        return elapsed


# Convenience function
def create_stream(auth_token: str | None = None) -> TradingViewStream:
    """
    Create and return a TradingViewStream instance.

    Args:
        auth_token: Optional auth token for real-time data.

    Returns:
        TradingViewStream instance (not connected).

    Example:
        >>> stream = bp.create_stream()
        >>> stream.connect()
    """
    return TradingViewStream(auth_token=auth_token)
