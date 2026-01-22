"""Tests for TradingView streaming functionality."""

import json
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from borsapy.stream import (
    CHART_TIMEFRAMES,
    QUOTE_FIELDS,
    PineStudy,
    StudySession,
    TradingViewStream,
    create_stream,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def stream():
    """Create a TradingViewStream instance (not connected)."""
    s = TradingViewStream()
    yield s
    # Cleanup
    if s.is_connected:
        s.disconnect()


@pytest.fixture
def mock_ws():
    """Mock WebSocketApp for unit tests."""
    with patch("borsapy.stream.websocket.WebSocketApp") as mock:
        yield mock


# =============================================================================
# Unit Tests - Protocol
# =============================================================================


class TestProtocol:
    """Tests for TradingView protocol handling."""

    def test_format_packet_string(self, stream):
        """Test packet formatting with string."""
        result = stream._format_packet("test")
        assert result == "~m~4~m~test"

    def test_format_packet_dict(self, stream):
        """Test packet formatting with dict."""
        result = stream._format_packet({"m": "test", "p": []})
        assert result.startswith("~m~")
        assert '{"m":"test","p":[]}' in result

    def test_create_message(self, stream):
        """Test message creation."""
        msg = stream._create_message("quote_create_session", ["qs_test123"])
        assert "~m~" in msg
        assert "quote_create_session" in msg
        assert "qs_test123" in msg

    def test_parse_packets_single(self, stream):
        """Test parsing single packet."""
        raw = '~m~26~m~{"m":"test","p":["hello"]}'
        packets = stream._parse_packets(raw)
        assert len(packets) == 1
        assert packets[0]["m"] == "test"
        assert packets[0]["p"] == ["hello"]

    def test_parse_packets_multiple(self, stream):
        """Test parsing multiple packets."""
        raw = '~m~16~m~{"m":"a","p":[]}~m~16~m~{"m":"b","p":[]}'
        packets = stream._parse_packets(raw)
        assert len(packets) == 2
        assert packets[0]["m"] == "a"
        assert packets[1]["m"] == "b"

    def test_parse_packets_heartbeat(self, stream):
        """Test parsing heartbeat packets."""
        raw = "~h~42"
        packets = stream._parse_packets(raw)
        assert len(packets) == 1
        assert packets[0] == "~h~42"

    def test_parse_packets_mixed(self, stream):
        """Test parsing mixed packets (data + heartbeat)."""
        raw = '~m~16~m~{"m":"a","p":[]}~h~42~m~16~m~{"m":"b","p":[]}'
        packets = stream._parse_packets(raw)
        assert len(packets) == 3
        assert packets[0]["m"] == "a"
        assert packets[1] == "~h~42"
        assert packets[2]["m"] == "b"

    def test_parse_packets_invalid_json(self, stream):
        """Test parsing with invalid JSON (should skip)."""
        raw = '~m~5~m~{bad}~m~16~m~{"m":"a","p":[]}'
        packets = stream._parse_packets(raw)
        # Should only parse the valid one
        assert len(packets) == 1
        assert packets[0]["m"] == "a"

    def test_generate_session_id(self, stream):
        """Test session ID generation."""
        sid1 = stream._generate_session_id("qs")
        sid2 = stream._generate_session_id("cs")

        assert sid1.startswith("qs_")
        assert sid2.startswith("cs_")
        assert len(sid1) == 15  # qs_ + 12 chars
        assert sid1 != sid2


# =============================================================================
# Unit Tests - Quote Handling
# =============================================================================


class TestQuoteHandling:
    """Tests for quote data handling."""

    def test_handle_quote_data(self, stream):
        """Test quote data handling."""
        # Simulate qsd packet params
        params = [
            "qs_test",
            {
                "n": "BIST:THYAO",
                "s": "ok",
                "v": {
                    "lp": 299.0,
                    "ch": -1.5,
                    "chp": -0.5,
                    "volume": 12345678,
                },
            },
        ]

        stream._handle_quote_data(params)

        # Check that quote was stored
        quote = stream.get_quote("THYAO")
        assert quote is not None
        assert quote["last"] == 299.0
        assert quote["change"] == -1.5
        assert quote["change_percent"] == -0.5
        assert quote["volume"] == 12345678

    def test_handle_quote_data_error(self, stream):
        """Test quote error handling."""
        params = [
            "qs_test",
            {"n": "BIST:INVALID", "s": "error", "v": {}},
        ]

        # Should not raise, just log warning
        stream._handle_quote_data(params)

        # No quote should be stored
        quote = stream.get_quote("INVALID")
        assert quote is None

    def test_quote_update_callback(self, stream):
        """Test callback is called on quote update."""
        callback_data = {}

        def on_update(symbol, quote):
            callback_data["symbol"] = symbol
            callback_data["quote"] = quote

        stream._callbacks["THYAO"] = [on_update]

        params = [
            "qs_test",
            {"n": "BIST:THYAO", "s": "ok", "v": {"lp": 300.0}},
        ]
        stream._handle_quote_data(params)

        assert callback_data["symbol"] == "THYAO"
        assert callback_data["quote"]["last"] == 300.0

    def test_global_callback(self, stream):
        """Test global callback is called for any symbol."""
        symbols_updated = []

        def on_any(symbol, quote):
            symbols_updated.append(symbol)

        stream._global_callbacks.append(on_any)

        # Simulate updates for multiple symbols
        for sym in ["THYAO", "GARAN", "ASELS"]:
            params = [
                "qs_test",
                {"n": f"BIST:{sym}", "s": "ok", "v": {"lp": 100.0}},
            ]
            stream._handle_quote_data(params)

        assert symbols_updated == ["THYAO", "GARAN", "ASELS"]

    def test_quote_accumulation(self, stream):
        """Test quote data accumulation across multiple packets."""
        # First packet - partial data
        params1 = [
            "qs_test",
            {"n": "BIST:THYAO", "s": "ok", "v": {"lp": 299.0, "ch": -1.0}},
        ]
        stream._handle_quote_data(params1)

        # Second packet - more data
        params2 = [
            "qs_test",
            {
                "n": "BIST:THYAO",
                "s": "ok",
                "v": {"volume": 1000000, "bid": 298.9, "ask": 299.1},
            },
        ]
        stream._handle_quote_data(params2)

        quote = stream.get_quote("THYAO")
        assert quote["last"] == 299.0  # From first packet
        assert quote["change"] == -1.0  # From first packet
        assert quote["volume"] == 1000000  # From second packet
        assert quote["bid"] == 298.9  # From second packet


# =============================================================================
# Unit Tests - Subscription
# =============================================================================


class TestSubscription:
    """Tests for symbol subscription."""

    def test_subscribe_not_connected(self, stream):
        """Test subscribe when not connected."""
        stream.subscribe("THYAO")

        assert "THYAO" in stream.subscribed_symbols

    def test_subscribe_duplicate(self, stream):
        """Test subscribing to same symbol twice."""
        stream.subscribe("THYAO")
        stream.subscribe("THYAO")

        assert len(stream.subscribed_symbols) == 1

    def test_unsubscribe(self, stream):
        """Test unsubscribe."""
        stream.subscribe("THYAO")
        stream.unsubscribe("THYAO")

        assert "THYAO" not in stream.subscribed_symbols

    def test_unsubscribe_clears_data(self, stream):
        """Test unsubscribe clears cached data."""
        # Add some data
        stream._quotes["THYAO"] = {"lp": 299.0}

        stream.unsubscribe("THYAO")

        assert stream.get_quote("THYAO") is None


# =============================================================================
# Unit Tests - Callbacks
# =============================================================================


class TestCallbacks:
    """Tests for callback registration."""

    def test_on_quote(self, stream):
        """Test registering symbol-specific callback."""

        def callback(symbol, quote):
            pass

        stream.on_quote("THYAO", callback)

        assert "THYAO" in stream._callbacks
        assert callback in stream._callbacks["THYAO"]

    def test_on_any_quote(self, stream):
        """Test registering global callback."""

        def callback(symbol, quote):
            pass

        stream.on_any_quote(callback)

        assert callback in stream._global_callbacks

    def test_remove_callback(self, stream):
        """Test removing callback."""

        def callback(symbol, quote):
            pass

        stream.on_quote("THYAO", callback)
        stream.remove_callback("THYAO", callback)

        assert callback not in stream._callbacks.get("THYAO", [])

    def test_callback_exception_handling(self, stream):
        """Test that callback exceptions don't break stream."""

        def bad_callback(symbol, quote):
            raise ValueError("Test error")

        stream._callbacks["THYAO"] = [bad_callback]

        # Should not raise
        params = [
            "qs_test",
            {"n": "BIST:THYAO", "s": "ok", "v": {"lp": 300.0}},
        ]
        stream._handle_quote_data(params)


# =============================================================================
# Unit Tests - Build Quote
# =============================================================================


class TestBuildQuote:
    """Tests for quote dict building."""

    def test_build_quote_full(self, stream):
        """Test building quote with all fields."""
        stream._quotes["THYAO"] = {
            "lp": 299.0,
            "ch": -1.5,
            "chp": -0.5,
            "open_price": 300.0,
            "high_price": 301.5,
            "low_price": 298.0,
            "prev_close_price": 300.5,
            "volume": 12345678,
            "bid": 298.9,
            "ask": 299.1,
            "bid_size": 1000,
            "ask_size": 1200,
            "lp_time": 1737123456,
            "description": "TURK HAVA YOLLARI",
            "currency_code": "TRY",
            "exchange": "BIST",
            "market_cap_basic": 250000000000,
            "price_earnings_ttm": 5.2,
            "earnings_per_share_basic_ttm": 57.5,
            "dividends_yield": 2.5,
            "beta_1_year": 1.1,
        }

        quote = stream._build_quote("THYAO")

        assert quote["symbol"] == "THYAO"
        assert quote["last"] == 299.0
        assert quote["change"] == -1.5
        assert quote["change_percent"] == -0.5
        assert quote["open"] == 300.0
        assert quote["high"] == 301.5
        assert quote["low"] == 298.0
        assert quote["prev_close"] == 300.5
        assert quote["volume"] == 12345678
        assert quote["bid"] == 298.9
        assert quote["ask"] == 299.1
        assert quote["market_cap"] == 250000000000
        assert quote["pe_ratio"] == 5.2
        assert quote["eps"] == 57.5
        assert quote["dividend_yield"] == 2.5
        assert quote["beta"] == 1.1

    def test_build_quote_empty(self, stream):
        """Test building quote with missing data."""
        stream._quotes["THYAO"] = {}

        quote = stream._build_quote("THYAO")

        assert quote["symbol"] == "THYAO"
        assert quote["last"] is None
        assert quote["change"] is None


# =============================================================================
# Unit Tests - Heartbeat
# =============================================================================


class TestHeartbeat:
    """Tests for heartbeat handling."""

    def test_handle_heartbeat(self, stream):
        """Test heartbeat handling."""
        stream._ws = MagicMock()
        stream._connected.set()

        initial_time = stream._last_heartbeat_time
        stream._handle_heartbeat("~h~42")

        # Should update time
        assert stream._last_heartbeat_time > initial_time

        # Should echo back
        stream._ws.send.assert_called_once()


# =============================================================================
# Unit Tests - Context Manager
# =============================================================================


class TestContextManager:
    """Tests for context manager usage."""

    def test_context_manager_not_connected(self, mock_ws):
        """Test context manager connects and disconnects."""
        mock_instance = MagicMock()
        mock_ws.return_value = mock_instance

        with patch.object(TradingViewStream, "connect") as mock_connect:
            with patch.object(TradingViewStream, "disconnect") as mock_disconnect:
                mock_connect.return_value = True

                with TradingViewStream() as stream:
                    pass

                mock_connect.assert_called_once()
                mock_disconnect.assert_called_once()


# =============================================================================
# Unit Tests - Thread Safety
# =============================================================================


class TestThreadSafety:
    """Tests for thread-safe operations."""

    def test_concurrent_quote_updates(self, stream):
        """Test concurrent quote updates are thread-safe."""
        results = []

        def update_quote(symbol, value):
            params = [
                "qs_test",
                {"n": f"BIST:{symbol}", "s": "ok", "v": {"lp": value}},
            ]
            stream._handle_quote_data(params)
            time.sleep(0.001)
            quote = stream.get_quote(symbol)
            if quote:
                results.append((symbol, quote["last"]))

        threads = []
        for i in range(10):
            t = threading.Thread(target=update_quote, args=(f"SYM{i}", i * 100))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All updates should be captured
        assert len(results) == 10


# =============================================================================
# Unit Tests - Utility
# =============================================================================


class TestUtility:
    """Tests for utility methods."""

    def test_get_all_quotes(self, stream):
        """Test getting all quotes."""
        stream._quotes["THYAO"] = {"lp": 299.0}
        stream._quotes["GARAN"] = {"lp": 60.0}

        all_quotes = stream.get_all_quotes()

        assert "THYAO" in all_quotes
        assert "GARAN" in all_quotes
        assert all_quotes["THYAO"]["last"] == 299.0
        assert all_quotes["GARAN"]["last"] == 60.0

    def test_create_stream_function(self):
        """Test create_stream convenience function."""
        stream = create_stream()
        assert isinstance(stream, TradingViewStream)
        assert not stream.is_connected


# =============================================================================
# Unit Tests - Properties
# =============================================================================


class TestProperties:
    """Tests for property accessors."""

    def test_is_connected_false(self, stream):
        """Test is_connected when not connected."""
        assert stream.is_connected is False

    def test_is_connected_true(self, stream):
        """Test is_connected when connected."""
        stream._connected.set()
        assert stream.is_connected is True

    def test_subscribed_symbols(self, stream):
        """Test subscribed_symbols returns copy."""
        stream._subscribed.add("THYAO")

        symbols = stream.subscribed_symbols
        symbols.add("GARAN")

        # Original should not be modified
        assert "GARAN" not in stream._subscribed


# =============================================================================
# Integration Tests (require network)
# =============================================================================


@pytest.mark.integration
class TestIntegration:
    """Integration tests (require network connection)."""

    def test_connect_and_subscribe(self):
        """Test real connection and subscription."""
        stream = TradingViewStream()

        try:
            # Connect
            stream.connect(timeout=10)
            assert stream.is_connected

            # Subscribe
            stream.subscribe("THYAO")
            assert "THYAO" in stream.subscribed_symbols

            # Wait for quote
            quote = stream.wait_for_quote("THYAO", timeout=10)

            # Verify quote has data
            assert quote is not None
            assert quote["symbol"] == "THYAO"
            assert quote["last"] is not None
            assert isinstance(quote["last"], (int, float))

        finally:
            stream.disconnect()

        assert not stream.is_connected

    def test_multiple_symbols(self):
        """Test subscribing to multiple symbols."""
        stream = TradingViewStream()

        try:
            stream.connect(timeout=10)

            symbols = ["THYAO", "GARAN", "ASELS"]
            for sym in symbols:
                stream.subscribe(sym)

            # Wait for quotes
            quotes = {}
            for sym in symbols:
                quotes[sym] = stream.wait_for_quote(sym, timeout=10)

            # All should have data
            for sym in symbols:
                assert quotes[sym] is not None
                assert quotes[sym]["last"] is not None

        finally:
            stream.disconnect()

    def test_callback_receives_updates(self):
        """Test that callback receives updates."""
        stream = TradingViewStream()
        updates = []

        def on_update(symbol, quote):
            updates.append((symbol, quote["last"]))

        try:
            stream.connect(timeout=10)
            stream.subscribe("THYAO")
            stream.on_quote("THYAO", on_update)

            # Wait for some updates
            time.sleep(5)

            # Should have received at least one update
            assert len(updates) > 0
            assert updates[0][0] == "THYAO"
            assert updates[0][1] is not None

        finally:
            stream.disconnect()

    def test_reconnection(self):
        """Test automatic reconnection."""
        stream = TradingViewStream()

        try:
            stream.connect(timeout=10)
            stream.subscribe("THYAO")

            # Wait for initial quote
            stream.wait_for_quote("THYAO", timeout=10)

            # Force disconnect
            if stream._ws:
                stream._ws.close()

            # Wait for reconnection
            time.sleep(5)

            # Should be reconnected
            assert stream.is_connected

            # Should still be subscribed
            assert "THYAO" in stream.subscribed_symbols

        finally:
            stream._should_reconnect = False
            stream.disconnect()

    def test_context_manager_integration(self):
        """Test context manager with real connection."""
        with TradingViewStream() as stream:
            stream.subscribe("THYAO")
            quote = stream.wait_for_quote("THYAO", timeout=10)
            assert quote is not None
            assert quote["last"] is not None

    def test_latency(self):
        """Test latency measurements."""
        stream = TradingViewStream()

        try:
            # Measure connect time
            start = time.time()
            stream.connect(timeout=10)
            connect_time = (time.time() - start) * 1000
            print(f"Connect time: {connect_time:.0f}ms")

            # Measure subscribe + first quote
            stream.subscribe("THYAO")
            start = time.time()
            stream.wait_for_quote("THYAO", timeout=10)
            first_quote_time = (time.time() - start) * 1000
            print(f"First quote time: {first_quote_time:.0f}ms")

            # Measure cached quote access
            times = []
            for _ in range(1000):
                start = time.time()
                stream.get_quote("THYAO")
                times.append((time.time() - start) * 1000)
            avg_cached = sum(times) / len(times)
            print(f"Cached quote avg: {avg_cached:.3f}ms")

            # Assert reasonable latencies
            assert connect_time < 5000  # <5s
            assert first_quote_time < 2000  # <2s
            assert avg_cached < 1  # <1ms

        finally:
            stream.disconnect()


# =============================================================================
# Quote Fields Test
# =============================================================================


class TestQuoteFields:
    """Tests for quote fields constant."""

    def test_quote_fields_not_empty(self):
        """Test QUOTE_FIELDS has values."""
        assert len(QUOTE_FIELDS) > 0

    def test_quote_fields_has_essential(self):
        """Test QUOTE_FIELDS has essential fields."""
        essential = ["lp", "ch", "chp", "bid", "ask", "volume"]
        for field in essential:
            assert field in QUOTE_FIELDS


# =============================================================================
# Unit Tests - Chart Session
# =============================================================================


class TestChartTimeframes:
    """Tests for chart timeframes constant."""

    def test_chart_timeframes_not_empty(self):
        """Test CHART_TIMEFRAMES has values."""
        assert len(CHART_TIMEFRAMES) > 0

    def test_chart_timeframes_has_essential(self):
        """Test CHART_TIMEFRAMES has essential intervals."""
        essential = ["1m", "5m", "15m", "1h", "1d"]
        for tf in essential:
            assert tf in CHART_TIMEFRAMES

    def test_chart_timeframes_mapping(self):
        """Test CHART_TIMEFRAMES maps correctly."""
        assert CHART_TIMEFRAMES["1m"] == "1"
        assert CHART_TIMEFRAMES["1h"] == "60"
        assert CHART_TIMEFRAMES["1d"] == "1D"


class TestChartSubscription:
    """Tests for chart subscription."""

    def test_subscribe_chart_not_connected(self, stream):
        """Test chart subscribe when not connected."""
        stream.subscribe_chart("THYAO", "1m")

        assert "THYAO" in stream._chart_subscribed
        assert "1m" in stream._chart_subscribed["THYAO"]

    def test_subscribe_chart_multiple_intervals(self, stream):
        """Test subscribing to multiple intervals for same symbol."""
        stream.subscribe_chart("THYAO", "1m")
        stream.subscribe_chart("THYAO", "1h")
        stream.subscribe_chart("THYAO", "1d")

        assert "1m" in stream._chart_subscribed["THYAO"]
        assert "1h" in stream._chart_subscribed["THYAO"]
        assert "1d" in stream._chart_subscribed["THYAO"]

    def test_subscribe_chart_duplicate(self, stream):
        """Test subscribing to same symbol/interval twice."""
        stream.subscribe_chart("THYAO", "1m")
        stream.subscribe_chart("THYAO", "1m")

        assert len(stream._chart_subscribed["THYAO"]) == 1

    def test_subscribe_chart_invalid_interval(self, stream):
        """Test subscribing with invalid interval."""
        with pytest.raises(ValueError, match="Invalid interval"):
            stream.subscribe_chart("THYAO", "invalid")

    def test_unsubscribe_chart(self, stream):
        """Test chart unsubscription."""
        stream.subscribe_chart("THYAO", "1m")
        stream.unsubscribe_chart("THYAO", "1m")

        if "THYAO" in stream._chart_subscribed:
            assert "1m" not in stream._chart_subscribed["THYAO"]

    def test_unsubscribe_chart_clears_data(self, stream):
        """Test unsubscription clears cached data."""
        stream.subscribe_chart("THYAO", "1m")
        stream._chart_data["THYAO"] = {"1m": [{"time": 123, "close": 100}]}

        stream.unsubscribe_chart("THYAO", "1m")

        if "THYAO" in stream._chart_data:
            assert "1m" not in stream._chart_data["THYAO"]

    def test_chart_subscriptions_property(self, stream):
        """Test chart_subscriptions property."""
        stream.subscribe_chart("THYAO", "1m")
        stream.subscribe_chart("GARAN", "1h")

        subs = stream.chart_subscriptions

        assert "THYAO" in subs
        assert "GARAN" in subs
        assert "1m" in subs["THYAO"]
        assert "1h" in subs["GARAN"]

    def test_chart_subscriptions_returns_copy(self, stream):
        """Test chart_subscriptions returns copy."""
        stream.subscribe_chart("THYAO", "1m")

        subs = stream.chart_subscriptions
        subs["THYAO"].add("5m")

        # Original should not be modified
        assert "5m" not in stream._chart_subscribed["THYAO"]


class TestChartDataHandling:
    """Tests for chart data handling."""

    def test_handle_chart_data(self, stream):
        """Test chart data handling."""
        # First subscribe
        stream.subscribe_chart("THYAO", "1m")

        # Add series mapping
        stream._chart_series_map["ser_1"] = ("THYAO", "1m")

        # Simulate timescale_update params
        params = [
            "cs_test",
            {
                "$prices": {
                    "s": [
                        {"v": [1737123456, 285.0, 286.5, 284.0, 285.5, 123456]},
                        {"v": [1737123516, 285.5, 287.0, 285.0, 286.0, 234567]},
                    ]
                }
            },
        ]

        stream._handle_chart_data(params)

        # Check that candles were stored
        candles = stream.get_candles("THYAO", "1m")
        assert len(candles) >= 2

    def test_update_chart_data(self, stream):
        """Test chart data update."""
        stream._chart_data["THYAO"] = {"1m": []}

        candles = [
            {"time": 1737123456, "open": 285.0, "high": 286.5, "low": 284.0, "close": 285.5, "volume": 123456},
        ]
        stream._update_chart_data("THYAO", "1m", candles)

        stored = stream._chart_data["THYAO"]["1m"]
        assert len(stored) == 1
        assert stored[0]["close"] == 285.5

    def test_update_chart_data_replaces_same_timestamp(self, stream):
        """Test that candle with same timestamp replaces existing."""
        stream._chart_data["THYAO"] = {"1m": [
            {"time": 1000, "open": 100, "high": 105, "low": 99, "close": 104, "volume": 1000}
        ]}

        # Update with same timestamp but new close
        candles = [{"time": 1000, "open": 100, "high": 106, "low": 99, "close": 105, "volume": 1100}]
        stream._update_chart_data("THYAO", "1m", candles)

        stored = stream._chart_data["THYAO"]["1m"]
        assert len(stored) == 1
        assert stored[0]["close"] == 105  # Updated
        assert stored[0]["volume"] == 1100  # Updated

    def test_get_candle(self, stream):
        """Test getting latest candle."""
        stream._chart_data["THYAO"] = {"1m": [
            {"time": 1000, "close": 100},
            {"time": 1060, "close": 101},
            {"time": 1120, "close": 102},
        ]}

        candle = stream.get_candle("THYAO", "1m")

        assert candle is not None
        assert candle["time"] == 1120
        assert candle["close"] == 102

    def test_get_candle_not_subscribed(self, stream):
        """Test getting candle when not subscribed."""
        candle = stream.get_candle("THYAO", "1m")
        assert candle is None

    def test_get_candle_no_data(self, stream):
        """Test getting candle when no data yet."""
        stream._chart_data["THYAO"] = {"1m": []}

        candle = stream.get_candle("THYAO", "1m")
        assert candle is None

    def test_get_candles(self, stream):
        """Test getting multiple candles."""
        stream._chart_data["THYAO"] = {"1m": [
            {"time": 1000, "close": 100},
            {"time": 1060, "close": 101},
            {"time": 1120, "close": 102},
        ]}

        candles = stream.get_candles("THYAO", "1m")
        assert len(candles) == 3

    def test_get_candles_with_count(self, stream):
        """Test getting limited number of candles."""
        stream._chart_data["THYAO"] = {"1m": [
            {"time": 1000, "close": 100},
            {"time": 1060, "close": 101},
            {"time": 1120, "close": 102},
        ]}

        candles = stream.get_candles("THYAO", "1m", count=2)
        assert len(candles) == 2
        assert candles[0]["time"] == 1060  # Second to last
        assert candles[1]["time"] == 1120  # Last

    def test_get_candles_empty(self, stream):
        """Test getting candles when not subscribed."""
        candles = stream.get_candles("THYAO", "1m")
        assert candles == []


class TestChartCallbacks:
    """Tests for chart callbacks."""

    def test_on_candle(self, stream):
        """Test registering candle callback."""
        def callback(symbol, interval, candle):
            pass

        stream.on_candle("THYAO", "1m", callback)

        assert "THYAO:1m" in stream._chart_callbacks
        assert callback in stream._chart_callbacks["THYAO:1m"]

    def test_on_any_candle(self, stream):
        """Test registering global candle callback."""
        def callback(symbol, interval, candle):
            pass

        stream.on_any_candle(callback)

        assert callback in stream._global_chart_callbacks

    def test_remove_candle_callback(self, stream):
        """Test removing candle callback."""
        def callback(symbol, interval, candle):
            pass

        stream.on_candle("THYAO", "1m", callback)
        stream.remove_candle_callback("THYAO", "1m", callback)

        assert callback not in stream._chart_callbacks.get("THYAO:1m", [])

    def test_candle_callback_called(self, stream):
        """Test callback is called on candle update."""
        callback_data = {}

        def on_candle(symbol, interval, candle):
            callback_data["symbol"] = symbol
            callback_data["interval"] = interval
            callback_data["candle"] = candle

        stream.on_candle("THYAO", "1m", on_candle)
        stream._chart_data["THYAO"] = {"1m": []}

        candles = [{"time": 1000, "open": 100, "high": 105, "low": 99, "close": 104, "volume": 1000}]
        stream._update_chart_data("THYAO", "1m", candles)

        assert callback_data["symbol"] == "THYAO"
        assert callback_data["interval"] == "1m"
        assert callback_data["candle"]["close"] == 104

    def test_global_candle_callback_called(self, stream):
        """Test global callback is called for any candle."""
        updates = []

        def on_any(symbol, interval, candle):
            updates.append((symbol, interval))

        stream.on_any_candle(on_any)
        stream._chart_data["THYAO"] = {"1m": [], "1h": []}
        stream._chart_data["GARAN"] = {"1m": []}

        stream._update_chart_data("THYAO", "1m", [{"time": 1000, "close": 100, "open": 100, "high": 100, "low": 100, "volume": 100}])
        stream._update_chart_data("THYAO", "1h", [{"time": 1000, "close": 200, "open": 200, "high": 200, "low": 200, "volume": 200}])
        stream._update_chart_data("GARAN", "1m", [{"time": 1000, "close": 50, "open": 50, "high": 50, "low": 50, "volume": 50}])

        assert ("THYAO", "1m") in updates
        assert ("THYAO", "1h") in updates
        assert ("GARAN", "1m") in updates

    def test_candle_callback_exception_handling(self, stream):
        """Test that callback exceptions don't break stream."""
        def bad_callback(symbol, interval, candle):
            raise ValueError("Test error")

        stream._chart_callbacks["THYAO:1m"] = [bad_callback]
        stream._chart_data["THYAO"] = {"1m": []}

        # Should not raise
        candles = [{"time": 1000, "close": 100, "open": 100, "high": 100, "low": 100, "volume": 100}]
        stream._update_chart_data("THYAO", "1m", candles)


# =============================================================================
# Chart Integration Tests
# =============================================================================


@pytest.mark.integration
class TestChartIntegration:
    """Integration tests for chart session (require network)."""

    def test_chart_subscribe_and_get_candle(self):
        """Test real chart subscription and candle retrieval."""
        stream = TradingViewStream()

        try:
            stream.connect(timeout=10)
            stream.subscribe_chart("THYAO", "1m")

            # Wait for candle
            candle = stream.wait_for_candle("THYAO", "1m", timeout=15)

            assert candle is not None
            assert "time" in candle
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle
            assert "volume" in candle

        finally:
            stream.disconnect()

    def test_chart_multiple_intervals(self):
        """Test subscribing to multiple intervals."""
        stream = TradingViewStream()

        try:
            stream.connect(timeout=10)
            stream.subscribe_chart("THYAO", "1m")
            stream.subscribe_chart("THYAO", "1h")

            # Wait for candles
            candle_1m = stream.wait_for_candle("THYAO", "1m", timeout=15)
            candle_1h = stream.wait_for_candle("THYAO", "1h", timeout=15)

            assert candle_1m is not None
            assert candle_1h is not None

        finally:
            stream.disconnect()

    def test_chart_callback_receives_updates(self):
        """Test that chart callback receives updates."""
        stream = TradingViewStream()
        updates = []

        def on_candle(symbol, interval, candle):
            updates.append((symbol, interval, candle["close"]))

        try:
            stream.connect(timeout=10)
            stream.subscribe_chart("THYAO", "1m")
            stream.on_candle("THYAO", "1m", on_candle)

            # Wait for some updates
            time.sleep(10)

            # Should have received at least one update
            assert len(updates) > 0
            assert updates[0][0] == "THYAO"
            assert updates[0][1] == "1m"

        finally:
            stream.disconnect()

    def test_chart_and_quote_together(self):
        """Test chart and quote subscription together."""
        stream = TradingViewStream()

        try:
            stream.connect(timeout=10)

            # Subscribe to both
            stream.subscribe("THYAO")
            stream.subscribe_chart("THYAO", "1m")

            # Wait for data
            quote = stream.wait_for_quote("THYAO", timeout=10)
            candle = stream.wait_for_candle("THYAO", "1m", timeout=15)

            assert quote is not None
            assert quote["last"] is not None
            assert candle is not None
            assert candle["close"] is not None

        finally:
            stream.disconnect()


# =============================================================================
# Unit Tests - PineStudy
# =============================================================================


class TestPineStudy:
    """Tests for PineStudy dataclass."""

    def test_pine_study_creation(self):
        """Test PineStudy creation with required fields."""
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
        )

        assert study.indicator_id == "STD;RSI"
        assert study.study_id == "st1"
        assert study.symbol == "THYAO"
        assert study.interval == "1m"
        assert study.inputs == {}
        assert study.metadata == {}
        assert study.values == {}
        assert study.ready is False

    def test_pine_study_with_inputs(self):
        """Test PineStudy with custom inputs."""
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
            inputs={"length": 7},
        )

        assert study.inputs == {"length": 7}

    def test_pine_study_ready_state(self):
        """Test PineStudy ready state change."""
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
        )

        assert study.ready is False

        study.ready = True
        assert study.ready is True

    def test_pine_study_values_update(self):
        """Test PineStudy values update."""
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
        )

        study.values = {"value": 48.5}
        assert study.values["value"] == 48.5


# =============================================================================
# Unit Tests - StudySession
# =============================================================================


class TestStudySession:
    """Tests for StudySession class."""

    @pytest.fixture
    def study_session(self, stream):
        """Create a StudySession for testing."""
        return StudySession(stream)

    def test_study_session_creation(self, stream):
        """Test StudySession initialization."""
        session = StudySession(stream)

        assert session._stream is stream
        assert session._studies == {}
        assert session._study_counter == 0
        assert session._callbacks == {}
        assert session._global_callbacks == []

    def test_normalize_indicator_short_name(self, stream):
        """Test indicator normalization with short name."""
        session = StudySession(stream)

        display, indicator_id = session._normalize_indicator("RSI")

        assert display == "RSI"
        assert indicator_id == "STD;RSI"

    def test_normalize_indicator_lowercase(self, stream):
        """Test indicator normalization with lowercase."""
        session = StudySession(stream)

        display, indicator_id = session._normalize_indicator("macd")

        assert display == "MACD"
        assert indicator_id == "STD;MACD"

    def test_normalize_indicator_full_id(self, stream):
        """Test indicator normalization with full ID."""
        session = StudySession(stream)

        display, indicator_id = session._normalize_indicator("STD;RSI")

        assert display == "RSI"
        assert indicator_id == "STD;RSI"

    def test_normalize_indicator_public(self, stream):
        """Test indicator normalization with public indicator."""
        session = StudySession(stream)

        display, indicator_id = session._normalize_indicator("PUB;abc123")

        assert display == "ABC123"
        assert indicator_id == "PUB;abc123"

    def test_normalize_indicator_unknown(self, stream):
        """Test indicator normalization with unknown name."""
        session = StudySession(stream)

        display, indicator_id = session._normalize_indicator("CustomInd")

        assert display == "CUSTOMIND"
        assert indicator_id == "STD;CustomInd"

    def test_add_study_stores_study(self, stream):
        """Test add() stores study correctly."""
        session = StudySession(stream)

        # Mock chart subscription
        stream._chart_subscribed = {"THYAO": {"1m"}}
        stream._chart_session_id = "cs_test"

        # Mock pine facade
        mock_pine_facade = MagicMock()
        mock_pine_facade.get_indicator.return_value = {"pineId": "STD;RSI", "inputs": {}}
        session._pine_facade = mock_pine_facade

        study_id = session.add("THYAO", "1m", "RSI")

        assert study_id.startswith("st")
        assert "THYAO" in session._studies
        assert "1m" in session._studies["THYAO"]
        assert "RSI" in session._studies["THYAO"]["1m"]

    def test_add_study_increments_counter(self, stream):
        """Test add() increments study counter."""
        session = StudySession(stream)

        # Mock chart subscription
        stream._chart_subscribed = {"THYAO": {"1m"}}
        stream._chart_session_id = "cs_test"

        # Mock pine facade
        mock_pine_facade = MagicMock()
        mock_pine_facade.get_indicator.return_value = {"pineId": "STD;RSI", "inputs": {}}
        session._pine_facade = mock_pine_facade

        session.add("THYAO", "1m", "RSI")
        session.add("THYAO", "1m", "MACD")

        assert session._study_counter == 2

    def test_add_study_no_chart_subscription(self, stream):
        """Test add() raises error if chart not subscribed."""
        session = StudySession(stream)

        with pytest.raises(ValueError, match="Chart not subscribed"):
            session.add("THYAO", "1m", "RSI")

    def test_remove_study(self, stream):
        """Test remove() removes study."""
        session = StudySession(stream)

        # Add a study manually
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
        )
        session._studies = {"THYAO": {"1m": {"RSI": study}}}
        session._study_id_map = {"st1": ("THYAO", "1m", "RSI")}

        session.remove("THYAO", "1m", "RSI")

        assert "RSI" not in session._studies.get("THYAO", {}).get("1m", {})

    def test_remove_study_nonexistent(self, stream):
        """Test remove() handles nonexistent study gracefully."""
        session = StudySession(stream)

        # Should not raise
        session.remove("THYAO", "1m", "RSI")

    def test_get_study(self, stream):
        """Test get() returns study values."""
        session = StudySession(stream)

        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
            values={"value": 48.5},
            ready=True,
        )
        session._studies = {"THYAO": {"1m": {"RSI": study}}}

        values = session.get("THYAO", "1m", "RSI")

        assert values == {"value": 48.5}

    def test_get_study_not_ready(self, stream):
        """Test get() returns None if study has no values (regardless of ready flag)."""
        session = StudySession(stream)

        # Study with no values should return None
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
            values={},  # Empty values
            ready=False,
        )
        session._studies = {"THYAO": {"1m": {"RSI": study}}}

        values = session.get("THYAO", "1m", "RSI")

        # get() returns None if study.values is empty, not based on ready flag
        assert values is None

    def test_get_study_nonexistent(self, stream):
        """Test get() returns None for nonexistent study."""
        session = StudySession(stream)

        values = session.get("THYAO", "1m", "RSI")

        assert values is None

    def test_get_all_studies(self, stream):
        """Test get_all() returns all studies for symbol/interval."""
        session = StudySession(stream)

        session._studies = {
            "THYAO": {
                "1m": {
                    "RSI": PineStudy(
                        indicator_id="STD;RSI",
                        study_id="st1",
                        symbol="THYAO",
                        interval="1m",
                        values={"value": 48.5},
                        ready=True,
                    ),
                    "MACD": PineStudy(
                        indicator_id="STD;MACD",
                        study_id="st2",
                        symbol="THYAO",
                        interval="1m",
                        values={"macd": 3.2, "signal": 2.8},
                        ready=True,
                    ),
                }
            }
        }

        all_studies = session.get_all("THYAO", "1m")

        assert "RSI" in all_studies
        assert "MACD" in all_studies
        assert all_studies["RSI"] == {"value": 48.5}
        assert all_studies["MACD"] == {"macd": 3.2, "signal": 2.8}

    def test_get_all_studies_empty(self, stream):
        """Test get_all() returns empty dict if no studies."""
        session = StudySession(stream)

        all_studies = session.get_all("THYAO", "1m")

        assert all_studies == {}


class TestStudySessionCallbacks:
    """Tests for StudySession callback functionality."""

    @pytest.fixture
    def study_session(self, stream):
        """Create a StudySession for testing."""
        return StudySession(stream)

    def test_on_update_registers_callback(self, study_session):
        """Test on_update() registers callback."""
        def callback(symbol, interval, indicator, values):
            pass

        study_session.on_update("THYAO", "1m", "RSI", callback)

        assert "THYAO:1m:RSI" in study_session._callbacks
        assert callback in study_session._callbacks["THYAO:1m:RSI"]

    def test_on_any_update_registers_global_callback(self, study_session):
        """Test on_any_update() registers global callback."""
        def callback(symbol, interval, indicator, values):
            pass

        study_session.on_any_update(callback)

        assert callback in study_session._global_callbacks

    def test_callback_called_on_study_update(self, stream):
        """Test callback is called when study data updates."""
        session = StudySession(stream)

        callback_data = {}

        def on_update(symbol, interval, indicator, values):
            callback_data["symbol"] = symbol
            callback_data["interval"] = interval
            callback_data["indicator"] = indicator
            callback_data["values"] = values

        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
            ready=True,
        )
        session._studies = {"THYAO": {"1m": {"RSI": study}}}
        session._study_id_map = {"st1": ("THYAO", "1m", "RSI")}
        session.on_update("THYAO", "1m", "RSI", on_update)

        # Simulate data update using handle_study_data (actual method)
        data = {"st": [{"i": 0, "v": [1737123456, 48.5]}]}
        session.handle_study_data("st1", data)

        assert callback_data["symbol"] == "THYAO"
        assert callback_data["interval"] == "1m"
        assert callback_data["indicator"] == "RSI"
        assert callback_data["values"]["value"] == 48.5

    def test_global_callback_called_for_any_study(self, stream):
        """Test global callback is called for any study update."""
        session = StudySession(stream)
        updates = []

        def on_any(symbol, interval, indicator, values):
            updates.append((symbol, interval, indicator))

        session._global_callbacks.append(on_any)

        # Add multiple studies
        session._studies = {
            "THYAO": {
                "1m": {
                    "RSI": PineStudy(
                        indicator_id="STD;RSI", study_id="st1",
                        symbol="THYAO", interval="1m", ready=True,
                    ),
                    "MACD": PineStudy(
                        indicator_id="STD;MACD", study_id="st2",
                        symbol="THYAO", interval="1m", ready=True,
                    ),
                }
            }
        }
        session._study_id_map = {
            "st1": ("THYAO", "1m", "RSI"),
            "st2": ("THYAO", "1m", "MACD"),
        }

        # Use handle_study_data (actual method)
        session.handle_study_data("st1", {"st": [{"i": 0, "v": [1737123456, 48.5]}]})
        session.handle_study_data("st2", {"st": [{"i": 0, "v": [1737123456, 3.2, 2.8, 0.4]}]})

        assert ("THYAO", "1m", "RSI") in updates
        assert ("THYAO", "1m", "MACD") in updates

    def test_callback_exception_handling(self, stream):
        """Test that callback exceptions don't break session."""
        session = StudySession(stream)

        def bad_callback(symbol, interval, indicator, values):
            raise ValueError("Test error")

        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
            ready=True,
        )
        session._studies = {"THYAO": {"1m": {"RSI": study}}}
        session._study_id_map = {"st1": ("THYAO", "1m", "RSI")}
        session._callbacks["THYAO:1m:RSI"] = [bad_callback]

        # Should not raise - use handle_study_data (actual method)
        session.handle_study_data("st1", {"st": [{"i": 0, "v": [1737123456, 48.5]}]})


class TestStudySessionMessageHandling:
    """Tests for StudySession message handling."""

    @pytest.fixture
    def study_session(self, stream):
        """Create a StudySession for testing."""
        return StudySession(stream)

    def test_handle_study_loading(self, study_session):
        """Test handle_study_loading() marks study as loading."""
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
        )
        study_session._studies = {"THYAO": {"1m": {"RSI": study}}}
        study_session._study_id_map = {"st1": ("THYAO", "1m", "RSI")}

        study_session.handle_study_loading("st1")

        # Study should still not be ready
        assert study.ready is False

    def test_handle_study_completed(self, study_session):
        """Test handle_study_completed() marks study as ready."""
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
        )
        study_session._studies = {"THYAO": {"1m": {"RSI": study}}}
        study_session._study_id_map = {"st1": ("THYAO", "1m", "RSI")}

        study_session.handle_study_completed("st1")

        # handle_study_completed only marks study as ready
        # events are set in handle_study_data when values are received
        assert study.ready is True

    def test_handle_study_error(self, study_session, caplog):
        """Test handle_study_error() logs error."""
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
        )
        study_session._studies = {"THYAO": {"1m": {"RSI": study}}}
        study_session._study_id_map = {"st1": ("THYAO", "1m", "RSI")}

        # Should not raise, just log warning
        study_session.handle_study_error("st1", "Test error")

        # Should have logged a warning
        assert "Study error for st1: Test error" in caplog.text

    def test_handle_study_data(self, study_session):
        """Test handle_study_data() updates study values."""
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
            ready=True,
        )
        study_session._studies = {"THYAO": {"1m": {"RSI": study}}}
        study_session._study_id_map = {"st1": ("THYAO", "1m", "RSI")}

        # Simulate study data
        data = {
            "st": [
                {"i": 0, "v": [1737123456, 48.5]},
            ]
        }

        study_session.handle_study_data("st1", data)

        # Values should be updated
        assert study.values.get("value") == 48.5 or study.values.get("plot_0") == 48.5


class TestStudySessionWaitFor:
    """Tests for StudySession wait_for functionality."""

    @pytest.fixture
    def study_session(self, stream):
        """Create a StudySession for testing."""
        return StudySession(stream)

    def test_wait_for_returns_immediately_if_ready(self, study_session):
        """Test wait_for() returns immediately if study is ready."""
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
            values={"value": 48.5},
            ready=True,
        )
        study_session._studies = {"THYAO": {"1m": {"RSI": study}}}

        values = study_session.wait_for("THYAO", "1m", "RSI", timeout=1.0)

        assert values == {"value": 48.5}

    def test_wait_for_timeout(self, study_session):
        """Test wait_for() raises TimeoutError on timeout."""
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
            values={},
            ready=False,  # Not ready
        )
        study_session._studies = {"THYAO": {"1m": {"RSI": study}}}
        study_session._study_events["st1"] = threading.Event()

        with pytest.raises(TimeoutError, match="Timeout"):
            study_session.wait_for("THYAO", "1m", "RSI", timeout=0.1)

    def test_wait_for_nonexistent(self, study_session):
        """Test wait_for() raises TimeoutError for nonexistent study."""
        # wait_for() creates an event and waits, but if study doesn't exist
        # it will timeout since no data will ever arrive
        with pytest.raises(TimeoutError, match="Timeout"):
            study_session.wait_for("THYAO", "1m", "RSI", timeout=0.1)


# =============================================================================
# Unit Tests - TradingViewStream Study Convenience Methods
# =============================================================================


class TestStreamStudyMethods:
    """Tests for TradingViewStream study convenience methods."""

    def test_studies_property(self, stream):
        """Test studies property returns StudySession."""
        session = stream.studies

        assert isinstance(session, StudySession)
        assert session._stream is stream

    def test_studies_property_singleton(self, stream):
        """Test studies property returns same instance."""
        session1 = stream.studies
        session2 = stream.studies

        assert session1 is session2

    def test_add_study_delegates_to_session(self, stream):
        """Test add_study() delegates to StudySession."""
        # Mock chart subscription
        stream._chart_subscribed = {"THYAO": {"1m"}}
        stream._chart_session_id = "cs_test"

        # Mock pine facade
        with patch.object(StudySession, "_get_pine_facade") as mock_get_pf:
            mock_pf = MagicMock()
            mock_pf.get_indicator.return_value = {"pineId": "STD;RSI", "inputs": {}}
            mock_get_pf.return_value = mock_pf

            study_id = stream.add_study("THYAO", "1m", "RSI")

            assert study_id.startswith("st")

    def test_get_study_delegates_to_session(self, stream):
        """Test get_study() delegates to StudySession."""
        # Setup study in session
        study = PineStudy(
            indicator_id="STD;RSI",
            study_id="st1",
            symbol="THYAO",
            interval="1m",
            values={"value": 48.5},
            ready=True,
        )
        stream.studies._studies = {"THYAO": {"1m": {"RSI": study}}}

        values = stream.get_study("THYAO", "1m", "RSI")

        assert values == {"value": 48.5}

    def test_get_studies_delegates_to_session(self, stream):
        """Test get_studies() delegates to StudySession."""
        # Setup studies in session
        stream.studies._studies = {
            "THYAO": {
                "1m": {
                    "RSI": PineStudy(
                        indicator_id="STD;RSI",
                        study_id="st1",
                        symbol="THYAO",
                        interval="1m",
                        values={"value": 48.5},
                        ready=True,
                    ),
                }
            }
        }

        all_studies = stream.get_studies("THYAO", "1m")

        assert "RSI" in all_studies

    def test_on_study_registers_callback(self, stream):
        """Test on_study() registers callback via StudySession."""
        def callback(symbol, interval, indicator, values):
            pass

        stream.on_study("THYAO", "1m", "RSI", callback)

        assert callback in stream.studies._callbacks.get("THYAO:1m:RSI", [])

    def test_on_any_study_registers_global_callback(self, stream):
        """Test on_any_study() registers global callback."""
        def callback(symbol, interval, indicator, values):
            pass

        stream.on_any_study(callback)

        assert callback in stream.studies._global_callbacks


# =============================================================================
# Study Integration Tests
# =============================================================================


@pytest.mark.integration
class TestStudyIntegration:
    """Integration tests for study functionality (require network)."""

    def test_add_study_and_get_values(self):
        """Test real study subscription and value retrieval."""
        stream = TradingViewStream()

        try:
            stream.connect(timeout=10)
            stream.subscribe_chart("THYAO", "1m")

            # Add RSI study
            stream.add_study("THYAO", "1m", "RSI")

            # Wait for study values
            values = stream.wait_for_study("THYAO", "1m", "RSI", timeout=15)

            assert values is not None
            assert "value" in values or "plot_0" in values

        finally:
            stream.disconnect()

    def test_multiple_studies(self):
        """Test multiple studies on same chart."""
        stream = TradingViewStream()

        try:
            stream.connect(timeout=10)
            stream.subscribe_chart("THYAO", "1m")

            # Add multiple studies
            stream.add_study("THYAO", "1m", "RSI")
            stream.add_study("THYAO", "1m", "MACD")

            # Wait for values
            rsi = stream.wait_for_study("THYAO", "1m", "RSI", timeout=15)
            macd = stream.wait_for_study("THYAO", "1m", "MACD", timeout=15)

            assert rsi is not None
            assert macd is not None

        finally:
            stream.disconnect()

    def test_study_callback_receives_updates(self):
        """Test that study callback receives updates."""
        stream = TradingViewStream()
        updates = []

        def on_study(symbol, interval, indicator, values):
            updates.append((symbol, interval, indicator, values))

        try:
            stream.connect(timeout=10)
            stream.subscribe_chart("THYAO", "1m")
            stream.add_study("THYAO", "1m", "RSI")
            stream.on_study("THYAO", "1m", "RSI", on_study)

            # Wait for some updates
            time.sleep(10)

            # Should have received at least one update
            assert len(updates) > 0
            assert updates[0][0] == "THYAO"
            assert updates[0][2] == "RSI"

        finally:
            stream.disconnect()
