"""BIST 100 research with explicit accounting bases and sector peer comparisons.

This is a current-universe research tool, not a historical backtest or a fair-value
model. Unknown accounting bases are never silently treated as nominal TRY data.
"""

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime
from math import isfinite
from pathlib import Path
from statistics import median
from threading import Lock
from zoneinfo import ZoneInfo

import pandas as pd

from borsapy._providers.bist_index import get_bist_index_provider
from borsapy._providers.isyatirim import IsYatirimProvider
from borsapy._providers.kap import KAPProvider
from borsapy._providers.kap_financials import FinancialReport, KAPFinancialProvider
from borsapy.exceptions import DataNotAvailableError
from borsapy.inflation import Inflation

# Prefer the most specific official index, not broad industrial/service indices.
SECTOR_CODES = (
    "XBANK",
    "XSGRT",
    "XAKUR",
    "XFINK",
    "XGMYO",
    "XGSYO",
    "XYORT",
    "XHOLD",
    "XPTIC",
    "XTTIC",
    "XYIHZ",
    "XKNKL",
    "XBLSM",
    "XGIDA",
    "XELKT",
    "XILTM",
    "XINSA",
    "XKAGT",
    "XKMYA",
    "XMADN",
    "XMANA",
    "XMESY",
    "XTAST",
    "XTEKS",
    "XULAS",
    "XSPOR",
    "XTRZM",
    "XUTEK",
)
FINANCIALS = {"XBANK", "XSGRT", "XAKUR", "XFINK"}
ASSET_VALUATION = {"XHOLD", "XGMYO", "XGSYO", "XYORT"}
FLOWS = ("revenue", "parent_profit", "profit", "operating_cash")


def finite(value) -> float | None:
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if isfinite(number) else None


def positive(value) -> float | None:
    number = finite(value)
    return number if number is not None and number > 0 else None


def rebase_amount(value: float, source_index: float, target_index: float) -> float:
    """Re-express an already restated monetary amount, not an untreated cash flow.

    The caller must establish the amount's purchasing-power date and ensure both
    index levels belong to the same CPI series/base. Negative amounts are valid.
    """
    if finite(value) is None or positive(source_index) is None or positive(target_index) is None:
        raise ValueError("Rebasing requires a finite amount and strictly positive CPI levels")
    return value * target_index / source_index


class CPIRebaser:
    def __init__(self):
        self._cache = {}
        self._lock = Lock()

    @property
    def evidence(self) -> list[dict]:
        return list(self._cache.values())

    def factor(self, start: str, end: str) -> float:
        if start == end:
            return 1.0
        if start > end:
            raise ValueError("The target purchasing-power month must not precede the source")
        with self._lock:
            if (start, end) not in self._cache:
                data = Inflation().calculate(100, start, end)
                factor = rebase_amount(1, data["start_cpi"], data["end_cpi"])
                self._cache[start, end] = {
                    "source_month": start,
                    "target_month": end,
                    "source_cpi": data["start_cpi"],
                    "target_cpi": data["end_cpi"],
                    "factor": factor,
                    "source": "https://appg.tcmb.gov.tr/KIMENFH/enflasyon/hesapla",
                }
            return self._cache[start, end]["factor"]


def normalize_financials(
    latest: FinancialReport,
    annual: FinancialReport | None,
    factor: Callable[[str, str], float],
) -> dict:
    """Use same-filing comparatives once; CPI-rebase only an older verified basis.

    Cross-filing TTM remains an estimate: CPI does not reconcile reclassifications,
    changes in consolidation scope or corrections to prior published accounts.
    """
    result = {
        "basis_status": "unverified",
        "real_revenue_growth_pct": None,
        "annual_rebase_factor": None,
        "ttm_is_estimate": None,
        **{f"ttm_{key}": None for key in FLOWS},
    }
    if latest.currency != "TRY" or latest.basis_month != latest.period_end[:7]:
        return result
    result["basis_status"] = "same_filing_verified"
    previous_revenue = positive(latest.comparative.get("revenue"))
    revenue = finite(latest.current.get("revenue"))
    if previous_revenue and revenue is not None and latest.comparative_end:
        result["real_revenue_growth_pct"] = (revenue / previous_revenue - 1) * 100
    if latest.period_end.endswith("-12-31"):
        result.update({f"ttm_{key}": finite(latest.current.get(key)) for key in FLOWS})
        result.update(
            basis_status="annual_verified", ttm_is_estimate=False, annual_rebase_factor=1.0
        )
        return result
    year = date.fromisoformat(latest.period_end).year
    expected_comparable = f"{year - 1}{latest.period_end[4:]}"
    if (
        annual is None
        or annual.period_end != f"{year - 1}-12-31"
        or annual.currency != latest.currency
        or not latest.scope
        or annual.scope != latest.scope
        or annual.basis_month != annual.period_end[:7]
        or latest.comparative_end != expected_comparable
    ):
        return result
    adjustment = factor(annual.basis_month, latest.basis_month)
    if positive(adjustment) is None:
        raise ValueError("Invalid CPI adjustment factor")
    for key in FLOWS:
        current = finite(latest.current.get(key))
        previous = finite(latest.comparative.get(key))
        annual_value = finite(annual.current.get(key))
        if all(v is not None for v in (current, previous, annual_value)):
            result[f"ttm_{key}"] = current + annual_value * adjustment - previous
    result.update(
        basis_status="cpi_rebased_estimate", annual_rebase_factor=adjustment, ttm_is_estimate=True
    )
    return result


def compare_peers(records: list[dict], min_peers: int = 3) -> list[dict]:
    """Leave-one-out medians; no mixing sectors, reporting bases or missing values."""
    if min_peers < 3:
        raise ValueError("At least three other companies are required for a peer comparison")
    for row in records:
        sector = row.get("sector_code")
        row.update(peer_count=0, peer_median=None, peer_discount_pct=None)
        if not sector:
            row.update(status="Sektör doğrulanamadı", primary_metric=None)
            continue
        if sector in ASSET_VALUATION:
            row.update(status="Net aktif değer analizi gerekli", primary_metric="reported_pb")
            continue
        metric = "reported_pb" if sector in FINANCIALS else "common_basis_pe"
        row["primary_metric"] = metric
        if row.get("report_stale"):
            row["status"] = "Güncel finansal rapor gerekli"
            continue
        basis = row.get("basis_month") if sector not in FINANCIALS else "provider_current"
        peers = [
            positive(other.get(metric))
            for other in records
            if other["symbol"] != row["symbol"]
            and not other.get("report_stale")
            and other.get("sector_code") == sector
            and (sector in FINANCIALS or (basis is not None and other.get("basis_month") == basis))
        ]
        peers = [value for value in peers if value is not None]
        row["peer_count"] = len(peers)
        value = positive(row.get(metric))
        parent_profit = finite(row.get("ttm_parent_profit"))
        if sector not in FINANCIALS and parent_profit is not None and parent_profit <= 0:
            row["status"] = "Zarar veya sıfır kâr"
        elif value is None:
            row["status"] = "Karşılaştırılabilir veri eksik"
        elif len(peers) < min_peers:
            row["status"] = "Yeterli akran yok"
        else:
            row["peer_median"] = median(peers)
            row["peer_discount_pct"] = (1 - value / row["peer_median"]) * 100
            if sector in FINANCIALS:
                row["status"] = "Finans sektörü incelemesi gerekli"
                row["flags"].append(
                    "PD/DD tek başına yeterli değil; özkaynak kârlılığı ve sermaye kalitesi incelenmeli"
                )
            elif row["peer_discount_pct"] <= 0:
                row["status"] = "Akran medyanının altında değil"
            elif (
                positive(row.get("ttm_profit")) is None
                or positive(row.get("ttm_operating_cash")) is None
            ):
                row["status"] = "Nakit veya kâr kontrolü gerekli"
            else:
                row["status"] = "İnceleme adayı"
    return records


@dataclass
class ResearchResult:
    companies: pd.DataFrame
    metadata: dict

    def save(self, directory: str | Path) -> dict[str, Path]:
        from borsapy.research_report import render_report

        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        records = json.loads(self.companies.to_json(orient="records", force_ascii=False))
        payload = {"metadata": self.metadata, "companies": records}
        paths = {kind: directory / f"bist100-research.{kind}" for kind in ("json", "csv", "html")}
        paths["json"].write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
        flat = self.companies.drop(
            columns=["latest_report", "annual_report"], errors="ignore"
        ).copy()
        flat["flags"] = flat["flags"].map(lambda values: " | ".join(values))
        flat.to_csv(paths["csv"], index=False, encoding="utf-8-sig")
        paths["html"].write_text(render_report(payload))
        return paths


def run_value_research(
    symbols: list[str] | None = None,
    *,
    max_workers: int = 4,
    min_peers: int = 3,
    cache_dir: str | Path | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> ResearchResult:
    """Fetch the current BIST 100 universe, KAP reports and current provider multiples.

    Optional symbols restrict the universe (and therefore the peer sample).
    Unavailable company data stays in the result with explicit flags.
    """
    if not 1 <= max_workers <= 4:
        raise ValueError("max_workers must be between 1 and 4")
    if min_peers < 3:
        raise ValueError("min_peers must be at least 3")
    now = datetime.now(ZoneInfo("Europe/Istanbul"))
    index = get_bist_index_provider()
    components = index.get_components("XU100")
    if len({item["symbol"] for item in components}) != 100:
        raise DataNotAvailableError(
            "The official BIST 100 list could not be verified; scan stopped"
        )
    if symbols is not None:
        requested = {s.upper().strip() for s in symbols}
        unknown = requested - {item["symbol"] for item in components}
        if unknown or not requested:
            raise ValueError(f"Symbols must be current BIST 100 members: {sorted(unknown)}")
        components = [item for item in components if item["symbol"] in requested]
    names = {item["symbol"]: item["name"] for item in index.get_available_indices()}
    memberships = {code: {c["symbol"] for c in index.get_components(code)} for code in SECTOR_CODES}
    kap = KAPProvider()
    try:
        oids = {item["symbol"]: kap.get_member_oid(item["symbol"]) for item in components}
    finally:
        kap.close()
    cpi = CPIRebaser()

    def collect(item):
        symbol = item["symbol"]
        sector = next((code for code in SECTOR_CODES if symbol in memberships[code]), None)
        row = {
            "symbol": symbol,
            "name": item["name"],
            "sector_code": sector,
            "sector": names.get(sector, "Bilinmiyor"),
            "flags": [],
            "retrieved_at": now.isoformat(),
            "market_data_asof": None,
            "market_source": f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={symbol}",
            "market_cap": None,
            "reported_pe": None,
            "reported_pb": None,
            "reported_ev_ebitda": None,
            "common_basis_pe": None,
            "basis_month": None,
            "basis_status": "unverified",
            "report_period": None,
            "report_stale": False,
            "real_revenue_growth_pct": None,
            "ttm_profit": None,
            "ttm_operating_cash": None,
            "latest_report": None,
            "annual_report": None,
        }
        market = IsYatirimProvider()
        reports = KAPFinancialProvider(Path(cache_dir) if cache_dir else None)
        try:
            try:
                metrics = market.get_company_metrics(symbol)
                for key, source in (
                    ("market_cap", "market_cap"),
                    ("reported_pe", "pe_ratio"),
                    ("reported_pb", "pb_ratio"),
                    ("reported_ev_ebitda", "ev_ebitda"),
                ):
                    row[key] = finite(metrics.get(source))
            except Exception as exc:
                row["flags"].append(f"Piyasa verisi alınamadı: {type(exc).__name__}")
            if not oids[symbol]:
                raise DataNotAvailableError("KAP şirket kimliği bulunamadı")
            disclosures = reports.disclosures(oids[symbol], now.date())
            if not disclosures:
                raise DataNotAvailableError("KAP finansal raporu bulunamadı")
            disclosures.sort(key=lambda d: (int(d["year"]), int(d["period"])), reverse=True)
            latest = reports.report(disclosures[0])
            row.update(
                latest_report=asdict(latest),
                report_period=latest.period_end,
                basis_month=latest.basis_month,
            )
            if (now.date() - date.fromisoformat(latest.period_end)).days > 220:
                row["report_stale"] = True
                row["flags"].append("Son finansal dönem 220 günden eski")
            annual = None
            if latest.basis_month and not latest.period_end.endswith("-12-31"):
                previous_year = int(latest.period_end[:4]) - 1
                candidates = [
                    d
                    for d in disclosures
                    if int(d["year"]) == previous_year and int(d["period"]) == 4
                ]
                if candidates:
                    try:
                        annual = reports.report(candidates[0])
                        row["annual_report"] = asdict(annual)
                    except Exception as exc:
                        row["flags"].append(f"Önceki yıllık rapor okunamadı: {type(exc).__name__}")
            # Preserve same-filing growth even when the external CPI service fails.
            row.update(normalize_financials(latest, None, cpi.factor))
            try:
                row.update(normalize_financials(latest, annual, cpi.factor))
            except Exception as exc:
                row["flags"].append(f"TÜFE dönüşümü yapılamadı: {type(exc).__name__}")
            profit = positive(row.get("ttm_parent_profit"))
            if profit and positive(row["market_cap"]):
                row["common_basis_pe"] = row["market_cap"] / profit
            if not latest.basis_month:
                row["flags"].append(
                    "Satın alma gücü bazı PDF başlığından doğrulanamadı; reel büyüme/TTM hesaplanmadı"
                )
            elif row.get("ttm_is_estimate"):
                row["flags"].append(
                    "TTM, TÜFE ile ortak baza taşınmış tahmindir; raporlar arası muhasebe değişikliklerini düzeltmez"
                )
            elif row["basis_status"] == "same_filing_verified":
                row["flags"].append(
                    "Yıllık karşılaştırma bazı doğrulanamadı; yalnızca aynı rapordan reel büyüme hesaplandı"
                )
        except Exception as exc:
            row["flags"].append(f"Finansal veri: {type(exc).__name__}: {str(exc)[:180]}")
        finally:
            market.close()
            reports.close()
        return row

    rows = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(collect, item): item["symbol"] for item in components}
        for future in as_completed(futures):
            rows.append(future.result())
            if progress:
                progress(len(rows), len(components), futures[future])
    compare_peers(rows, min_peers)
    rows.sort(
        key=lambda r: (
            r["status"] != "İnceleme adayı",
            -(r.get("peer_discount_pct") or 0),
            r["symbol"],
        )
    )
    metadata = {
        "generated_at": now.isoformat(),
        "universe": "XU100",
        "company_count": len(rows),
        "partial_universe": symbols is not None,
        "min_other_peers": min_peers,
        "universe_source": "https://www.borsaistanbul.com/datum/hisse_endeks_ds.csv",
        "cpi": cpi.evidence,
        "methodology": [
            "Güncel BIST 100 üyeleri; geçmişe dönük performans testi değildir.",
            "Akran medyanları hedef şirket hariç hesaplanır; en az üç akran gerekir.",
            "Sanayi/hizmet şirketleri yalnızca aynı sektör ve satın alma gücü ayındaki pozitif F/K ile karşılaştırılır.",
            "Bankalar ve diğer finans şirketlerinde kaynak PD/DD oranı ayrı değerlendirilir; otomatik aday üretilmez.",
            "Holding, GYO ve yatırım ortaklıklarında net aktif değer analizi gerekir; otomatik aday üretilmez.",
            "Aynı KAP raporundaki düzeltilmiş karşılaştırmalı rakama tekrar TÜFE uygulanmaz.",
            "Ara dönem TTM tahmini, eski yıllık raporu TCMB TÜFE endeks oranıyla yeni baza taşır; yeniden sınıflandırmaları uzlaştırmaz.",
            "İnceleme adayı: akran medyanından düşük ortak baz F/K, pozitif toplam kâr ve faaliyet nakdi. Kalite veya gerçek değer garantisi değildir.",
            "İndirim, akran çarpan medyanına göredir; hedef fiyat veya beklenen getiri değildir.",
            "Sektör endeksleri geniş gruplardır; iş modeli ve büyüme farkları ayrıca incelenmelidir.",
            "220 günden eski raporlar akran hesabına ve otomatik aday listesine alınmaz.",
            "Piyasa verisinin işlem zamanı kaynak tarafından verilmez; çekilme zamanı işlem zamanı değildir.",
        ],
    }
    return ResearchResult(pd.DataFrame(rows), metadata)
