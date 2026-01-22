"""TradingView symbol search provider.

This module provides symbol search functionality via TradingView's public API.
Based on: https://github.com/Mathieu2301/TradingView-API

Examples:
    >>> from borsapy._providers.tradingview_search import get_search_provider
    >>> provider = get_search_provider()
    >>> results = provider.search("banka")
    >>> print([r['symbol'] for r in results[:5]])
    ['AKBNK', 'GARAN', 'ISCTR', 'YKBNK', 'HALKB']
"""

from __future__ import annotations

import logging
from typing import Any

from borsapy._providers.base import BaseProvider

logger = logging.getLogger(__name__)


# TradingView search API endpoints (trailing slash required)
SEARCH_URL_V3 = "https://symbol-search.tradingview.com/symbol_search/v3/"
SEARCH_URL_LEGACY = "https://symbol-search.tradingview.com/symbol_search/"

# Asset type mappings
TYPE_MAPPING = {
    "stock": "stock",
    "forex": "forex",
    "fx": "forex",
    "crypto": "crypto",
    "index": "index",
    "futures": "futures",
    "bond": "bond",
    "fund": "fund",
    "etf": "fund",
}

# Exchange name mappings
EXCHANGE_MAPPING = {
    "bist": "BIST",
    "ist": "BIST",
    "istanbul": "BIST",
    "nasdaq": "NASDAQ",
    "nyse": "NYSE",
    "lse": "LSE",
    "xetr": "XETR",
    "amex": "AMEX",
}

# Cache TTL in seconds (1 hour)
CACHE_TTL = 3600


class TradingViewSearchProvider(BaseProvider):
    """TradingView symbol search provider.

    Provides search functionality for symbols across multiple exchanges.
    Uses TradingView's public symbol search API.

    Attributes:
        DEFAULT_LIMIT: Default number of results to return (50)
        MAX_LIMIT: Maximum number of results (100)
    """

    DEFAULT_LIMIT = 50
    MAX_LIMIT = 100

    def __init__(self):
        """Initialize the search provider."""
        super().__init__()
        # Override User-Agent for TradingView
        self._client.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36",
            "Accept": "application/json",
            "Origin": "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/",
        })

    def search(
        self,
        query: str,
        asset_type: str | None = None,
        exchange: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search for symbols matching the query.

        Args:
            query: Search query (e.g., "banka", "enerji", "THY")
            asset_type: Filter by type (stock, forex, crypto, index, futures, bond, fund)
            exchange: Filter by exchange (BIST, NASDAQ, NYSE, etc.)
            limit: Maximum number of results (default 50, max 100)

        Returns:
            List of matching symbols with metadata:
            [
                {
                    "symbol": "AKBNK",
                    "full_name": "BIST:AKBNK",
                    "description": "AKBANK T.A.S.",
                    "exchange": "BIST",
                    "type": "stock",
                    "currency": "TRY",
                    "country": "TR"
                },
                ...
            ]

        Examples:
            >>> provider.search("banka")
            >>> provider.search("gold", asset_type="forex")
            >>> provider.search("THY", exchange="BIST")
        """
        # Check cache first
        cache_key = f"tv_search:{query}:{asset_type}:{exchange}:{limit}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # Normalize inputs
        query = query.strip()
        if not query:
            return []

        limit = min(limit or self.DEFAULT_LIMIT, self.MAX_LIMIT)

        # Build request parameters
        params: dict[str, Any] = {
            "text": query,
            "start": 0,
        }

        # Add exchange filter
        if exchange:
            exchange_norm = EXCHANGE_MAPPING.get(exchange.lower(), exchange.upper())
            params["exchange"] = exchange_norm

        # Add type filter
        if asset_type:
            type_norm = TYPE_MAPPING.get(asset_type.lower(), asset_type.lower())
            params["type"] = type_norm

        # Make request
        try:
            response = self._get(SEARCH_URL_V3, params=params)
            data = response.json()
        except Exception as e:
            logger.warning(f"V3 search failed, trying legacy: {e}")
            try:
                # Fallback to legacy endpoint
                response = self._get(SEARCH_URL_LEGACY, params=params)
                data = response.json()
            except Exception as e2:
                logger.error(f"Search failed: {e2}")
                return []

        # Parse results
        results = self._parse_results(data, limit)

        # Cache results
        self._cache_set(cache_key, results, CACHE_TTL)

        return results

    def _parse_results(self, data: Any, limit: int) -> list[dict[str, Any]]:
        """Parse search API response.

        Args:
            data: Raw API response (list or dict with 'symbols' key)
            limit: Maximum results to return

        Returns:
            Normalized list of symbol dictionaries
        """
        # Handle both response formats
        if isinstance(data, dict):
            symbols = data.get("symbols", [])
        elif isinstance(data, list):
            symbols = data
        else:
            return []

        results = []
        for item in symbols[:limit]:
            try:
                result = {
                    "symbol": item.get("symbol", ""),
                    "full_name": item.get("full_name", f"{item.get('exchange', '')}:{item.get('symbol', '')}"),
                    "description": item.get("description", ""),
                    "exchange": item.get("exchange", ""),
                    "type": item.get("type", "stock"),
                    "currency": item.get("currency_code", ""),
                    "country": item.get("country", ""),
                    "provider_id": item.get("provider_id", ""),
                }

                # Skip empty results
                if result["symbol"]:
                    results.append(result)

            except Exception as e:
                logger.debug(f"Failed to parse result: {e}")
                continue

        return results

    def search_bist(self, query: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Search only BIST symbols.

        Convenience method for searching Turkish stocks.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of BIST symbols
        """
        return self.search(query, asset_type="stock", exchange="BIST", limit=limit)

    def search_crypto(self, query: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Search cryptocurrency symbols.

        Args:
            query: Search query (e.g., "BTC", "ETH")
            limit: Maximum results

        Returns:
            List of crypto symbols
        """
        return self.search(query, asset_type="crypto", limit=limit)

    def search_forex(self, query: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Search forex symbols.

        Args:
            query: Search query (e.g., "USD", "EUR")
            limit: Maximum results

        Returns:
            List of forex symbols
        """
        return self.search(query, asset_type="forex", limit=limit)

    def get_symbols(self, symbols: list[str]) -> list[str]:
        """Extract symbol names from search results.

        Convenience method to get just symbol names.

        Args:
            symbols: List of search result dicts

        Returns:
            List of symbol strings
        """
        return [s["symbol"] for s in symbols if s.get("symbol")]


# Singleton instance
_provider: TradingViewSearchProvider | None = None


def get_search_provider() -> TradingViewSearchProvider:
    """Get the singleton TradingViewSearchProvider instance.

    Returns:
        TradingViewSearchProvider instance
    """
    global _provider
    if _provider is None:
        _provider = TradingViewSearchProvider()
    return _provider
