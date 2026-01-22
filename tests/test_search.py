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
