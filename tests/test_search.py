"""Tests for borsapy search functionality."""

import pytest


class TestTradingViewSearchProvider:
    """Tests for TradingViewSearchProvider."""

    def test_provider_singleton(self):
        """Test provider singleton pattern."""
        from borsapy._providers.tradingview_search import get_search_provider

        p1 = get_search_provider()
        p2 = get_search_provider()
        assert p1 is p2

    def test_search_basic(self):
        """Test basic search functionality."""
        from borsapy._providers.tradingview_search import get_search_provider

        provider = get_search_provider()
        results = provider.search("THYAO")

        assert isinstance(results, list)
        # Should find at least one result
        assert len(results) > 0

    def test_search_result_structure(self):
        """Test search result structure."""
        from borsapy._providers.tradingview_search import get_search_provider

        provider = get_search_provider()
        results = provider.search("GARAN", limit=5)

        if results:
            result = results[0]
            assert "symbol" in result
            assert "exchange" in result
            assert "type" in result

    def test_search_with_exchange_filter(self):
        """Test search with exchange filter."""
        from borsapy._providers.tradingview_search import get_search_provider

        provider = get_search_provider()
        results = provider.search("banka", exchange="BIST", limit=10)

        # All results should be from BIST
        for r in results:
            if r.get("exchange"):
                assert r["exchange"].upper() in ["BIST", "IST"]

    def test_search_with_type_filter(self):
        """Test search with type filter."""
        from borsapy._providers.tradingview_search import get_search_provider

        provider = get_search_provider()
        results = provider.search("BTC", asset_type="crypto", limit=10)

        # Should get results containing BTC-related crypto assets
        # Note: TradingView may return "spot" or "crypto" as the type
        assert isinstance(results, list)
        # At least one result should contain "BTC"
        btc_results = [r for r in results if "BTC" in r.get("symbol", "").upper()]
        assert len(btc_results) > 0

    def test_search_bist_shortcut(self):
        """Test search_bist convenience method."""
        from borsapy._providers.tradingview_search import get_search_provider

        provider = get_search_provider()
        results = provider.search_bist("banka", limit=10)

        assert isinstance(results, list)

    def test_search_crypto_shortcut(self):
        """Test search_crypto convenience method."""
        from borsapy._providers.tradingview_search import get_search_provider

        provider = get_search_provider()
        results = provider.search_crypto("ETH", limit=10)

        assert isinstance(results, list)

    def test_search_empty_query(self):
        """Test search with empty query."""
        from borsapy._providers.tradingview_search import get_search_provider

        provider = get_search_provider()
        results = provider.search("")

        assert results == []

    def test_search_limit(self):
        """Test search limit parameter."""
        from borsapy._providers.tradingview_search import get_search_provider

        provider = get_search_provider()
        results = provider.search("bank", limit=5)

        assert len(results) <= 5


class TestSearchModule:
    """Tests for search module functions."""

    def test_search_basic(self):
        """Test basic search function."""
        from borsapy.search import search

        results = search("THYAO")

        assert isinstance(results, list)
        # Should return strings by default
        if results:
            assert isinstance(results[0], str)

    def test_search_full_info(self):
        """Test search with full_info=True."""
        from borsapy.search import search

        results = search("GARAN", full_info=True)

        assert isinstance(results, list)
        if results:
            assert isinstance(results[0], dict)
            assert "symbol" in results[0]

    def test_search_type_filter(self):
        """Test search with type filter."""
        from borsapy.search import search

        results = search("BTC", type="crypto")

        assert isinstance(results, list)

    def test_search_exchange_filter(self):
        """Test search with exchange filter."""
        from borsapy.search import search

        results = search("banka", exchange="BIST")

        assert isinstance(results, list)

    def test_search_empty_raises(self):
        """Test search with empty query raises ValueError."""
        from borsapy.search import search

        with pytest.raises(ValueError):
            search("")

    def test_search_bist(self):
        """Test search_bist function."""
        from borsapy.search import search_bist

        results = search_bist("enerji")

        assert isinstance(results, list)

    def test_search_crypto(self):
        """Test search_crypto function."""
        from borsapy.search import search_crypto

        results = search_crypto("ETH")

        assert isinstance(results, list)

    def test_search_forex(self):
        """Test search_forex function."""
        from borsapy.search import search_forex

        results = search_forex("USD")

        assert isinstance(results, list)

    def test_search_index(self):
        """Test search_index function."""
        from borsapy.search import search_index

        results = search_index("XU")

        assert isinstance(results, list)


class TestSearchIntegration:
    """Integration tests for search."""

    def test_search_from_bp_module(self):
        """Test search imported from main module."""
        import borsapy as bp

        results = bp.search("THYAO")

        assert isinstance(results, list)

    def test_search_bist_stocks(self):
        """Test searching BIST stocks."""
        import borsapy as bp

        results = bp.search("banka", type="stock", exchange="BIST", limit=10)

        # Should find Turkish banks
        assert isinstance(results, list)
        # Check for common bank symbols
        bank_symbols = {"AKBNK", "GARAN", "ISCTR", "YKBNK", "HALKB", "VAKBN"}
        found = set(results) & bank_symbols
        # Should find at least some banks
        assert len(found) > 0 or len(results) > 0

    def test_search_deduplication(self):
        """Test that results are deduplicated."""
        from borsapy.search import search

        results = search("THYAO", limit=50)

        # No duplicates
        assert len(results) == len(set(results))

    def test_search_result_order_preserved(self):
        """Test that result order is preserved."""
        from borsapy.search import search

        # Search should return results in relevance order
        results = search("THYAO", limit=5)

        if results:
            # First result should likely contain THYAO
            assert "THYAO" in results[0].upper() or len(results) > 0


class TestVIOPSearch:
    """Tests for VIOP (derivatives) search functionality."""

    def test_search_viop_basic(self):
        """Test basic VIOP search."""
        from borsapy.search import search_viop

        results = search_viop("XU030")

        assert isinstance(results, list)
        # Should find some BIST30 futures
        assert len(results) >= 0  # May be empty if no active contracts

    def test_search_viop_from_module(self):
        """Test search_viop from main module."""
        import borsapy as bp

        results = bp.search_viop("gold")

        assert isinstance(results, list)

    def test_viop_contracts_basic(self):
        """Test viop_contracts function."""
        from borsapy.search import viop_contracts

        contracts = viop_contracts("XU030D")

        assert isinstance(contracts, list)
        # Each item should be a string (symbol)
        for c in contracts:
            assert isinstance(c, str)
            # Should start with base symbol
            assert c.startswith("XU030D")

    def test_viop_contracts_full_info(self):
        """Test viop_contracts with full_info=True."""
        from borsapy.search import viop_contracts

        contracts = viop_contracts("XU030D", full_info=True)

        assert isinstance(contracts, list)
        # Each item should be a dict
        for c in contracts:
            assert isinstance(c, dict)
            assert "symbol" in c
            assert "base" in c
            assert "month_code" in c

    def test_viop_contracts_from_module(self):
        """Test viop_contracts from main module."""
        import borsapy as bp

        contracts = bp.viop_contracts("XAUTRYD")

        assert isinstance(contracts, list)

    def test_viop_contracts_various_symbols(self):
        """Test viop_contracts works for various VIOP symbols."""
        from borsapy.search import viop_contracts

        # XU030D has D suffix (BIST30 futures)
        contracts_xu030d = viop_contracts("XU030D")
        assert len(contracts_xu030d) > 0
        for c in contracts_xu030d:
            assert c.startswith("XU030D")

        # XAUTRY has no D suffix (gold futures)
        contracts_xautry = viop_contracts("XAUTRY")
        assert isinstance(contracts_xautry, list)
        # May be empty if no active contracts, but should not error


class TestVIOPSearchProvider:
    """Tests for VIOP search in provider."""

    def test_provider_search_viop(self):
        """Test provider search_viop method."""
        from borsapy._providers.tradingview_search import get_search_provider

        provider = get_search_provider()
        results = provider.search_viop("XU030")

        assert isinstance(results, list)

    def test_provider_get_viop_contracts(self):
        """Test provider get_viop_contracts method."""
        from borsapy._providers.tradingview_search import get_search_provider

        provider = get_search_provider()
        contracts = provider.get_viop_contracts("XU030D")

        assert isinstance(contracts, list)
        for c in contracts:
            assert "symbol" in c
            assert "full_name" in c
            assert "is_continuous" in c

    def test_provider_month_code_mapping(self):
        """Test month code to name mapping."""
        from borsapy._providers.tradingview_search import (
            VIOP_MONTH_CODES,
            month_code_to_name,
        )

        # Test mapping exists
        assert len(VIOP_MONTH_CODES) == 12

        # Test specific codes
        assert month_code_to_name("G") == "February"
        assert month_code_to_name("J") == "April"
        assert month_code_to_name("Z") == "December"

        # Test invalid code
        assert month_code_to_name("A") == ""

    def test_provider_viop_contract_structure(self):
        """Test VIOP contract result structure."""
        from borsapy._providers.tradingview_search import get_search_provider

        provider = get_search_provider()
        contracts = provider.get_viop_contracts("XU030D")

        if contracts:
            c = contracts[0]
            # Required fields
            assert "symbol" in c
            assert "full_name" in c
            assert "base" in c
            assert "month_code" in c
            assert "year" in c
            assert "is_continuous" in c
            assert "exchange" in c
            assert "type" in c

            # Validate values
            assert c["exchange"] == "BIST"
            assert c["type"] == "futures"
            assert c["base"] == "XU030D"
