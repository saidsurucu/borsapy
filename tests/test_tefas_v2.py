"""Tests for the 2026-04 TEFAS v2 API migration (v0.9.0).

Covers:
- ``fonFiyatBilgiGetir`` history with the new ``periyod`` enum
- Client-side ``start``/``end`` filtering when no native bucket fits
- ``fonProfilBilgiGetir`` profile fields merged into ``get_fund_detail``
- Playwright-based ``get_allocation`` (lazy import + parsing)
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pandas as pd
import pytest

from borsapy._providers.tefas import TEFASProvider
from borsapy.cache import Cache
from borsapy.exceptions import APIError, DataNotAvailableError


def _envelope(result_list: list[dict] | None) -> dict:
    """Wrap a payload in the v2 ``{errorCode, errorMessage, resultList}`` envelope."""
    return {"errorCode": None, "errorMessage": None, "resultList": result_list or []}


def _mock_response(payload: dict, status: int = 200) -> MagicMock:
    body = json.dumps(payload).encode("utf-8")
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.content = body
    resp.headers = {"content-type": "application/json; charset=utf-8"}
    resp.raise_for_status = MagicMock()
    resp.json = lambda: json.loads(body)
    return resp


def _make_provider(post_side_effect):
    """Build a TEFASProvider whose ``_client.post`` returns the given mocks."""
    provider = TEFASProvider.__new__(TEFASProvider)
    provider._client = MagicMock()
    provider._client.post = MagicMock(side_effect=post_side_effect)
    provider._cache = Cache()
    return provider


# =============================================================================
# get_history with fonFiyatBilgiGetir
# =============================================================================


HISTORY_ROWS = [
    {"fonKodu": "AAK", "fonUnvan": "AK PORTFOY", "tarih": "2026-04-01", "fiyat": 35.10},
    {"fonKodu": "AAK", "fonUnvan": "AK PORTFOY", "tarih": "2026-04-15", "fiyat": 35.30},
    {"fonKodu": "AAK", "fonUnvan": "AK PORTFOY", "tarih": "2026-04-30", "fiyat": 35.21},
]


class TestPeriodToPeriyod:
    """``_resolve_periyod`` maps borsapy period strings to API codes."""

    def test_default_mapping(self):
        provider = TEFASProvider.__new__(TEFASProvider)
        for label, code in [
            ("1d", 13), ("5d", 13), ("1mo", 1), ("3mo", 3), ("6mo", 6),
            ("ytd", 0), ("1y", 12), ("3y", 36), ("5y", 60), ("max", 60),
        ]:
            assert provider._resolve_periyod(label, None, None) == code, label

    def test_unknown_period_falls_back_to_1mo(self):
        provider = TEFASProvider.__new__(TEFASProvider)
        assert provider._resolve_periyod("eternity", None, None) == 1

    def test_explicit_start_picks_smallest_covering_bucket(self):
        from datetime import datetime, timedelta
        provider = TEFASProvider.__new__(TEFASProvider)
        now = datetime.now()
        # 5 days back -> weekly (13)
        assert provider._resolve_periyod("ignored", now - timedelta(days=5), None) == 13
        # 25 days back -> 1 month bucket
        assert provider._resolve_periyod("ignored", now - timedelta(days=25), None) == 1
        # 100 days back -> 6 month bucket
        assert provider._resolve_periyod("ignored", now - timedelta(days=100), None) == 6
        # 4 years back -> 5 year bucket
        assert provider._resolve_periyod("ignored", now - timedelta(days=365 * 4), None) == 60


class TestGetHistoryMocked:
    def test_returns_dataframe_with_price(self):
        provider = _make_provider([_mock_response(_envelope(HISTORY_ROWS))])
        df = provider.get_history("AAK", period="1mo")
        assert isinstance(df, pd.DataFrame)
        assert "Price" in df.columns
        assert df["Price"].iloc[0] == 35.10
        assert len(df) == 3
        # Index is datetime
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_legacy_columns_present_for_compat(self):
        provider = _make_provider([_mock_response(_envelope(HISTORY_ROWS))])
        df = provider.get_history("AAK", period="1mo")
        # FundSize and Investors no longer come from the API but kept for compat
        assert "FundSize" in df.columns
        assert "Investors" in df.columns

    def test_calls_correct_endpoint_with_periyod(self):
        provider = _make_provider([_mock_response(_envelope(HISTORY_ROWS))])
        provider.get_history("AAK", period="3y")
        called_url, called_kwargs = (
            provider._client.post.call_args.args,
            provider._client.post.call_args.kwargs,
        )
        # URL is positional first arg
        assert "fonFiyatBilgiGetir" in called_url[0]
        # JSON body has periyod=36 for 3y
        assert called_kwargs["json"]["periyod"] == 36
        assert called_kwargs["json"]["fonKodu"] == "AAK"

    def test_empty_result_raises_data_not_available(self):
        provider = _make_provider([_mock_response(_envelope([]))])
        with pytest.raises(DataNotAvailableError):
            provider.get_history("ZZZ", period="1mo")

    def test_client_side_date_filtering(self):
        from datetime import datetime
        provider = _make_provider([_mock_response(_envelope(HISTORY_ROWS))])
        df = provider.get_history(
            "AAK",
            start=datetime(2026, 4, 10),
            end=datetime(2026, 4, 20),
        )
        # Only the 2026-04-15 row should remain
        assert len(df) == 1
        assert df.index[0] == pd.Timestamp("2026-04-15")
        assert df["Price"].iloc[0] == 35.30

    def test_filtered_to_empty_raises(self):
        from datetime import datetime
        provider = _make_provider([_mock_response(_envelope(HISTORY_ROWS))])
        with pytest.raises(DataNotAvailableError):
            provider.get_history(
                "AAK",
                start=datetime(2030, 1, 1),
                end=datetime(2030, 12, 31),
            )

    def test_caches_by_periyod(self):
        provider = _make_provider([_mock_response(_envelope(HISTORY_ROWS))])
        provider.get_history("AAK", period="1mo")
        provider.get_history("AAK", period="1mo")
        # Only one underlying API call thanks to cache
        assert provider._client.post.call_count == 1

    def test_returns_propagated_api_error(self):
        err_resp = _mock_response(
            {"errorCode": None, "errorMessage": "Sistem Hatası!!", "resultList": None}
        )
        provider = _make_provider([err_resp])
        with pytest.raises(APIError, match="Sistem Hatası"):
            provider.get_history("AAK", period="1mo")


# =============================================================================
# get_fund_detail merges fonProfilBilgiGetir
# =============================================================================


FUND_INFO_ROW = {
    "fonKodu": "AAK",
    "fonUnvan": "AK PORTFOY",
    "sonFiyat": 35.21,
    "portBuyukluk": 1_500_000_000.0,
    "yatirimciSayi": 12345,
    "fonKategori": "Karma Fon",
    "gunlukGetiri": 0.42,
    "kategoriDerece": 30,
    "kategoriFonSay": 100,
    "pazarPayi": 0.5,
}

FUND_RETURN_ROW = {
    "fonKodu": "AAK",
    "fonTurAciklama": "Karma Şemsiye Fonu",
    "riskDegeri": "4",
    "getiri1a": 4.78,
    "getiri3a": 2.29,
    "getiri6a": 16.27,
    "getiriyb": 8.88,
    "getiri1y": 40.20,
    "getiri3y": 255.65,
    "getiri5y": 692.75,
}

FUND_PROFILE_ROW = {
    "fonKodu": "AAK",
    "fonUnvan": "AK PORTFOY",
    "isinKodu": "TRMAF1WWWWW4",
    "sonIsSaat": "17:30",
    "basIsSaat": "09:00",
    "minAlis": 1,
    "minSatis": 1,
    "maxAlis": None,
    "maxSatis": None,
    "fonGeriAlisValor": 1,
    "fonSatisValor": 2,
    "girisKomisyonu": None,
    "cikisKomisyonu": None,
    "kapLink": "https://www.kap.org.tr/tr/fon-bilgileri/genel/aak",
    "tefasDurum": "TEFAS'ta işlem görüyor",
    "riskDegeri": "4",
}


class TestGetFundDetailV2:
    def test_includes_isin_and_kap_link(self):
        # 3 sequential API calls: fonBilgiGetir, fonGetiriBazliBilgiGetir, fonProfilBilgiGetir
        provider = _make_provider([
            _mock_response(_envelope([FUND_INFO_ROW])),
            _mock_response(_envelope([FUND_RETURN_ROW])),
            _mock_response(_envelope([FUND_PROFILE_ROW])),
        ])
        detail = provider.get_fund_detail("AAK")
        assert detail["isin"] == "TRMAF1WWWWW4"
        assert detail["kap_link"].startswith("https://www.kap.org.tr/")
        assert detail["last_trading_time"] == "17:30"
        assert detail["first_trading_time"] == "09:00"
        assert detail["buy_valor"] == 1
        assert detail["sell_valor"] == 2
        assert detail["tefas_status"] == "TEFAS'ta işlem görüyor"

    def test_includes_returns_from_returns_endpoint(self):
        provider = _make_provider([
            _mock_response(_envelope([FUND_INFO_ROW])),
            _mock_response(_envelope([FUND_RETURN_ROW])),
            _mock_response(_envelope([FUND_PROFILE_ROW])),
        ])
        detail = provider.get_fund_detail("AAK")
        assert detail["return_1y"] == 40.20
        assert detail["return_5y"] == 692.75
        assert detail["fund_type"] == "Karma Şemsiye Fonu"

    def test_fund_class_detected_yat(self):
        provider = _make_provider([
            _mock_response(_envelope([FUND_INFO_ROW])),
            _mock_response(_envelope([FUND_RETURN_ROW])),
            _mock_response(_envelope([FUND_PROFILE_ROW])),
        ])
        detail = provider.get_fund_detail("AAK", fund_type="YAT")
        assert detail["fund_class"] == "YAT"

    def test_fund_class_falls_back_to_emk_on_yat_miss(self):
        # YAT list doesn't contain AAK; EMK does.
        provider = _make_provider([
            _mock_response(_envelope([FUND_INFO_ROW])),  # fonBilgiGetir
            _mock_response(_envelope([{"fonKodu": "OTHER"}])),  # YAT returns — miss
            _mock_response(_envelope([FUND_RETURN_ROW])),  # EMK returns — hit
            _mock_response(_envelope([FUND_PROFILE_ROW])),
        ])
        detail = provider.get_fund_detail("AAK", fund_type="YAT")
        assert detail["fund_class"] == "EMK"

    def test_profile_fetch_failure_does_not_break_detail(self):
        # fonProfilBilgiGetir returns error — should still return detail with None ISIN
        bad = _mock_response(
            {"errorCode": None, "errorMessage": "Sistem Hatası!!", "resultList": None}
        )
        provider = _make_provider([
            _mock_response(_envelope([FUND_INFO_ROW])),
            _mock_response(_envelope([FUND_RETURN_ROW])),
            bad,
        ])
        detail = provider.get_fund_detail("AAK")
        assert detail["fund_code"] == "AAK"
        assert detail["isin"] is None
        assert detail["kap_link"] is None

    def test_no_data_raises(self):
        provider = _make_provider([_mock_response(_envelope([]))])
        with pytest.raises(DataNotAvailableError):
            provider.get_fund_detail("UNKNOWN")


# =============================================================================
# get_allocation (Playwright-based)
# =============================================================================


# Real TEFAS SSR HTML embeds escaped JSON inside a <script> as
#   \"fonKodu\":\"AAK\",\"kiymetTip\":\"Hisse Senedi\",\"portfoyOrani\":29.75
# Each backslash-quote is a single escape (\ + ").
SAMPLE_SSR_HTML = r"""
<html><head></head><body>
<script>
window.__data = "...\"varlikData\":[
  {\"fonKodu\":\"AAK\",\"kiymetTip\":\"Hisse Senedi\",\"portfoyOrani\":29.75},
  {\"fonKodu\":\"AAK\",\"kiymetTip\":\"Ters-Repo\",\"portfoyOrani\":18.40},
  {\"fonKodu\":\"AAK\",\"kiymetTip\":\"Finansman Bonosu\",\"portfoyOrani\":5.40}
]...";
</script>
</body></html>
"""


class TestGetAllocationParsing:
    def test_parses_varlikdata_from_html(self):
        provider = TEFASProvider.__new__(TEFASProvider)
        provider._cache = Cache()
        with patch.object(provider, "_fetch_fund_page_html", return_value=SAMPLE_SSR_HTML):
            df = provider.get_allocation("AAK")
        assert isinstance(df, pd.DataFrame)
        assert set(df["asset_type"]) == {"Hisse Senedi", "Ters-Repo", "Finansman Bonosu"}
        # Sorted descending by weight
        assert df["weight"].iloc[0] == 29.75
        assert df["weight"].iloc[-1] == 5.40
        # Standardization applied
        assert "Stocks" in df["asset_name"].values

    def test_no_matches_raises_data_not_available(self):
        provider = TEFASProvider.__new__(TEFASProvider)
        provider._cache = Cache()
        with patch.object(provider, "_fetch_fund_page_html", return_value="<html></html>"):
            with pytest.raises(DataNotAvailableError):
                provider.get_allocation("AAK")

    def test_caches_result(self):
        provider = TEFASProvider.__new__(TEFASProvider)
        provider._cache = Cache()
        with patch.object(
            provider, "_fetch_fund_page_html", return_value=SAMPLE_SSR_HTML
        ) as mock_fetch:
            provider.get_allocation("AAK")
            provider.get_allocation("AAK")
        assert mock_fetch.call_count == 1


class TestPlaywrightLazyImport:
    def test_missing_playwright_raises_helpful_importerror(self, monkeypatch):
        provider = TEFASProvider.__new__(TEFASProvider)
        provider._cache = Cache()

        # Force the playwright import to fail
        import sys
        monkeypatch.setitem(sys.modules, "playwright.sync_api", None)

        with pytest.raises(ImportError) as exc_info:
            provider._fetch_fund_page_html("AAK")
        msg = str(exc_info.value)
        assert "playwright" in msg.lower()
        assert "borsapy[allocation]" in msg
