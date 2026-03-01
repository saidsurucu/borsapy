"""Twitter/X tweet search for Turkish financial assets."""

from __future__ import annotations

import pandas as pd

from borsapy._providers.twitter import get_twitter_provider

# ─────────────────────────────────────────────────────────────────────
# FX / Commodity → Twitter query mapping (Turkish search terms)
# ─────────────────────────────────────────────────────────────────────

FX_QUERY_MAP = {
    "USD": "$USDTRY OR dolar kur OR dolar TL",
    "EUR": "$EURTRY OR euro kur OR euro TL",
    "GBP": "$GBPTRY OR sterlin kur",
    "JPY": "japon yeni OR $JPYTRY",
    "CHF": "isvicre frangi OR $CHFTRY",
    "gram-altin": "gram altin OR altin fiyat OR #altin",
    "ceyrek-altin": "ceyrek altin OR altin fiyat",
    "yarim-altin": "yarim altin OR altin fiyat",
    "tam-altin": "tam altin OR altin fiyat",
    "cumhuriyet-altin": "cumhuriyet altini OR altin fiyat",
    "ons-altin": "ons altin OR #gold OR $XAUUSD",
    "gram-gumus": "gram gumus OR gumus fiyat",
    "BRENT": "brent petrol OR #brent OR $BRENT",
    "XAU": "$XAUUSD OR #gold OR altin ons",
    "XAG": "$XAGUSD OR gumus ons",
}

CRYPTO_QUERY_MAP = {
    "BTC": "$BTC OR #Bitcoin",
    "ETH": "$ETH OR #Ethereum",
    "BNB": "$BNB OR #Binance",
    "SOL": "$SOL OR #Solana",
    "XRP": "$XRP OR #Ripple",
    "DOGE": "$DOGE OR #Dogecoin",
    "ADA": "$ADA OR #Cardano",
    "AVAX": "$AVAX OR #Avalanche",
    "DOT": "$DOT OR #Polkadot",
}


# ─────────────────────────────────────────────────────────────────────
# Query builder functions
# ─────────────────────────────────────────────────────────────────────


def _build_stock_query(symbol: str) -> str:
    """
    Build a Twitter search query for a BIST stock.

    Includes cashtag, hashtag, symbol, and company name from KAP.

    Args:
        symbol: BIST stock symbol (e.g., "THYAO").

    Returns:
        Query string like '$THYAO OR #THYAO OR THYAO OR "TURK HAVA YOLLARI"'.
    """
    parts = [f"${symbol}", f"#{symbol}", symbol]

    try:
        from borsapy._providers.kap import get_kap_provider

        df = get_kap_provider().search(symbol)
        if not df.empty:
            name = df.iloc[0]["name"]
            # Clean company name (remove A.S., A.O., etc.)
            for suffix in (" A.S.", " A.Ş.", " A.O.", " A.Ş"):
                name = name.replace(suffix, "")
            name = name.strip()
            if name:
                parts.append(f'"{name}"')
    except Exception:
        pass  # KAP unavailable, search with symbol only

    return " OR ".join(parts)


def _build_fund_query(code: str, name: str | None = None) -> str:
    """
    Build a Twitter search query for a mutual fund.

    Args:
        code: Fund code (e.g., "AAK").
        name: Fund name (optional, from Fund.info).

    Returns:
        Query string like '#AAK OR AAK OR "AK PORTFOY KISA VADELI BONO"'.
    """
    parts = [f"#{code}", code]

    if name:
        # Truncate long names for better search results
        short_name = name[:60].strip()
        if short_name:
            parts.append(f'"{short_name}"')

    return " OR ".join(parts)


def _build_fx_query(asset: str) -> str:
    """
    Build a Twitter search query for an FX/commodity asset.

    Args:
        asset: Asset symbol (e.g., "USD", "gram-altin").

    Returns:
        Query string with Turkish search terms.
    """
    if asset in FX_QUERY_MAP:
        return FX_QUERY_MAP[asset]

    # Fallback: generic query
    return f"${asset}TRY OR {asset} kur"


def _build_crypto_query(pair: str) -> str:
    """
    Build a Twitter search query for a cryptocurrency.

    Args:
        pair: Trading pair (e.g., "BTCTRY", "ETHTRY").

    Returns:
        Query string like '$BTC OR #Bitcoin'.
    """
    # Extract base coin from pair (e.g., BTCTRY -> BTC, ETHUSDT -> ETH)
    base = pair
    for suffix in ("TRY", "USDT", "USD", "BTC", "ETH", "EUR"):
        if pair.endswith(suffix) and len(pair) > len(suffix):
            base = pair[: -len(suffix)]
            break

    if base in CRYPTO_QUERY_MAP:
        return CRYPTO_QUERY_MAP[base]

    # Fallback: cashtag + hashtag
    return f"${base} OR #{base}"


# ─────────────────────────────────────────────────────────────────────
# Standalone search function
# ─────────────────────────────────────────────────────────────────────


def search_tweets(
    query: str,
    period: str | None = "7d",
    since: str | None = None,
    until: str | None = None,
    lang: str | None = None,
    limit: int = 100,
) -> pd.DataFrame:
    """
    Search Twitter/X for tweets matching a query.

    Requires authentication: call bp.set_twitter_auth() first.
    Requires optional dependency: pip install borsapy[twitter]

    Args:
        query: Search query (e.g., "$THYAO", "dolar kur", "#Bitcoin").
        period: Time period ("1d", "7d", "1mo"). Ignored if since/until set.
        since: Start date (YYYY-MM-DD). Overrides period.
        until: End date (YYYY-MM-DD). Overrides period.
        lang: Language filter (e.g., "tr", "en").
        limit: Maximum number of tweets (default 100).

    Returns:
        DataFrame with columns: tweet_id, created_at, text, author_handle,
        author_name, likes, retweets, replies, views, quotes, bookmarks,
        author_followers, author_verified, lang, url.

    Examples:
        >>> import borsapy as bp
        >>> bp.set_twitter_auth(auth_token="...", ct0="...")
        >>> df = bp.search_tweets("$THYAO", period="7d")
        >>> df = bp.search_tweets("dolar kur", period="1d", lang="tr", limit=50)
    """
    provider = get_twitter_provider()
    return provider.search_tweets(
        query=query,
        period=period,
        since=since,
        until=until,
        lang=lang,
        limit=limit,
    )


# ─────────────────────────────────────────────────────────────────────
# TwitterMixin for asset classes
# ─────────────────────────────────────────────────────────────────────


class TwitterMixin:
    """Mixin that adds tweets() method to asset classes."""

    def _get_tweet_query(self) -> str:
        """Return the default Twitter search query for this asset.

        Subclasses should override this method.
        """
        raise NotImplementedError

    def tweets(
        self,
        period: str | None = "7d",
        since: str | None = None,
        until: str | None = None,
        lang: str | None = None,
        limit: int = 100,
        query: str | None = None,
    ) -> pd.DataFrame:
        """
        Search Twitter/X for tweets related to this asset.

        Requires authentication: call bp.set_twitter_auth() first.
        Requires optional dependency: pip install borsapy[twitter]

        Args:
            period: Time period ("1d", "7d", "1mo"). Ignored if since/until set.
            since: Start date (YYYY-MM-DD). Overrides period.
            until: End date (YYYY-MM-DD). Overrides period.
            lang: Language filter (e.g., "tr", "en").
            limit: Maximum number of tweets (default 100).
            query: Custom query override. If set, replaces the default query.

        Returns:
            DataFrame with tweet data.

        Examples:
            >>> stock = bp.Ticker("THYAO")
            >>> df = stock.tweets(period="7d")
            >>> df = stock.tweets(query="THY ucak grev")  # Custom query
        """
        q = query or self._get_tweet_query()
        return search_tweets(
            query=q,
            period=period,
            since=since,
            until=until,
            lang=lang,
            limit=limit,
        )
