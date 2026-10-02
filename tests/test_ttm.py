"""Regression tests for TTM calculations from cumulative financial statements."""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from borsapy._providers.isyatirim import IsYatirimProvider
from borsapy.ticker import Ticker


@pytest.fixture
def ticker():
    ticker = Ticker.__new__(Ticker)
    ticker._symbol = "BIMAS"
    ticker._isyatirim = MagicMock()
    return ticker


@pytest.mark.parametrize("quarter, expected", [(1, 140), (2, 180), (3, 220), (4, 260)])
def test_ttm_matches_four_discrete_quarters(ticker, quarter, expected):
    # Actual quarterly earnings: 10, 20, 30, 40 in 2024; 50, 60, 70, 80 in 2025.
    # The provider reports cumulative YTD amounts, including a full year in Q4.
    values = {"2024Q1": [10], "2024Q2": [30], "2024Q3": [60], "2024Q4": [100]}
    for q, value in enumerate([50, 110, 180, 260], 1):
        if q <= quarter:
            values[f"2025Q{q}"] = [value]
    # Deliberately oldest first: column order must not determine the latest period.
    result = ticker._calculate_ttm(pd.DataFrame(values, index=["Net income"]))
    assert result.loc["Net income", "TTM"] == expected


def test_year_end_needs_only_the_annual_column(ticker):
    data = pd.DataFrame({"2025Q4": [100, -20]}, index=["Revenue", "Net income"])
    expected = data.rename(columns={"2025Q4": "TTM"})
    pd.testing.assert_frame_equal(ticker._calculate_ttm(data), expected)


@pytest.mark.parametrize("missing_period", ["2024Q4", "2024Q2"])
def test_missing_required_period_does_not_produce_partial_ttm(ticker, missing_period):
    data = pd.DataFrame(
        {"2025Q2": [110], "2025Q1": [50], "2024Q4": [100], "2024Q3": [60], "2024Q2": [30]}
    )
    result = ticker._calculate_ttm(data.drop(columns=missing_period))
    assert result.empty
    assert list(result.columns) == ["TTM"]


def test_unneeded_intermediate_quarters_may_be_absent(ticker):
    data = pd.DataFrame({"2025Q2": [110], "2024Q4": [100], "2024Q2": [30]})
    assert ticker._calculate_ttm(data).iloc[0, 0] == 180


@pytest.mark.parametrize("missing", [None, float("nan"), "unavailable"])
@pytest.mark.parametrize("period", ["2025Q2", "2024Q4", "2024Q2"])
def test_missing_line_item_stays_missing(ticker, missing, period):
    values = {
        "2025Q2": [110, 0],
        "2025Q1": [50, 0],
        "2024Q4": [100, 0],
        "2024Q3": [60, 0],
        "2024Q2": [30, 0],
    }
    values[period][0] = missing
    result = ticker._calculate_ttm(pd.DataFrame(values, index=["Missing", "Zero"]))
    assert pd.isna(result.loc["Missing", "TTM"])
    assert result.loc["Zero", "TTM"] == 0


def test_empty_financials_return_empty_ttm(ticker):
    result = ticker._calculate_ttm(pd.DataFrame())
    assert result.empty
    assert list(result.columns) == ["TTM"]


@pytest.mark.parametrize("statement", ["income_stmt", "cashflow"])
def test_public_ttm_methods_fetch_prior_year_comparable(ticker, statement):
    ticker._isyatirim.get_financial_statements.return_value = pd.DataFrame(
        {"2025Q2": [110], "2025Q1": [50], "2024Q4": [100], "2024Q3": [60], "2024Q2": [30]}
    )
    result = getattr(ticker, f"get_ttm_{statement}")(financial_group="XI_29")
    assert result.iloc[0, 0] == 180
    ticker._isyatirim.get_financial_statements.assert_called_once_with(
        symbol="BIMAS",
        statement_type=statement,
        quarterly=True,
        financial_group="XI_29",
        last_n=5,
    )


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_short_financial_batches_supply_all_required_api_slots(count):
    provider = IsYatirimProvider()
    periods = [(2025, month) for month in [12, 9, 6, 3]][:count]

    def response_for_request(url, params):
        # MaliTablo returns no rows when any of its four period slots is absent.
        complete = all(f"{key}{i}" in params for key in ("year", "period") for i in range(1, 5))
        row = {"itemCode": "3A", "itemDescTr": "Revenue"}
        row.update({f"value{i}": params.get(f"period{i}") for i in range(1, 5)})
        return MagicMock(**{"json.return_value": {"value": [row] if complete else []}})

    provider._get = MagicMock(side_effect=response_for_request)
    try:
        result = provider._fetch_financial_table(
            "BIMAS",
            "XI_29",
            periods,
            quarterly=True,
            statement_type="income_stmt",
        )
        assert list(result.columns) == [f"{year}Q{month // 3}" for year, month in periods]
        assert result.loc["Revenue"].tolist() == [month for _, month in periods]
    finally:
        provider.close()
