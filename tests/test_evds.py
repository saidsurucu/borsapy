"""Tests for EVDS (TCMB Elektronik Veri Dağıtım Sistemi) module.

Live tests cover the anonymous v3 backend endpoints (categories, serieList,
dashboards, baslangicBitis). Tests for ``POST /fe`` (the data endpoint) are
marked ``integration`` and may fail when the TCMB gateway is degraded —
that is a backend availability issue, not a borsapy bug.
"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from borsapy._providers.evds import (
    AGGREGATION,
    BASE_URL,
    FORMULA,
    FREQUENCY,
    NUMERIC_FREQ_NORMALIZE,
    EVDSProvider,
    _format_date,
    clear_evds_key,
    denormalize_code,
    get_evds_key,
    get_evds_provider,
    normalize_code,
    period_to_dates,
    set_evds_key,
)
from borsapy.evds import (
    EVDS,
    EVDSSeries,
    _frame_from_payload,
    _parse_evds_date,
    evds_categories,
    evds_download,
    evds_search,
    evds_series,
)
from borsapy.exceptions import APIError, DataNotAvailableError

# =============================================================================
# Helper / pure function tests (unit, no network)
# =============================================================================


class TestCodeNormalization:
    def test_dot_to_underscore(self):
        assert normalize_code("TP.DK.USD.A") == "TP_DK_USD_A"

    def test_underscore_passthrough(self):
        assert normalize_code("TP_DK_USD_A") == "TP_DK_USD_A"

    def test_underscore_to_dot(self):
        assert denormalize_code("TP_DK_USD_A") == "TP.DK.USD.A"

    def test_dot_passthrough(self):
        assert denormalize_code("TP.DK.USD.A") == "TP.DK.USD.A"

    def test_round_trip(self):
        original = "TP.FG.J0"
        assert denormalize_code(normalize_code(original)) == original


class TestDateFormat:
    def test_iso_string(self):
        assert _format_date("2024-01-15") == "15-01-2024"

    def test_dd_mm_yyyy_string(self):
        assert _format_date("15-01-2024") == "15-01-2024"

    def test_dotted_string(self):
        assert _format_date("15.01.2024") == "15-01-2024"

    def test_date_object(self):
        assert _format_date(date(2024, 1, 15)) == "15-01-2024"

    def test_datetime_object(self):
        assert _format_date(datetime(2024, 1, 15, 12, 30)) == "15-01-2024"

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            _format_date("not-a-date")

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            _format_date(12345)


class TestPeriodToDates:
    def test_1y(self):
        start, end = period_to_dates("1y")
        assert len(start) == 10 and len(end) == 10
        assert start.split("-")[2].isdigit()  # ends with year

    def test_max(self):
        start, end = period_to_dates("max")
        assert int(start.split("-")[2]) <= 1950

    def test_ytd(self):
        start, end = period_to_dates("ytd")
        assert start.startswith("01-01-")

    def test_invalid_period(self):
        with pytest.raises(ValueError):
            period_to_dates("99x")

    def test_case_insensitive(self):
        s1, e1 = period_to_dates("1Y")
        s2, e2 = period_to_dates("1y")
        assert s1 == s2 and e1 == e2


class TestParseEvdsDate:
    def test_dd_mm_yyyy(self):
        result = _parse_evds_date("15-01-2024")
        assert result == pd.Timestamp("2024-01-15")

    def test_yyyy_mm(self):
        result = _parse_evds_date("2024-01")
        assert result == pd.Timestamp("2024-01-01")

    def test_yyyy_only(self):
        result = _parse_evds_date("2024")
        assert result == pd.Timestamp("2024-01-01")

    def test_none(self):
        assert _parse_evds_date(None) is None

    def test_empty(self):
        assert _parse_evds_date("") is None

    def test_passthrough_timestamp(self):
        ts = pd.Timestamp("2024-01-15")
        assert _parse_evds_date(ts) == ts


class TestEnumConstants:
    def test_frequency_keys(self):
        assert "daily" in FREQUENCY
        assert "monthly" in FREQUENCY
        assert "annual" in FREQUENCY
        # Backend integer encoding (from bundle: 5=MONTH, 8=YEAR).
        assert FREQUENCY["monthly"] == 5
        assert FREQUENCY["annual"] == 8

    def test_aggregation_values(self):
        for agg in ("avg", "min", "max", "first", "last", "sum"):
            assert agg in AGGREGATION

    def test_formula_values(self):
        # ID 0..8, with snake_case keys.
        assert FORMULA["level"] == ("0", "Düzey")
        assert FORMULA["pct_change"][0] == "1"
        assert FORMULA["yoy_pct"][0] == "3"

    def test_numeric_freq_normalize(self):
        # Metadata sometimes uses 9/13/16/18 (legacy v2 codes); these must
        # map to the bundle's 1..8 encoding.
        assert NUMERIC_FREQ_NORMALIZE[9] == 5     # 9 (AYLIK metadata) → 5 (MONTH)
        assert NUMERIC_FREQ_NORMALIZE[13] == 6    # 13 → 6 (QUARTER)
        assert NUMERIC_FREQ_NORMALIZE[18] == 8    # 18 → 8 (YEAR)
        assert NUMERIC_FREQ_NORMALIZE[5] == 5     # passthrough


# =============================================================================
# Provider unit tests (mocked HTTP)
# =============================================================================


class TestProviderResolveFrequency:
    @pytest.fixture
    def provider(self):
        return EVDSProvider()

    def test_snake_case(self, provider):
        assert provider._resolve_frequency("daily") == 1
        assert provider._resolve_frequency("monthly") == 5
        assert provider._resolve_frequency("annual") == 8

    def test_integer(self, provider):
        assert provider._resolve_frequency(5) == 5
        assert provider._resolve_frequency(9) == 5  # metadata 9 → MONTH

    def test_string_int(self, provider):
        assert provider._resolve_frequency("5") == 5

    def test_invalid(self, provider):
        with pytest.raises(ValueError):
            provider._resolve_frequency("monthlyish")


class TestProviderResolveFormula:
    @pytest.fixture
    def provider(self):
        return EVDSProvider()

    def test_snake_case_key(self, provider):
        fid, label = provider._resolve_formula("level")
        assert fid == "0" and label == "Düzey"

    def test_string_id(self, provider):
        fid, label = provider._resolve_formula("3")
        assert fid == "3" and "Yıllık" in label

    def test_invalid_raises(self, provider):
        with pytest.raises(ValueError):
            provider._resolve_formula("madeup")


class TestProviderGetSeriesDataValidation:
    """Argument validation + REST routing for get_series_data.

    POST /fe and any other fallback paths have been removed in v0.10.0; an
    EVDS API key is now required for time-series fetches.
    """

    @pytest.fixture
    def provider(self):
        import borsapy._providers.evds as mod
        from borsapy.cache import get_cache
        get_cache().clear()
        clear_evds_key()
        mod._provider = None
        set_evds_key("dummy-test-key-for-validation")
        p = get_evds_provider()
        # Stub the REST call so arg checks never hit the network.
        p._get_series_data_rest = MagicMock(return_value={"items": []})
        yield p
        clear_evds_key()
        mod._provider = None
        get_cache().clear()

    def test_single_series_routes_to_rest(self, provider):
        provider.get_series_data(
            "TP.FG.J0",
            start="2024-01-01", end="2024-12-31",
        )
        kwargs = provider._get_series_data_rest.call_args.kwargs
        # REST endpoint requires DOT-form (verified against TCMB Web Service guide)
        assert kwargs["codes_str"] == "TP.FG.J0"
        assert kwargs["agg_str"] == "avg"
        assert kwargs["formulas_str"] == "0"
        assert kwargs["start_str"] == "01-01-2024"
        assert kwargs["end_str"] == "31-12-2024"
        assert kwargs["freq_int"] == 5            # MONTH (default monthly)

    def test_multi_series_dash_joined(self, provider):
        provider.get_series_data(
            ["TP.FG.J0", "TP.DK.USD.A"],
            start="2024-01-01", end="2024-12-31",
            aggregation=["avg", "last"],
            formula=["level", "yoy_pct"],
        )
        kwargs = provider._get_series_data_rest.call_args.kwargs
        assert kwargs["codes_str"] == "TP.FG.J0-TP.DK.USD.A"
        assert kwargs["agg_str"] == "avg-last"
        assert kwargs["formulas_str"] == "0-3"

    def test_aggregation_list_length_mismatch(self, provider):
        with pytest.raises(ValueError, match="aggregation list length"):
            provider.get_series_data(
                ["TP.FG.J0", "TP.DK.USD.A"],
                start="2024-01-01", end="2024-12-31",
                aggregation=["avg"],
            )

    def test_max_series_enforced(self, provider):
        too_many = [f"TP.X.{i}" for i in range(provider.MAX_SERIES_PER_CALL + 1)]
        with pytest.raises(ValueError, match="max"):
            provider.get_series_data(too_many, start="2024-01-01", end="2024-12-31")


class TestProviderRequiresApiKey:
    """Without an EVDS API key, get_series_data raises a clear APIError —
    no POST /fe or stealth-browser fallback is attempted (those were
    removed in v0.10.0 because the gateway returns 500 for every external
    client)."""

    @pytest.fixture(autouse=True)
    def _clear_key(self):
        import borsapy._providers.evds as mod
        from borsapy.cache import get_cache
        clear_evds_key()
        mod._provider = None
        get_cache().clear()
        yield
        clear_evds_key()
        mod._provider = None
        get_cache().clear()

    def test_raises_when_no_key(self):
        p = get_evds_provider()
        # Defensive: ensure no inherited header sneaks in
        p._client.headers.pop("key", None)
        assert not p.has_api_key
        with pytest.raises(APIError, match="API key"):
            p.get_series_data(
                "TP.DK.USD.A",
                start="2024-01-01", end="2024-12-31",
            )


class TestApiKeyManagement:
    def test_set_and_get(self):
        set_evds_key("my-secret-key")
        try:
            assert get_evds_key() == "my-secret-key"
        finally:
            clear_evds_key()

    def test_clear(self, monkeypatch):
        monkeypatch.delenv("EVDS_API_KEY", raising=False)
        set_evds_key("temp")
        clear_evds_key()
        assert get_evds_key() is None or get_evds_key() == ""

    def test_invalid_key_raises(self):
        with pytest.raises(ValueError):
            set_evds_key("")
        with pytest.raises(ValueError):
            set_evds_key(None)

    def test_env_var_fallback(self, monkeypatch):
        clear_evds_key()
        monkeypatch.setenv("EVDS_API_KEY", "env-key-abc")
        assert get_evds_key() == "env-key-abc"


class TestProviderGetSeriesRange:
    @pytest.fixture
    def provider(self):
        p = EVDSProvider()
        p._post_json = MagicMock(
            return_value=[
                {"SERIE_CODE": "TP_FG_J0", "START_DATE": "01-01-2003", "END_DATE": "01-11-2025"}
            ]
        )
        return p

    def test_body_shape(self, provider):
        provider.get_series_range(
            ["TP.FG.J0"], datagroup_codes=["bie_tukfiy4"], frequency="monthly"
        )
        path, body = provider._post_json.call_args[0]
        assert path == "/serieList/baslangicBitis"
        assert body == {
            "frequency": 5,
            "series": ["TP_FG_J0"],
            "datagroups": ["bie_tukfiy4"],
        }

    def test_returns_normalized_dict(self, provider):
        out = provider.get_series_range(
            ["TP.FG.J0"], datagroup_codes=["bie_tukfiy4"], frequency="monthly"
        )
        assert "TP_FG_J0" in out
        assert out["TP_FG_J0"]["start"] == "01-01-2003"


class TestProviderHelpers:
    @pytest.fixture
    def provider(self):
        return EVDSProvider()

    def test_api_url(self, provider):
        assert provider._api("/fe") == f"{BASE_URL}/igmevdsms-dis/fe"

    def test_singleton(self):
        a = get_evds_provider()
        b = get_evds_provider()
        assert a is b


# =============================================================================
# DataFrame conversion tests
# =============================================================================


class TestFrameFromPayload:
    def test_items_with_tarih_column(self):
        payload = {
            "totalCount": 2,
            "items": [
                {"Tarih": "2024-01-01", "TP_FG_J0": "100.50"},
                {"Tarih": "2024-02-01", "TP_FG_J0": "102.30"},
            ],
        }
        df = _frame_from_payload(payload, ["TP.FG.J0"])
        assert len(df) == 2
        assert "Value" in df.columns                    # single-series renamed
        assert df["Value"].iloc[0] == pytest.approx(100.50)

    def test_data_wrapper(self):
        payload = {"data": [{"Tarih": "2024-01-01", "TP_FG_J0": "1.0"}]}
        df = _frame_from_payload(payload, ["TP.FG.J0"])
        assert len(df) == 1

    def test_empty_payload(self):
        assert _frame_from_payload({}, ["X"]).empty

    def test_multi_series_keeps_columns(self):
        payload = {
            "items": [
                {"Tarih": "2024-01-01", "TP_FG_J0": "1.0", "TP_DK_USD_A": "30.0"},
            ],
        }
        df = _frame_from_payload(payload, ["TP.FG.J0", "TP.DK.USD.A"])
        # Surface user-facing dot-codes.
        assert set(df.columns) == {"TP.FG.J0", "TP.DK.USD.A"}


# =============================================================================
# User-facing class unit tests (mocked provider)
# =============================================================================


class TestEVDSSeriesUnit:
    def test_init_validates_code(self):
        with pytest.raises(ValueError):
            EVDSSeries("")
        with pytest.raises(ValueError):
            EVDSSeries(None)

    def test_code_property(self):
        s = EVDSSeries("TP.DK.USD.A")
        assert s.code == "TP.DK.USD.A"
        assert s._code_normalized == "TP_DK_USD_A"

    def test_info_lookup_uses_dot_form(self):
        with patch("borsapy.evds.get_evds_provider") as mp:
            mock_provider = MagicMock()
            mock_provider.find_series.return_value = {
                "SERIE_CODE": "TP.DK.USD.A",
                "SERIE_NAME": "USD",
                "FREQUENCY_STR": "GÜNLÜK",
                "FREQUENCY": 1,
                "_datagroup": {"DATAGROUP_CODE": "bie_dkdovizgn"},
                "_category": {"TOPIC_TITLE_TR": "TCMB DÖVİZ KURLARI"},
            }
            mp.return_value = mock_provider
            s = EVDSSeries("TP.DK.USD.A")
            info = s.info
            assert info["SERIE_CODE"] == "TP.DK.USD.A"
            assert info["DATAGROUP_CODE"] == "bie_dkdovizgn"
            assert info["CATEGORY_TR"] == "TCMB DÖVİZ KURLARI"

    def test_info_raises_when_missing(self):
        with patch("borsapy.evds.get_evds_provider") as mp:
            mp.return_value.find_series.return_value = None
            with pytest.raises(DataNotAvailableError):
                _ = EVDSSeries("TP.MADE.UP").info

    def test_native_frequency_from_metadata_int(self):
        with patch("borsapy.evds.get_evds_provider") as mp:
            mp.return_value.find_series.return_value = {
                "SERIE_CODE": "TP_X",
                "FREQUENCY": 9,    # legacy AYLIK
                "FREQUENCY_STR": "AYLIK",
            }
            s = EVDSSeries("TP.X")
            assert s.native_frequency == "monthly"


class TestEVDSCatalogUnit:
    def test_categories_dataframe(self):
        with patch("borsapy.evds.get_evds_provider") as mp:
            mp.return_value.get_categories.return_value = [
                {
                    "CATEGORY_ID": 1, "TOPIC_TITLE_TR": "A", "TOPIC_TITLE_ENG": "A",
                    "UST_CATEGORY_ID": 0, "SEVIYE": 1,
                    "DATAGROUPS": [{"DATAGROUP_CODE": "g1"}, {"DATAGROUP_CODE": "g2"}],
                },
            ]
            df = EVDS().categories
            assert len(df) == 1
            assert df.iloc[0]["DATAGROUP_COUNT"] == 2

    def test_search_datagroups_only(self):
        with patch("borsapy.evds.get_evds_provider") as mp:
            mp.return_value.get_categories.return_value = [
                {
                    "CATEGORY_ID": 1, "TOPIC_TITLE_TR": "Faiz",
                    "TOPIC_TITLE_ENG": "Rates",
                    "DATAGROUPS": [
                        {
                            "DATAGROUP_CODE": "g1",
                            "DATAGROUP_TYPE": "Dolar Kuru",
                            "DATAGROUP_TYPE_ENG": "Dollar Rate",
                        },
                        {
                            "DATAGROUP_CODE": "g2",
                            "DATAGROUP_TYPE": "Euro Kuru",
                            "DATAGROUP_TYPE_ENG": "Euro Rate",
                        },
                    ],
                },
            ]
            hits = EVDS().search("dolar", scope="datagroups")
            assert len(hits) == 1
            assert hits.iloc[0]["CODE"] == "g1"


# =============================================================================
# Integration tests (live API; require --run-integration)
# =============================================================================


@pytest.mark.integration
class TestEVDSAnonymousLive:
    """Verify the anonymous EVDS v3 endpoints with a real network call."""

    def test_categories(self):
        df = EVDS().categories
        assert isinstance(df, pd.DataFrame)
        assert len(df) >= 100, f"expected ≥100 categories, got {len(df)}"
        assert {"CATEGORY_ID", "TOPIC_TITLE_TR", "TOPIC_TITLE_EN"} <= set(df.columns)

    def test_datagroups_filter(self):
        df = EVDS().datagroups(category_id=400401)
        assert not df.empty
        assert all(df["CATEGORY_ID"] == 400401)

    def test_series_in_dkdovizgn(self):
        df = EVDS().series_in_group("bie_dkdovizgn")
        assert len(df) > 100
        # USD buying-rate series must be present.
        assert (df["SERIE_CODE"].str.upper() == "TP.DK.USD.A").any()

    def test_search_dolar(self):
        hits = EVDS().search("dolar", scope="datagroups")
        assert len(hits) >= 1

    def test_dashboard_baslica(self):
        dash = EVDS().dashboard("baslica-gostergeler")
        assert "chartsList" in dash
        assert len(dash["chartsList"]) > 0

    def test_evdsseries_info(self):
        info = EVDSSeries("TP.DK.USD.A").info
        assert info["SERIE_CODE"] == "TP.DK.USD.A"
        assert info["DATAGROUP_CODE"] == "bie_dkdovizgn"

    def test_module_shortcut_categories(self):
        df = evds_categories()
        assert len(df) >= 100

    def test_module_shortcut_search(self):
        df = evds_search("kur", scope="datagroups")
        assert len(df) >= 1


@pytest.mark.integration
class TestEVDSRestLive:
    """REST time-series endpoint (key required).

    Run with ``EVDS_API_KEY=<your_key> pytest --run-integration -k Rest``.
    Skipped when no key is configured so CI stays green.
    """

    def test_evds_series_usd_1mo(self):
        if not get_evds_key():
            pytest.skip("EVDS_API_KEY not set; cannot exercise REST endpoint")
        df = evds_series("TP.DK.USD.A", period="1mo", frequency="daily")
        assert isinstance(df, pd.DataFrame)
        assert "Value" in df.columns or df.shape[1] >= 1

    def test_evds_download_multi(self):
        if not get_evds_key():
            pytest.skip("EVDS_API_KEY not set; cannot exercise REST endpoint")
        df = evds_download(
            ["TP.DK.USD.A", "TP.DK.EUR.A"], period="1mo", frequency="daily"
        )
        assert isinstance(df, pd.DataFrame)
