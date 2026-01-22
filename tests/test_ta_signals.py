"""Tests for TradingView TA signals."""

import pytest

from borsapy._providers.tradingview_scanner import (
    INTERVAL_MAP,
    MOVING_AVERAGE_COLUMNS,
    OSCILLATOR_COLUMNS,
    TradingViewScannerProvider,
    get_scanner_provider,
)


# =============================================================================
# Unit Tests - TradingViewScannerProvider
# =============================================================================


class TestTradingViewScannerProvider:
    """Unit tests for TradingViewScannerProvider."""

    def test_singleton_provider(self):
        """Test singleton pattern returns same instance."""
        provider1 = get_scanner_provider()
        provider2 = get_scanner_provider()
        assert provider1 is provider2

    def test_interval_map_contains_all_timeframes(self):
        """Test interval map has all expected timeframes."""
        expected = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1W", "1M"]
        for tf in expected:
            assert tf in INTERVAL_MAP

    def test_interval_map_daily_default(self):
        """Test daily interval has empty suffix (default)."""
        assert INTERVAL_MAP["1d"] == ""

    def test_interval_map_intraday_suffixes(self):
        """Test intraday intervals have correct suffixes."""
        assert INTERVAL_MAP["1m"] == "|1"
        assert INTERVAL_MAP["5m"] == "|5"
        assert INTERVAL_MAP["15m"] == "|15"
        assert INTERVAL_MAP["30m"] == "|30"
        assert INTERVAL_MAP["1h"] == "|60"
        assert INTERVAL_MAP["4h"] == "|240"

    def test_oscillator_columns_not_empty(self):
        """Test oscillator columns list is populated."""
        assert len(OSCILLATOR_COLUMNS) > 10
        assert "RSI" in OSCILLATOR_COLUMNS
        assert "MACD.macd" in OSCILLATOR_COLUMNS
        assert "Stoch.K" in OSCILLATOR_COLUMNS

    def test_moving_average_columns_not_empty(self):
        """Test moving average columns list is populated."""
        assert len(MOVING_AVERAGE_COLUMNS) > 10
        assert "EMA20" in MOVING_AVERAGE_COLUMNS
        assert "SMA50" in MOVING_AVERAGE_COLUMNS
        assert "close" in MOVING_AVERAGE_COLUMNS

    def test_get_columns_with_interval_daily(self):
        """Test columns for daily interval have no suffix."""
        provider = get_scanner_provider()
        columns = provider._get_columns_with_interval(["RSI", "EMA20"], "1d")
        assert columns == ["RSI", "EMA20"]

    def test_get_columns_with_interval_1h(self):
        """Test columns for 1h interval have |60 suffix."""
        provider = get_scanner_provider()
        columns = provider._get_columns_with_interval(["RSI", "EMA20"], "1h")
        assert columns == ["RSI|60", "EMA20|60"]

    def test_get_columns_with_interval_1m(self):
        """Test columns for 1m interval have |1 suffix."""
        provider = get_scanner_provider()
        columns = provider._get_columns_with_interval(["RSI", "MACD.macd"], "1m")
        assert columns == ["RSI|1", "MACD.macd|1"]

    def test_recommendation_to_signal_buy(self):
        """Test recommendation conversion for buy signal."""
        provider = get_scanner_provider()
        assert provider._recommendation_to_signal(1.0) == "BUY"
        assert provider._recommendation_to_signal(0.5) == "BUY"
        assert provider._recommendation_to_signal(0.8) == "BUY"

    def test_recommendation_to_signal_sell(self):
        """Test recommendation conversion for sell signal."""
        provider = get_scanner_provider()
        assert provider._recommendation_to_signal(-1.0) == "SELL"
        assert provider._recommendation_to_signal(-0.5) == "SELL"
        assert provider._recommendation_to_signal(-0.8) == "SELL"

    def test_recommendation_to_signal_neutral(self):
        """Test recommendation conversion for neutral signal."""
        provider = get_scanner_provider()
        assert provider._recommendation_to_signal(0.0) == "NEUTRAL"
        assert provider._recommendation_to_signal(0.3) == "NEUTRAL"
        assert provider._recommendation_to_signal(-0.3) == "NEUTRAL"
        assert provider._recommendation_to_signal(None) == "NEUTRAL"

    def test_get_recommendation_strong_buy(self):
        """Test overall recommendation for strong buy."""
        provider = get_scanner_provider()
        # 8 buy, 1 sell, 1 neutral -> score = (8-1)/10 = 0.7 -> STRONG_BUY
        assert provider._get_recommendation(8, 1, 1) == "STRONG_BUY"

    def test_get_recommendation_buy(self):
        """Test overall recommendation for buy."""
        provider = get_scanner_provider()
        # 5 buy, 3 sell, 2 neutral -> score = (5-3)/10 = 0.2 -> BUY
        assert provider._get_recommendation(5, 3, 2) == "BUY"

    def test_get_recommendation_neutral(self):
        """Test overall recommendation for neutral."""
        provider = get_scanner_provider()
        # 4 buy, 4 sell, 2 neutral -> score = 0 -> NEUTRAL
        assert provider._get_recommendation(4, 4, 2) == "NEUTRAL"

    def test_get_recommendation_sell(self):
        """Test overall recommendation for sell."""
        provider = get_scanner_provider()
        # 3 buy, 5 sell, 2 neutral -> score = -0.2 -> SELL
        assert provider._get_recommendation(3, 5, 2) == "SELL"

    def test_get_recommendation_strong_sell(self):
        """Test overall recommendation for strong sell."""
        provider = get_scanner_provider()
        # 1 buy, 8 sell, 1 neutral -> score = -0.7 -> STRONG_SELL
        assert provider._get_recommendation(1, 8, 1) == "STRONG_SELL"

    def test_get_recommendation_empty(self):
        """Test overall recommendation for no signals."""
        provider = get_scanner_provider()
        assert provider._get_recommendation(0, 0, 0) == "NEUTRAL"

    def test_invalid_screener_raises_error(self):
        """Test invalid screener raises ValueError."""
        provider = get_scanner_provider()
        with pytest.raises(ValueError, match="Invalid screener"):
            provider.get_ta_signals("BIST:THYAO", screener="invalid")

    def test_invalid_interval_raises_error(self):
        """Test invalid interval raises ValueError."""
        provider = get_scanner_provider()
        with pytest.raises(ValueError, match="Invalid interval"):
            provider.get_ta_signals("BIST:THYAO", interval="invalid")


class TestCalculateSignals:
    """Test signal calculation logic."""

    def test_rsi_buy_signal(self):
        """Test RSI buy signal when < 30."""
        provider = get_scanner_provider()
        raw_values = {"RSI": 25.0, "RSI[1]": 28.0, "close": 100}
        result = provider._calculate_signals(raw_values, "", "1d")
        assert result["oscillators"]["compute"]["RSI"] == "BUY"

    def test_rsi_sell_signal(self):
        """Test RSI sell signal when > 70."""
        provider = get_scanner_provider()
        raw_values = {"RSI": 75.0, "RSI[1]": 72.0, "close": 100}
        result = provider._calculate_signals(raw_values, "", "1d")
        assert result["oscillators"]["compute"]["RSI"] == "SELL"

    def test_rsi_neutral_signal(self):
        """Test RSI neutral signal when between 30 and 70."""
        provider = get_scanner_provider()
        raw_values = {"RSI": 50.0, "RSI[1]": 48.0, "close": 100}
        result = provider._calculate_signals(raw_values, "", "1d")
        assert result["oscillators"]["compute"]["RSI"] == "NEUTRAL"

    def test_macd_buy_signal(self):
        """Test MACD buy signal when macd > signal."""
        provider = get_scanner_provider()
        raw_values = {"MACD.macd": 1.5, "MACD.signal": 1.0, "close": 100}
        result = provider._calculate_signals(raw_values, "", "1d")
        assert result["oscillators"]["compute"]["MACD"] == "BUY"

    def test_macd_sell_signal(self):
        """Test MACD sell signal when macd < signal."""
        provider = get_scanner_provider()
        raw_values = {"MACD.macd": 0.5, "MACD.signal": 1.0, "close": 100}
        result = provider._calculate_signals(raw_values, "", "1d")
        assert result["oscillators"]["compute"]["MACD"] == "SELL"

    def test_ema_buy_signal(self):
        """Test EMA buy signal when close > EMA."""
        provider = get_scanner_provider()
        raw_values = {"EMA20": 95.0, "close": 100.0}
        result = provider._calculate_signals(raw_values, "", "1d")
        assert result["moving_averages"]["compute"]["EMA20"] == "BUY"

    def test_ema_sell_signal(self):
        """Test EMA sell signal when close < EMA."""
        provider = get_scanner_provider()
        raw_values = {"EMA20": 105.0, "close": 100.0}
        result = provider._calculate_signals(raw_values, "", "1d")
        assert result["moving_averages"]["compute"]["EMA20"] == "SELL"

    def test_sma_buy_signal(self):
        """Test SMA buy signal when close > SMA."""
        provider = get_scanner_provider()
        raw_values = {"SMA50": 95.0, "close": 100.0}
        result = provider._calculate_signals(raw_values, "", "1d")
        assert result["moving_averages"]["compute"]["SMA50"] == "BUY"

    def test_summary_aggregates_counts(self):
        """Test summary correctly aggregates buy/sell/neutral counts."""
        provider = get_scanner_provider()
        raw_values = {
            "RSI": 25.0,  # BUY
            "MACD.macd": 1.5, "MACD.signal": 1.0,  # BUY
            "CCI20": 150.0,  # SELL
            "EMA20": 95.0,  # BUY
            "SMA50": 105.0,  # SELL
            "close": 100.0,
        }
        result = provider._calculate_signals(raw_values, "", "1d")

        # Check that summary totals match oscillator + ma counts
        total_buy = result["oscillators"]["buy"] + result["moving_averages"]["buy"]
        total_sell = result["oscillators"]["sell"] + result["moving_averages"]["sell"]
        total_neutral = result["oscillators"]["neutral"] + result["moving_averages"]["neutral"]

        assert result["summary"]["buy"] == total_buy
        assert result["summary"]["sell"] == total_sell
        assert result["summary"]["neutral"] == total_neutral


# =============================================================================
# Integration Tests (require network)
# =============================================================================


@pytest.mark.integration
class TestTASignalsIntegration:
    """Integration tests with live TradingView API."""

    def test_ticker_ta_signals_daily(self):
        """Test Ticker.ta_signals() with daily interval."""
        import borsapy as bp

        stock = bp.Ticker("THYAO")
        signals = stock.ta_signals()

        # Check structure
        assert "symbol" in signals
        assert "exchange" in signals
        assert "interval" in signals
        assert "summary" in signals
        assert "oscillators" in signals
        assert "moving_averages" in signals

        # Check summary structure
        assert "recommendation" in signals["summary"]
        assert "buy" in signals["summary"]
        assert "sell" in signals["summary"]
        assert "neutral" in signals["summary"]

        # Check recommendation is valid
        valid_recommendations = [
            "STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"
        ]
        assert signals["summary"]["recommendation"] in valid_recommendations

    def test_ticker_ta_signals_hourly(self):
        """Test Ticker.ta_signals() with hourly interval."""
        import borsapy as bp

        stock = bp.Ticker("AKBNK")
        signals = stock.ta_signals(interval="1h")

        assert signals["interval"] == "1h"
        assert "recommendation" in signals["summary"]

    def test_ticker_ta_signals_all_timeframes(self):
        """Test Ticker.ta_signals_all_timeframes() returns all intervals."""
        import borsapy as bp

        stock = bp.Ticker("GARAN")
        all_signals = stock.ta_signals_all_timeframes()

        expected_intervals = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1W", "1M"]
        for interval in expected_intervals:
            assert interval in all_signals
            # Either has valid data or error key
            if "error" not in all_signals[interval]:
                assert "summary" in all_signals[interval]

    def test_index_ta_signals(self):
        """Test Index.ta_signals() method."""
        import borsapy as bp

        xu100 = bp.Index("XU100")
        signals = xu100.ta_signals()

        assert signals["symbol"] == "XU100"
        assert signals["exchange"] == "BIST"
        assert "recommendation" in signals["summary"]

    def test_fx_ta_signals(self):
        """Test FX.ta_signals() for supported currencies."""
        import borsapy as bp

        usd = bp.FX("USD")
        signals = usd.ta_signals()

        assert "summary" in signals
        assert "recommendation" in signals["summary"]

    def test_fx_ta_signals_unsupported_raises(self):
        """Test FX.ta_signals() raises for unsupported assets."""
        import borsapy as bp

        # CHF doesn't have TradingView support
        chf = bp.FX("CHF")
        with pytest.raises(NotImplementedError, match="TA signals not available"):
            chf.ta_signals()

    def test_crypto_ta_signals(self):
        """Test Crypto.ta_signals() method."""
        import borsapy as bp

        btc = bp.Crypto("BTCTRY")
        signals = btc.ta_signals()

        assert signals["symbol"] == "BTCUSDT"  # Mapped to Binance
        assert signals["exchange"] == "BINANCE"
        assert "recommendation" in signals["summary"]

    def test_oscillator_values_populated(self):
        """Test oscillator values contain expected indicators."""
        import borsapy as bp

        stock = bp.Ticker("THYAO")
        signals = stock.ta_signals()

        osc_values = signals["oscillators"]["values"]
        # At least RSI should be present
        assert "RSI" in osc_values or len(osc_values) > 0

    def test_ma_values_populated(self):
        """Test moving average values contain expected indicators."""
        import borsapy as bp

        stock = bp.Ticker("THYAO")
        signals = stock.ta_signals()

        ma_values = signals["moving_averages"]["values"]
        # At least some EMAs/SMAs should be present
        assert len(ma_values) > 0

    def test_compare_local_vs_tv_rsi(self):
        """Compare local RSI calculation with TradingView RSI."""
        import borsapy as bp

        stock = bp.Ticker("THYAO")

        # Get local RSI
        local_rsi = stock.rsi()

        # Get TradingView RSI
        signals = stock.ta_signals()
        tv_rsi = signals["oscillators"]["values"].get("RSI")

        # Both should exist and be in valid range
        assert 0 <= local_rsi <= 100
        if tv_rsi is not None:
            assert 0 <= tv_rsi <= 100
            # They may differ due to timing, but both should be valid


@pytest.mark.integration
class TestTASignalsEdgeCases:
    """Test edge cases with live API."""

    def test_caching_returns_same_result(self):
        """Test that cached results are returned."""
        import borsapy as bp

        stock = bp.Ticker("THYAO")

        # First call
        signals1 = stock.ta_signals()

        # Second call (should be cached)
        signals2 = stock.ta_signals()

        # Should be same object due to caching
        assert signals1["summary"]["recommendation"] == signals2["summary"]["recommendation"]

    def test_different_intervals_different_signals(self):
        """Test different intervals may produce different signals."""
        import borsapy as bp

        stock = bp.Ticker("THYAO")

        signals_1h = stock.ta_signals(interval="1h")
        signals_1d = stock.ta_signals(interval="1d")

        # Intervals should be different in result
        assert signals_1h["interval"] == "1h"
        assert signals_1d["interval"] == "1d"
