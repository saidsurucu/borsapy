"""Tests for Twitter/X tweet search feature."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from borsapy._providers.twitter import (
    PERIOD_DAYS,
    TWEET_COLUMNS,
    TwitterProvider,
    _normalize_tweet,
    _safe_int,
    clear_twitter_auth,
    get_twitter_auth,
    set_twitter_auth,
)
from borsapy.twitter import (
    TwitterMixin,
    _build_crypto_query,
    _build_fund_query,
    _build_fx_query,
    _build_stock_query,
    search_tweets,
)

# =============================================================================
# Unit Tests: Auth management
# =============================================================================


class TestTwitterAuth:
    """Tests for Twitter authentication management."""

    def setup_method(self):
        clear_twitter_auth()

    def teardown_method(self):
        clear_twitter_auth()

    def test_set_auth_with_tokens(self):
        set_twitter_auth(auth_token="abc123", ct0="xyz789")
        creds = get_twitter_auth()
        assert creds is not None
        assert creds["cookies"]["auth_token"] == "abc123"
        assert creds["cookies"]["ct0"] == "xyz789"

    def test_set_auth_with_cookies_dict(self):
        set_twitter_auth(cookies={"auth_token": "token1", "ct0": "ct0val"})
        creds = get_twitter_auth()
        assert creds is not None
        assert creds["cookies"]["auth_token"] == "token1"

    def test_set_auth_with_cookies_file(self):
        set_twitter_auth(cookies_file="/path/to/cookies.json")
        creds = get_twitter_auth()
        assert creds is not None
        assert creds["cookies_file"] == "/path/to/cookies.json"

    def test_set_auth_no_args_raises(self):
        with pytest.raises(ValueError, match="Provide auth_token"):
            set_twitter_auth()

    def test_set_auth_cookies_missing_token_raises(self):
        with pytest.raises(ValueError, match="auth_token"):
            set_twitter_auth(cookies={"ct0": "only_ct0"})

    def test_clear_auth(self):
        set_twitter_auth(auth_token="abc", ct0="xyz")
        assert get_twitter_auth() is not None
        clear_twitter_auth()
        assert get_twitter_auth() is None

    def test_get_auth_default_none(self):
        assert get_twitter_auth() is None

    def test_auth_token_without_ct0(self):
        set_twitter_auth(auth_token="abc123")
        creds = get_twitter_auth()
        assert creds["cookies"]["auth_token"] == "abc123"
        assert creds["cookies"]["ct0"] == ""


# =============================================================================
# Unit Tests: Query building
# =============================================================================


class TestBuildStockQuery:
    """Tests for stock query building."""

    @patch("borsapy._providers.kap.get_kap_provider")
    def test_with_kap_name(self, mock_kap):
        mock_provider = MagicMock()
        mock_kap.return_value = mock_provider
        mock_provider.search.return_value = pd.DataFrame(
            [{"name": "TURK HAVA YOLLARI A.O.", "symbol": "THYAO"}]
        )
        query = _build_stock_query("THYAO")
        assert "$THYAO" in query
        assert "#THYAO" in query
        assert "THYAO" in query
        assert '"TURK HAVA YOLLARI"' in query
        assert "A.O." not in query

    @patch("borsapy._providers.kap.get_kap_provider", side_effect=Exception("no KAP"))
    def test_without_kap(self, mock_kap):
        query = _build_stock_query("THYAO")
        assert "$THYAO" in query
        assert "#THYAO" in query
        assert "THYAO" in query

    def test_query_uses_or(self):
        with patch("borsapy._providers.kap.get_kap_provider", side_effect=Exception):
            query = _build_stock_query("GARAN")
            assert " OR " in query


class TestBuildFundQuery:
    """Tests for fund query building."""

    def test_basic_fund_query(self):
        query = _build_fund_query("AAK")
        assert "#AAK" in query
        assert "AAK" in query

    def test_fund_query_with_name(self):
        query = _build_fund_query("AAK", "AK PORTFOY KISA VADELI BONO")
        assert "#AAK" in query
        assert '"AK PORTFOY KISA VADELI BONO"' in query

    def test_fund_query_name_truncation(self):
        long_name = "A" * 100
        query = _build_fund_query("XYZ", long_name)
        # Name should be truncated to 60 chars
        quoted_parts = [p for p in query.split(" OR ") if p.startswith('"')]
        assert len(quoted_parts) == 1
        assert len(quoted_parts[0]) <= 62 + 2  # 60 chars + quotes

    def test_fund_query_none_name(self):
        query = _build_fund_query("TTE", None)
        assert "#TTE" in query
        assert "TTE" in query
        # No quoted name
        assert '"' not in query


class TestBuildFxQuery:
    """Tests for FX query building."""

    def test_usd_query(self):
        query = _build_fx_query("USD")
        assert "$USDTRY" in query
        assert "dolar" in query

    def test_eur_query(self):
        query = _build_fx_query("EUR")
        assert "$EURTRY" in query
        assert "euro" in query

    def test_gold_query(self):
        query = _build_fx_query("gram-altin")
        assert "altin" in query

    def test_brent_query(self):
        query = _build_fx_query("BRENT")
        assert "brent" in query.lower()

    def test_unknown_fx_fallback(self):
        query = _build_fx_query("NOK")
        assert "$NOKTRY" in query
        assert "kur" in query


class TestBuildCryptoQuery:
    """Tests for crypto query building."""

    def test_btctry(self):
        query = _build_crypto_query("BTCTRY")
        assert "$BTC" in query
        assert "#Bitcoin" in query

    def test_ethtry(self):
        query = _build_crypto_query("ETHTRY")
        assert "$ETH" in query
        assert "#Ethereum" in query

    def test_unknown_crypto_fallback(self):
        query = _build_crypto_query("ATOMTRY")
        assert "$ATOM" in query
        assert "#ATOM" in query

    def test_usdt_pair(self):
        query = _build_crypto_query("SOLUSDT")
        assert "$SOL" in query
        assert "#Solana" in query


# =============================================================================
# Unit Tests: Tweet normalization
# =============================================================================


class TestNormalizeTweet:
    """Tests for normalizing raw GraphQL tweet data."""

    def test_graphql_format(self):
        raw = {
            "rest_id": "123456789",
            "legacy": {
                "full_text": "THYAO yükseliyor!",
                "favorite_count": 42,
                "retweet_count": 10,
                "reply_count": 5,
                "quote_count": 2,
                "bookmark_count": 3,
                "lang": "tr",
                "created_at": "Mon Feb 17 14:30:00 +0000 2025",
            },
            "core": {
                "user_results": {
                    "result": {
                        "legacy": {
                            "screen_name": "trader1",
                            "name": "Trader One",
                            "followers_count": 5000,
                        },
                        "is_blue_verified": True,
                    }
                }
            },
            "views": {"count": "1500"},
        }
        result = _normalize_tweet(raw)
        assert result["tweet_id"] == "123456789"
        assert result["text"] == "THYAO yükseliyor!"
        assert result["likes"] == 42
        assert result["retweets"] == 10
        assert result["replies"] == 5
        assert result["quotes"] == 2
        assert result["bookmarks"] == 3
        assert result["views"] == 1500
        assert result["author_handle"] == "trader1"
        assert result["author_name"] == "Trader One"
        assert result["author_followers"] == 5000
        assert result["author_verified"] is True
        assert result["lang"] == "tr"
        assert "x.com/trader1/status/123456789" in result["url"]

    def test_flat_format(self):
        raw = {
            "id_str": "987654321",
            "text": "Hello world",
            "favorite_count": 1,
            "screen_name": "user1",
        }
        result = _normalize_tweet(raw)
        assert result["tweet_id"] == "987654321"
        assert result["text"] == "Hello world"
        assert result["likes"] == 1

    def test_empty_dict(self):
        result = _normalize_tweet({})
        assert result["tweet_id"] == ""
        assert result["text"] == ""
        assert result["likes"] == 0
        assert result["views"] == 0

    def test_url_format(self):
        raw = {
            "rest_id": "111",
            "core": {
                "user_results": {
                    "result": {
                        "legacy": {"screen_name": "testuser"},
                    }
                }
            },
        }
        result = _normalize_tweet(raw)
        assert result["url"] == "https://x.com/testuser/status/111"

    def test_new_graphql_user_core_format(self):
        """Test GraphQL where screen_name/name are in user_result.core (new API)."""
        raw = {
            "rest_id": "777",
            "legacy": {
                "full_text": "New API format",
                "favorite_count": 20,
                "retweet_count": 5,
                "reply_count": 3,
                "lang": "tr",
            },
            "core": {
                "user_results": {
                    "result": {
                        "core": {
                            "screen_name": "new_api_user",
                            "name": "New API User",
                        },
                        "legacy": {
                            "followers_count": 1500,
                        },
                        "is_blue_verified": True,
                    }
                }
            },
            "views": {"count": "800"},
        }
        result = _normalize_tweet(raw)
        assert result["tweet_id"] == "777"
        assert result["text"] == "New API format"
        assert result["author_handle"] == "new_api_user"
        assert result["author_name"] == "New API User"
        assert result["author_followers"] == 1500
        assert result["author_verified"] is True
        assert result["views"] == 800
        assert "x.com/new_api_user/status/777" in result["url"]

    def test_wrapped_graphql_format(self):
        """Test GraphQL dict with 'tweet' wrapper key."""
        raw = {
            "tweet": {
                "rest_id": "555",
                "legacy": {
                    "full_text": "Wrapped tweet",
                    "favorite_count": 10,
                    "retweet_count": 2,
                    "reply_count": 1,
                    "lang": "en",
                },
                "core": {
                    "user_results": {
                        "result": {
                            "legacy": {
                                "screen_name": "wrapped_user",
                                "name": "Wrapped User",
                            }
                        }
                    }
                },
            }
        }
        result = _normalize_tweet(raw)
        assert result["tweet_id"] == "555"
        assert result["text"] == "Wrapped tweet"
        assert result["author_handle"] == "wrapped_user"
        assert result["likes"] == 10

    def test_tweet_record_format(self):
        """Test TweetRecord model_dump format (Pydantic fallback)."""
        raw = {
            "tweet_id": "999",
            "user": {"screen_name": "pydantic_user", "name": "Pydantic User"},
            "timestamp": "Mon Feb 17 14:30:00 +0000 2025",
            "text": "Model dump tweet",
            "likes": 7,
            "retweets": 3,
            "comments": 2,
            "tweet_url": "https://x.com/pydantic_user/status/999",
        }
        result = _normalize_tweet(raw)
        assert result["tweet_id"] == "999"
        assert result["text"] == "Model dump tweet"
        assert result["author_handle"] == "pydantic_user"
        assert result["author_name"] == "Pydantic User"
        assert result["likes"] == 7
        assert result["retweets"] == 3
        assert result["replies"] == 2
        assert result["url"] == "https://x.com/pydantic_user/status/999"


# =============================================================================
# Unit Tests: Safe int conversion
# =============================================================================


class TestSafeInt:
    def test_int(self):
        assert _safe_int(42) == 42

    def test_str_int(self):
        assert _safe_int("100") == 100

    def test_none(self):
        assert _safe_int(None) == 0

    def test_invalid_str(self):
        assert _safe_int("not_a_number") == 0

    def test_float(self):
        assert _safe_int(3.7) == 3


# =============================================================================
# Unit Tests: Period resolution
# =============================================================================


class TestPeriodResolution:
    def test_known_periods(self):
        assert PERIOD_DAYS["1d"] == 1
        assert PERIOD_DAYS["7d"] == 7
        assert PERIOD_DAYS["1w"] == 7
        assert PERIOD_DAYS["1mo"] == 30

    def test_all_periods_positive(self):
        for period, days in PERIOD_DAYS.items():
            assert days > 0, f"Period {period} has non-positive days: {days}"


# =============================================================================
# Unit Tests: TwitterProvider with mocked Scweet
# =============================================================================


class TestSearchTweetsMocked:
    """Tests for search_tweets with mocked Scweet."""

    def setup_method(self):
        clear_twitter_auth()

    def teardown_method(self):
        clear_twitter_auth()

    def test_search_no_auth_raises(self):
        from borsapy.exceptions import AuthenticationError

        provider = TwitterProvider()
        with pytest.raises((ImportError, AuthenticationError)):
            provider.search_tweets("test")

    @patch("borsapy._providers.twitter.get_twitter_auth")
    def test_search_returns_dataframe(self, mock_auth):
        mock_auth.return_value = {"cookies": {"auth_token": "tok", "ct0": "ct"}}
        provider = TwitterProvider()

        mock_scweet = MagicMock()
        mock_scweet.search.return_value = [
            {
                "rest_id": "1",
                "legacy": {
                    "full_text": "Test tweet",
                    "favorite_count": 5,
                    "retweet_count": 1,
                    "reply_count": 0,
                    "quote_count": 0,
                    "bookmark_count": 0,
                    "lang": "en",
                    "created_at": "Mon Feb 17 14:30:00 +0000 2025",
                },
                "core": {
                    "user_results": {
                        "result": {
                            "legacy": {
                                "screen_name": "user1",
                                "name": "User One",
                                "followers_count": 100,
                            }
                        }
                    }
                },
                "views": {"count": "50"},
            }
        ]
        provider._create_scweet = MagicMock(return_value=mock_scweet)

        df = provider.search_tweets("test query", period="1d")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["tweet_id"] == "1"
        assert df.iloc[0]["text"] == "Test tweet"
        assert df.iloc[0]["likes"] == 5

    @patch("borsapy._providers.twitter.get_twitter_auth")
    def test_search_empty_results(self, mock_auth):
        mock_auth.return_value = {"cookies": {"auth_token": "tok", "ct0": "ct"}}
        provider = TwitterProvider()

        mock_scweet = MagicMock()
        mock_scweet.search.return_value = []
        provider._create_scweet = MagicMock(return_value=mock_scweet)

        df = provider.search_tweets("nonexistent query")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert list(df.columns) == TWEET_COLUMNS


# =============================================================================
# Unit Tests: TwitterMixin
# =============================================================================


class TestTwitterMixin:
    """Tests for the TwitterMixin class."""

    def test_mixin_get_tweet_query_not_implemented(self):
        mixin = TwitterMixin()
        with pytest.raises(NotImplementedError):
            mixin._get_tweet_query()

    def test_mixin_tweets_uses_custom_query(self):
        mixin = TwitterMixin()
        # Override _get_tweet_query
        mixin._get_tweet_query = lambda: "$THYAO"

        with patch("borsapy.twitter.get_twitter_provider") as mock_prov:
            mock_instance = MagicMock()
            mock_prov.return_value = mock_instance
            mock_instance.search_tweets.return_value = pd.DataFrame(columns=TWEET_COLUMNS)

            # With custom query override
            mixin.tweets(query="custom query")
            mock_instance.search_tweets.assert_called_with(
                query="custom query",
                period="7d",
                since=None,
                until=None,
                lang=None,
                limit=100,
            )

    def test_mixin_tweets_uses_default_query(self):
        mixin = TwitterMixin()
        mixin._get_tweet_query = lambda: "$DEFAULT"

        with patch("borsapy.twitter.get_twitter_provider") as mock_prov:
            mock_instance = MagicMock()
            mock_prov.return_value = mock_instance
            mock_instance.search_tweets.return_value = pd.DataFrame(columns=TWEET_COLUMNS)

            mixin.tweets(period="1d")
            mock_instance.search_tweets.assert_called_with(
                query="$DEFAULT",
                period="1d",
                since=None,
                until=None,
                lang=None,
                limit=100,
            )


# =============================================================================
# Unit Tests: DataFrame columns
# =============================================================================


class TestTweetColumns:
    def test_column_count(self):
        assert len(TWEET_COLUMNS) == 15

    def test_required_columns(self):
        required = ["tweet_id", "text", "likes", "retweets", "author_handle", "url"]
        for col in required:
            assert col in TWEET_COLUMNS


# =============================================================================
# Integration Tests (require Scweet + auth)
# =============================================================================


@pytest.mark.integration
class TestTwitterIntegration:
    """Integration tests that require real Twitter auth and Scweet installed."""

    def test_search_tweets_real(self):
        """Test real tweet search (requires auth)."""
        df = search_tweets("$THYAO", period="1d", limit=5)
        assert isinstance(df, pd.DataFrame)
        assert len(df) <= 5
        if not df.empty:
            assert "tweet_id" in df.columns
            assert "text" in df.columns

    def test_ticker_tweets_real(self):
        """Test Ticker.tweets() (requires auth)."""
        from borsapy.ticker import Ticker

        stock = Ticker("THYAO")
        df = stock.tweets(period="1d", limit=5)
        assert isinstance(df, pd.DataFrame)
