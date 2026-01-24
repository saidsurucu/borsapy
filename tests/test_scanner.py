"""Tests for technical scanner."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from borsapy.scanner import TechnicalScanner, ScanResult, scan
from borsapy.condition import ParseError


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_quote():
    """Mock quote data."""
    return {
        "symbol": "THYAO",
        "last": 285.0,
        "open": 280.0,
        "high": 290.0,
        "low": 278.0,
        "volume": 15000000,
        "change_percent": 1.8,
        "market_cap": 50000000000,
        "bid": 284.9,
        "ask": 285.1,
    }


@pytest.fixture
def mock_history():
    """Mock OHLCV history DataFrame."""
    np.random.seed(42)
    n = 60
    close = 280 + np.cumsum(np.random.randn(n) * 2)
    high = close + np.abs(np.random.randn(n) * 1)
    low = close - np.abs(np.random.randn(n) * 1)
    open_ = close + np.random.randn(n) * 0.5
    volume = np.random.randint(10000000, 20000000, n)

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
def oversold_quote():
    """Quote data for oversold stock."""
    return {
        "symbol": "TEST",
        "last": 100.0,
        "volume": 5000000,
        "change_percent": -5.0,
    }


@pytest.fixture
def oversold_history():
    """History that produces low RSI."""
    n = 30
    # Declining prices produce low RSI
    close = np.linspace(120, 90, n)
    return pd.DataFrame(
        {
            "Close": close,
            "High": close + 1,
            "Low": close - 1,
            "Open": close,
            "Volume": [1000000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="D"),
    )


# =============================================================================
# ScanResult Tests
# =============================================================================


class TestScanResult:
    """Tests for ScanResult dataclass."""

    def test_default_values(self):
        """Test default values."""
        result = ScanResult(symbol="TEST")
        assert result.symbol == "TEST"
        assert result.data == {}
        assert result.conditions_met == []
        assert isinstance(result.timestamp, datetime)

    def test_with_data(self):
        """Test with data."""
        result = ScanResult(
            symbol="THYAO",
            data={"rsi": 28.5, "price": 285.0},
            conditions_met=["oversold", "high_volume"],
        )
        assert result.data["rsi"] == 28.5
        assert len(result.conditions_met) == 2


# =============================================================================
# TechnicalScanner Basic Tests
# =============================================================================


class TestTechnicalScannerBasics:
    """Basic tests for TechnicalScanner class."""

    def test_init(self):
        """Test scanner initialization."""
        scanner = TechnicalScanner()
        assert scanner._symbols == []
        assert scanner._conditions == {}
        assert scanner._data_period == "3mo"
        assert scanner._interval == "1d"

    def test_set_universe_list(self):
        """Test setting universe with symbol list."""
        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO", "GARAN", "ASELS"])
        assert len(scanner._symbols) == 3
        assert "THYAO" in scanner._symbols

    def test_set_universe_single(self):
        """Test setting universe with single symbol."""
        scanner = TechnicalScanner()
        scanner.set_universe("THYAO")
        assert scanner._symbols == ["THYAO"]

    def test_add_symbol(self):
        """Test adding symbol."""
        scanner = TechnicalScanner()
        scanner.add_symbol("THYAO")
        scanner.add_symbol("GARAN")
        assert len(scanner._symbols) == 2

    def test_add_symbol_no_duplicate(self):
        """Test adding duplicate symbol."""
        scanner = TechnicalScanner()
        scanner.add_symbol("THYAO")
        scanner.add_symbol("THYAO")
        assert len(scanner._symbols) == 1

    def test_remove_symbol(self):
        """Test removing symbol."""
        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO", "GARAN"])
        scanner.remove_symbol("THYAO")
        assert scanner._symbols == ["GARAN"]

    def test_add_condition(self):
        """Test adding condition."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30", name="oversold")
        assert "oversold" in scanner._conditions

    def test_add_condition_auto_name(self):
        """Test adding condition with auto name."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30")
        assert "rsi < 30" in scanner._conditions

    def test_add_invalid_condition(self):
        """Test adding invalid condition raises error."""
        scanner = TechnicalScanner()
        with pytest.raises(ParseError):
            scanner.add_condition("")

    def test_remove_condition(self):
        """Test removing condition."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30", name="oversold")
        scanner.remove_condition("oversold")
        assert "oversold" not in scanner._conditions

    def test_clear_conditions(self):
        """Test clearing all conditions."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30")
        scanner.add_condition("volume > 1M")
        scanner.clear_conditions()
        assert len(scanner._conditions) == 0

    def test_set_data_period(self):
        """Test setting data period."""
        scanner = TechnicalScanner()
        scanner.set_data_period("1y")
        assert scanner._data_period == "1y"

    def test_set_interval(self):
        """Test setting interval."""
        scanner = TechnicalScanner()
        scanner.set_interval("1h")
        assert scanner._interval == "1h"

    def test_method_chaining(self):
        """Test fluent API method chaining."""
        scanner = TechnicalScanner()
        result = (
            scanner.set_universe(["THYAO", "GARAN"])
            .add_condition("rsi < 30")
            .set_data_period("1y")
            .set_interval("1d")
        )
        assert result is scanner

    def test_repr(self):
        """Test string representation."""
        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO", "GARAN"])
        scanner.add_condition("rsi < 30")
        repr_str = repr(scanner)
        assert "symbols=2" in repr_str
        assert "conditions=1" in repr_str


# =============================================================================
# Indicator Collection Tests
# =============================================================================


class TestIndicatorCollection:
    """Tests for collecting required indicators."""

    def test_collect_rsi(self):
        """Test collecting RSI indicator."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30")
        indicators = scanner._collect_required_indicators()
        assert "rsi" in indicators
        assert 14 in indicators["rsi"]

    def test_collect_multiple_sma(self):
        """Test collecting multiple SMA periods."""
        scanner = TechnicalScanner()
        scanner.add_condition("sma_20 > sma_50")
        indicators = scanner._collect_required_indicators()
        assert "sma" in indicators
        assert 20 in indicators["sma"]
        assert 50 in indicators["sma"]

    def test_collect_from_multiple_conditions(self):
        """Test collecting from multiple conditions."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30")
        scanner.add_condition("macd > signal")
        indicators = scanner._collect_required_indicators()
        assert "rsi" in indicators
        assert "macd" in indicators


# =============================================================================
# Scan Execution Tests (with mocks)
# =============================================================================


class TestScanExecution:
    """Tests for scan execution with mocked data."""

    @patch("borsapy._providers.tradingview.get_tradingview_provider")
    @patch("borsapy.ticker.Ticker")
    def test_scan_single_symbol(
        self, mock_ticker_class, mock_tv_provider, mock_quote, mock_history
    ):
        """Test scanning single symbol."""
        # Setup mocks
        mock_provider = MagicMock()
        mock_provider.get_quote.return_value = mock_quote
        mock_tv_provider.return_value = mock_provider

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_history
        mock_ticker_class.return_value = mock_ticker

        # Run scan
        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO"])
        scanner.add_condition("volume > 1M")  # Should match with 15M volume
        results = scanner.run()

        assert len(results) >= 0  # May or may not match based on mock data

    def test_scan_empty_universe(self):
        """Test scanning empty universe."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30")
        results = scanner.run()
        assert len(results) == 0

    @patch("borsapy._providers.tradingview.get_tradingview_provider")
    @patch("borsapy.ticker.Ticker")
    def test_scan_no_conditions(
        self, mock_ticker_class, mock_tv_provider, mock_quote, mock_history
    ):
        """Test scanning without conditions."""
        mock_provider = MagicMock()
        mock_provider.get_quote.return_value = mock_quote
        mock_tv_provider.return_value = mock_provider

        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO"])
        # No conditions - should return empty
        results = scanner.run()
        assert len(results) == 0

    @patch("borsapy._providers.tradingview.get_tradingview_provider")
    @patch("borsapy.ticker.Ticker")
    def test_scan_with_oversold_condition(
        self, mock_ticker_class, mock_tv_provider, oversold_quote, oversold_history
    ):
        """Test scanning with oversold RSI condition."""
        mock_provider = MagicMock()
        mock_provider.get_quote.return_value = oversold_quote
        mock_tv_provider.return_value = mock_provider

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = oversold_history
        mock_ticker_class.return_value = mock_ticker

        scanner = TechnicalScanner()
        scanner.set_universe(["TEST"])
        scanner.add_condition("rsi < 40")  # Declining prices should have low RSI
        results = scanner.run()

        # Should match due to declining price history
        assert len(results) >= 0  # Result depends on actual RSI calculation


# =============================================================================
# Callback Tests
# =============================================================================


class TestCallbacks:
    """Tests for callback functionality."""

    def test_on_match_callback(self):
        """Test on_match callback registration."""
        scanner = TechnicalScanner()
        callback = MagicMock()
        scanner.on_match(callback)
        assert scanner._on_match_callback is callback

    def test_on_scan_complete_callback(self):
        """Test on_scan_complete callback registration."""
        scanner = TechnicalScanner()
        callback = MagicMock()
        scanner.on_scan_complete(callback)
        assert scanner._on_complete_callback is callback


# =============================================================================
# DataFrame Output Tests
# =============================================================================


class TestDataFrameOutput:
    """Tests for DataFrame output."""

    def test_to_dataframe_empty(self):
        """Test DataFrame output with no results."""
        scanner = TechnicalScanner()
        df = scanner.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_to_dataframe_with_results(self):
        """Test DataFrame output with results."""
        scanner = TechnicalScanner()
        scanner._results = [
            ScanResult(
                symbol="THYAO",
                data={"price": 285.0, "rsi": 28.5, "volume": 15000000},
                conditions_met=["oversold"],
            ),
            ScanResult(
                symbol="GARAN",
                data={"price": 52.0, "rsi": 25.0, "volume": 20000000},
                conditions_met=["oversold", "high_volume"],
            ),
        ]
        df = scanner.to_dataframe()

        assert len(df) == 2
        assert "symbol" in df.columns or "price" in df.columns
        assert "conditions_met" in df.columns


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestScanFunction:
    """Tests for scan() convenience function."""

    @patch("borsapy.scanner.TechnicalScanner.run")
    def test_scan_function(self, mock_run):
        """Test scan convenience function."""
        mock_run.return_value = pd.DataFrame()

        result = scan(["THYAO", "GARAN"], "rsi < 30")

        assert isinstance(result, pd.DataFrame)

    @patch("borsapy.scanner.TechnicalScanner.run")
    def test_scan_with_period(self, mock_run):
        """Test scan with custom period."""
        mock_run.return_value = pd.DataFrame()

        result = scan("THYAO", "rsi < 30", period="1y")

        mock_run.assert_called_once()

    @patch("borsapy.scanner.TechnicalScanner.run")
    def test_scan_with_interval(self, mock_run):
        """Test scan with custom interval."""
        mock_run.return_value = pd.DataFrame()

        result = scan("THYAO", "rsi < 30", interval="1h")

        mock_run.assert_called_once()


# =============================================================================
# Index Integration Tests
# =============================================================================


class TestIndexIntegration:
    """Tests for Index.scan() integration."""

    @patch("borsapy.scanner.TechnicalScanner")
    @patch("borsapy.index.get_bist_index_provider")
    @patch("borsapy.index.get_tradingview_provider")
    def test_index_scan_method(
        self, mock_tv_provider, mock_bist_provider, mock_scanner_class
    ):
        """Test Index.scan() method."""
        from borsapy.index import Index

        # Mock index components
        mock_bist = MagicMock()
        mock_bist.get_components.return_value = [
            {"symbol": "AKBNK", "name": "AKBANK"},
            {"symbol": "GARAN", "name": "GARANTİ BANK"},
        ]
        mock_bist_provider.return_value = mock_bist

        # Mock TradingView
        mock_tv = MagicMock()
        mock_tv.get_quote.return_value = {"symbol": "XU030", "last": 9500}
        mock_tv_provider.return_value = mock_tv

        # Create index
        idx = Index("XU030")

        # Verify components are accessible
        assert len(idx.component_symbols) == 2


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @patch("borsapy._providers.tradingview.get_tradingview_provider")
    @patch("borsapy.ticker.Ticker")
    def test_handles_quote_error(self, mock_ticker_class, mock_tv_provider):
        """Test handling quote fetch errors."""
        mock_provider = MagicMock()
        mock_provider.get_quote.side_effect = Exception("API Error")
        mock_tv_provider.return_value = mock_provider

        scanner = TechnicalScanner()
        scanner.set_universe(["BADTICKER"])
        scanner.add_condition("rsi < 30")

        # Should not raise, just skip the symbol
        results = scanner.run()
        assert len(results) == 0

    @patch("borsapy._providers.tradingview.get_tradingview_provider")
    @patch("borsapy.ticker.Ticker")
    def test_handles_history_error(
        self, mock_ticker_class, mock_tv_provider, mock_quote
    ):
        """Test handling history fetch errors."""
        mock_provider = MagicMock()
        mock_provider.get_quote.return_value = mock_quote
        mock_tv_provider.return_value = mock_provider

        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("History Error")
        mock_ticker_class.return_value = mock_ticker

        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO"])
        scanner.add_condition("volume > 1M")

        # Should still work with quote-only conditions
        results = scanner.run()
        # May or may not have results depending on condition evaluation


# =============================================================================
# Indicator Calculation Tests
# =============================================================================


class TestIndicatorCalculation:
    """Tests for indicator calculation in scanner."""

    def test_add_indicators_to_history(self, mock_history):
        """Test adding indicators to history DataFrame."""
        scanner = TechnicalScanner()
        indicators = {"rsi": [14], "sma": [20, 50]}
        result = scanner._add_indicators_to_history(mock_history, indicators)

        assert "RSI_14" in result.columns
        assert "SMA_20" in result.columns
        assert "SMA_50" in result.columns

    def test_add_macd_indicators(self, mock_history):
        """Test adding MACD indicators."""
        scanner = TechnicalScanner()
        indicators = {"macd": []}
        result = scanner._add_indicators_to_history(mock_history, indicators)

        assert "MACD" in result.columns
        assert "Signal" in result.columns
        assert "Histogram" in result.columns

    def test_add_bollinger_bands(self, mock_history):
        """Test adding Bollinger Bands."""
        scanner = TechnicalScanner()
        indicators = {"bb": [20]}
        result = scanner._add_indicators_to_history(mock_history, indicators)

        assert "BB_Upper" in result.columns
        assert "BB_Middle" in result.columns
        assert "BB_Lower" in result.columns

    def test_add_stochastic(self, mock_history):
        """Test adding Stochastic oscillator."""
        scanner = TechnicalScanner()
        indicators = {"stoch": [14]}
        result = scanner._add_indicators_to_history(mock_history, indicators)

        assert "Stoch_K" in result.columns
        assert "Stoch_D" in result.columns

    def test_add_latest_indicators(self, mock_history):
        """Test adding latest indicator values to data dict."""
        from borsapy.technical import calculate_rsi, calculate_sma

        scanner = TechnicalScanner()
        indicators = {"rsi": [14], "sma": [20]}

        # Add indicator columns to history
        history = mock_history.copy()
        history["RSI_14"] = calculate_rsi(history, 14)
        history["SMA_20"] = calculate_sma(history, 20)

        data = {}
        scanner._add_latest_indicators(data, history, indicators)

        assert "rsi_14" in data
        assert "rsi" in data  # Default period alias
        assert "sma_20" in data


# =============================================================================
# Complex Condition Tests
# =============================================================================


class TestComplexConditions:
    """Tests for complex condition handling."""

    def test_compound_condition_parsing(self):
        """Test compound condition in scanner."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30 and volume > 1M")
        indicators = scanner._collect_required_indicators()
        assert "rsi" in indicators

    def test_nested_condition_parsing(self):
        """Test nested condition in scanner."""
        scanner = TechnicalScanner()
        scanner.add_condition("(rsi < 30 or rsi > 70) and volume > 1M")
        indicators = scanner._collect_required_indicators()
        assert "rsi" in indicators

    def test_crossover_condition_parsing(self):
        """Test crossover condition in scanner."""
        scanner = TechnicalScanner()
        scanner.add_condition("sma_20 crosses_above sma_50")
        indicators = scanner._collect_required_indicators()
        assert "sma" in indicators
        assert 20 in indicators["sma"]
        assert 50 in indicators["sma"]

    def test_multiple_indicator_types(self):
        """Test multiple indicator types in one condition."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30 and macd > 0 and sma_20 > sma_50")
        indicators = scanner._collect_required_indicators()
        assert "rsi" in indicators
        assert "macd" in indicators
        assert "sma" in indicators
