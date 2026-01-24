"""Tests for technical scanner using TradingView-native API."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from borsapy.scanner import TechnicalScanner, ScanResult, scan


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_scan_result():
    """Mock scan result DataFrame."""
    return pd.DataFrame(
        {
            "symbol": ["THYAO", "GARAN"],
            "close": [285.0, 52.0],
            "volume": [15000000, 20000000],
            "change": [1.8, 2.1],
            "market_cap": [50000000000, 30000000000],
            "rsi": [28.5, 25.0],
        }
    )


@pytest.fixture
def empty_result():
    """Empty scan result DataFrame."""
    return pd.DataFrame()


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
        assert scanner._conditions == []
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
        assert "rsi < 30" in scanner._conditions
        assert scanner._condition_names["rsi < 30"] == "oversold"

    def test_add_condition_auto_name(self):
        """Test adding condition with auto name."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30")
        assert "rsi < 30" in scanner._conditions
        assert scanner._condition_names["rsi < 30"] == "rsi < 30"

    def test_add_compound_condition(self):
        """Test adding compound condition."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30 and volume > 1M")
        assert "rsi < 30" in scanner._conditions
        assert "volume > 1m" in scanner._conditions

    def test_remove_condition(self):
        """Test removing condition."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30", name="oversold")
        scanner.remove_condition("oversold")
        assert "rsi < 30" not in scanner._conditions

    def test_remove_condition_by_string(self):
        """Test removing condition by condition string."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30")
        scanner.remove_condition("rsi < 30")
        assert "rsi < 30" not in scanner._conditions

    def test_clear_conditions(self):
        """Test clearing all conditions."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30")
        scanner.add_condition("volume > 1M")
        scanner.clear_conditions()
        assert len(scanner._conditions) == 0

    def test_set_interval(self):
        """Test setting interval."""
        scanner = TechnicalScanner()
        scanner.set_interval("1h")
        assert scanner._interval == "1h"

    def test_add_column(self):
        """Test adding extra column."""
        scanner = TechnicalScanner()
        scanner.add_column("ema_200")
        assert "ema_200" in scanner._extra_columns

    def test_method_chaining(self):
        """Test fluent API method chaining."""
        scanner = TechnicalScanner()
        result = (
            scanner.set_universe(["THYAO", "GARAN"])
            .add_condition("rsi < 30")
            .set_interval("1d")
            .add_column("macd")
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
        assert "interval='1d'" in repr_str

    def test_symbols_property(self):
        """Test symbols property returns copy."""
        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO", "GARAN"])
        symbols = scanner.symbols
        symbols.append("ASELS")
        assert len(scanner._symbols) == 2

    def test_conditions_property(self):
        """Test conditions property returns copy."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30")
        conditions = scanner.conditions
        conditions.append("volume > 1M")
        assert len(scanner._conditions) == 1


# =============================================================================
# Scan Execution Tests (with mocks)
# =============================================================================


class TestScanExecution:
    """Tests for scan execution with mocked provider."""

    @patch("borsapy.scanner.get_tv_screener_provider")
    def test_run_returns_dataframe(self, mock_get_provider, mock_scan_result):
        """Test that run() returns a DataFrame."""
        mock_provider = MagicMock()
        mock_provider.scan.return_value = mock_scan_result
        mock_get_provider.return_value = mock_provider

        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO", "GARAN"])
        scanner.add_condition("rsi < 30")
        result = scanner.run()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    @patch("borsapy.scanner.get_tv_screener_provider")
    def test_run_adds_conditions_met(self, mock_get_provider, mock_scan_result):
        """Test that run() adds conditions_met column."""
        mock_provider = MagicMock()
        mock_provider.scan.return_value = mock_scan_result
        mock_get_provider.return_value = mock_provider

        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO"])
        scanner.add_condition("rsi < 30", name="oversold")
        result = scanner.run()

        assert "conditions_met" in result.columns
        assert result["conditions_met"].iloc[0] == ["oversold"]

    @patch("borsapy.scanner.get_tv_screener_provider")
    def test_run_empty_symbols(self, mock_get_provider):
        """Test run with empty symbols returns empty DataFrame."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30")
        result = scanner.run()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        mock_get_provider.return_value.scan.assert_not_called()

    @patch("borsapy.scanner.get_tv_screener_provider")
    def test_run_empty_conditions(self, mock_get_provider):
        """Test run with empty conditions returns empty DataFrame."""
        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO"])
        result = scanner.run()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        mock_get_provider.return_value.scan.assert_not_called()

    @patch("borsapy.scanner.get_tv_screener_provider")
    def test_run_with_limit(self, mock_get_provider, mock_scan_result):
        """Test run with custom limit."""
        mock_provider = MagicMock()
        mock_provider.scan.return_value = mock_scan_result
        mock_get_provider.return_value = mock_provider

        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO"])
        scanner.add_condition("rsi < 30")
        scanner.run(limit=50)

        mock_provider.scan.assert_called_once()
        call_kwargs = mock_provider.scan.call_args[1]
        assert call_kwargs["limit"] == 50

    @patch("borsapy.scanner.get_tv_screener_provider")
    def test_run_passes_interval(self, mock_get_provider, mock_scan_result):
        """Test run passes interval to provider."""
        mock_provider = MagicMock()
        mock_provider.scan.return_value = mock_scan_result
        mock_get_provider.return_value = mock_provider

        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO"])
        scanner.add_condition("rsi < 30")
        scanner.set_interval("1h")
        scanner.run()

        call_kwargs = mock_provider.scan.call_args[1]
        assert call_kwargs["interval"] == "1h"

    @patch("borsapy.scanner.get_tv_screener_provider")
    def test_run_passes_extra_columns(self, mock_get_provider, mock_scan_result):
        """Test run passes extra columns to provider."""
        mock_provider = MagicMock()
        mock_provider.scan.return_value = mock_scan_result
        mock_get_provider.return_value = mock_provider

        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO"])
        scanner.add_condition("rsi < 30")
        scanner.add_column("ema_200")
        scanner.run()

        call_kwargs = mock_provider.scan.call_args[1]
        assert "ema_200" in call_kwargs["columns"]


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
        mock_run.assert_called_once()

    @patch("borsapy.scanner.TechnicalScanner.run")
    def test_scan_with_interval(self, mock_run):
        """Test scan with custom interval."""
        mock_run.return_value = pd.DataFrame()

        result = scan("THYAO", "rsi < 30", interval="1h")

        mock_run.assert_called_once()

    @patch("borsapy.scanner.TechnicalScanner.run")
    def test_scan_with_limit(self, mock_run):
        """Test scan with custom limit."""
        mock_run.return_value = pd.DataFrame()

        result = scan("THYAO", "rsi < 30", limit=50)

        mock_run.assert_called_once_with(limit=50)


# =============================================================================
# Index Integration Tests
# =============================================================================


class TestIndexIntegration:
    """Tests for Index integration."""

    @patch("borsapy.index.get_bist_index_provider")
    @patch("borsapy.index.get_tradingview_provider")
    def test_set_universe_index(self, mock_tv_provider, mock_bist_provider):
        """Test setting universe with index symbol."""
        # Mock index components
        mock_bist = MagicMock()
        mock_bist.get_components.return_value = [
            {"symbol": "AKBNK", "name": "AKBANK"},
            {"symbol": "GARAN", "name": "GARANTİ BANK"},
            {"symbol": "THYAO", "name": "TÜRK HAVA YOLLARI"},
        ]
        mock_bist_provider.return_value = mock_bist

        # Mock TradingView
        mock_tv = MagicMock()
        mock_tv.get_quote.return_value = {"symbol": "XU030", "last": 9500}
        mock_tv_provider.return_value = mock_tv

        scanner = TechnicalScanner()
        scanner.set_universe("XU030")

        assert len(scanner._symbols) == 3
        assert "AKBNK" in scanner._symbols
        assert "GARAN" in scanner._symbols
        assert "THYAO" in scanner._symbols


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Tests for backward compatibility methods."""

    def test_set_data_period_deprecated(self):
        """Test set_data_period shows deprecation warning."""
        scanner = TechnicalScanner()
        with pytest.warns(DeprecationWarning):
            scanner.set_data_period("1y")

    def test_results_property_empty(self):
        """Test results property returns empty list."""
        scanner = TechnicalScanner()
        assert scanner.results == []

    @patch("borsapy.scanner.get_tv_screener_provider")
    def test_to_dataframe(self, mock_get_provider, mock_scan_result):
        """Test to_dataframe calls run."""
        mock_provider = MagicMock()
        mock_provider.scan.return_value = mock_scan_result
        mock_get_provider.return_value = mock_provider

        scanner = TechnicalScanner()
        scanner.set_universe(["THYAO"])
        scanner.add_condition("rsi < 30")
        result = scanner.to_dataframe()

        assert isinstance(result, pd.DataFrame)

    def test_on_match_deprecated(self):
        """Test on_match shows deprecation warning."""
        scanner = TechnicalScanner()
        with pytest.warns(DeprecationWarning):
            scanner.on_match(lambda s, d: None)

    def test_on_scan_complete_deprecated(self):
        """Test on_scan_complete shows deprecation warning."""
        scanner = TechnicalScanner()
        with pytest.warns(DeprecationWarning):
            scanner.on_scan_complete(lambda r: None)


# =============================================================================
# Provider Tests
# =============================================================================


class TestTVScreenerProvider:
    """Tests for TVScreenerProvider."""

    def test_provider_field_map(self):
        """Test that FIELD_MAP contains expected fields."""
        from borsapy._providers.tradingview_screener_native import TVScreenerProvider

        provider = TVScreenerProvider()

        # Check key fields exist
        assert "rsi" in provider.FIELD_MAP
        assert "close" in provider.FIELD_MAP
        assert "macd" in provider.FIELD_MAP
        assert "sma_50" in provider.FIELD_MAP

    def test_provider_interval_map(self):
        """Test that INTERVAL_MAP contains expected intervals."""
        from borsapy._providers.tradingview_screener_native import TVScreenerProvider

        provider = TVScreenerProvider()

        assert "1d" in provider.INTERVAL_MAP
        assert "1h" in provider.INTERVAL_MAP
        assert "5m" in provider.INTERVAL_MAP

    def test_parse_number_simple(self):
        """Test parsing simple numbers."""
        from borsapy._providers.tradingview_screener_native import TVScreenerProvider

        provider = TVScreenerProvider()

        assert provider._parse_number("100") == 100.0
        assert provider._parse_number("1.5") == 1.5
        assert provider._parse_number("-50") == -50.0

    def test_parse_number_suffixes(self):
        """Test parsing numbers with K/M/B suffixes."""
        from borsapy._providers.tradingview_screener_native import TVScreenerProvider

        provider = TVScreenerProvider()

        assert provider._parse_number("1K") == 1000.0
        assert provider._parse_number("1.5M") == 1500000.0
        assert provider._parse_number("2B") == 2000000000.0

    def test_get_tv_column_mapped(self):
        """Test getting TV column for mapped fields."""
        from borsapy._providers.tradingview_screener_native import TVScreenerProvider

        provider = TVScreenerProvider()

        assert provider._get_tv_column("rsi") == "RSI"
        assert provider._get_tv_column("close") == "close"
        assert provider._get_tv_column("macd") == "MACD.macd"

    def test_get_tv_column_dynamic_sma(self):
        """Test getting TV column for dynamic SMA."""
        from borsapy._providers.tradingview_screener_native import TVScreenerProvider

        provider = TVScreenerProvider()

        assert provider._get_tv_column("sma_100") == "SMA100"
        assert provider._get_tv_column("sma_150") == "SMA150"

    def test_get_tv_column_dynamic_ema(self):
        """Test getting TV column for dynamic EMA."""
        from borsapy._providers.tradingview_screener_native import TVScreenerProvider

        provider = TVScreenerProvider()

        assert provider._get_tv_column("ema_100") == "EMA100"
        assert provider._get_tv_column("ema_150") == "EMA150"

    def test_get_tv_column_with_interval(self):
        """Test getting TV column with non-daily interval."""
        from borsapy._providers.tradingview_screener_native import TVScreenerProvider

        provider = TVScreenerProvider()

        assert provider._get_tv_column("rsi", "1h") == "RSI|60"
        assert provider._get_tv_column("close", "5m") == "close|5"

    def test_extract_fields_from_condition(self):
        """Test extracting fields from condition."""
        from borsapy._providers.tradingview_screener_native import TVScreenerProvider

        provider = TVScreenerProvider()

        fields = provider._extract_fields_from_condition("rsi < 30")
        assert "rsi" in fields

        fields = provider._extract_fields_from_condition("close > sma_50")
        assert "close" in fields
        assert "sma_50" in fields

    def test_scan_empty_symbols(self):
        """Test scan with empty symbols."""
        from borsapy._providers.tradingview_screener_native import TVScreenerProvider

        provider = TVScreenerProvider()
        result = provider.scan([], ["rsi < 30"])

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_scan_empty_conditions(self):
        """Test scan with empty conditions."""
        from borsapy._providers.tradingview_screener_native import TVScreenerProvider

        provider = TVScreenerProvider()
        result = provider.scan(["THYAO"], [])

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


# =============================================================================
# Complex Condition Tests
# =============================================================================


class TestComplexConditions:
    """Tests for complex condition handling."""

    def test_compound_condition_parsed(self):
        """Test compound condition is split."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30 and volume > 1M")

        assert "rsi < 30" in scanner._conditions
        assert "volume > 1m" in scanner._conditions

    def test_crossover_condition_parsed(self):
        """Test crossover condition."""
        scanner = TechnicalScanner()
        scanner.add_condition("sma_20 crosses_above sma_50")

        assert "sma_20 crosses_above sma_50" in scanner._conditions

    def test_multiple_conditions(self):
        """Test adding multiple conditions."""
        scanner = TechnicalScanner()
        scanner.add_condition("rsi < 30", name="oversold")
        scanner.add_condition("macd > signal", name="macd_bullish")

        assert len(scanner._conditions) == 2
        assert "rsi < 30" in scanner._conditions
        assert "macd > signal" in scanner._conditions


# =============================================================================
# Integration Tests (requires network)
# =============================================================================


@pytest.mark.skip(reason="Integration test requires network access")
class TestIntegration:
    """Integration tests with real TradingView API."""

    def test_scan_xu030_rsi(self):
        """Test scanning XU030 for RSI oversold."""
        result = scan("XU030", "rsi < 40")
        assert isinstance(result, pd.DataFrame)
        print(f"Found {len(result)} stocks with RSI < 40")

    def test_scan_compound_condition(self):
        """Test scanning with compound condition."""
        result = scan("XU030", "rsi < 40 and close > sma_50")
        assert isinstance(result, pd.DataFrame)
        print(f"Found {len(result)} stocks matching compound condition")

    def test_scan_crossover(self):
        """Test scanning for crossover."""
        result = scan("XU030", "sma_20 crosses_above sma_50")
        assert isinstance(result, pd.DataFrame)
        print(f"Found {len(result)} stocks with golden cross")

    def test_scan_hourly_timeframe(self):
        """Test scanning with hourly timeframe."""
        result = scan("XU030", "rsi < 40", interval="1h")
        assert isinstance(result, pd.DataFrame)
        print(f"Found {len(result)} stocks with 1h RSI < 40")
