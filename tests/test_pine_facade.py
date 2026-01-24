"""Tests for Pine Facade provider (TradingView indicator metadata)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from borsapy._providers.pine_facade import (
    INDICATOR_OUTPUTS,
    STANDARD_INDICATORS,
    PineFacadeProvider,
    clear_indicator_cache,
    get_pine_facade_provider,
)
from borsapy.exceptions import AuthenticationError, DataNotAvailableError


class TestStandardIndicatorsMapping:
    """Test STANDARD_INDICATORS constant."""

    def test_rsi_mapping(self):
        """RSI should map to STD;RSI."""
        assert STANDARD_INDICATORS["RSI"] == "STD;RSI"

    def test_macd_mapping(self):
        """MACD should map to STD;MACD."""
        assert STANDARD_INDICATORS["MACD"] == "STD;MACD"

    def test_bollinger_aliases(self):
        """Both BB and BOLLINGER should map to STD;BB."""
        assert STANDARD_INDICATORS["BB"] == "STD;BB"
        assert STANDARD_INDICATORS["BOLLINGER"] == "STD;BB"

    def test_stochastic_aliases(self):
        """Both STOCHASTIC and STOCH should map to STD;Stochastic."""
        assert STANDARD_INDICATORS["STOCHASTIC"] == "STD;Stochastic"
        assert STANDARD_INDICATORS["STOCH"] == "STD;Stochastic"

    def test_moving_averages(self):
        """EMA and SMA should be mapped."""
        assert STANDARD_INDICATORS["EMA"] == "STD;EMA"
        assert STANDARD_INDICATORS["SMA"] == "STD;SMA"

    def test_all_standard_indicators_have_std_prefix(self):
        """All standard indicators should start with STD;."""
        for name, indicator_id in STANDARD_INDICATORS.items():
            assert indicator_id.startswith("STD;"), f"{name} should start with STD;"


class TestIndicatorOutputsMapping:
    """Test INDICATOR_OUTPUTS constant."""

    def test_rsi_outputs(self):
        """RSI should have single 'value' output."""
        assert "STD;RSI" in INDICATOR_OUTPUTS
        assert INDICATOR_OUTPUTS["STD;RSI"] == {"plot_0": "value"}

    def test_macd_outputs(self):
        """MACD should have macd, signal, histogram outputs."""
        assert "STD;MACD" in INDICATOR_OUTPUTS
        outputs = INDICATOR_OUTPUTS["STD;MACD"]
        assert outputs["plot_0"] == "macd"
        assert outputs["plot_1"] == "signal"
        assert outputs["plot_2"] == "histogram"

    def test_bollinger_outputs(self):
        """Bollinger Bands should have middle, upper, lower outputs."""
        assert "STD;BB" in INDICATOR_OUTPUTS
        outputs = INDICATOR_OUTPUTS["STD;BB"]
        assert outputs["plot_0"] == "middle"
        assert outputs["plot_1"] == "upper"
        assert outputs["plot_2"] == "lower"

    def test_stochastic_outputs(self):
        """Stochastic should have k and d outputs."""
        assert "STD;Stochastic" in INDICATOR_OUTPUTS
        outputs = INDICATOR_OUTPUTS["STD;Stochastic"]
        assert outputs["plot_0"] == "k"
        assert outputs["plot_1"] == "d"

    def test_adx_outputs(self):
        """ADX should have adx, plus_di, minus_di outputs."""
        assert "STD;ADX" in INDICATOR_OUTPUTS
        outputs = INDICATOR_OUTPUTS["STD;ADX"]
        assert outputs["plot_0"] == "adx"
        assert outputs["plot_1"] == "plus_di"
        assert outputs["plot_2"] == "minus_di"

    def test_single_value_indicators(self):
        """Indicators with single output should map to 'value'."""
        single_value_indicators = [
            "STD;RSI",
            "STD;EMA",
            "STD;SMA",
            "STD;ATR",
            "STD;OBV",
            "STD;VWAP",
            "STD;CCI",
            "STD;MFI",
            "STD;ROC",
            "STD;CMF",
        ]
        for indicator_id in single_value_indicators:
            assert indicator_id in INDICATOR_OUTPUTS
            assert INDICATOR_OUTPUTS[indicator_id] == {"plot_0": "value"}


class TestPineFacadeProviderInit:
    """Test PineFacadeProvider initialization."""

    def test_provider_creation(self):
        """Provider should be created with correct base URL."""
        provider = PineFacadeProvider()
        assert provider.BASE_URL == "https://pine-facade.tradingview.com/pine-facade"

    def test_provider_timeout(self):
        """Provider should have 15 second timeout."""
        provider = PineFacadeProvider()
        # Timeout is set in __init__
        assert provider._client.timeout.read == 15.0


class TestNormalizeIndicatorId:
    """Test _normalize_indicator_id method."""

    def test_short_name_to_full_id(self):
        """Short name should be normalized to full ID."""
        provider = PineFacadeProvider()

        assert provider._normalize_indicator_id("RSI") == "STD;RSI"
        assert provider._normalize_indicator_id("MACD") == "STD;MACD"
        assert provider._normalize_indicator_id("BB") == "STD;BB"

    def test_lowercase_short_name(self):
        """Lowercase short name should be normalized correctly."""
        provider = PineFacadeProvider()

        assert provider._normalize_indicator_id("rsi") == "STD;RSI"
        assert provider._normalize_indicator_id("macd") == "STD;MACD"

    def test_full_id_unchanged(self):
        """Full ID should remain unchanged."""
        provider = PineFacadeProvider()

        assert provider._normalize_indicator_id("STD;RSI") == "STD;RSI"
        assert provider._normalize_indicator_id("PUB;abc123") == "PUB;abc123"
        assert provider._normalize_indicator_id("USER;xyz789") == "USER;xyz789"

    def test_unknown_name_gets_std_prefix(self):
        """Unknown indicator name should get STD; prefix."""
        provider = PineFacadeProvider()

        assert provider._normalize_indicator_id("Unknown") == "STD;Unknown"
        assert provider._normalize_indicator_id("CustomInd") == "STD;CustomInd"


class TestNeedsAuth:
    """Test _needs_auth method."""

    def test_standard_indicators_no_auth(self):
        """Standard indicators (STD;*) should not require auth."""
        provider = PineFacadeProvider()

        assert provider._needs_auth("STD;RSI") is False
        assert provider._needs_auth("STD;MACD") is False
        assert provider._needs_auth("STD;BB") is False

    def test_public_indicators_need_auth(self):
        """Public indicators (PUB;*) should require auth."""
        provider = PineFacadeProvider()

        assert provider._needs_auth("PUB;abc123") is True
        assert provider._needs_auth("PUB;xyz789") is True

    def test_user_indicators_need_auth(self):
        """User indicators (USER;*) should require auth."""
        provider = PineFacadeProvider()

        assert provider._needs_auth("USER;abc123") is True
        assert provider._needs_auth("USER;xyz789") is True


class TestGetAuthCookies:
    """Test _get_auth_cookies method."""

    def test_explicit_session_and_signature(self):
        """Explicit session and signature should be used."""
        provider = PineFacadeProvider()

        result = provider._get_auth_cookies("my_session", "my_signature")

        assert result == {"sessionid": "my_session", "sessionid_sign": "my_signature"}

    def test_explicit_session_only(self):
        """Session only should return empty signature."""
        provider = PineFacadeProvider()

        result = provider._get_auth_cookies("my_session", None)

        assert result == {"sessionid": "my_session", "sessionid_sign": ""}

    @patch("borsapy._providers.pine_facade.get_tradingview_auth")
    def test_global_auth_used_when_no_explicit(self, mock_auth):
        """Global auth should be used when no explicit credentials provided."""
        mock_auth.return_value = {"session": "global_session", "session_sign": "global_sign"}
        provider = PineFacadeProvider()

        result = provider._get_auth_cookies(None, None)

        assert result == {"sessionid": "global_session", "sessionid_sign": "global_sign"}

    @patch("borsapy._providers.pine_facade.get_tradingview_auth")
    def test_empty_when_no_auth(self, mock_auth):
        """Empty values should be returned when no auth available."""
        mock_auth.return_value = None
        provider = PineFacadeProvider()

        result = provider._get_auth_cookies(None, None)

        assert result == {"sessionid": "", "sessionid_sign": ""}


class TestParseIndicatorResponse:
    """Test _parse_indicator_response method."""

    def test_basic_response_parsing(self):
        """Basic response should be parsed correctly."""
        provider = PineFacadeProvider()
        data = {
            "version": "v5",
            "inputs": [
                {"name": "length", "type": "integer", "defval": 14, "min": 1, "max": 500}
            ],
            "plots": [{"id": "plot_0", "type": "line", "title": "RSI"}],
        }

        result = provider._parse_indicator_response("STD;RSI", data)

        assert result["pineId"] == "STD;RSI"
        assert result["pineVersion"] == "v5"
        assert "length" in result["inputs"]
        assert result["inputs"]["length"]["defval"] == 14
        assert result["defaults"]["length"] == 14
        assert "plot_0" in result["plots"]

    def test_output_mapping_added(self):
        """Output mapping should be added for known indicators."""
        provider = PineFacadeProvider()
        data = {"inputs": [], "plots": []}

        result = provider._parse_indicator_response("STD;RSI", data)

        assert "output_mapping" in result
        assert result["output_mapping"] == {"plot_0": "value"}

    def test_no_output_mapping_for_unknown(self):
        """No output mapping for unknown indicators."""
        provider = PineFacadeProvider()
        data = {"inputs": [], "plots": []}

        result = provider._parse_indicator_response("STD;Unknown", data)

        assert "output_mapping" not in result

    def test_empty_inputs_and_plots(self):
        """Empty inputs and plots should be handled."""
        provider = PineFacadeProvider()
        data = {}

        result = provider._parse_indicator_response("STD;Test", data)

        assert result["inputs"] == {}
        assert result["plots"] == {}
        assert result["defaults"] == {}

    def test_input_without_name(self):
        """Input without name should get generated name."""
        provider = PineFacadeProvider()
        data = {
            "inputs": [
                {"type": "integer", "defval": 14}  # No name
            ]
        }

        result = provider._parse_indicator_response("STD;Test", data)

        assert "in_0" in result["inputs"]
        assert result["inputs"]["in_0"]["defval"] == 14

    def test_plot_without_id(self):
        """Plot without id should get generated id."""
        provider = PineFacadeProvider()
        data = {
            "plots": [
                {"type": "line", "title": "Plot"}  # No id
            ]
        }

        result = provider._parse_indicator_response("STD;Test", data)

        assert "plot_0" in result["plots"]


class TestGetOutputMapping:
    """Test get_output_mapping method."""

    def test_short_name_mapping(self):
        """Short name should be normalized and mapping returned."""
        provider = PineFacadeProvider()

        mapping = provider.get_output_mapping("RSI")

        assert mapping == {"plot_0": "value"}

    def test_full_id_mapping(self):
        """Full ID should return mapping."""
        provider = PineFacadeProvider()

        mapping = provider.get_output_mapping("STD;MACD")

        assert mapping == {"plot_0": "macd", "plot_1": "signal", "plot_2": "histogram"}

    def test_unknown_indicator_empty_mapping(self):
        """Unknown indicator should return empty dict."""
        provider = PineFacadeProvider()

        mapping = provider.get_output_mapping("Unknown")

        assert mapping == {}


class TestGetIndicator:
    """Test get_indicator method."""

    @patch.object(PineFacadeProvider, "_fetch_indicator")
    def test_standard_indicator_no_auth_required(self, mock_fetch):
        """Standard indicator should not require auth."""
        mock_fetch.return_value = {"pineId": "STD;RSI", "inputs": {}}
        provider = PineFacadeProvider()

        result = provider.get_indicator("RSI")

        assert result["pineId"] == "STD;RSI"
        mock_fetch.assert_called_once()

    @patch("borsapy._providers.pine_facade.get_tradingview_auth")
    def test_custom_indicator_requires_auth(self, mock_auth):
        """Custom indicator without auth should raise AuthenticationError."""
        mock_auth.return_value = None
        provider = PineFacadeProvider()

        with pytest.raises(AuthenticationError) as exc_info:
            provider.get_indicator("PUB;abc123")

        assert "requires TradingView authentication" in str(exc_info.value)

    @patch.object(PineFacadeProvider, "_fetch_indicator")
    @patch("borsapy._providers.pine_facade.get_tradingview_auth")
    def test_custom_indicator_with_explicit_auth(self, mock_auth, mock_fetch):
        """Custom indicator with explicit auth should work."""
        mock_auth.return_value = None  # No global auth
        mock_fetch.return_value = {"pineId": "PUB;abc123", "inputs": {}}
        provider = PineFacadeProvider()

        result = provider.get_indicator("PUB;abc123", session="my_session", signature="my_sign")

        assert result["pineId"] == "PUB;abc123"
        mock_fetch.assert_called_once_with("PUB;abc123", "last", "my_session", "my_sign")

    @patch.object(PineFacadeProvider, "_fetch_indicator")
    @patch("borsapy._providers.pine_facade.get_tradingview_auth")
    def test_custom_indicator_with_global_auth(self, mock_auth, mock_fetch):
        """Custom indicator with global auth should work."""
        mock_auth.return_value = {"session": "global_sess", "session_sign": "global_sign"}
        mock_fetch.return_value = {"pineId": "USER;xyz789", "inputs": {}}
        provider = PineFacadeProvider()

        result = provider.get_indicator("USER;xyz789")

        assert result["pineId"] == "USER;xyz789"
        mock_fetch.assert_called_once_with("USER;xyz789", "last", "global_sess", "global_sign")


class TestFetchIndicatorErrors:
    """Test error handling in _fetch_indicator."""

    def test_404_raises_data_not_available(self):
        """404 error should raise DataNotAvailableError."""
        provider = PineFacadeProvider()

        # Mock the client to raise an exception with 404
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        provider._client.get = MagicMock(return_value=mock_response)

        # Clear cache first
        clear_indicator_cache()

        with pytest.raises(DataNotAvailableError) as exc_info:
            provider._fetch_indicator("STD;NotFound", "last", "", "")

        assert "not found" in str(exc_info.value)

    def test_401_raises_auth_error(self):
        """401 error should raise AuthenticationError."""
        provider = PineFacadeProvider()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
        provider._client.get = MagicMock(return_value=mock_response)

        clear_indicator_cache()

        with pytest.raises(AuthenticationError) as exc_info:
            provider._fetch_indicator("PUB;protected", "last", "", "")

        assert "Access denied" in str(exc_info.value)

    def test_403_raises_auth_error(self):
        """403 error should raise AuthenticationError."""
        provider = PineFacadeProvider()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("403 Forbidden")
        provider._client.get = MagicMock(return_value=mock_response)

        clear_indicator_cache()

        with pytest.raises(AuthenticationError) as exc_info:
            provider._fetch_indicator("USER;private", "last", "", "")

        assert "Access denied" in str(exc_info.value)

    def test_network_error_raises_data_not_available(self):
        """Network error should raise DataNotAvailableError."""
        provider = PineFacadeProvider()

        provider._client.get = MagicMock(side_effect=Exception("Connection timeout"))

        clear_indicator_cache()

        with pytest.raises(DataNotAvailableError) as exc_info:
            provider._fetch_indicator("STD;RSI", "last", "", "")

        assert "Failed to fetch" in str(exc_info.value)


class TestSingleton:
    """Test singleton pattern for provider."""

    def test_get_pine_facade_provider_returns_singleton(self):
        """get_pine_facade_provider should return same instance."""
        # Reset singleton
        import borsapy._providers.pine_facade as pf_module

        pf_module._provider = None

        provider1 = get_pine_facade_provider()
        provider2 = get_pine_facade_provider()

        assert provider1 is provider2

    def test_singleton_is_pine_facade_provider(self):
        """Singleton should be PineFacadeProvider instance."""
        import borsapy._providers.pine_facade as pf_module

        pf_module._provider = None

        provider = get_pine_facade_provider()

        assert isinstance(provider, PineFacadeProvider)


class TestModuleCache:
    """Test module-level caching behavior."""

    def test_cache_can_be_cleared(self):
        """clear_indicator_cache should clear the cache."""
        import borsapy._providers.pine_facade as pf_module

        # Add something to cache
        pf_module._indicator_cache[("test", "last", "", "")] = {"test": True}

        # Clear cache
        clear_indicator_cache()

        # Check cache is empty
        assert len(pf_module._indicator_cache) == 0

    def test_cache_stores_results(self):
        """Cache should store fetched results."""
        import borsapy._providers.pine_facade as pf_module

        provider = PineFacadeProvider()
        clear_indicator_cache()

        # Mock the client
        mock_response = MagicMock()
        mock_response.json.return_value = {"inputs": [], "plots": []}
        provider._client.get = MagicMock(return_value=mock_response)

        # Fetch indicator
        provider._fetch_indicator("STD;RSI", "last", "", "")

        # Check cache has entry
        assert len(pf_module._indicator_cache) == 1


class TestURLEncoding:
    """Test URL encoding for indicator IDs."""

    def test_semicolon_encoded_in_url(self):
        """Semicolon in indicator ID should be URL encoded."""
        provider = PineFacadeProvider()

        # Mock the client
        mock_response = MagicMock()
        mock_response.json.return_value = {"inputs": [], "plots": []}
        provider._client.get = MagicMock(return_value=mock_response)
        clear_indicator_cache()

        provider._fetch_indicator("STD;RSI", "last", "", "")

        # Check URL was called with encoded semicolon
        call_args = provider._client.get.call_args
        url = call_args[0][0]
        assert "STD%3BRSI" in url  # %3B is encoded semicolon

    def test_percent_encoded_in_url(self):
        """Percent signs should be double-encoded."""
        provider = PineFacadeProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {"inputs": [], "plots": []}
        provider._client.get = MagicMock(return_value=mock_response)
        clear_indicator_cache()

        provider._fetch_indicator("STD;Williams%25R", "last", "", "")

        call_args = provider._client.get.call_args
        url = call_args[0][0]
        # %25 becomes %2525 when URL encoded
        assert "STD%3BWilliams%2525R" in url


class TestAuthHeaders:
    """Test authentication headers are set correctly."""

    def test_headers_with_session_only(self):
        """Headers should include sessionid cookie when provided."""
        provider = PineFacadeProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {"inputs": [], "plots": []}
        provider._client.get = MagicMock(return_value=mock_response)
        clear_indicator_cache()

        provider._fetch_indicator("STD;RSI", "last", "my_session", "")

        call_args = provider._client.get.call_args
        headers = call_args[1]["headers"]
        assert "Cookie" in headers
        assert "sessionid=my_session" in headers["Cookie"]

    def test_headers_with_session_and_signature(self):
        """Headers should include both cookies when provided."""
        provider = PineFacadeProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {"inputs": [], "plots": []}
        provider._client.get = MagicMock(return_value=mock_response)
        clear_indicator_cache()

        provider._fetch_indicator("STD;RSI", "last", "my_session", "my_sign")

        call_args = provider._client.get.call_args
        headers = call_args[1]["headers"]
        assert "sessionid=my_session" in headers["Cookie"]
        assert "sessionid_sign=my_sign" in headers["Cookie"]

    def test_headers_without_auth(self):
        """Headers should not include Cookie when no auth."""
        provider = PineFacadeProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {"inputs": [], "plots": []}
        provider._client.get = MagicMock(return_value=mock_response)
        clear_indicator_cache()

        provider._fetch_indicator("STD;RSI", "last", "", "")

        call_args = provider._client.get.call_args
        headers = call_args[1]["headers"]
        assert "Cookie" not in headers

    def test_origin_and_referer_headers(self):
        """Origin and Referer headers should be set."""
        provider = PineFacadeProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {"inputs": [], "plots": []}
        provider._client.get = MagicMock(return_value=mock_response)
        clear_indicator_cache()

        provider._fetch_indicator("STD;RSI", "last", "", "")

        call_args = provider._client.get.call_args
        headers = call_args[1]["headers"]
        assert headers["Origin"] == "https://www.tradingview.com"
        assert headers["Referer"] == "https://www.tradingview.com/"


# Integration tests (skipped by default, require network)
@pytest.mark.skip(reason="Requires network access to TradingView")
class TestIntegration:
    """Integration tests requiring network access."""

    def test_fetch_rsi_metadata(self):
        """Fetch real RSI metadata from TradingView."""
        provider = PineFacadeProvider()

        result = provider.get_indicator("RSI")

        assert result["pineId"] == "STD;RSI"
        assert "inputs" in result
        assert "plots" in result

    def test_fetch_macd_metadata(self):
        """Fetch real MACD metadata from TradingView."""
        provider = PineFacadeProvider()

        result = provider.get_indicator("MACD")

        assert result["pineId"] == "STD;MACD"
        assert "inputs" in result
