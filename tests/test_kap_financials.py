"""KAP HTML parsing and conservative PDF basis verification."""

import json
from datetime import date
from unittest.mock import Mock

import httpx
import pytest

from borsapy._providers.kap_financials import (
    FinancialReport,
    KAPFinancialProvider,
    decode_payload,
    parse_number,
    parse_report,
    verify_pdf_basis,
)
from borsapy.exceptions import DataNotAvailableError


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1.234,50", 1234.5),
        ("(1.000)", -1000),
        ("-1.200", -1200),
        ("0", 0),
        ("-", None),
        ("", None),
        ("abc", None),
        ("...", None),
        ("1.20", None),
    ],
)
def test_turkish_amounts(value, expected):
    assert parse_number(value) == expected


def payload():
    return """<table class="financial-header-table"><tr><td>Sunum Para Birimi</td><td>1.000 TL</td></tr>
    <tr><td>Finansal Tablo Niteliği</td><td>Konsolide</td></tr></table>
    <table class="financial-table"><tr>
    <td class="context-header">01.01.2026 - 30.06.2026</td>
    <td class="context-header">01.01.2025 - 30.06.2025</td>
    <td class="context-header">01.04.2026 - 30.06.2026</td></tr>
    <tr class="data-input-row"><td class="taxonomy-field-name">ifrs-full_Revenue|</td>
    <td class="taxonomy-context-value">1.200</td><td class="taxonomy-context-value">1.000</td>
    <td class="taxonomy-context-value">700</td></tr></table>"""


def disclosure():
    return {"year": 2026, "period": 2, "disclosureIndex": 1, "publishDate": "17.08.2026 12:00:00"}


def test_nextjs_decoding_and_ytd_selection():
    html = "<script>self.__next_f.push([1," + json.dumps(payload()) + "])</script>"
    report = parse_report(decode_payload(html), disclosure())
    assert report.current["revenue"] == 1_200_000
    assert report.comparative["revenue"] == 1_000_000
    assert report.unit == 1000
    assert report.basis_month is None
    assert report.comparative_end == "2025-06-30"


def test_unrecognized_currency_is_not_assumed_to_be_try():
    with pytest.raises(DataNotAvailableError):
        parse_report(payload().replace("1.000 TL", "unknown"), disclosure())


def test_quarter_only_is_not_treated_as_ytd():
    with pytest.raises(DataNotAvailableError):
        parse_report(payload().replace("01.01.", "01.04."), disclosure())


def test_inconsistent_statement_units_fail_closed():
    another_header = '<table class="financial-header-table"><tr><td>Sunum Para Birimi</td><td>TL</td></tr></table>'
    with pytest.raises(DataNotAvailableError, match="units or consolidation"):
        parse_report(payload() + another_header, disclosure())


def basis_report():
    return FinancialReport(
        1,
        "https://www.kap.org.tr/tr/Bildirim/1",
        "17.08.2026 12:00:00",
        "2026-06-30",
        "TRY",
        1000,
        "Konsolide",
        current={"revenue": 1_200_000, "parent_profit": 200_000},
    )


def test_pdf_header_requires_date_and_matching_financial_numbers():
    report = basis_report()
    verify_pdf_basis(
        report,
        [
            "KONSOLİDE FİNANSAL DURUM TABLOSU. Tutarlar 30 Haziran 2026 tarihi "
            "itibarıyla satın alma gücü esasına göre ifade edilmiştir. 1.200 200"
        ],
    )
    assert report.basis_month == "2026-06"
    assert report.pdf_page == 1


@pytest.mark.parametrize(
    "page",
    [
        "TMS 29 standardı 2027'de uygulanacaktır. 1.200 200",
        "Finansal durum tablosu. Tutarlar 30 Haziran 2025 satın alma gücü ile. 1.200 200",
        "Finansal durum tablosu. Tutarlar 30 Haziran 2026 satın alma gücü ile. 9.999 500",
        "Finansal durum tablosu. Tutarlar 30 Haziran 2026 satın alma gücü ile. 11.200 1.200",
    ],
)
def test_mentions_old_dates_or_unmatched_pdfs_do_not_verify_basis(page):
    report = basis_report()
    verify_pdf_basis(report, [page])
    assert report.basis_month is None


def test_read_request_recovers_from_a_disconnect(monkeypatch):
    monkeypatch.setattr("borsapy._providers.kap_financials.sleep", lambda _: None)
    provider = KAPFinancialProvider()
    response = httpx.Response(200, json=[], request=httpx.Request("GET", "https://example.com"))
    request = Mock(side_effect=[httpx.RemoteProtocolError("Disconnected"), response])
    monkeypatch.setattr(provider.client, "request", request)
    try:
        assert provider._request("GET", "https://example.com") is response
        assert request.call_count == 2
    finally:
        provider.close()


@pytest.mark.parametrize("status, headers", [(429, {}), (503, {"Retry-After": "120"}), (404, {})])
def test_rate_limits_and_permanent_errors_are_not_retried(monkeypatch, status, headers):
    monkeypatch.setattr("borsapy._providers.kap_financials.sleep", lambda _: None)
    provider = KAPFinancialProvider()
    response = httpx.Response(
        status, headers=headers, request=httpx.Request("GET", "https://example.com")
    )
    request = Mock(return_value=response)
    monkeypatch.setattr(provider.client, "request", request)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            provider._request("GET", "https://example.com")
        assert request.call_count == 1
    finally:
        provider.close()


def test_disclosures_ignore_notices_without_financial_periods(monkeypatch):
    provider = KAPFinancialProvider()
    response = Mock()
    response.json.return_value = [
        disclosure(),
        {"year": None, "period": None},
        {"year": 2026, "period": 5},
    ]
    monkeypatch.setattr(provider, "_request", Mock(return_value=response))
    try:
        assert provider.disclosures("oid", date(2026, 10, 3)) == [disclosure()]
    finally:
        provider.close()
