"""Tests for technical analysis indicators."""

import numpy as np
import pandas as pd
import pytest

from borsapy.technical import (
    TechnicalAnalyzer,
    add_indicators,
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

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def simple_df():
    """Simple DataFrame for basic tests."""
    return pd.DataFrame(
        {
            "Close": [100, 102, 101, 103, 104, 102, 105, 106, 104, 107],
        },
        index=pd.date_range("2024-01-01", periods=10, freq="D"),
    )


@pytest.fixture
def ohlcv_df():
    """OHLCV DataFrame for full tests."""
    np.random.seed(42)
    n = 50
    close = 100 + np.cumsum(np.random.randn(n) * 2)
    high = close + np.abs(np.random.randn(n) * 1)
    low = close - np.abs(np.random.randn(n) * 1)
    open_ = close + np.random.randn(n) * 0.5
    volume = np.random.randint(100000, 500000, n)

    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="D"),
    )


@pytest.fixture
def no_volume_df(ohlcv_df):
    """OHLC DataFrame without Volume."""
    return ohlcv_df.drop(columns=["Volume"])


@pytest.fixture
def empty_df():
    """Empty DataFrame for edge case tests."""
    return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


# =============================================================================
# SMA Tests
# =============================================================================


class TestSMA:
    """Tests for Simple Moving Average."""

    def test_sma_basic(self, simple_df):
        """Test SMA calculation with simple data."""
        sma = calculate_sma(simple_df, period=3)
        assert len(sma) == 10
        # Last 3 values: 104, 106, 107 -> mean = 105.67
        assert abs(sma.iloc[-1] - (104 + 106 + 107) / 3) < 0.01

    def test_sma_period_5(self, ohlcv_df):
        """Test SMA with period 5."""
        sma = calculate_sma(ohlcv_df, period=5)
        assert len(sma) == len(ohlcv_df)
        # First 4 values should be partial averages (min_periods=1)
        assert not np.isnan(sma.iloc[0])

    def test_sma_missing_column(self, simple_df):
        """Test SMA with missing column."""
        sma = calculate_sma(simple_df, column="NonExistent")
        assert np.isnan(sma.iloc[-1])


# =============================================================================
# EMA Tests
# =============================================================================


class TestEMA:
    """Tests for Exponential Moving Average."""

    def test_ema_basic(self, simple_df):
        """Test EMA calculation."""
        ema = calculate_ema(simple_df, period=5)
        assert len(ema) == 10
        # EMA should be close to price for recent values
        assert not np.isnan(ema.iloc[-1])

    def test_ema_vs_sma(self, ohlcv_df):
        """EMA should give more weight to recent values than SMA."""
        ema = calculate_ema(ohlcv_df, period=10)
        sma = calculate_sma(ohlcv_df, period=10)
        # Both should be similar but not identical
        assert abs(ema.iloc[-1] - sma.iloc[-1]) < 10


# =============================================================================
# RSI Tests
# =============================================================================


class TestRSI:
    """Tests for Relative Strength Index."""

    def test_rsi_bounds(self, ohlcv_df):
        """RSI should always be between 0 and 100."""
        rsi = calculate_rsi(ohlcv_df, period=14)
        assert rsi.min() >= 0
        assert rsi.max() <= 100

    def test_rsi_default_period(self, ohlcv_df):
        """Test RSI with default period of 14."""
        rsi = calculate_rsi(ohlcv_df)
        assert len(rsi) == len(ohlcv_df)

    def test_rsi_short_data(self):
        """Test RSI with insufficient data."""
        short_df = pd.DataFrame({"Close": [100, 101, 102]})
        rsi = calculate_rsi(short_df, period=14)
        # Should still return series with NaN or neutral values
        assert len(rsi) == 3


# =============================================================================
# MACD Tests
# =============================================================================


class TestMACD:
    """Tests for MACD."""

    def test_macd_columns(self, ohlcv_df):
        """MACD should return DataFrame with correct columns."""
        macd = calculate_macd(ohlcv_df)
        assert "MACD" in macd.columns
        assert "Signal" in macd.columns
        assert "Histogram" in macd.columns

    def test_macd_histogram(self, ohlcv_df):
        """Histogram should be MACD - Signal."""
        macd = calculate_macd(ohlcv_df)
        expected_hist = macd["MACD"] - macd["Signal"]
        np.testing.assert_array_almost_equal(macd["Histogram"], expected_hist)

    def test_macd_custom_periods(self, ohlcv_df):
        """Test MACD with custom periods."""
        macd = calculate_macd(ohlcv_df, fast=8, slow=21, signal=5)
        assert len(macd) == len(ohlcv_df)


# =============================================================================
# Bollinger Bands Tests
# =============================================================================


class TestBollingerBands:
    """Tests for Bollinger Bands."""

    def test_bollinger_columns(self, ohlcv_df):
        """Bollinger should return DataFrame with correct columns."""
        bb = calculate_bollinger_bands(ohlcv_df)
        assert "BB_Upper" in bb.columns
        assert "BB_Middle" in bb.columns
        assert "BB_Lower" in bb.columns

    def test_bollinger_relationship(self, ohlcv_df):
        """Upper > Middle > Lower always."""
        bb = calculate_bollinger_bands(ohlcv_df)
        # After warmup period
        valid_idx = bb.index[20:]
        assert (bb.loc[valid_idx, "BB_Upper"] >= bb.loc[valid_idx, "BB_Middle"]).all()
        assert (bb.loc[valid_idx, "BB_Middle"] >= bb.loc[valid_idx, "BB_Lower"]).all()

    def test_bollinger_std_dev(self, ohlcv_df):
        """Test with different standard deviation."""
        bb_2 = calculate_bollinger_bands(ohlcv_df, std_dev=2.0)
        bb_3 = calculate_bollinger_bands(ohlcv_df, std_dev=3.0)
        # 3 std dev bands should be wider
        width_2 = bb_2["BB_Upper"].iloc[-1] - bb_2["BB_Lower"].iloc[-1]
        width_3 = bb_3["BB_Upper"].iloc[-1] - bb_3["BB_Lower"].iloc[-1]
        assert width_3 > width_2


# =============================================================================
# ATR Tests
# =============================================================================


class TestATR:
    """Tests for Average True Range."""

    def test_atr_requires_hlc(self, simple_df):
        """ATR requires High, Low, Close columns."""
        atr = calculate_atr(simple_df)
        assert np.isnan(atr.iloc[-1])

    def test_atr_positive(self, ohlcv_df):
        """ATR should always be positive."""
        atr = calculate_atr(ohlcv_df)
        valid_atr = atr.dropna()
        assert (valid_atr >= 0).all()

    def test_atr_period(self, ohlcv_df):
        """Test ATR with different periods."""
        atr_7 = calculate_atr(ohlcv_df, period=7)
        atr_14 = calculate_atr(ohlcv_df, period=14)
        # Both should be valid
        assert not np.isnan(atr_7.iloc[-1])
        assert not np.isnan(atr_14.iloc[-1])


# =============================================================================
# Stochastic Tests
# =============================================================================


class TestStochastic:
    """Tests for Stochastic Oscillator."""

    def test_stochastic_bounds(self, ohlcv_df):
        """Stochastic should be between 0 and 100."""
        stoch = calculate_stochastic(ohlcv_df)
        # Skip NaN values
        valid_k = stoch["Stoch_K"].dropna()
        valid_d = stoch["Stoch_D"].dropna()
        assert valid_k.min() >= 0
        assert valid_k.max() <= 100
        assert valid_d.min() >= 0
        assert valid_d.max() <= 100

    def test_stochastic_columns(self, ohlcv_df):
        """Stochastic should return %K and %D."""
        stoch = calculate_stochastic(ohlcv_df)
        assert "Stoch_K" in stoch.columns
        assert "Stoch_D" in stoch.columns


# =============================================================================
# OBV Tests
# =============================================================================


class TestOBV:
    """Tests for On-Balance Volume."""

    def test_obv_requires_volume(self, no_volume_df):
        """OBV requires Volume column."""
        obv = calculate_obv(no_volume_df)
        assert np.isnan(obv.iloc[-1])

    def test_obv_cumulative(self, ohlcv_df):
        """OBV should be cumulative."""
        obv = calculate_obv(ohlcv_df)
        # OBV changes with each bar
        assert len(obv) == len(ohlcv_df)


# =============================================================================
# VWAP Tests
# =============================================================================


class TestVWAP:
    """Tests for Volume Weighted Average Price."""

    def test_vwap_requires_all(self, no_volume_df):
        """VWAP requires HLC and Volume."""
        vwap = calculate_vwap(no_volume_df)
        assert np.isnan(vwap.iloc[-1])

    def test_vwap_in_range(self, ohlcv_df):
        """VWAP should be within price range."""
        vwap = calculate_vwap(ohlcv_df)
        last_vwap = vwap.iloc[-1]
        # VWAP should be in reasonable range of prices
        assert ohlcv_df["Low"].min() <= last_vwap <= ohlcv_df["High"].max()


# =============================================================================
# ADX Tests
# =============================================================================


class TestADX:
    """Tests for Average Directional Index."""

    def test_adx_bounds(self, ohlcv_df):
        """ADX should be between 0 and 100."""
        adx = calculate_adx(ohlcv_df)
        valid_adx = adx.dropna()
        assert valid_adx.min() >= 0
        assert valid_adx.max() <= 100

    def test_adx_requires_hlc(self, simple_df):
        """ADX requires High, Low, Close columns."""
        adx = calculate_adx(simple_df)
        assert np.isnan(adx.iloc[-1])


# =============================================================================
# add_indicators Tests
# =============================================================================


class TestAddIndicators:
    """Tests for add_indicators convenience function."""

    def test_add_all_indicators(self, ohlcv_df):
        """Test adding all applicable indicators."""
        result = add_indicators(ohlcv_df)
        # Should have original columns plus indicators
        assert "Close" in result.columns
        assert "SMA_20" in result.columns
        assert "RSI_14" in result.columns
        assert "MACD" in result.columns

    def test_add_specific_indicators(self, ohlcv_df):
        """Test adding specific indicators."""
        result = add_indicators(ohlcv_df, indicators=["sma", "rsi"])
        assert "SMA_20" in result.columns
        assert "RSI_14" in result.columns
        # Should not have MACD if not requested
        assert "MACD" not in result.columns

    def test_custom_periods(self, ohlcv_df):
        """Test with custom periods."""
        result = add_indicators(ohlcv_df, sma_period=50, rsi_period=7)
        assert "SMA_50" in result.columns
        assert "RSI_7" in result.columns


# =============================================================================
# TechnicalAnalyzer Tests
# =============================================================================


class TestTechnicalAnalyzer:
    """Tests for TechnicalAnalyzer class."""

    def test_analyzer_init(self, ohlcv_df):
        """Test analyzer initialization."""
        ta = TechnicalAnalyzer(ohlcv_df)
        assert ta._df is not None

    def test_analyzer_methods(self, ohlcv_df):
        """Test all analyzer methods return valid data."""
        ta = TechnicalAnalyzer(ohlcv_df)

        assert len(ta.sma(20)) == len(ohlcv_df)
        assert len(ta.ema(12)) == len(ohlcv_df)
        assert len(ta.rsi(14)) == len(ohlcv_df)
        assert "MACD" in ta.macd().columns
        assert "BB_Upper" in ta.bollinger_bands().columns
        assert len(ta.atr(14)) == len(ohlcv_df)
        assert "Stoch_K" in ta.stochastic().columns
        assert len(ta.obv()) == len(ohlcv_df)
        assert len(ta.vwap()) == len(ohlcv_df)
        assert len(ta.adx(14)) == len(ohlcv_df)

    def test_analyzer_latest(self, ohlcv_df):
        """Test latest property returns dict with all indicators."""
        ta = TechnicalAnalyzer(ohlcv_df)
        latest = ta.latest

        assert isinstance(latest, dict)
        assert "sma_20" in latest
        assert "rsi_14" in latest
        assert "macd" in latest
        assert "bb_upper" in latest
        assert "atr_14" in latest
        assert "obv" in latest

    def test_analyzer_all(self, ohlcv_df):
        """Test all() method returns DataFrame with indicators."""
        ta = TechnicalAnalyzer(ohlcv_df)
        result = ta.all()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(ohlcv_df)
        assert "SMA_20" in result.columns


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_dataframe(self, empty_df):
        """Test with empty DataFrame."""
        sma = calculate_sma(empty_df)
        rsi = calculate_rsi(empty_df)
        assert len(sma) == 0
        assert len(rsi) == 0

    def test_single_row(self):
        """Test with single row DataFrame."""
        df = pd.DataFrame({"Close": [100]}, index=pd.date_range("2024-01-01", periods=1))
        sma = calculate_sma(df, period=20)
        assert len(sma) == 1

    def test_nan_in_data(self):
        """Test with NaN values in data."""
        df = pd.DataFrame(
            {"Close": [100, np.nan, 102, 103, 104]},
            index=pd.date_range("2024-01-01", periods=5),
        )
        sma = calculate_sma(df, period=3)
        # Should handle NaN gracefully
        assert len(sma) == 5


# =============================================================================
# Integration Tests (require network)
# =============================================================================


@pytest.mark.integration
class TestIntegration:
    """Integration tests with live API (marked for optional execution)."""

    def test_ticker_rsi(self):
        """Test Ticker.rsi() method."""
        import borsapy as bp

        stock = bp.Ticker("THYAO")
        rsi = stock.rsi()
        assert 0 <= rsi <= 100

    def test_ticker_technicals(self):
        """Test Ticker.technicals() method."""
        import borsapy as bp

        stock = bp.Ticker("THYAO")
        ta = stock.technicals(period="3mo")
        latest = ta.latest
        assert "rsi_14" in latest

    def test_ticker_history_with_indicators(self):
        """Test Ticker.history_with_indicators() method."""
        import borsapy as bp

        stock = bp.Ticker("THYAO")
        df = stock.history_with_indicators(period="1mo")
        assert "RSI_14" in df.columns
        assert "SMA_20" in df.columns
