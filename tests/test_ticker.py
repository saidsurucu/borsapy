"""Tests for Ticker price adjustment helpers."""

import pandas as pd
import pytest

from borsapy.ticker import _compute_adj_close


class TestComputeAdjClose:
    """Backward dividend adjustment yielding a yfinance-style Adj Close."""

    def test_empty_close_returns_empty(self):
        close = pd.Series([], dtype=float, name="Close")
        divs = pd.DataFrame({"Amount": []}, index=pd.DatetimeIndex([]))
        result = _compute_adj_close(close, divs)
        assert result.empty

    def test_no_dividends_returns_close_unchanged(self):
        idx = pd.date_range("2024-01-01", periods=5, freq="D")
        close = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0], index=idx)
        divs = pd.DataFrame(columns=["Amount"])
        result = _compute_adj_close(close, divs)
        pd.testing.assert_series_equal(result, close)

    def test_missing_amount_column_returns_close_unchanged(self):
        idx = pd.date_range("2024-01-01", periods=3, freq="D")
        close = pd.Series([100.0, 101.0, 102.0], index=idx)
        divs = pd.DataFrame(
            {"OtherCol": [1.0]},
            index=pd.DatetimeIndex(["2024-01-02"]),
        )
        result = _compute_adj_close(close, divs)
        pd.testing.assert_series_equal(result, close)

    def test_single_dividend_scales_prior_prices(self):
        # Close=100 on ex-date with $1 dividend → factor = 99/100 = 0.99
        # All rows BEFORE ex-date multiplied by 0.99; ex-date and after unchanged.
        idx = pd.date_range("2024-01-01", periods=4, freq="D")
        close = pd.Series([100.0, 100.0, 100.0, 100.0], index=idx)
        divs = pd.DataFrame(
            {"Amount": [1.0]},
            index=pd.DatetimeIndex(["2024-01-03"]),  # 3rd row
        )
        result = _compute_adj_close(close, divs)
        assert result.iloc[0] == pytest.approx(99.0)
        assert result.iloc[1] == pytest.approx(99.0)
        assert result.iloc[2] == pytest.approx(100.0)  # ex-date unchanged
        assert result.iloc[3] == pytest.approx(100.0)

    def test_multiple_dividends_compound(self):
        # Two dividends → factors multiply on rows BEFORE each ex-date
        # Ex1: 2024-01-02, close=100, div=1 → factor_1 = 0.99 applied to row 0
        # Ex2: 2024-01-04, close=100, div=2 → factor_2 = 0.98 applied to rows 0,1,2
        # Row 0 (2024-01-01): 100 * 0.99 * 0.98 = 97.02  (before both)
        # Row 1 (2024-01-02): 100 * 0.98 = 98.00  (ex-date 1, before ex-date 2)
        # Row 2 (2024-01-03): 100 * 0.98 = 98.00  (after ex-date 1, before ex-date 2)
        # Row 3 (2024-01-04): 100.0  (ex-date 2 itself, nothing after)
        idx = pd.date_range("2024-01-01", periods=4, freq="D")
        close = pd.Series([100.0, 100.0, 100.0, 100.0], index=idx)
        divs = pd.DataFrame(
            {"Amount": [1.0, 2.0]},
            index=pd.DatetimeIndex(["2024-01-02", "2024-01-04"]),
        )
        result = _compute_adj_close(close, divs)
        assert result.iloc[0] == pytest.approx(100.0 * 0.99 * 0.98)
        assert result.iloc[1] == pytest.approx(100.0 * 0.98)
        assert result.iloc[2] == pytest.approx(100.0 * 0.98)
        assert result.iloc[3] == pytest.approx(100.0)

    def test_dividend_outside_close_range_is_skipped(self):
        idx = pd.date_range("2024-01-01", periods=3, freq="D")
        close = pd.Series([100.0, 100.0, 100.0], index=idx)
        divs = pd.DataFrame(
            {"Amount": [5.0]},
            index=pd.DatetimeIndex(["2025-06-01"]),  # way outside
        )
        result = _compute_adj_close(close, divs)
        pd.testing.assert_series_equal(result, close)

    def test_zero_or_negative_amount_skipped(self):
        idx = pd.date_range("2024-01-01", periods=3, freq="D")
        close = pd.Series([100.0, 100.0, 100.0], index=idx)
        divs = pd.DataFrame(
            {"Amount": [0.0, -1.0]},
            index=pd.DatetimeIndex(["2024-01-02", "2024-01-03"]),
        )
        result = _compute_adj_close(close, divs)
        pd.testing.assert_series_equal(result, close)

    def test_nonzero_close_guarded_against_zero(self):
        # If close on ex-date is 0, adjustment would divide by zero — skip it.
        idx = pd.date_range("2024-01-01", periods=3, freq="D")
        close = pd.Series([100.0, 0.0, 100.0], index=idx)
        divs = pd.DataFrame(
            {"Amount": [1.0]},
            index=pd.DatetimeIndex(["2024-01-02"]),
        )
        result = _compute_adj_close(close, divs)
        # No adjustment applied because close_on_ex <= 0
        pd.testing.assert_series_equal(result, close)

    def test_timezone_aware_close_matches_naive_dividend(self):
        # Index is tz-aware (Europe/Istanbul); dividend index is tz-naive.
        # They should still match by calendar date.
        idx = pd.date_range("2024-01-01", periods=3, freq="D", tz="Europe/Istanbul")
        close = pd.Series([100.0, 100.0, 100.0], index=idx)
        divs = pd.DataFrame(
            {"Amount": [1.0]},
            index=pd.DatetimeIndex(["2024-01-02"]),  # tz-naive
        )
        result = _compute_adj_close(close, divs)
        assert result.iloc[0] == pytest.approx(99.0)
        assert result.iloc[1] == pytest.approx(100.0)

    def test_returns_copy_when_unchanged(self):
        # Caller may mutate result; it shouldn't alias the input.
        idx = pd.date_range("2024-01-01", periods=2, freq="D")
        close = pd.Series([100.0, 100.0], index=idx)
        divs = pd.DataFrame(columns=["Amount"])
        result = _compute_adj_close(close, divs)
        result.iloc[0] = 999.0
        assert close.iloc[0] == 100.0
