"""Regression tests for incomplete data in the value-stock example."""

from types import SimpleNamespace

import pandas as pd
import pytest

from examples import value_stock_finder as finder


@pytest.fixture
def metrics():
    return {"pe": 4.0, "pb": 0.4, "dividend_yield": 9.0, "debt_to_equity": 0.0}


@pytest.mark.parametrize("key", ["pe", "pb", "dividend_yield", "debt_to_equity"])
def test_removing_a_metric_cannot_increase_score(metrics, key):
    complete_score = finder.calculate_value_score(metrics)
    assert complete_score == 100
    assert finder.calculate_value_score({**metrics, key: None}) == 75


def test_missing_high_debt_cannot_improve_score():
    metrics = {"pe": 4, "pb": 0.4, "dividend_yield": 0, "debt_to_equity": 3}
    assert finder.calculate_value_score(metrics) == 50
    assert finder.calculate_value_score({**metrics, "debt_to_equity": None}) == 50


@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), -float("inf"), pd.NA])
@pytest.mark.parametrize("key", ["pe", "pb", "dividend_yield", "debt_to_equity"])
def test_missing_or_nonfinite_metrics_receive_no_credit(metrics, key, invalid):
    assert finder.calculate_value_score({**metrics, key: invalid}) == 75


def test_negative_debt_ratio_is_not_rewarded(metrics):
    assert finder.calculate_value_score({**metrics, "debt_to_equity": -1}) == 75


def test_no_metrics_means_no_evidence_of_value():
    assert finder.calculate_value_score({}) == 0


def test_analyze_preserves_zero_values(monkeypatch):
    ticker = SimpleNamespace(
        info={"pe": 4, "pb": 0.4, "dividend_yield": 0, "dividendYield": 9},
        balance_sheet=pd.DataFrame(
            {"2025": [0, 100]}, index=["Finansal Borçlar", "Ana Ortaklık Özkaynaklar"]
        ),
        income_stmt=pd.DataFrame(
            {"2025": [100, 0]}, index=["Satış Gelirleri", "Ana Ortaklık Payları"]
        ),
    )
    monkeypatch.setattr(finder.bp, "Ticker", lambda symbol: ticker)
    result = finder.analyze_value_metrics("TEST")
    assert result["dividend_yield"] == 0
    assert result["debt_to_equity"] == 0
    assert result["net_margin"] == 0


def test_missing_dividend_is_not_reported_as_zero(monkeypatch):
    ticker = SimpleNamespace(info={}, balance_sheet=pd.DataFrame(), income_stmt=pd.DataFrame())
    monkeypatch.setattr(finder.bp, "Ticker", lambda symbol: ticker)
    assert finder.analyze_value_metrics("TEST")["dividend_yield"] is None


def test_scan_reports_coverage_and_formats_missing_values(monkeypatch, capsys):
    monkeypatch.setattr(
        finder.bp, "Index", lambda index: SimpleNamespace(component_symbols=["TEST"])
    )
    monkeypatch.setattr(
        finder,
        "analyze_value_metrics",
        lambda symbol: {
            "symbol": symbol,
            "pe": 4,
            "pb": 0.4,
            "dividend_yield": None,
            "debt_to_equity": float("nan"),
        },
    )
    result = finder.scan_value_stocks(verbose=True)
    assert result.loc[0, "value_score"] == 50
    assert result.loc[0, "metrics_available"] == 2
    output = capsys.readouterr().out
    assert "2/4" in output
    assert "N/A" in output
    assert "nan" not in output.lower()
