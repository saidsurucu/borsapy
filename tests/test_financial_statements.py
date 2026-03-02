"""Tests for parametric financial statements (last_n) feature."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from borsapy._providers.isyatirim import IsYatirimProvider  # noqa: I001

# =============================================================================
# Unit Tests: _resolve_last_n
# =============================================================================


class TestResolveLastN:
    """Tests for last_n parameter validation and resolution."""

    def test_none_returns_default_5(self):
        assert IsYatirimProvider._resolve_last_n(None, quarterly=False) == 5

    def test_none_returns_default_5_quarterly(self):
        assert IsYatirimProvider._resolve_last_n(None, quarterly=True) == 5

    def test_integer_passthrough(self):
        assert IsYatirimProvider._resolve_last_n(10, quarterly=False) == 10

    def test_integer_1(self):
        assert IsYatirimProvider._resolve_last_n(1, quarterly=False) == 1

    def test_all_annual(self):
        assert IsYatirimProvider._resolve_last_n("all", quarterly=False) == 15

    def test_all_quarterly(self):
        assert IsYatirimProvider._resolve_last_n("all", quarterly=True) == 40

    def test_all_case_insensitive(self):
        assert IsYatirimProvider._resolve_last_n("ALL", quarterly=False) == 15
        assert IsYatirimProvider._resolve_last_n("All", quarterly=True) == 40

    def test_zero_raises_value_error(self):
        with pytest.raises(ValueError, match="positive integer"):
            IsYatirimProvider._resolve_last_n(0, quarterly=False)

    def test_negative_raises_value_error(self):
        with pytest.raises(ValueError, match="positive integer"):
            IsYatirimProvider._resolve_last_n(-1, quarterly=False)

    def test_invalid_string_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid last_n"):
            IsYatirimProvider._resolve_last_n("invalid", quarterly=False)

    def test_float_raises_value_error(self):
        with pytest.raises(ValueError):
            IsYatirimProvider._resolve_last_n(3.5, quarterly=False)


# =============================================================================
# Unit Tests: _get_periods
# =============================================================================


class TestGetPeriods:
    """Tests for period generation logic."""

    def setup_method(self):
        self.provider = IsYatirimProvider()

    def test_annual_count_5(self):
        periods = self.provider._get_periods(2026, quarterly=False, count=5)
        assert len(periods) == 5
        # Most recent first: 2025, 2024, 2023, 2022, 2021 (all period=12)
        assert periods[0] == (2025, 12)
        assert periods[4] == (2021, 12)

    def test_annual_count_10(self):
        periods = self.provider._get_periods(2026, quarterly=False, count=10)
        assert len(periods) == 10
        assert periods[0] == (2025, 12)
        assert periods[9] == (2016, 12)

    def test_annual_count_1(self):
        periods = self.provider._get_periods(2026, quarterly=False, count=1)
        assert len(periods) == 1
        assert periods[0] == (2025, 12)

    def test_quarterly_count_5_generates_exactly_5(self):
        """Fix: previously generated count*4 = 20 tuples."""
        with patch("borsapy._providers.isyatirim.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 15)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            periods = self.provider._get_periods(2026, quarterly=True, count=5)
        assert len(periods) == 5

    def test_quarterly_count_20(self):
        with patch("borsapy._providers.isyatirim.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 15)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            periods = self.provider._get_periods(2026, quarterly=True, count=20)
        assert len(periods) == 20

    def test_quarterly_start_month_jan(self):
        """Jan-Feb: latest available is Q3 of previous year."""
        with patch("borsapy._providers.isyatirim.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 15)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            periods = self.provider._get_periods(2026, quarterly=True, count=3)
        assert periods[0] == (2025, 9)  # Q3 2025
        assert periods[1] == (2025, 6)  # Q2 2025
        assert periods[2] == (2025, 3)  # Q1 2025

    def test_quarterly_start_month_mar(self):
        """Mar-May: latest available is Q4 of previous year."""
        with patch("borsapy._providers.isyatirim.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 1)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            periods = self.provider._get_periods(2026, quarterly=True, count=3)
        assert periods[0] == (2025, 12)  # Q4 2025
        assert periods[1] == (2025, 9)   # Q3 2025
        assert periods[2] == (2025, 6)   # Q2 2025

    def test_quarterly_start_month_jun(self):
        """Jun-Aug: latest available is Q1 of current year."""
        with patch("borsapy._providers.isyatirim.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 1)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            periods = self.provider._get_periods(2026, quarterly=True, count=3)
        assert periods[0] == (2026, 3)   # Q1 2026
        assert periods[1] == (2025, 12)  # Q4 2025
        assert periods[2] == (2025, 9)   # Q3 2025

    def test_quarterly_start_month_dec(self):
        """Dec: latest available is Q3 of current year."""
        with patch("borsapy._providers.isyatirim.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 12, 1)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            periods = self.provider._get_periods(2026, quarterly=True, count=2)
        assert periods[0] == (2026, 9)  # Q3 2026
        assert periods[1] == (2026, 6)  # Q2 2026

    def test_quarterly_wraps_year_boundary(self):
        """Quarters should wrap around year boundary correctly."""
        with patch("borsapy._providers.isyatirim.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 1)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            periods = self.provider._get_periods(2026, quarterly=True, count=8)
        # Q1 2026, Q4 2025, Q3 2025, Q2 2025, Q1 2025, Q4 2024, Q3 2024, Q2 2024
        assert periods[0] == (2026, 3)
        assert periods[4] == (2025, 3)
        assert periods[7] == (2024, 6)


# =============================================================================
# Unit Tests: _period_sort_key
# =============================================================================


class TestPeriodSortKey:
    """Tests for column sort key generation."""

    def test_annual_column(self):
        assert IsYatirimProvider._period_sort_key("2024") == (2024, 0)

    def test_quarterly_column(self):
        assert IsYatirimProvider._period_sort_key("2024Q3") == (2024, 3)

    def test_sorting_order_annual(self):
        cols = ["2022", "2024", "2023", "2021"]
        sorted_cols = sorted(cols, key=IsYatirimProvider._period_sort_key, reverse=True)
        assert sorted_cols == ["2024", "2023", "2022", "2021"]

    def test_sorting_order_quarterly(self):
        cols = ["2024Q1", "2023Q4", "2024Q3", "2023Q2", "2024Q2"]
        sorted_cols = sorted(cols, key=IsYatirimProvider._period_sort_key, reverse=True)
        assert sorted_cols == ["2024Q3", "2024Q2", "2024Q1", "2023Q4", "2023Q2"]

    def test_invalid_column_returns_zero(self):
        assert IsYatirimProvider._period_sort_key("Unknown") == (0, 0)


# =============================================================================
# Unit Tests: _parse_financial_response with quarterly flag
# =============================================================================


class TestParseFinancialResponse:
    """Tests for parsing API response with explicit quarterly flag."""

    def setup_method(self):
        self.provider = IsYatirimProvider()

    def _make_response(self, values):
        """Create a mock API response with given values."""
        items = []
        row = {"itemDescTr": "Revenue"}
        for i, val in enumerate(values, 1):
            row[f"value{i}"] = val
        items.append(row)
        return {"value": items}

    def test_annual_column_names(self):
        data = self._make_response([100, 200, 300])
        periods = [(2025, 12), (2024, 12), (2023, 12)]
        df = self.provider._parse_financial_response(data, periods, quarterly=False)
        assert list(df.columns) == ["2025", "2024", "2023"]

    def test_quarterly_column_names(self):
        data = self._make_response([100, 200, 300])
        periods = [(2025, 12), (2025, 9), (2025, 6)]
        df = self.provider._parse_financial_response(data, periods, quarterly=True)
        assert list(df.columns) == ["2025Q4", "2025Q3", "2025Q2"]

    def test_quarterly_flag_prevents_misdetection(self):
        """Single-quarter batch with period=12 should still be quarterly if flag says so."""
        data = self._make_response([100])
        periods = [(2025, 12)]
        df = self.provider._parse_financial_response(data, periods, quarterly=True)
        assert list(df.columns) == ["2025Q4"]

    def test_empty_data_returns_empty_df(self):
        df = self.provider._parse_financial_response({}, [], quarterly=False)
        assert df.empty

    def test_none_data_returns_empty_df(self):
        df = self.provider._parse_financial_response(None, [], quarterly=False)
        assert df.empty


# =============================================================================
# Unit Tests: Batching in get_financial_statements
# =============================================================================


class TestBatching:
    """Tests for multi-batch fetching logic."""

    def setup_method(self):
        self.provider = IsYatirimProvider()

    def _mock_fetch(self, quarterly=False):
        """Create a mock _fetch_financial_table that returns distinct DataFrames per batch."""
        call_count = {"n": 0}

        def side_effect(symbol, table_name, financial_group, periods, quarterly=False):
            call_count["n"] += 1
            batch_num = call_count["n"]
            records = []
            for _i, (year, period) in enumerate(periods):
                if quarterly:
                    col = f"{year}Q{period // 3}"
                else:
                    col = str(year)
                records.append(col)

            data = {"Item": ["Revenue", "COGS"]}
            for col in records:
                data[col] = [batch_num * 1000 + i for i, _ in enumerate(["Revenue", "COGS"])]

            df = pd.DataFrame(data).set_index("Item")
            return df

        return side_effect, call_count

    @patch.object(IsYatirimProvider, "_cache_get", return_value=None)
    @patch.object(IsYatirimProvider, "_cache_set")
    def test_single_batch_for_5_periods(self, mock_cache_set, mock_cache_get):
        """last_n=5 should result in 1 API call (1 batch of 5)."""
        fetch_mock, call_count = self._mock_fetch()
        with patch.object(self.provider, "_fetch_financial_table", side_effect=fetch_mock):
            result = self.provider.get_financial_statements(
                "THYAO", "income_stmt", quarterly=False, last_n=5
            )
        # income_stmt has 1 table → 1 batch → 1 call
        assert call_count["n"] == 1
        assert not result.empty

    @patch.object(IsYatirimProvider, "_cache_get", return_value=None)
    @patch.object(IsYatirimProvider, "_cache_set")
    def test_two_batches_for_10_periods(self, mock_cache_set, mock_cache_get):
        """last_n=10 should result in 2 API calls (2 batches of 5)."""
        fetch_mock, call_count = self._mock_fetch()
        with patch.object(self.provider, "_fetch_financial_table", side_effect=fetch_mock):
            result = self.provider.get_financial_statements(
                "THYAO", "income_stmt", quarterly=False, last_n=10
            )
        assert call_count["n"] == 2
        assert len(result.columns) == 10

    @patch.object(IsYatirimProvider, "_cache_get", return_value=None)
    @patch.object(IsYatirimProvider, "_cache_set")
    def test_three_batches_for_12_periods(self, mock_cache_set, mock_cache_get):
        """last_n=12 needs 3 batches (5+5+2)."""
        fetch_mock, call_count = self._mock_fetch()
        with patch.object(self.provider, "_fetch_financial_table", side_effect=fetch_mock):
            self.provider.get_financial_statements(
                "THYAO", "income_stmt", quarterly=False, last_n=12
            )
        assert call_count["n"] == 3

    @patch.object(IsYatirimProvider, "_cache_get", return_value=None)
    @patch.object(IsYatirimProvider, "_cache_set")
    def test_balance_sheet_batches_per_table(self, mock_cache_set, mock_cache_get):
        """balance_sheet has 2 tables; each should get batched separately."""
        fetch_mock, call_count = self._mock_fetch()
        with patch.object(self.provider, "_fetch_financial_table", side_effect=fetch_mock):
            self.provider.get_financial_statements(
                "THYAO", "balance_sheet", quarterly=False, last_n=6
            )
        # 2 tables × 2 batches each = 4 calls
        assert call_count["n"] == 4


# =============================================================================
# Unit Tests: Cache key differentiation
# =============================================================================


class TestCacheKeys:
    """Tests that different last_n values produce different cache keys."""

    def setup_method(self):
        self.provider = IsYatirimProvider()

    @patch.object(IsYatirimProvider, "_cache_set")
    @patch.object(IsYatirimProvider, "_fetch_financial_table", return_value=pd.DataFrame({"2025": [1]}, index=pd.Index(["Revenue"], name="Item")))
    def test_different_last_n_different_cache_key(self, mock_fetch, mock_cache_set):
        """last_n=5 and last_n=10 should use different cache keys."""
        with patch.object(self.provider, "_cache_get", return_value=None):
            self.provider.get_financial_statements("THYAO", "income_stmt", last_n=5)
            key1 = mock_cache_set.call_args_list[0][0][0]

            self.provider.get_financial_statements("THYAO", "income_stmt", last_n=10)
            key2 = mock_cache_set.call_args_list[1][0][0]

        assert key1 != key2
        assert ":5" in key1
        assert ":10" in key2


# =============================================================================
# Unit Tests: Column sorting
# =============================================================================


class TestColumnSorting:
    """Tests that result columns are sorted most-recent-first."""

    def setup_method(self):
        self.provider = IsYatirimProvider()

    @patch.object(IsYatirimProvider, "_cache_get", return_value=None)
    @patch.object(IsYatirimProvider, "_cache_set")
    def test_annual_columns_sorted_descending(self, mock_cache_set, mock_cache_get):
        """Annual columns should be ordered most recent first."""
        # Mock fetch to return out-of-order columns
        def mock_fetch(symbol, table_name, financial_group, periods, quarterly=False):
            data = {"2022": [1], "2024": [2], "2023": [3]}
            return pd.DataFrame(data, index=pd.Index(["Revenue"], name="Item"))

        with patch.object(self.provider, "_fetch_financial_table", side_effect=mock_fetch):
            result = self.provider.get_financial_statements("THYAO", "income_stmt", last_n=3)

        assert list(result.columns) == ["2024", "2023", "2022"]

    @patch.object(IsYatirimProvider, "_cache_get", return_value=None)
    @patch.object(IsYatirimProvider, "_cache_set")
    def test_quarterly_columns_sorted_descending(self, mock_cache_set, mock_cache_get):
        """Quarterly columns should be ordered most recent first."""
        def mock_fetch(symbol, table_name, financial_group, periods, quarterly=False):
            data = {"2024Q1": [1], "2024Q3": [2], "2024Q2": [3]}
            return pd.DataFrame(data, index=pd.Index(["Revenue"], name="Item"))

        with patch.object(self.provider, "_fetch_financial_table", side_effect=mock_fetch):
            result = self.provider.get_financial_statements(
                "THYAO", "income_stmt", quarterly=True, last_n=3
            )

        assert list(result.columns) == ["2024Q3", "2024Q2", "2024Q1"]


# =============================================================================
# Unit Tests: Ticker passthrough
# =============================================================================


class TestTickerPassthrough:
    """Tests that Ticker methods pass last_n to the provider."""

    def _make_ticker(self):
        """Create a Ticker with a mocked isyatirim provider."""
        from borsapy.ticker import Ticker

        mock_provider = MagicMock()
        mock_provider.get_financial_statements.return_value = pd.DataFrame()

        ticker = Ticker.__new__(Ticker)
        ticker._symbol = "THYAO"
        ticker._isyatirim = mock_provider
        ticker._tradingview = None
        ticker._kap = None
        ticker._hedeffiyat = None
        ticker._isin_provider = None
        ticker._etf_provider = None
        return ticker, mock_provider

    def test_get_income_stmt_passes_last_n(self):
        ticker, mock_provider = self._make_ticker()
        ticker.get_income_stmt(quarterly=True, last_n=20)

        mock_provider.get_financial_statements.assert_called_once_with(
            symbol="THYAO",
            statement_type="income_stmt",
            quarterly=True,
            financial_group=None,
            last_n=20,
        )

    def test_get_balance_sheet_passes_last_n(self):
        ticker, mock_provider = self._make_ticker()
        ticker.get_balance_sheet(last_n="all")

        mock_provider.get_financial_statements.assert_called_once_with(
            symbol="THYAO",
            statement_type="balance_sheet",
            quarterly=False,
            financial_group=None,
            last_n="all",
        )

    def test_get_cashflow_passes_last_n(self):
        ticker, mock_provider = self._make_ticker()
        ticker.get_cashflow(quarterly=True, last_n=8, financial_group="UFRS")

        mock_provider.get_financial_statements.assert_called_once_with(
            symbol="THYAO",
            statement_type="cashflow",
            quarterly=True,
            financial_group="UFRS",
            last_n=8,
        )

    def test_default_last_n_is_none(self):
        """When last_n is not specified, None should be passed (backward compat)."""
        ticker, mock_provider = self._make_ticker()
        ticker.get_income_stmt()

        call_kwargs = mock_provider.get_financial_statements.call_args[1]
        assert call_kwargs["last_n"] is None


# =============================================================================
# Unit Tests: Merge dedup
# =============================================================================


class TestMergeDedup:
    """Tests for horizontal merge across batches (no duplicate columns)."""

    def setup_method(self):
        self.provider = IsYatirimProvider()

    @patch.object(IsYatirimProvider, "_cache_get", return_value=None)
    @patch.object(IsYatirimProvider, "_cache_set")
    def test_no_duplicate_columns_across_batches(self, mock_cache_set, mock_cache_get):
        """Columns should not be duplicated when batches return overlapping periods."""
        call_idx = {"n": 0}

        def mock_fetch(symbol, table_name, financial_group, periods, quarterly=False):
            call_idx["n"] += 1
            if call_idx["n"] == 1:
                # Batch 1 returns 5 columns
                data = {"2025": [100], "2024": [200], "2023": [300], "2022": [400], "2021": [500]}
            else:
                # Batch 2 has an overlap column "2021" (happens if API returns it)
                data = {"2021": [500], "2020": [600]}
            return pd.DataFrame(data, index=pd.Index(["Revenue"], name="Item"))

        with patch.object(self.provider, "_fetch_financial_table", side_effect=mock_fetch):
            result = self.provider.get_financial_statements("THYAO", "income_stmt", last_n=7)

        # Should have exactly 6 unique columns, not 7 (2021 deduped)
        assert len(result.columns) == 6
        assert "2021" in result.columns
        assert "2020" in result.columns


# =============================================================================
# Unit Tests: Edge cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge case handling."""

    def setup_method(self):
        self.provider = IsYatirimProvider()

    @patch.object(IsYatirimProvider, "_cache_get", return_value=None)
    @patch.object(IsYatirimProvider, "_cache_set")
    def test_empty_older_batch_still_returns_recent(self, mock_cache_set, mock_cache_get):
        """If older batch returns empty, recent data should still be present."""
        call_idx = {"n": 0}

        def mock_fetch(symbol, table_name, financial_group, periods, quarterly=False):
            call_idx["n"] += 1
            if call_idx["n"] == 1:
                data = {"2025": [100], "2024": [200]}
                return pd.DataFrame(data, index=pd.Index(["Revenue"], name="Item"))
            return pd.DataFrame()  # Empty older batch

        with patch.object(self.provider, "_fetch_financial_table", side_effect=mock_fetch):
            result = self.provider.get_financial_statements("THYAO", "income_stmt", last_n=10)

        assert not result.empty
        assert "2025" in result.columns

    def test_last_n_equal_to_batch_size(self):
        """last_n=5 should produce exactly 1 batch."""
        count = IsYatirimProvider._resolve_last_n(5, quarterly=False)
        periods = self.provider._get_periods(2026, quarterly=False, count=count)
        batches = [
            periods[i : i + 5] for i in range(0, len(periods), 5)
        ]
        assert len(batches) == 1
        assert len(batches[0]) == 5
