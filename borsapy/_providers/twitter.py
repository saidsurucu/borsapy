"""Twitter/X provider using Scweet for tweet search."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from borsapy.cache import TTL, get_cache
from borsapy.exceptions import AuthenticationError

# Module-level auth storage (same pattern as tradingview.py)
_twitter_credentials: dict | None = None


def set_twitter_auth(
    auth_token: str | None = None,
    ct0: str | None = None,
    cookies: dict | None = None,
    cookies_file: str | None = None,
) -> None:
    """
    Set Twitter/X authentication credentials for tweet search.

    Twitter requires cookie-based authentication. You can get these values
    from your browser's developer tools after logging into twitter.com/x.com.

    Args:
        auth_token: The auth_token cookie value from Twitter/X.
        ct0: The ct0 cookie value from Twitter/X.
        cookies: Dict with 'auth_token' and 'ct0' keys.
        cookies_file: Path to a cookies JSON file (Scweet format).

    Examples:
        >>> import borsapy as bp
        >>> # Method 1: Direct cookie values
        >>> bp.set_twitter_auth(auth_token="abc123...", ct0="xyz789...")
        >>> # Method 2: Dict
        >>> bp.set_twitter_auth(cookies={"auth_token": "abc123", "ct0": "xyz789"})
        >>> # Method 3: Cookies file
        >>> bp.set_twitter_auth(cookies_file="cookies.json")
    """
    global _twitter_credentials

    if cookies_file:
        _twitter_credentials = {"cookies_file": cookies_file}
    elif cookies:
        if "auth_token" not in cookies:
            raise ValueError("cookies dict must contain 'auth_token' key")
        _twitter_credentials = {"cookies": cookies}
    elif auth_token:
        _twitter_credentials = {"cookies": {"auth_token": auth_token, "ct0": ct0 or ""}}
    else:
        raise ValueError(
            "Provide auth_token/ct0, cookies dict, or cookies_file. "
            "Get auth_token and ct0 from browser DevTools > Application > Cookies > x.com"
        )


def clear_twitter_auth() -> None:
    """Clear Twitter/X authentication credentials."""
    global _twitter_credentials
    _twitter_credentials = None


def get_twitter_auth() -> dict | None:
    """Get current Twitter/X authentication credentials."""
    return _twitter_credentials


# Period string -> days mapping
PERIOD_DAYS = {
    "1d": 1,
    "3d": 3,
    "5d": 5,
    "7d": 7,
    "1w": 7,
    "2w": 14,
    "1mo": 30,
    "3mo": 90,
}

# DataFrame column names for normalized tweets
TWEET_COLUMNS = [
    "tweet_id",
    "created_at",
    "text",
    "author_handle",
    "author_name",
    "likes",
    "retweets",
    "replies",
    "views",
    "quotes",
    "bookmarks",
    "author_followers",
    "author_verified",
    "lang",
    "url",
]


class TwitterProvider:
    """Provider for Twitter/X tweet search using Scweet."""

    def __init__(self):
        self._cache = get_cache()
        self._temp_db_path: str | None = None

    def _create_scweet(self):
        """Create a fresh Scweet client with current credentials.

        Uses a temporary DB path to avoid persistent cooldown/rate-limit state
        that would block subsequent calls. Scweet internally calls aclose()
        after each search(), so a fresh instance is needed every time.
        """
        try:
            from Scweet import Scweet
        except ImportError as err:
            raise ImportError(
                "Scweet is required for Twitter search. "
                "Install it with: pip install borsapy[twitter]"
            ) from err

        creds = get_twitter_auth()
        if creds is None:
            raise AuthenticationError(
                "Twitter authentication required. Call bp.set_twitter_auth() first. "
                "Get auth_token and ct0 from browser DevTools > Application > Cookies > x.com"
            )

        # Use a temp DB to avoid persistent cooldown state between calls
        db_fd, db_path = tempfile.mkstemp(suffix=".db", prefix="borsapy_scweet_")
        os.close(db_fd)
        self._temp_db_path = db_path

        if "cookies_file" in creds:
            return Scweet.from_sources(
                cookies_file=creds["cookies_file"],
                output_format="none",
                db_path=db_path,
            )
        else:
            # Scweet accepts cookies as a plain dict: {"auth_token": "...", "ct0": "..."}
            return Scweet.from_sources(
                cookies=creds["cookies"],
                output_format="none",
                db_path=db_path,
            )

    def _cleanup_temp_db(self):
        """Remove temporary Scweet state DB."""
        if self._temp_db_path and os.path.exists(self._temp_db_path):
            try:
                os.unlink(self._temp_db_path)
            except OSError:
                pass
        self._temp_db_path = None

    def search_tweets(
        self,
        query: str,
        period: str | None = "7d",
        since: str | None = None,
        until: str | None = None,
        lang: str | None = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        Search tweets matching a query.

        Args:
            query: Search query (e.g., "$THYAO", "dolar kur").
            period: Time period ("1d", "7d", "1mo", etc.). Ignored if since/until set.
            since: Start date (YYYY-MM-DD). Overrides period.
            until: End date (YYYY-MM-DD). Overrides period.
            lang: Language filter (e.g., "tr", "en").
            limit: Maximum number of tweets to return.

        Returns:
            DataFrame with tweet data (tweet_id, text, likes, etc.).
        """
        # Resolve date range
        if since and until:
            since_str = since
            until_str = until
        else:
            days = PERIOD_DAYS.get(period or "7d", 7)
            until_dt = datetime.now()
            since_dt = until_dt - timedelta(days=days)
            since_str = since_dt.strftime("%Y-%m-%d")
            until_str = until_dt.strftime("%Y-%m-%d")

        # Check cache
        cache_key = f"twitter:{query}:{since_str}:{until_str}:{lang}:{limit}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Build search kwargs using Scweet v4 recommended search() API.
        # Language filter uses Twitter search syntax: "query lang:tr"
        search_query = query
        if lang:
            search_query = f"{query} lang:{lang}"

        kwargs: dict[str, Any] = {
            "search_query": search_query,
            "since": since_str,
            "until": until_str,
            "limit": limit,
            "display_type": "Latest",
        }

        # Execute search — create a fresh Scweet each time because it
        # calls aclose() internally, invalidating the instance.
        # Use search() (recommended v4 API), fall back to scrape() for older Scweet.
        scweet = self._create_scweet()
        try:
            if hasattr(scweet, "search"):
                raw_tweets = scweet.search(**kwargs)
            else:
                # Scweet < 4.1: scrape() uses "words" instead of "search_query"
                kwargs["words"] = kwargs.pop("search_query")
                raw_tweets = scweet.scrape(**kwargs)
        finally:
            self._cleanup_temp_db()

        # Normalize results
        if not raw_tweets:
            df = pd.DataFrame(columns=TWEET_COLUMNS)
        else:
            rows = [_normalize_tweet(t) for t in raw_tweets]
            df = pd.DataFrame(rows, columns=TWEET_COLUMNS)
            # Sort by created_at descending (newest first)
            if not df.empty and "created_at" in df.columns:
                df = df.sort_values("created_at", ascending=False).reset_index(drop=True)

        # Cache result
        self._cache.set(cache_key, df, TTL.SOCIAL_DATA)

        return df


def _normalize_tweet(raw: dict) -> dict:
    """
    Normalize a raw Scweet tweet dict into a flat dict.

    Scweet v4 returns raw GraphQL dicts. The structure may be:
    1. Direct GraphQL: {rest_id, legacy, core, views, ...}
    2. Wrapped GraphQL: {tweet: {rest_id, legacy, core, views, ...}}
    3. TweetRecord model_dump: {tweet_id, user, text, likes, tweet_url, ...}
    """
    # Unwrap "tweet" wrapper if present (GraphQL format variant)
    tweet = raw.get("tweet", raw) if isinstance(raw.get("tweet"), dict) else raw

    # Detect TweetRecord model_dump format (has "user" dict with "screen_name")
    user_obj = tweet.get("user")
    if isinstance(user_obj, dict) and "screen_name" in user_obj:
        return _normalize_tweet_record(tweet)

    # GraphQL format: legacy contains tweet data,
    # core.user_results.result.legacy contains user data
    return _normalize_graphql(tweet)


def _normalize_graphql(tweet: dict) -> dict:
    """Normalize raw GraphQL tweet dict.

    Twitter GraphQL user data lives in two places:
      - user_result["core"]: screen_name, name, created_at  (new API)
      - user_result["legacy"]: followers_count, verified, description  (old/still used)
    We check both paths for backwards compatibility.
    """
    legacy = tweet.get("legacy", tweet)
    user_result = (
        tweet.get("core", {})
        .get("user_results", {})
        .get("result", {})
    )
    user_core = user_result.get("core", {}) if isinstance(user_result, dict) else {}
    user_legacy = user_result.get("legacy", {}) if isinstance(user_result, dict) else {}

    tweet_id = tweet.get("rest_id") or legacy.get("id_str", "")

    created_at = _parse_twitter_date(legacy.get("created_at", ""))

    # screen_name can be in user_result.core (new) or user_result.legacy (old)
    author_handle = (
        user_core.get("screen_name")
        or user_legacy.get("screen_name")
        or legacy.get("screen_name")
        or ""
    )

    author_name = (
        user_core.get("name")
        or user_legacy.get("name")
        or ""
    )

    # Views can be in different places
    views_data = tweet.get("views", {})
    views = 0
    if isinstance(views_data, dict):
        views = _safe_int(views_data.get("count", 0))
    elif isinstance(views_data, (int, float)):
        views = int(views_data)

    return {
        "tweet_id": str(tweet_id),
        "created_at": created_at,
        "text": legacy.get("full_text") or legacy.get("text", ""),
        "author_handle": author_handle,
        "author_name": author_name,
        "likes": _safe_int(legacy.get("favorite_count", 0)),
        "retweets": _safe_int(legacy.get("retweet_count", 0)),
        "replies": _safe_int(legacy.get("reply_count", 0)),
        "views": views,
        "quotes": _safe_int(legacy.get("quote_count", 0)),
        "bookmarks": _safe_int(legacy.get("bookmark_count", 0)),
        "author_followers": _safe_int(user_legacy.get("followers_count", 0)),
        "author_verified": (
            user_result.get("is_blue_verified", False)
            or user_legacy.get("verified", False)
        ),
        "lang": legacy.get("lang", ""),
        "url": f"https://x.com/{author_handle}/status/{tweet_id}" if tweet_id else "",
    }


def _normalize_tweet_record(tweet: dict) -> dict:
    """Normalize a TweetRecord model_dump dict (Scweet Pydantic fallback)."""
    user = tweet.get("user", {}) or {}
    tweet_id = tweet.get("tweet_id", "")
    author_handle = user.get("screen_name", "")
    created_at = _parse_twitter_date(tweet.get("timestamp", ""))

    return {
        "tweet_id": str(tweet_id),
        "created_at": created_at,
        "text": tweet.get("text", ""),
        "author_handle": author_handle,
        "author_name": user.get("name", ""),
        "likes": _safe_int(tweet.get("likes", 0)),
        "retweets": _safe_int(tweet.get("retweets", 0)),
        "replies": _safe_int(tweet.get("comments", 0)),
        "views": 0,
        "quotes": 0,
        "bookmarks": 0,
        "author_followers": 0,
        "author_verified": False,
        "lang": "",
        "url": tweet.get("tweet_url", "")
            or (f"https://x.com/{author_handle}/status/{tweet_id}" if tweet_id else ""),
    }


def _parse_twitter_date(date_str: str | None) -> datetime | None:
    """Parse Twitter's date format into datetime."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
    except (ValueError, TypeError):
        return None


def _safe_int(value: Any) -> int:
    """Safely convert a value to int, defaulting to 0."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


# Singleton
_twitter_provider: TwitterProvider | None = None


def get_twitter_provider() -> TwitterProvider:
    """Get the singleton TwitterProvider instance."""
    global _twitter_provider
    if _twitter_provider is None:
        _twitter_provider = TwitterProvider()
    return _twitter_provider
