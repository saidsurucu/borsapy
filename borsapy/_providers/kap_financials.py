"""Read dated, unit-aware financial statements directly from KAP disclosures.

Next.js payloads are decoded as data, never evaluated. A purchasing-power basis
is accepted only when a matching PDF statement header explicitly identifies it.
"""

import calendar
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Lock
from time import monotonic, sleep

import httpx
from bs4 import BeautifulSoup

from borsapy.exceptions import DataNotAvailableError

BASE = "https://www.kap.org.tr"
PDF_LOCK = Lock()  # PyMuPDF document operations must not run on multiple threads.
REQUEST_LOCK = Lock()
_last_request = 0.0
FINANCIAL_SUBJECT = "4028328c594bfdca01594c0af9aa0057"
MONTHS = (
    "",
    "ocak",
    "subat",
    "mart",
    "nisan",
    "mayis",
    "haziran",
    "temmuz",
    "agustos",
    "eylul",
    "ekim",
    "kasim",
    "aralik",
)
FIELDS = {
    "ifrs-full_Revenue": "revenue",
    "ifrs-full_ProfitLossAttributableToOwnersOfParent": "parent_profit",
    "ifrs-full_ProfitLoss": "profit",
    "ifrs-full_CashFlowsFromUsedInOperatingActivities": "operating_cash",
    "ifrs-full_EquityAttributableToOwnersOfParent": "parent_equity",
    "ifrs-full_Equity": "equity",
    "ifrs-full_CurrentAssets": "current_assets",
    "ifrs-full_CurrentLiabilities": "current_liabilities",
}


def normalize_text(value: str) -> str:
    value = value.replace("ı", "i").replace("İ", "I")
    return " ".join(
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower().split()
    )


def parse_number(value: str) -> float | None:
    """Parse Turkish monetary amounts; an empty cell or dash is unknown, not zero."""
    value = value.strip().replace("\u2212", "-").replace("\xa0", "")
    if value in ("", "-", "—"):
        return None
    if value.startswith("(") and value.endswith(")"):
        value = "-" + value[1:-1]
    if not re.fullmatch(r"-?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?", value):
        return None
    return float(value.replace(".", "").replace(",", "."))


def decode_payload(html: str) -> str:
    chunks = []
    for script in BeautifulSoup(html, "lxml").find_all("script"):
        match = re.fullmatch(
            r'self\.__next_f\.push\(\[1,(".*")\]\);?', (script.string or "").strip(), re.DOTALL
        )
        if match:
            chunks.append(json.loads(match.group(1)))
    # Legacy disclosure pages already contain their financial tables in the DOM.
    return "".join(chunks) if chunks else html


@dataclass
class FinancialReport:
    disclosure_id: int
    source_url: str
    published_at: str
    period_end: str
    currency: str
    unit: float
    scope: str
    current: dict[str, float | None] = field(default_factory=dict)
    comparative: dict[str, float | None] = field(default_factory=dict)
    comparative_end: str | None = None
    basis_month: str | None = None
    basis_evidence: str | None = None
    pdf_url: str | None = None
    pdf_page: int | None = None


def parse_report(payload: str, disclosure: dict) -> FinancialReport:
    soup = BeautifulSoup(payload, "lxml")
    headers = soup.select("table.financial-header-table")
    if not headers:
        raise DataNotAvailableError("KAP financial table headers are missing")
    all_metadata = []
    for header in headers:
        metadata = {}
        for row in header.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) == 2:
                metadata[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True)
        all_metadata.append(metadata)
    metadata = all_metadata[0]
    for other in all_metadata[1:]:
        for field_name in ("Sunum Para Birimi", "Finansal Tablo Niteliği"):
            if other.get(field_name) != metadata.get(field_name):
                raise DataNotAvailableError("KAP statement units or consolidation scopes differ")
    currency_label = normalize_text(metadata.get("Sunum Para Birimi", ""))
    match = re.fullmatch(
        r"(?:(1(?:\.000){0,3}|bin|milyon)\s*)?(tl|try|turk lirasi|usd|eur)", currency_label
    )
    if not match:
        raise DataNotAvailableError(f"Unrecognized KAP currency/unit: {currency_label}")
    scale, currency = match.groups()
    unit = {None: 1, "bin": 1000, "milyon": 1_000_000}.get(scale)
    if unit is None:
        unit = int(scale.replace(".", ""))
    currency = "TRY" if currency in ("tl", "try", "turk lirasi") else currency.upper()
    year, month = int(disclosure["year"]), int(disclosure["period"]) * 3
    period_end = date(year, month, calendar.monthrange(year, month)[1])
    report = FinancialReport(
        disclosure_id=int(disclosure["disclosureIndex"]),
        source_url=f"{BASE}/tr/Bildirim/{disclosure['disclosureIndex']}",
        published_at=disclosure["publishDate"],
        period_end=period_end.isoformat(),
        currency=currency,
        unit=unit,
        scope=metadata.get("Finansal Tablo Niteliği", ""),
    )
    for table in soup.select("table.financial-table"):
        contexts = []
        for header in table.select("td.context-header"):
            tr = header.select_one(".content-tr") or header
            contexts.append(re.findall(r"\d{2}\.\d{2}\.\d{4}", tr.get_text(" ", strip=True)))
        if len(contexts) < 2 or not contexts[0]:
            continue
        current_dates = [datetime.strptime(d, "%d.%m.%Y").date() for d in contexts[0]]
        previous_dates = [datetime.strptime(d, "%d.%m.%Y").date() for d in contexts[1]]
        if current_dates[-1] != period_end:
            continue
        # Only calendar-year cumulative flows are supported. Quarter-only columns
        # must never be mistaken for YTD or combined with a different duration.
        is_flow = len(current_dates) == 2
        if is_flow:
            if (
                current_dates[0] != date(year, 1, 1)
                or len(previous_dates) != 2
                or previous_dates[0] != date(year - 1, 1, 1)
                or previous_dates[-1].year != year - 1
                or previous_dates[-1].month != month
                or previous_dates[-1].day != period_end.day
            ):
                continue
            report.comparative_end = previous_dates[-1].isoformat()
        for row in table.select("tr.data-input-row"):
            taxonomy = row.select_one(".taxonomy-field-name")
            dimension = row.select_one(".taxonomy-nondimensional-context-cell")
            if not taxonomy or (dimension and dimension.get_text(strip=True)):
                continue
            key = FIELDS.get(taxonomy.get_text(strip=True).split("|")[0])
            if not key:
                continue
            if (key in ("revenue", "parent_profit", "profit", "operating_cash")) != is_flow:
                continue
            cells = row.find_all("td", class_="taxonomy-context-value", recursive=False)
            if len(cells) < 2:
                continue
            values = [parse_number(c.get_text(strip=True)) for c in cells[:2]]
            values = [v * unit if v is not None else None for v in values]
            # Repeated dimension/statement rows must not silently overwrite totals.
            if key in report.current and (
                report.current[key] != values[0] or report.comparative[key] != values[1]
            ):
                raise DataNotAvailableError(f"Ambiguous KAP financial item: {key}")
            report.current[key], report.comparative[key] = values
    if not report.current:
        raise DataNotAvailableError("No supported KAP financial items or calendar-year periods")
    return report


def verify_pdf_basis(report: FinancialReport, pages: list[str]) -> None:
    """Require a dated purchasing-power statement header and matching amounts.

    Merely mentioning TMS 29 in accounting policies is insufficient (it may be
    a discussion of a future standard or of subsidiaries with another currency).
    """
    if report.currency != "TRY":
        return
    end = date.fromisoformat(report.period_end)
    date_pattern = rf"{end.day}\s+{MONTHS[end.month]}\s+{end.year}"
    date_pattern = rf"(?:{date_pattern}|{end.day:02d}\.{end.month:02d}\.{end.year})"
    all_text = " ".join(pages)
    matching = 0
    for key in ("revenue", "parent_profit", "parent_equity", "operating_cash"):
        value = report.current.get(key)
        if value is not None and value != 0:
            token = f"{abs(value / report.unit):,.0f}".replace(",", ".")
            matching += bool(re.search(r"(?<![\d.,])" + re.escape(token) + r"(?![\d.,])", all_text))
    if matching < 2:
        return
    for page_number, page in enumerate(pages, 1):
        header = normalize_text(page[:1800])
        if not any(t in header for t in ("finansal durum", "kar veya zarar", "nakit akis")):
            continue
        match = re.search(date_pattern + r".{0,100}satin alma gucu.{0,130}", header)
        if match and "tutar" in header:
            report.basis_month = report.period_end[:7]
            report.basis_evidence = match.group(0)
            report.pdf_page = page_number
            return


class KAPFinancialProvider:
    def __init__(self, cache_dir: Path | None = None):
        self.client = httpx.Client(
            timeout=25, follow_redirects=True, limits=httpx.Limits(max_keepalive_connections=0)
        )
        self.cache_dir = cache_dir

    def close(self):
        self.client.close()

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Retry transient failures of these read-only requests, at most twice.

        Rate limits and responses with Retry-After are surfaced without retrying.
        """
        global _last_request
        for attempt in range(3):
            # Share the limit across all company workers: at most 40 starts/minute.
            with REQUEST_LOCK:
                sleep(max(0, 1.5 - (monotonic() - _last_request)))
                _last_request = monotonic()
            try:
                response = self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if (
                    exc.response.status_code not in (500, 502, 503, 504)
                    or "retry-after" in exc.response.headers
                    or attempt == 2
                ):
                    raise
            except httpx.TransportError:
                if attempt == 2:
                    raise
            sleep(2**attempt)
        raise AssertionError("Unreachable")

    def disclosures(self, member_oid: str, today: date) -> list[dict]:
        response = self._request(
            "POST",
            f"{BASE}/tr/api/disclosure/members/byCriteria",
            json={
                "fromDate": (today - timedelta(days=365)).isoformat(),
                "toDate": today.isoformat(),
                "disclosureClass": "FR",
                "subjectList": [FINANCIAL_SUBJECT],
                "mkkMemberOidList": [member_oid],
                "inactiveMkkMemberOidList": [],
                "bdkMemberOidList": [],
                "fromSrc": False,
                "disclosureIndexList": [],
            },
        )
        data = response.json()
        if not isinstance(data, list):
            raise DataNotAvailableError("KAP disclosure list has an unexpected format")
        # Other notices can share the subject but have no financial year/period.
        reports = []
        for item in data:
            try:
                year, period = int(item.get("year")), int(item.get("period"))
            except (ValueError, TypeError):
                continue
            if 1900 <= year <= today.year and period in (1, 2, 3, 4):
                reports.append(item)
        return sorted(
            reports,
            key=lambda d: datetime.strptime(d["publishDate"], "%d.%m.%Y %H:%M:%S"),
            reverse=True,
        )

    def report(self, disclosure: dict) -> FinancialReport:
        cache = (
            self.cache_dir / f"kap-v2-{disclosure['disclosureIndex']}.json"
            if self.cache_dir
            else None
        )
        if cache and cache.exists():
            return FinancialReport(**json.loads(cache.read_text()))
        response = self._request("GET", f"{BASE}/tr/Bildirim/{disclosure['disclosureIndex']}")
        payload = decode_payload(response.text)
        report = parse_report(payload, disclosure)
        attachments = re.findall(r'\{"objId":"[^"}]+","fileName":"(?:\\.|[^"}])+"[^}]*}', payload)
        attachments = [json.loads(a) for a in attachments]
        attachments = [a for a in attachments if a.get("fileExtension", "").lower() == "pdf"]
        attachments.sort(key=lambda a: bool(re.search(r"eng|english", a["fileName"], re.I)))
        if attachments:
            report.pdf_url = f"{BASE}/tr/api/file/download/{attachments[0]['objId']}"
            pdf_response = self._request("GET", report.pdf_url)
            if len(pdf_response.content) <= 20_000_000:
                import pymupdf

                with PDF_LOCK, pymupdf.open(stream=pdf_response.content, filetype="pdf") as pdf:
                    pages = [pdf[i].get_text() for i in range(min(12, len(pdf)))]
                verify_pdf_basis(report, pages)
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(asdict(report), ensure_ascii=False, allow_nan=False))
        return report
