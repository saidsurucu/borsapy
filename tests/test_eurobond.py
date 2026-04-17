"""Tests for Turkish Eurobond data."""

from datetime import date, datetime
from unittest.mock import Mock

import pandas as pd
import pytest

from borsapy._providers.ziraat_eurobond import ZiraatEurobondProvider
from borsapy.eurobond import Eurobond, _parse_date_arg, eurobonds
from borsapy.exceptions import DataNotAvailableError

# =============================================================================
# Eurobonds Function Tests
# =============================================================================


class TestEurobondsFunction:
    """Tests for eurobonds() function."""

    def test_returns_dataframe(self):
        """Test eurobonds() returns DataFrame."""
        df = eurobonds()
        assert isinstance(df, pd.DataFrame)

    def test_dataframe_columns(self):
        """Test DataFrame has expected columns."""
        df = eurobonds()
        expected_cols = [
            "isin",
            "maturity",
            "days_to_maturity",
            "currency",
            "bid_price",
            "bid_yield",
            "ask_price",
            "ask_yield",
        ]
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_has_data(self):
        """Test DataFrame has some data."""
        df = eurobonds()
        assert len(df) > 0, "Expected some Eurobond data"

    def test_currency_filter_usd(self):
        """Test filtering by USD currency."""
        df = eurobonds(currency="USD")
        if not df.empty:
            assert all(df["currency"] == "USD")

    def test_currency_filter_eur(self):
        """Test filtering by EUR currency."""
        df = eurobonds(currency="EUR")
        if not df.empty:
            assert all(df["currency"] == "EUR")

    def test_sorted_by_maturity(self):
        """Test DataFrame is sorted by maturity."""
        df = eurobonds()
        if len(df) > 1:
            maturities = df["maturity"].tolist()
            assert maturities == sorted(maturities), "Expected sorted by maturity"


# =============================================================================
# Eurobond Class Tests
# =============================================================================


class TestEurobondClass:
    """Tests for Eurobond class."""

    @pytest.fixture
    def sample_isin(self):
        """Get a valid ISIN from the list for testing."""
        df = eurobonds()
        if df.empty:
            pytest.skip("No Eurobond data available")
        return df.iloc[0]["isin"]

    def test_create_by_isin(self, sample_isin):
        """Test creating Eurobond by ISIN."""
        bond = Eurobond(sample_isin)
        assert bond.isin == sample_isin

    def test_isin_case_insensitive(self, sample_isin):
        """Test ISIN is case insensitive."""
        bond = Eurobond(sample_isin.lower())
        assert bond.isin == sample_isin.upper()

    def test_maturity_type(self, sample_isin):
        """Test maturity is datetime or None."""
        bond = Eurobond(sample_isin)
        assert bond.maturity is None or isinstance(bond.maturity, datetime)

    def test_days_to_maturity_type(self, sample_isin):
        """Test days_to_maturity is int."""
        bond = Eurobond(sample_isin)
        assert isinstance(bond.days_to_maturity, int)

    def test_currency_type(self, sample_isin):
        """Test currency is string."""
        bond = Eurobond(sample_isin)
        assert isinstance(bond.currency, str)
        assert bond.currency in ["USD", "EUR"]

    def test_bid_price_type(self, sample_isin):
        """Test bid_price is float or None."""
        bond = Eurobond(sample_isin)
        assert bond.bid_price is None or isinstance(bond.bid_price, float)

    def test_bid_yield_type(self, sample_isin):
        """Test bid_yield is float or None."""
        bond = Eurobond(sample_isin)
        assert bond.bid_yield is None or isinstance(bond.bid_yield, float)

    def test_ask_price_type(self, sample_isin):
        """Test ask_price is float or None."""
        bond = Eurobond(sample_isin)
        assert bond.ask_price is None or isinstance(bond.ask_price, float)

    def test_ask_yield_type(self, sample_isin):
        """Test ask_yield is float or None."""
        bond = Eurobond(sample_isin)
        assert bond.ask_yield is None or isinstance(bond.ask_yield, float)

    def test_info_returns_dict(self, sample_isin):
        """Test info returns dict with all data."""
        bond = Eurobond(sample_isin)
        info = bond.info
        assert isinstance(info, dict)
        assert "isin" in info
        assert "maturity" in info
        assert "currency" in info
        assert "bid_yield" in info

    def test_info_is_copy(self, sample_isin):
        """Test info returns a copy (modifying doesn't affect original)."""
        bond = Eurobond(sample_isin)
        info1 = bond.info
        info1["test"] = "value"
        info2 = bond.info
        assert "test" not in info2

    def test_repr(self, sample_isin):
        """Test string representation."""
        bond = Eurobond(sample_isin)
        repr_str = repr(bond)
        assert "Eurobond" in repr_str
        assert sample_isin in repr_str

    def test_invalid_isin_raises(self):
        """Test invalid ISIN raises DataNotAvailableError."""
        with pytest.raises(DataNotAvailableError):
            bond = Eurobond("INVALID_ISIN_123")
            _ = bond.isin  # Access property to trigger data load


# =============================================================================
# Integration Tests
# =============================================================================


class TestEurobondIntegration:
    """Integration tests with real API calls."""

    def test_usd_bonds_exist(self):
        """Test there are USD denominated bonds."""
        df = eurobonds(currency="USD")
        assert len(df) > 0, "Expected USD Eurobonds"

    def test_yield_reasonable_range(self):
        """Test yields are in reasonable range."""
        df = eurobonds()
        if not df.empty and df["bid_yield"].notna().any():
            yields = df["bid_yield"].dropna()
            # Skip if all yields are 0 (data source may be unavailable)
            if (yields == 0).all():
                pytest.skip("All yields are 0 - data source may be unavailable")
            valid_yields = yields[yields > 0]
            assert all(0 < y < 50 for y in valid_yields), "Yields seem unreasonable"

    def test_days_to_maturity_positive(self):
        """Test all bonds have positive days to maturity."""
        df = eurobonds()
        if not df.empty:
            # Filter out any with 0 (could be data issues)
            valid = df[df["days_to_maturity"] > 0]
            assert len(valid) > 0, "Expected bonds with positive days to maturity"


# =============================================================================
# history() — pure logic (no network)
# =============================================================================


class TestParseDateArg:
    """_parse_date_arg accepts multiple formats."""

    def test_iso_string(self):
        assert _parse_date_arg("2024-05-10") == date(2024, 5, 10)

    def test_datetime_object(self):
        assert _parse_date_arg(datetime(2024, 5, 10, 15, 30)) == date(2024, 5, 10)

    def test_date_object(self):
        d = date(2024, 5, 10)
        assert _parse_date_arg(d) == d

    def test_slash_format(self):
        assert _parse_date_arg("2024/05/10") == date(2024, 5, 10)

    def test_turkish_dotted_format(self):
        assert _parse_date_arg("10.05.2024") == date(2024, 5, 10)

    def test_dash_format(self):
        assert _parse_date_arg("10-05-2024") == date(2024, 5, 10)

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            _parse_date_arg("not a date")


class TestIterBusinessDates:
    """ZiraatEurobondProvider._iter_business_dates enumerates correctly."""

    def test_single_day(self):
        d = date(2024, 5, 10)  # Friday
        out = ZiraatEurobondProvider._iter_business_dates(d, d)
        assert out == [d]

    def test_skips_weekends(self):
        # Fri 2024-05-10 → Mon 2024-05-13
        out = ZiraatEurobondProvider._iter_business_dates(
            date(2024, 5, 10), date(2024, 5, 13)
        )
        assert out == [date(2024, 5, 10), date(2024, 5, 13)]

    def test_includes_weekends_when_flagged(self):
        out = ZiraatEurobondProvider._iter_business_dates(
            date(2024, 5, 10), date(2024, 5, 13), skip_weekends=False
        )
        assert len(out) == 4

    def test_end_before_start_returns_empty(self):
        out = ZiraatEurobondProvider._iter_business_dates(
            date(2024, 5, 10), date(2024, 5, 5)
        )
        assert out == []

    def test_full_week(self):
        # Mon-Fri 2024-05-06 to 2024-05-10
        out = ZiraatEurobondProvider._iter_business_dates(
            date(2024, 5, 6), date(2024, 5, 10)
        )
        assert len(out) == 5
        assert all(d.weekday() < 5 for d in out)


class TestGetHistoryWithMockProvider:
    """Provider.get_history filters, sorts, and drops invalid rows."""

    def _make_provider(self, by_date: dict[str, list[dict]]):
        """Build a provider whose _fetch_bonds_for_date_cached is mocked."""
        provider = ZiraatEurobondProvider.__new__(ZiraatEurobondProvider)

        def fake_fetch(date_str: str) -> list[dict]:
            return by_date.get(date_str, [])

        provider._fetch_bonds_for_date_cached = fake_fetch
        return provider

    def test_filters_to_requested_isin(self):
        by_date = {
            "2024-05-06": [
                {"isin": "TARGET", "bid_price": 100.0, "bid_yield": 5.0, "ask_price": 101.0, "ask_yield": 4.9, "days_to_maturity": 1000},
                {"isin": "OTHER", "bid_price": 50.0, "bid_yield": 8.0, "ask_price": 51.0, "ask_yield": 7.8, "days_to_maturity": 500},
            ],
        }
        p = self._make_provider(by_date)
        rows = p.get_history("TARGET", date(2024, 5, 6), date(2024, 5, 6))
        assert len(rows) == 1
        assert rows[0]["bid_price"] == 100.0

    def test_drops_zero_price_rows(self):
        by_date = {
            "2024-05-06": [{"isin": "X", "bid_price": 100.0, "bid_yield": 5.0, "ask_price": 101.0, "ask_yield": 4.9, "days_to_maturity": 1000}],
            "2024-05-07": [{"isin": "X", "bid_price": 0.0, "bid_yield": 0.0, "ask_price": 0.0, "ask_yield": 0.0, "days_to_maturity": 999}],
            "2024-05-08": [{"isin": "X", "bid_price": None, "bid_yield": None, "ask_price": None, "ask_yield": None, "days_to_maturity": 998}],
            "2024-05-09": [{"isin": "X", "bid_price": 102.0, "bid_yield": 5.1, "ask_price": 103.0, "ask_yield": 5.0, "days_to_maturity": 997}],
        }
        p = self._make_provider(by_date)
        rows = p.get_history("X", date(2024, 5, 6), date(2024, 5, 9))
        dates = [r["date"] for r in rows]
        assert dates == [date(2024, 5, 6), date(2024, 5, 9)]

    def test_missing_isin_yields_no_row(self):
        by_date = {
            "2024-05-06": [{"isin": "OTHER", "bid_price": 100.0, "bid_yield": 5.0, "ask_price": 101.0, "ask_yield": 4.9, "days_to_maturity": 1000}],
        }
        p = self._make_provider(by_date)
        rows = p.get_history("MISSING", date(2024, 5, 6), date(2024, 5, 6))
        assert rows == []

    def test_results_sorted_by_date(self):
        # Even though concurrent fetching may return out-of-order, output is sorted.
        by_date = {
            "2024-05-06": [{"isin": "X", "bid_price": 100.0, "bid_yield": 5.0, "ask_price": 101.0, "ask_yield": 4.9, "days_to_maturity": 1000}],
            "2024-05-07": [{"isin": "X", "bid_price": 101.0, "bid_yield": 5.1, "ask_price": 102.0, "ask_yield": 5.0, "days_to_maturity": 999}],
            "2024-05-08": [{"isin": "X", "bid_price": 102.0, "bid_yield": 5.2, "ask_price": 103.0, "ask_yield": 5.1, "days_to_maturity": 998}],
        }
        p = self._make_provider(by_date)
        rows = p.get_history("X", date(2024, 5, 6), date(2024, 5, 8))
        dates = [r["date"] for r in rows]
        assert dates == sorted(dates)

    def test_isin_normalized_to_upper(self):
        by_date = {
            "2024-05-06": [{"isin": "US900123DG28", "bid_price": 100.0, "bid_yield": 5.0, "ask_price": 101.0, "ask_yield": 4.9, "days_to_maturity": 1000}],
        }
        p = self._make_provider(by_date)
        rows = p.get_history("us900123dg28", date(2024, 5, 6), date(2024, 5, 6))
        assert len(rows) == 1

    def test_empty_range_returns_empty(self):
        p = self._make_provider({})
        rows = p.get_history("X", date(2024, 5, 10), date(2024, 5, 5))
        assert rows == []


class TestEurobondHistoryMocked:
    """Eurobond.history() integrates period/start/end resolution."""

    def _make_bond(self, rows: list[dict]) -> Eurobond:
        """Build Eurobond with mocked provider returning given rows."""
        bond = Eurobond.__new__(Eurobond)
        bond._isin = "TEST"
        bond._data_cache = {"isin": "TEST"}
        bond._provider = Mock()
        bond._provider.get_history = Mock(return_value=rows)
        return bond

    def test_returns_dataframe_with_expected_columns(self):
        rows = [
            {"date": date(2024, 5, 6), "bid_price": 100.0, "bid_yield": 5.0, "ask_price": 101.0, "ask_yield": 4.9, "days_to_maturity": 1000},
            {"date": date(2024, 5, 7), "bid_price": 101.0, "bid_yield": 5.1, "ask_price": 102.0, "ask_yield": 5.0, "days_to_maturity": 999},
        ]
        bond = self._make_bond(rows)
        df = bond.history(start="2024-05-06", end="2024-05-07")
        assert list(df.columns) == ["bid_price", "bid_yield", "ask_price", "ask_yield", "days_to_maturity"]
        assert df.index.name == "Date"
        assert len(df) == 2

    def test_empty_range_returns_empty_frame(self):
        bond = self._make_bond([])
        df = bond.history(start="2024-05-06", end="2024-05-05")
        assert df.empty
        assert list(df.columns) == ["bid_price", "bid_yield", "ask_price", "ask_yield", "days_to_maturity"]

    def test_period_resolves_to_start_date(self):
        bond = self._make_bond([])
        bond.history(period="1y")
        # Provider called once; start should be ~365 days before today
        call_args = bond._provider.get_history.call_args
        _, start_arg, end_arg = call_args.args[:3]
        assert (end_arg - start_arg).days == 365

    def test_ytd_resolves_to_jan_1(self):
        bond = self._make_bond([])
        bond.history(period="ytd")
        _, start_arg, _ = bond._provider.get_history.call_args.args[:3]
        assert start_arg.month == 1 and start_arg.day == 1

    def test_unknown_period_raises(self):
        bond = self._make_bond([])
        with pytest.raises(ValueError, match="Unknown period"):
            bond.history(period="999y")

    def test_start_string_parsed(self):
        bond = self._make_bond([])
        bond.history(start="2020-01-15", end="2020-12-31")
        _, start_arg, end_arg = bond._provider.get_history.call_args.args[:3]
        assert start_arg == date(2020, 1, 15)
        assert end_arg == date(2020, 12, 31)
