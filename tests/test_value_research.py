"""Accounting and peer-comparison invariants for value research."""

import json
from copy import deepcopy
from datetime import datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from typer.testing import CliRunner

from borsapy._providers.kap_financials import FinancialReport
from borsapy.research_report import render_report
from borsapy.value_research import compare_peers, normalize_financials, rebase_amount


def report(end="2026-06-30", **overrides):
    values = {
        "disclosure_id": 1,
        "source_url": "https://www.kap.org.tr/tr/Bildirim/1",
        "published_at": "17.08.2026 12:00:00",
        "period_end": end,
        "currency": "TRY",
        "unit": 1,
        "scope": "Konsolide",
        "basis_month": end[:7],
        "current": {"revenue": 120, "parent_profit": 20, "profit": 25, "operating_cash": 30},
        "comparative": {"revenue": 100, "parent_profit": 10, "profit": 12, "operating_cash": 20},
        "comparative_end": "2025-06-30",
    }
    return FinancialReport(**{**values, **overrides})


def test_same_filing_comparatives_are_never_inflated_twice():
    latest = report()
    annual = report(
        "2025-12-31",
        current={"revenue": 200, "parent_profit": 40, "profit": 50, "operating_cash": 60},
    )
    factor = Mock(return_value=1.2)
    result = normalize_financials(latest, annual, factor)
    assert result["real_revenue_growth_pct"] == pytest.approx(20)
    assert result["ttm_revenue"] == 260  # 120 + 200 * 1.2 - 100, not -100*1.2
    assert result["ttm_parent_profit"] == 58
    assert result["ttm_operating_cash"] == 82
    assert result["ttm_is_estimate"] is True
    factor.assert_called_once_with("2025-12", "2026-06")


def test_year_end_needs_no_cpi_or_prior_report():
    factor = Mock(side_effect=AssertionError("No CPI should be applied"))
    result = normalize_financials(report("2025-12-31"), None, factor)
    assert result["ttm_parent_profit"] == 20
    assert result["ttm_is_estimate"] is False


@pytest.mark.parametrize(
    "changes", [{"basis_month": None}, {"basis_month": "2025-06"}, {"currency": "USD"}]
)
def test_unknown_or_foreign_basis_does_not_get_turkish_cpi(changes):
    factor = Mock(side_effect=AssertionError("Unverified basis"))
    result = normalize_financials(report(**changes), report("2025-12-31"), factor)
    assert result["ttm_parent_profit"] is None
    assert result["real_revenue_growth_pct"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"scope": "Konsolide Olmayan"},
        {"basis_month": None},
        {"currency": "USD"},
        {"period_end": "2024-12-31"},
    ],
)
def test_incompatible_annual_does_not_destroy_same_report_growth(changes):
    factor = Mock(side_effect=AssertionError("Incompatible annual statement"))
    result = normalize_financials(report(), report("2025-12-31", **changes), factor)
    assert result["ttm_parent_profit"] is None
    assert result["real_revenue_growth_pct"] == pytest.approx(20)


def test_missing_values_are_not_zero_and_losses_are_preserved():
    latest = report(current={"revenue": 0, "parent_profit": -30})
    annual = report("2025-12-31", current={"revenue": 100, "parent_profit": -40})
    result = normalize_financials(latest, annual, lambda a, b: 1)
    assert result["ttm_parent_profit"] == -80
    assert result["ttm_operating_cash"] is None
    assert result["real_revenue_growth_pct"] == -100


@pytest.mark.parametrize(
    "value, start, end",
    [(1, 0, 120), (1, -2, 100), (1, 100, float("inf")), (float("nan"), 100, 120)],
)
def test_bad_cpi_inputs_fail_closed(value, start, end):
    with pytest.raises(ValueError):
        rebase_amount(value, start, end)


def test_negative_money_can_be_rebased():
    assert rebase_amount(-100, 100, 120) == -120


def peers():
    return [
        {
            "symbol": f"S{i}",
            "sector_code": "XPTIC",
            "basis_month": "2026-06",
            "common_basis_pe": pe,
            "reported_pb": pe / 10,
            "ttm_profit": 100,
            "ttm_operating_cash": 100,
            "flags": [],
        }
        for i, pe in enumerate([5, 10, 20, 30])
    ]


def test_peer_median_excludes_target_company():
    result = compare_peers(peers())
    assert result[0]["peer_median"] == 20
    assert result[0]["peer_discount_pct"] == 75
    assert result[0]["peer_count"] == 3
    assert result[0]["status"] == "İnceleme adayı"


@pytest.mark.parametrize(
    "changes",
    [
        {"sector_code": "XGIDA"},
        {"basis_month": "2025-12"},
        {"common_basis_pe": -3},
        {"common_basis_pe": None},
        {"common_basis_pe": float("nan")},
        {"report_stale": True},
    ],
)
def test_incompatible_or_missing_peers_are_excluded(changes):
    rows = peers()
    rows[-1].update(changes)
    result = compare_peers(rows)
    assert result[0]["peer_count"] == 2
    assert result[0]["peer_discount_pct"] is None
    assert result[0]["status"] == "Yeterli akran yok"


def test_negative_cash_flow_prevents_candidate_status():
    rows = peers()
    rows[0]["ttm_operating_cash"] = -1
    assert compare_peers(rows)[0]["status"] == "Nakit veya kâr kontrolü gerekli"


def test_reported_loss_is_distinguished_from_missing_data():
    rows = peers()
    rows[0].update(ttm_parent_profit=-100, common_basis_pe=None)
    assert compare_peers(rows)[0]["status"] == "Zarar veya sıfır kâr"


def test_stale_report_never_becomes_a_candidate():
    rows = peers()
    rows[0]["report_stale"] = True
    assert compare_peers(rows)[0]["status"] == "Güncel finansal rapor gerekli"


@pytest.mark.parametrize("sector", ["XBANK", "XSGRT", "XAKUR", "XFINK", "XHOLD", "XGMYO"])
def test_special_sectors_never_use_industrial_candidate_rule(sector):
    rows = peers()
    for row in rows:
        row["sector_code"] = sector
    result = compare_peers(rows)
    assert all(row["status"] != "İnceleme adayı" for row in result)
    assert result[0]["primary_metric"] == "reported_pb"


def test_html_escapes_external_content():
    row = {
        **peers()[0],
        "name": "<script>alert(1)</script>",
        "sector": "<sector>",
        "market_source": "https://example.com",
        "flags": ["<img src=x>"],
        "status": "İnceleme adayı",
        "peer_count": 3,
    }
    html = render_report(
        {
            "companies": [deepcopy(row)],
            "metadata": {
                "generated_at": "2026-10-03",
                "methodology": ["<unsafe>"],
                "partial_universe": False,
            },
        }
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=x&gt;" in html


@pytest.mark.parametrize("cpi_unavailable", [False, True])
def test_scan_and_exports_preserve_failed_companies_and_growth(
    monkeypatch, tmp_path, cpi_unavailable
):
    import borsapy.value_research as research

    companies = [{"symbol": f"S{i}", "name": f"Şirket {i}"} for i in range(100)]
    index = Mock()
    index.get_components.side_effect = lambda code: companies if code in ("XU100", "XPTIC") else []
    index.get_available_indices.return_value = [{"symbol": "XPTIC", "name": "Perakende"}]
    monkeypatch.setattr(research, "get_bist_index_provider", lambda: index)
    kap = Mock()
    kap.get_member_oid.side_effect = lambda symbol: symbol
    monkeypatch.setattr(research, "KAPProvider", lambda: kap)
    market = Mock()
    market.get_company_metrics.return_value = {"market_cap": 580, "pe_ratio": 8, "pb_ratio": 2}
    monkeypatch.setattr(research, "IsYatirimProvider", lambda: market)
    provider = Mock()

    def disclosures(oid, today):
        if oid == "S3":
            raise RuntimeError("Unavailable company")
        return [{"year": 2026, "period": 2}, {"year": 2025, "period": 4}]

    provider.disclosures.side_effect = disclosures
    provider.report.side_effect = lambda d: (
        report()
        if d["year"] == 2026
        else report(
            "2025-12-31",
            current={"revenue": 200, "parent_profit": 40, "profit": 50, "operating_cash": 60},
        )
    )
    monkeypatch.setattr(research, "KAPFinancialProvider", lambda cache: provider)
    cpi = Mock(evidence=[])
    cpi.factor = (
        Mock(side_effect=RuntimeError("CPI offline")) if cpi_unavailable else Mock(return_value=1.2)
    )
    monkeypatch.setattr(research, "CPIRebaser", lambda: cpi)
    now = datetime(2026, 10, 3, tzinfo=ZoneInfo("Europe/Istanbul"))
    monkeypatch.setattr(research, "datetime", Mock(now=Mock(return_value=now)))
    result = research.run_value_research(["S0", "S1", "S2", "S3"], max_workers=2)
    paths = result.save(tmp_path)
    data = json.loads(paths["json"].read_text())
    rows = {r["symbol"]: r for r in data["companies"]}
    assert len(rows) == 4
    assert rows["S3"]["common_basis_pe"] is None
    assert any("Unavailable company" in flag for flag in rows["S3"]["flags"])
    assert rows["S0"]["real_revenue_growth_pct"] == pytest.approx(20)
    assert rows["S0"]["common_basis_pe"] == (None if cpi_unavailable else 10)
    assert rows["S0"]["market_data_asof"] is None
    assert data["metadata"]["partial_universe"] is True
    assert "Şirket 0" in paths["html"].read_text()
    assert "latest_report" not in paths["csv"].read_text(encoding="utf-8-sig").splitlines()[0]


def test_unverified_index_membership_stops_scan(monkeypatch):
    import borsapy.value_research as research
    from borsapy.exceptions import DataNotAvailableError

    index = Mock()
    index.get_components.return_value = []
    monkeypatch.setattr(research, "get_bist_index_provider", lambda: index)
    with pytest.raises(DataNotAvailableError, match="official BIST 100"):
        research.run_value_research()


def test_cli_research_is_registered_and_rejects_unsafe_peer_count():
    from borsapy.cli.app import app

    runner = CliRunner()
    assert runner.invoke(app, ["research", "--help"]).exit_code == 0
    assert runner.invoke(app, ["research", "--min-peers", "1"]).exit_code == 2
