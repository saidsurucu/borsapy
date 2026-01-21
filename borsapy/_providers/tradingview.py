"""TradingView WebSocket provider for real-time and historical data."""

import json
import platform
import random
import re
import string
import time
from datetime import datetime

import httpx
import pandas as pd

from borsapy._providers.base import BaseProvider
from borsapy.exceptions import APIError, AuthenticationError

# Module-level auth storage
_auth_credentials: dict | None = None


def set_tradingview_auth(
    username: str | None = None,
    password: str | None = None,
    session: str | None = None,
    session_sign: str | None = None,
) -> dict:
    """
    Set TradingView authentication credentials for real-time data access.

    You can authenticate in two ways:
    1. Username/password: Will perform login and get session tokens
    2. Session tokens: Use existing sessionid and sessionid_sign cookies

    Args:
        username: TradingView username or email
        password: TradingView password
        session: Existing sessionid cookie value
        session_sign: Existing sessionid_sign cookie value

    Returns:
        Dict with user info and session details

    Examples:
        >>> import borsapy as bp
        >>> # Login with credentials
        >>> bp.set_tradingview_auth(username="user@email.com", password="mypassword")
        >>> # Or use existing session
        >>> bp.set_tradingview_auth(session="abc123", session_sign="xyz789")
        >>> # Now get real-time data
        >>> stock = bp.Ticker("THYAO")
        >>> stock.info["last"]  # Real-time price (no 15min delay)
    """
    global _auth_credentials

    provider = get_tradingview_provider()

    if username and password:
        # Login with credentials
        user_info = provider.login_user(username, password)
        _auth_credentials = {
            "session": user_info["session"],
            "session_sign": user_info["session_sign"],
            "auth_token": user_info.get("auth_token"),
            "user": user_info,
        }
    elif session:
        # Use existing session tokens
        user_info = provider.get_user(session, session_sign or "")
        _auth_credentials = {
            "session": session,
            "session_sign": session_sign or "",
            "auth_token": user_info.get("auth_token"),
            "user": user_info,
        }
    else:
        raise ValueError("Provide either username/password or session/session_sign")

    return _auth_credentials


def clear_tradingview_auth() -> None:
    """Clear TradingView authentication credentials."""
    global _auth_credentials
    _auth_credentials = None


def get_tradingview_auth() -> dict | None:
    """Get current TradingView authentication credentials."""
    return _auth_credentials


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

    def _get_user_agent(self) -> str:
        """Generate User-Agent string."""
        os_name = platform.system()
        os_version = platform.release()
        return f"borsapy/1.0 ({os_name} {os_version})"

    def login_user(
        self,
        username: str,
        password: str,
        remember: bool = True,
    ) -> dict:
        """
        Login to TradingView and get session tokens.

        Args:
            username: TradingView username or email
            password: TradingView password
            remember: Whether to create a persistent session (default True)

        Returns:
            Dict with session info:
            - session: sessionid cookie value
            - session_sign: sessionid_sign cookie value
            - auth_token: Authentication token for WebSocket
            - user: User profile data

        Raises:
            AuthenticationError: If login fails
        """
        login_url = "https://www.tradingview.com/accounts/signin/"

        headers = {
            "User-Agent": self._get_user_agent(),
            "Origin": "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "username": username,
            "password": password,
            "remember": "on" if remember else "",
        }

        try:
            response = self._client.post(
                login_url,
                data=data,
                headers=headers,
                follow_redirects=False,
            )
        except httpx.RequestError as e:
            raise AuthenticationError(f"Login request failed: {e}") from e

        # Check for errors in response
        if response.status_code == 200:
            try:
                result = response.json()
                if "error" in result:
                    raise AuthenticationError(f"Login failed: {result['error']}")
            except json.JSONDecodeError:
                pass

        # Extract cookies from response
        cookies = response.cookies
        session_id = cookies.get("sessionid")
        session_sign = cookies.get("sessionid_sign")

        # Also check Set-Cookie headers
        if not session_id:
            for cookie in response.headers.get_list("set-cookie"):
                if "sessionid=" in cookie and "sessionid_sign" not in cookie:
                    match = re.search(r"sessionid=([^;]+)", cookie)
                    if match:
                        session_id = match.group(1)
                elif "sessionid_sign=" in cookie:
                    match = re.search(r"sessionid_sign=([^;]+)", cookie)
                    if match:
                        session_sign = match.group(1)

        if not session_id:
            raise AuthenticationError(
                "Login failed: No session cookie received. "
                "Check your credentials or try again later."
            )

        # Get user info and auth token
        user_info = self.get_user(session_id, session_sign or "")

        return {
            "session": session_id,
            "session_sign": session_sign or "",
            "auth_token": user_info.get("auth_token"),
            "user": user_info,
        }

    def get_user(self, session: str, signature: str = "") -> dict:
        """
        Get user info from existing session tokens.

        Args:
            session: sessionid cookie value
            signature: sessionid_sign cookie value

        Returns:
            Dict with user info including auth_token

        Raises:
            AuthenticationError: If session is invalid or expired
        """
        url = "https://www.tradingview.com/"

        # Build cookie header
        cookies = f"sessionid={session}"
        if signature:
            cookies += f"; sessionid_sign={signature}"

        headers = {
            "User-Agent": self._get_user_agent(),
            "Cookie": cookies,
        }

        try:
            response = self._client.get(url, headers=headers, follow_redirects=True)
        except httpx.RequestError as e:
            raise AuthenticationError(f"Failed to validate session: {e}") from e

        html = response.text

        # Check if session is valid
        if "auth_token" not in html and '"id":' not in html:
            raise AuthenticationError(
                "Invalid or expired session. Please login again."
            )

        # Extract user data from HTML
        user_data = {}

        # Extract auth_token
        auth_match = re.search(r'"auth_token"\s*:\s*"([^"]+)"', html)
        if auth_match:
            user_data["auth_token"] = auth_match.group(1)

        # Extract user ID
        id_match = re.search(r'"id"\s*:\s*(\d+)', html)
        if id_match:
            user_data["id"] = int(id_match.group(1))

        # Extract username
        username_match = re.search(r'"username"\s*:\s*"([^"]+)"', html)
        if username_match:
            user_data["username"] = username_match.group(1)

        # Extract pro status
        pro_match = re.search(r'"pro_plan"\s*:\s*"([^"]+)"', html)
        if pro_match:
            user_data["pro_plan"] = pro_match.group(1)

        # Check if premium
        user_data["is_premium"] = bool(
            user_data.get("pro_plan") and user_data["pro_plan"] != "free"
        )

        return user_data

    def _get_auth_token(self) -> str:
        """Get auth token - either from credentials or unauthorized."""
        global _auth_credentials
        if _auth_credentials and _auth_credentials.get("auth_token"):
            return _auth_credentials["auth_token"]
        return "unauthorized_user_token"

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
            # 1. Set auth token (authenticated or unauthorized)
            auth_token = self._get_auth_token()
            ws.send(self._create_message("set_auth_token", [auth_token]))

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
            # 1. Set auth token (authenticated or unauthorized)
            auth_token = self._get_auth_token()
            ws.send(self._create_message("set_auth_token", [auth_token]))

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
