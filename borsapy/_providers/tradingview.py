"""TradingView WebSocket provider for real-time and historical data."""

import json
import random
import string
import time
from datetime import datetime

import pandas as pd

from borsapy._providers.base import BaseProvider
from borsapy.exceptions import APIError


class TradingViewProvider(BaseProvider):
    """
    TradingView data provider using WebSocket protocol.

    Based on: https://github.com/Mathieu2301/TradingView-API

    Symbol format for Turkish stocks: BIST:THYAO, BIST:GARAN, etc.
    """

    WS_URL = "wss://data.tradingview.com/socket.io/websocket"
    ORIGIN = "https://www.tradingview.com"

    # TradingView timeframe mapping (interval -> TradingView format)
    TIMEFRAMES = {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "4h": "240",
        "1d": "1D",
        "1wk": "1W",
        "1w": "1W",
        "1mo": "1M",
    }

    # Period to approximate days mapping
    PERIOD_DAYS = {
        "1d": 1,
        "5d": 5,
        "1mo": 30,
        "3mo": 90,
        "6mo": 180,
        "1y": 365,
        "2y": 730,
        "5y": 1825,
        "10y": 3650,
        "ytd": 365,  # Will be calculated dynamically
        "max": 3650,
    }

    def __init__(self):
        super().__init__()
        self._session_id = None
        self._chart_session_id = None

    def _generate_session_id(self, prefix: str = "cs") -> str:
        """Generate a random session ID."""
        chars = string.ascii_lowercase + string.digits
        random_part = "".join(random.choice(chars) for _ in range(12))
        return f"{prefix}_{random_part}"

    def _format_packet(self, data: str) -> str:
        """Format data into TradingView packet format: ~m~{length}~m~{data}"""
        return f"~m~{len(data)}~m~{data}"

    def _create_message(self, method: str, params: list) -> str:
        """Create a TradingView message."""
        msg = json.dumps({"m": method, "p": params}, separators=(",", ":"))
        return self._format_packet(msg)

    def _parse_packets(self, raw: str) -> list[dict]:
        """Parse TradingView packets from raw WebSocket message."""
        packets = []
        # Split by ~m~{number}~m~ pattern
        import re
        parts = re.split(r"~m~\d+~m~", raw)
        for part in parts:
            if not part or part.startswith("~h~"):
                continue
            try:
                packets.append(json.loads(part))
            except json.JSONDecodeError:
                continue
        return packets

    def _calculate_bars(
        self,
        period: str,
        interval: str,
        start: datetime | None,
        end: datetime | None,
    ) -> int:
        """Calculate number of bars to request based on period/interval."""
        if start and end:
            days = (end - start).days
        elif start:
            days = (datetime.now() - start).days
        elif period == "ytd":
            days = datetime.now().timetuple().tm_yday
        else:
            days = self.PERIOD_DAYS.get(period, 30)

        # Calculate bars based on interval
        interval_minutes = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "4h": 240, "1d": 1440, "1wk": 10080, "1w": 10080, "1mo": 43200,
        }.get(interval, 1440)

        # Approximate trading minutes per day (BIST: 09:30-18:00 = 510 min)
        trading_minutes_per_day = 510 if interval_minutes < 1440 else 1440

        bars = int((days * trading_minutes_per_day) / interval_minutes)
        return max(bars, 10)  # Minimum 10 bars

    def get_history(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
        start: datetime | None = None,
        end: datetime | None = None,
        exchange: str = "BIST",
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data from TradingView.

        Args:
            symbol: Stock symbol (e.g., "THYAO")
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo)
            start: Start date (overrides period if provided)
            end: End date (defaults to now)
            exchange: Exchange name (default: "BIST" for Turkish stocks)

        Returns:
            DataFrame with OHLCV data (columns: Open, High, Low, Close, Volume)
        """
        import websocket

        # Normalize symbol
        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        tv_symbol = f"{exchange}:{symbol}"
        tf = self.TIMEFRAMES.get(interval, "1D")
        bars = self._calculate_bars(period, interval, start, end)

        chart_session = self._generate_session_id("cs")

        # Collected data
        periods = {}
        symbol_info = {}
        data_received = False
        error_msg = None

        def on_message(ws, message):
            nonlocal periods, symbol_info, data_received, error_msg

            packets = self._parse_packets(message)
            for packet in packets:
                if not isinstance(packet, dict):
                    continue

                method = packet.get("m")
                params = packet.get("p", [])

                if method == "symbol_resolved":
                    if len(params) >= 3:
                        symbol_info = params[2] if isinstance(params[2], dict) else {}

                elif method == "timescale_update":
                    if len(params) >= 2 and isinstance(params[1], dict):
                        series_data = params[1].get("$prices", {}).get("s", [])
                        for candle in series_data:
                            v = candle.get("v", [])
                            if len(v) >= 6:
                                ts = int(v[0])
                                periods[ts] = {
                                    "time": ts,
                                    "open": v[1],
                                    "high": v[2],
                                    "low": v[3],
                                    "close": v[4],
                                    "volume": v[5],
                                }
                        data_received = True

                elif method == "series_completed":
                    data_received = True

                elif method == "critical_error" or method == "symbol_error":
                    error_msg = str(params)
                    ws.close()

        def on_open(ws):
            # 1. Set auth token (unauthorized)
            ws.send(self._create_message("set_auth_token", ["unauthorized_user_token"]))

            # 2. Create chart session
            ws.send(self._create_message("chart_create_session", [chart_session, ""]))

            # 3. Resolve symbol
            symbol_config = {
                "symbol": tv_symbol,
                "adjustment": "splits",
                "session": "regular",
            }
            ws.send(self._create_message("resolve_symbol", [
                chart_session,
                "ser_1",
                f"={json.dumps(symbol_config, separators=(',', ':'))}",
            ]))

            # 4. Create series (request data)
            ws.send(self._create_message("create_series", [
                chart_session,
                "$prices",
                "s1",
                "ser_1",
                tf,
                bars,
                "",
            ]))

        def on_error(ws, error):
            nonlocal error_msg
            error_msg = str(error)

        # Connect and fetch data
        ws = websocket.WebSocketApp(
            f"{self.WS_URL}?type=chart",
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            header={"Origin": self.ORIGIN},
        )

        # Run with timeout
        import threading
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()

        # Wait for data with timeout
        timeout = 10
        start = time.time()
        while not data_received and not error_msg and (time.time() - start) < timeout:
            time.sleep(0.1)

        ws.close()
        ws_thread.join(timeout=1)

        if error_msg:
            raise APIError(f"TradingView error: {error_msg}")

        if not periods:
            raise APIError(f"No data received for {tv_symbol}")

        # Convert to DataFrame
        df = pd.DataFrame(list(periods.values()))
        df["Date"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("Date").sort_index()
        df = df[["open", "high", "low", "close", "volume"]]
        df.columns = ["Open", "High", "Low", "Close", "Volume"]

        # Convert to Istanbul timezone
        df.index = df.index.tz_convert("Europe/Istanbul")

        return df

    def get_quote(self, symbol: str, exchange: str = "BIST") -> dict:
        """
        Get current quote from TradingView.

        Args:
            symbol: Stock symbol (e.g., "THYAO")
            exchange: Exchange name (default: "BIST")

        Returns:
            Dict with current price info
        """
        import websocket

        tv_symbol = f"{exchange}:{symbol}"
        quote_session = self._generate_session_id("qs")

        # Accumulate data from multiple packets
        raw_data = {}
        data_complete = False
        error_msg = None

        def on_message(ws, message):
            nonlocal raw_data, data_complete, error_msg

            packets = self._parse_packets(message)
            for packet in packets:
                if not isinstance(packet, dict):
                    continue

                method = packet.get("m")
                params = packet.get("p", [])

                if method == "qsd":
                    if len(params) >= 2 and isinstance(params[1], dict):
                        v = params[1].get("v", {})
                        # Merge data from multiple packets
                        raw_data.update(v)
                        # Check if we have essential data (lp = last price)
                        if "lp" in raw_data:
                            data_complete = True

                elif method == "critical_error" or method == "symbol_error":
                    error_msg = str(params)
                    ws.close()

        def on_open(ws):
            # 1. Set auth token
            ws.send(self._create_message("set_auth_token", ["unauthorized_user_token"]))

            # 2. Create quote session
            ws.send(self._create_message("quote_create_session", [quote_session]))

            # 3. Set fields - request all useful fields
            fields = [
                "lp", "ch", "chp", "open_price", "high_price", "low_price",
                "prev_close_price", "volume", "bid", "ask", "bid_size", "ask_size",
                "lp_time", "description", "currency_code", "exchange", "type",
            ]
            ws.send(self._create_message("quote_set_fields", [quote_session, *fields]))

            # 4. Add symbol
            ws.send(self._create_message("quote_add_symbols", [quote_session, tv_symbol]))

        def on_error(ws, error):
            nonlocal error_msg
            error_msg = str(error)

        ws = websocket.WebSocketApp(
            f"{self.WS_URL}?type=chart",
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            header={"Origin": self.ORIGIN},
        )

        import threading
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()

        # Wait for complete data
        timeout = 10
        start = time.time()
        while not data_complete and not error_msg and (time.time() - start) < timeout:
            time.sleep(0.1)

        # Give a tiny bit more time for additional data
        time.sleep(0.2)

        ws.close()
        ws_thread.join(timeout=1)

        if error_msg:
            raise APIError(f"TradingView error: {error_msg}")

        if not raw_data:
            raise APIError(f"No quote data received for {tv_symbol}")

        # Build standardized quote dict
        quote_data = {
            "symbol": symbol,
            "exchange": exchange,
            "last": raw_data.get("lp"),
            "change": raw_data.get("ch"),
            "change_percent": raw_data.get("chp"),
            "open": raw_data.get("open_price"),
            "high": raw_data.get("high_price"),
            "low": raw_data.get("low_price"),
            "prev_close": raw_data.get("prev_close_price"),
            "volume": raw_data.get("volume"),
            "bid": raw_data.get("bid"),
            "ask": raw_data.get("ask"),
            "bid_size": raw_data.get("bid_size"),
            "ask_size": raw_data.get("ask_size"),
            "timestamp": raw_data.get("lp_time"),
            "description": raw_data.get("description"),
            "currency": raw_data.get("currency_code"),
        }

        return quote_data


# Singleton instance
_provider = None


def get_tradingview_provider() -> TradingViewProvider:
    """Get singleton TradingView provider instance."""
    global _provider
    if _provider is None:
        _provider = TradingViewProvider()
    return _provider
