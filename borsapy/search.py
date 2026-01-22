"""Symbol search functionality for borsapy.

This module provides unified symbol search across TradingView and local KAP data.

Examples:
    >>> import borsapy as bp
    >>> bp.search("banka")               # Search all assets
    ['AKBNK', 'GARAN', 'ISCTR', 'YKBNK', 'HALKB', ...]

    >>> bp.search("gold", type="forex")  # Filter by type
    ['XAUUSD', 'XAUTRY', ...]

    >>> bp.search("GARAN", exchange="BIST")  # Filter by exchange
    ['GARAN']
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def search(
    query: str,
    type: str | None = None,
    exchange: str | None = None,
    limit: int = 50,
    full_info: bool = False,
) -> list[str] | list[dict[str, Any]]:
    """Search for symbols matching the query.

    Searches TradingView's symbol database and optionally merges with local
    KAP company data for comprehensive BIST coverage.

    Args:
        query: Search query (e.g., "banka", "enerji", "THY", "gold")
        type: Filter by asset type:
              - "stock": Stocks/equities
              - "forex" or "fx": Forex pairs
              - "crypto": Cryptocurrencies
              - "index": Market indices
              - "futures": Futures contracts
              - "fund" or "etf": Funds and ETFs
              - "bond": Bonds
        exchange: Filter by exchange (e.g., "BIST", "NASDAQ", "NYSE")
        limit: Maximum number of results (default 50, max 100)
        full_info: If True, return full result dicts; if False, return symbol list

    Returns:
        If full_info=False (default):
            List of symbol strings: ['AKBNK', 'GARAN', ...]

        If full_info=True:
            List of result dicts:
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
        >>> import borsapy as bp

        >>> # Simple search
        >>> bp.search("banka")
        ['AKBNK', 'GARAN', 'ISCTR', 'YKBNK', 'HALKB', ...]

        >>> # Search with type filter
        >>> bp.search("gold", type="forex")
        ['XAUUSD', 'XAUTRY', ...]

        >>> # Search with exchange filter
        >>> bp.search("THY", exchange="BIST")
        ['THYAO']

        >>> # Get full info
        >>> bp.search("GARAN", full_info=True)
        [{'symbol': 'GARAN', 'description': 'TURKIYE GARANTI BANKASI A.S.', ...}]

        >>> # Search crypto
        >>> bp.search("BTC", type="crypto")
        ['BTCUSD', 'BTCTRY', 'BTCUSDT', ...]

        >>> # Search indices
        >>> bp.search("XU", type="index", exchange="BIST")
        ['XU100', 'XU030', 'XU050', ...]

    Raises:
        ValueError: If query is empty
    """
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")

    from borsapy._providers.tradingview_search import get_search_provider

    provider = get_search_provider()

    # Search TradingView
    results = provider.search(
        query=query,
        asset_type=type,
        exchange=exchange,
        limit=limit,
    )

    # Try to enhance with KAP data for BIST stocks
    if not type or type.lower() == "stock":
        if not exchange or exchange.upper() == "BIST":
            results = _merge_with_kap(results, query)

    if full_info:
        return results
    else:
        # Return just symbol list (deduplicated, maintaining order)
        seen = set()
        symbols = []
        for r in results:
            sym = r.get("symbol", "")
            if sym and sym not in seen:
                seen.add(sym)
                symbols.append(sym)
        return symbols


def _merge_with_kap(
    tv_results: list[dict[str, Any]], query: str
) -> list[dict[str, Any]]:
    """Merge TradingView results with KAP company data.

    Adds any local KAP matches that TradingView might have missed.

    Args:
        tv_results: TradingView search results
        query: Original search query

    Returns:
        Merged results with KAP data appended
    """
    try:
        from borsapy.market import search_companies

        # Get KAP matches
        kap_results = search_companies(query)

        if not kap_results.empty:
            # Get symbols already in TV results
            tv_symbols = {r.get("symbol", "").upper() for r in tv_results}

            # Add KAP results not already in TV
            for _, row in kap_results.iterrows():
                symbol = str(row.get("symbol", "")).upper()
                if symbol and symbol not in tv_symbols:
                    tv_results.append({
                        "symbol": symbol,
                        "full_name": f"BIST:{symbol}",
                        "description": str(row.get("company", "")),
                        "exchange": "BIST",
                        "type": "stock",
                        "currency": "TRY",
                        "country": "TR",
                        "source": "kap",
                    })

    except Exception as e:
        logger.debug(f"KAP merge failed: {e}")

    return tv_results


def search_bist(query: str, limit: int = 50) -> list[str]:
    """Search BIST symbols only.

    Convenience function for Turkish stock search.

    Args:
        query: Search query
        limit: Maximum results

    Returns:
        List of BIST symbol strings

    Examples:
        >>> bp.search_bist("banka")
        ['AKBNK', 'GARAN', 'ISCTR', 'YKBNK', 'HALKB']
    """
    return search(query, type="stock", exchange="BIST", limit=limit)


def search_crypto(query: str, limit: int = 50) -> list[str]:
    """Search cryptocurrency symbols.

    Args:
        query: Search query (e.g., "BTC", "ETH")
        limit: Maximum results

    Returns:
        List of crypto symbol strings

    Examples:
        >>> bp.search_crypto("BTC")
        ['BTCUSD', 'BTCTRY', 'BTCUSDT', ...]
    """
    return search(query, type="crypto", limit=limit)


def search_forex(query: str, limit: int = 50) -> list[str]:
    """Search forex symbols.

    Args:
        query: Search query (e.g., "USD", "EUR", "gold")
        limit: Maximum results

    Returns:
        List of forex symbol strings

    Examples:
        >>> bp.search_forex("gold")
        ['XAUUSD', 'XAUTRY', ...]
    """
    return search(query, type="forex", limit=limit)


def search_index(query: str, limit: int = 50) -> list[str]:
    """Search market index symbols.

    Args:
        query: Search query (e.g., "XU", "SP500")
        limit: Maximum results

    Returns:
        List of index symbol strings

    Examples:
        >>> bp.search_index("XU")
        ['XU100', 'XU030', 'XU050', ...]
    """
    return search(query, type="index", limit=limit)
