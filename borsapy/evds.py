"""EVDS (TCMB Elektronik Veri Dağıtım Sistemi) — yfinance-like API.

Comprehensive interface to the Turkish Central Bank's EVDS catalogue:
145 categories, thousands of data groups, tens of thousands of macro series
(interest rates, FX, money supply, BOP, real sector, expectations etc.).

The legacy ``evds2.tcmb.gov.tr/service/evds/`` JSON API was retired in late
2025 — every request now 302-redirects to the EVDS3 SPA, breaking the entire
historical Python ecosystem (PyPI ``evds`` etc.). This module wraps the new
v3 anonymous backend (``/igmevdsms-dis/...``) so borsapy users keep working.

Examples:
    >>> import borsapy as bp
    >>> ev = bp.EVDS()

    # Catalogue navigation
    >>> ev.categories                      # 145 rows: CATEGORY_ID, titles
    >>> ev.datagroups(category_id=400401)  # Short Term External Debt → 6 groups
    >>> ev.series_in_group("bie_dkdovizgn")  # Daily FX → 137 series

    # Search across catalogue
    >>> ev.search("dolar")                 # Anything mentioning USD
    >>> ev.search("inflation", lang="en")

    # Series wrapper (`bp.Ticker`-style)
    >>> usd = ev.series("TP.DK.USD.A")
    >>> usd.info                           # SERIE_NAME, FREQUENCY, BIRIMI, ...
    >>> usd.range                          # (date(1950, 1, 2), date(2025, ...))
    >>> usd.history(period="1mo")          # DataFrame, DatetimeIndex + Value

    # Module-level shortcuts (yfinance-like one-liners)
    >>> bp.evds_series("TP.DK.USD.A", period="1y")
    >>> bp.evds_series("TP.FG.J0", period="3y", formula="yoy_pct")
    >>> bp.evds_download(["TP.DK.USD.A", "TP.DK.EUR.A"], start="2024-01-01")

    # Pre-built dashboards
    >>> ev.dashboard("baslica-gostergeler")  # 9-chart "major indicators" board
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from borsapy._providers.evds import (
    AGGREGATION,
    FORMULA,
    FREQUENCY,
    NUMERIC_FREQ_NORMALIZE,
    clear_evds_key,
    denormalize_code,
    get_evds_key,
    get_evds_provider,
    normalize_code,
    period_to_dates,
    set_evds_key,
)
from borsapy.exceptions import APIError, DataNotAvailableError

# ----- Date helpers -----------------------------------------------------------

def _resolve_window(
    period: str | None,
    start: str | date | datetime | None,
    end: str | date | datetime | None,
) -> tuple[str, str]:
    """Coerce period / start / end inputs into a (start_dd_mm_yyyy, end_dd_mm_yyyy).

    When ``start`` is given without ``end``, defaults ``end`` to
    ``"01-01-2999"`` per the TCMB Web Service guide's recommendation —
    "Hazırladığınız sorgunun sürekli güncel veriyi alması için bu alana çok
    uzak bir tarih yazınız. Örneğin 01-01-2999". This way newly-published
    observations land in the response without rebuilding queries.
    """
    if start is not None or end is not None:
        from borsapy._providers.evds import _format_date  # local import keeps surface tidy
        if start is None:
            start = "1950-01-01"
        if end is None:
            # TCMB-recommended sentinel for "always current".
            return _format_date(start), "01-01-2999"
        return _format_date(start), _format_date(end)
    return period_to_dates(period or "1y")


def _parse_evds_date(value: str | None) -> pd.Timestamp | None:
    """Parse an EVDS date stamp (DD-MM-YYYY or quarter/year shorthands) into Timestamp."""
    if not value:
        return None
    if isinstance(value, pd.Timestamp):
        return value
    s = str(value).strip()
    if not s:
        return None
    # EVDS commonly returns DD-MM-YYYY for daily; YYYY-MM for monthly; YYYY for annual.
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return pd.to_datetime(datetime.strptime(s, fmt))
        except ValueError:
            continue
    # Quarter shorthand (2024-Q1 / 2024Q1)
    try:
        return pd.to_datetime(s.replace("Q", "-Q"), format="%Y-Q%q", errors="raise")
    except Exception:
        return pd.to_datetime(s, errors="coerce")


def _frame_from_payload(
    payload: Any,
    series_codes: list[str],
) -> pd.DataFrame:
    """Convert a raw EVDS REST response into a tidy DataFrame.

    The backend usually returns ``{"totalCount": N, "items": [{"Tarih": "...",
    "TP_FG_J0": "12.34"}, ...]}`` — but several deployments emit either
    ``{"data": [...]}`` or a top-level list. We normalize all of them.
    """
    rows: list[dict] = []
    if isinstance(payload, dict):
        for key in ("items", "data", "observations", "result"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    elif isinstance(payload, list):
        rows = payload
    if not rows:
        return pd.DataFrame(columns=series_codes)

    df = pd.DataFrame(rows)

    # Identify the date column (commonly "Tarih", "TARIH", "date", "DATE").
    date_col = next(
        (c for c in df.columns if c.upper() in {"TARIH", "DATE", "TARİH", "TARI"}),
        None,
    )
    if date_col is None:
        # Some payloads use UNIXTIME / dateString.
        for c in ("UNIXTIME", "dateString", "OBS_DATE"):
            if c in df.columns:
                date_col = c
                break
    if date_col is not None:
        if date_col == "UNIXTIME":
            # UNIXTIME often arrives as {"$numberLong": "1704056400"} — extract.
            unix_series = df[date_col].map(
                lambda v: int(v["$numberLong"]) if isinstance(v, dict) else v
            )
            df["_date"] = pd.to_datetime(
                pd.to_numeric(unix_series, errors="coerce"), unit="s"
            )
        else:
            df["_date"] = df[date_col].map(_parse_evds_date)
        df = df.dropna(subset=["_date"]).set_index("_date").drop(columns=[date_col])
        df.index.name = "Date"

    # Drop housekeeping columns the REST endpoint includes alongside values.
    drop_cols = {
        c for c in df.columns
        if c.upper() in {"YEAR", "MONTH", "DAY", "QUARTER", "_DATE", "UNIXTIME"}
    }
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    # Strip formula suffixes such as "TP.FG.J0-3" → "TP.FG.J0" (the REST
    # endpoint appends ``-<formula_id>`` whenever a non-default formula is
    # applied). Map against both dot and underscore variants.
    normalized_dot = {denormalize_code(c).upper() for c in series_codes}
    normalized_us = {normalize_code(c).upper() for c in series_codes}
    rename_map: dict[str, str] = {}
    for col in list(df.columns):
        col_dot = denormalize_code(col).upper()
        # Try exact match first (no formula suffix).
        if col_dot in normalized_dot:
            rename_map[col] = denormalize_code(col)
            continue
        # Try with formula suffix `-N` stripped.
        if "-" in col_dot:
            base = col_dot.rsplit("-", 1)[0]
            if base in normalized_dot:
                rename_map[col] = denormalize_code(col.rsplit("-", 1)[0])
                continue
        if col.upper() in normalized_us:
            rename_map[col] = denormalize_code(col)

    df = df.rename(columns=rename_map)

    # Numericify recognised series columns.
    for col in df.columns:
        if denormalize_code(col).upper() in normalized_dot:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # If single series with a single value column, surface it as "Value".
    if len(series_codes) == 1 and len(df.columns) == 1:
        df.columns = ["Value"]
    return df.sort_index()


# ----- EVDSSeries (single-series wrapper) -------------------------------------

class EVDSSeries:
    """Single time series from EVDS.

    The user-facing API mirrors :class:`borsapy.Ticker`: a small lazy-loaded
    wrapper with ``info`` / ``range`` / ``history()``.
    """

    def __init__(self, code: str) -> None:
        if not code or not isinstance(code, str):
            raise ValueError("EVDS series code is required (e.g. 'TP.DK.USD.A')")
        self._code_user = code
        self._code_normalized = normalize_code(code)
        self._provider = get_evds_provider()
        self._info_cache: dict | None = None

    @property
    def code(self) -> str:
        """User-facing series code (dot-separated, e.g. ``"TP.DK.USD.A"``)."""
        return self._code_user

    @property
    def info(self) -> dict:
        """Catalogue metadata: SERIE_NAME, FREQUENCY_STR, BIRIMI, etc."""
        if self._info_cache is not None:
            return self._info_cache
        located = self._provider.find_series(self._code_user)
        if not located:
            raise DataNotAvailableError(
                f"EVDS series not found: {self._code_user}"
            )
        # Surface user-facing dot codes in the result.
        info = dict(located)
        info["SERIE_CODE"] = denormalize_code(info.get("SERIE_CODE", self._code_user))
        # Embed convenience fields without leaking internal keys.
        dg = info.pop("_datagroup", {}) or {}
        cat = info.pop("_category", {}) or {}
        info.setdefault("DATAGROUP_CODE", dg.get("DATAGROUP_CODE"))
        info.setdefault("DATAGROUP_TYPE", dg.get("DATAGROUP_TYPE"))
        info.setdefault("CATEGORY_ID", cat.get("CATEGORY_ID"))
        info.setdefault("CATEGORY_TR", cat.get("TOPIC_TITLE_TR"))
        info.setdefault("CATEGORY_EN", cat.get("TOPIC_TITLE_ENG"))
        self._info_cache = info
        return info

    @property
    def datagroup(self) -> str | None:
        """Datagroup code that owns this series."""
        return self.info.get("DATAGROUP_CODE")

    @property
    def native_frequency(self) -> str | None:
        """The series's native frequency (snake_case key in :data:`FREQUENCY`)."""
        info = self.info
        # Try numeric metadata first (FREQUENCY in datagroup).
        raw = info.get("FREQUENCY")
        if isinstance(raw, int):
            normalized = NUMERIC_FREQ_NORMALIZE.get(raw, raw)
            for key, val in FREQUENCY.items():
                if val == normalized:
                    return key
        # Fallback: parse FREQUENCY_STR like "AYLIK", "GÜNLÜK".
        s = (info.get("FREQUENCY_STR") or "").upper()
        mapping = {
            "GÜNLÜK": "daily",
            "İŞ GÜNÜ": "workday",
            "HAFTALIK": "weekly",
            "İKİ HAFTALIK": "biweekly",
            "AYLIK": "monthly",
            "ÜÇ AYLIK": "quarterly",
            "ALTI AYLIK": "semiannual",
            "YILLIK": "annual",
        }
        return mapping.get(s)

    @property
    def range(self) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
        """Min/max available observation dates as ``(start, end)``."""
        freq = self.native_frequency or "monthly"
        info = self.info
        dg = info.get("DATAGROUP_CODE", "")
        rng = self._provider.get_series_range([self._code_user], [dg], frequency=freq)
        entry = rng.get(self._code_normalized.upper(), {})
        return _parse_evds_date(entry.get("start")), _parse_evds_date(entry.get("end"))

    def history(
        self,
        period: str = "1y",
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
        frequency: str | int | None = None,
        aggregation: str = "avg",
        formula: str = "level",
        decimals: int = 2,
        decimal_separator: str = ".",
    ) -> pd.DataFrame:
        """Fetch observation history.

        Args:
            period: yfinance-style period (``"1mo"``, ``"3mo"``, ``"1y"``,
                ``"5y"``, ``"max"``, ``"ytd"`` ...). Ignored if start/end are
                supplied.
            start: Start date (``YYYY-MM-DD``, ``date``, ``datetime``).
            end: End date (defaults to ``"01-01-2999"`` — TCMB-recommended
                "always current" sentinel — when start is given).
            frequency: snake_case (``"monthly"``) or integer 1..8. ``None``
                means use the series's native frequency.
            aggregation: ``avg|min|max|first|last|sum``.
            formula: ``"level"``, ``"pct_change"``, ``"yoy_pct"``, etc.
                See :data:`borsapy._providers.evds.FORMULA`.
            decimals: decimal places for backend rounding.
            decimal_separator: ``"."`` (default) or ``","`` — useful for
                Turkish-locale Excel exports.

        Returns:
            DataFrame indexed by Date with one ``Value`` column.
        """
        start_str, end_str = _resolve_window(period, start, end)
        freq = frequency or self.native_frequency or "monthly"
        payload = self._provider.get_series_data(
            [self._code_user],
            start=start_str,
            end=end_str,
            frequency=freq,
            aggregation=aggregation,
            formula=formula,
            decimals=decimals,
            decimal_separator=decimal_separator,
        )
        return _frame_from_payload(payload, [self._code_user])

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"EVDSSeries({self._code_user!r})"


# ----- EVDS (catalogue + dashboards) ------------------------------------------

class EVDS:
    """Top-level EVDS interface.

    Combines catalogue navigation, search and dashboards. For individual
    series use :meth:`series` or the module-level :func:`evds_series`
    shortcut.
    """

    def __init__(self) -> None:
        self._provider = get_evds_provider()

    # ----- Catalogue ----------------------------------------------------------

    @property
    def categories(self) -> pd.DataFrame:
        """All EVDS top-level categories (one row per category)."""
        cats = self._provider.get_categories()
        rows = [
            {
                "CATEGORY_ID": c.get("CATEGORY_ID"),
                "TOPIC_TITLE_TR": c.get("TOPIC_TITLE_TR"),
                "TOPIC_TITLE_EN": c.get("TOPIC_TITLE_ENG"),
                "PARENT_CATEGORY_ID": c.get("UST_CATEGORY_ID"),
                "LEVEL": c.get("SEVIYE"),
                "DATAGROUP_COUNT": len(c.get("DATAGROUPS", []) or []),
            }
            for c in cats
        ]
        return pd.DataFrame(rows)

    def datagroups(self, category_id: int | None = None) -> pd.DataFrame:
        """List datagroups, optionally filtered by category.

        Includes the full metadata set returned by the EVDS catalogue:
        unit, source, last update, methodology link, revision policy link,
        application change log link, and free-form notes (where available).
        """
        cats = self._provider.get_categories()
        rows = []
        for c in cats:
            if category_id is not None and c.get("CATEGORY_ID") != category_id:
                continue
            for dg in c.get("DATAGROUPS", []) or []:
                rows.append({
                    "DATAGROUP_CODE": dg.get("DATAGROUP_CODE"),
                    "DATAGROUP_TYPE": dg.get("DATAGROUP_TYPE"),
                    "DATAGROUP_TYPE_EN": dg.get("DATAGROUP_TYPE_ENG"),
                    "CATEGORY_ID": c.get("CATEGORY_ID"),
                    "CATEGORY_TR": c.get("TOPIC_TITLE_TR"),
                    "FREQUENCY": dg.get("FREQUENCY"),
                    "FREQUENCY_STR": dg.get("FREQUENCY_STR"),
                    "UNIT_TR": dg.get("BIRIMI"),
                    "UNIT_EN": dg.get("BIRIMI_EN"),
                    "DATA_SOURCE": dg.get("DATASOURCE"),
                    "DATA_SOURCE_EN": dg.get("DATASOURCE_ENG"),
                    "LAST_UPDATED": dg.get("LAST_UPDATED"),
                    "METADATA_LINK": dg.get("METADATA_LINK"),
                    "METADATA_LINK_EN": dg.get("METADATA_LINK_ENG"),
                    "REV_POL_LINK": dg.get("REV_POL_LINK"),
                    "REV_POL_LINK_EN": dg.get("REV_POL_LINK_ENG"),
                    "APP_CHA_LINK": dg.get("APP_CHA_LINK"),
                    "APP_CHA_LINK_EN": dg.get("APP_CHA_LINK_ENG"),
                    "NOTE": dg.get("NOTE"),
                    "NOTE_EN": dg.get("NOTE_ENG"),
                })
        return pd.DataFrame(rows)

    def series_in_group(self, datagroup_code: str) -> pd.DataFrame:
        """List all series that belong to a datagroup."""
        rows = self._provider.get_series_list(datagroup_code)
        if not rows:
            return pd.DataFrame()
        # Surface dot-form codes for friendlier UX.
        for r in rows:
            if r.get("SERIE_CODE"):
                r["SERIE_CODE"] = denormalize_code(r["SERIE_CODE"])
        return pd.DataFrame(rows)

    def search(
        self,
        term: str,
        lang: str = "tr",
        scope: str = "all",
    ) -> pd.DataFrame:
        """Full-text search across categories, datagroups and series.

        Args:
            term: Substring to look for (case-insensitive).
            lang: ``"tr"`` (default) — searches Turkish + English titles.
                ``"en"`` — restrict to English.
            scope: ``"all"`` (default), ``"categories"``, ``"datagroups"``
                or ``"series"``. ``"series"`` requires drilling into every
                datagroup so the first call is slow (subsequent calls are
                cached).

        Returns:
            DataFrame with at least ``hit_type``, ``CODE``, ``NAME_TR``,
            ``NAME_EN`` columns. Type-specific extras included where useful.
        """
        if not term or not isinstance(term, str):
            raise ValueError("search term is required")
        needle = term.strip().lower()
        if not needle:
            return pd.DataFrame()
        results: list[dict] = []

        cats = self._provider.get_categories()
        if scope in {"all", "categories"}:
            for c in cats:
                tr = (c.get("TOPIC_TITLE_TR") or "").lower()
                en = (c.get("TOPIC_TITLE_ENG") or "").lower()
                hit = (lang == "tr" and (needle in tr or needle in en)) or (
                    lang == "en" and needle in en
                )
                if hit:
                    results.append({
                        "hit_type": "category",
                        "CODE": c.get("CATEGORY_ID"),
                        "NAME_TR": c.get("TOPIC_TITLE_TR"),
                        "NAME_EN": c.get("TOPIC_TITLE_ENG"),
                    })
        if scope in {"all", "datagroups"}:
            for c in cats:
                for dg in c.get("DATAGROUPS", []) or []:
                    tr = (dg.get("DATAGROUP_TYPE") or "").lower()
                    en = (dg.get("DATAGROUP_TYPE_ENG") or "").lower()
                    hit = (lang == "tr" and (needle in tr or needle in en)) or (
                        lang == "en" and needle in en
                    )
                    if hit:
                        results.append({
                            "hit_type": "datagroup",
                            "CODE": dg.get("DATAGROUP_CODE"),
                            "NAME_TR": dg.get("DATAGROUP_TYPE"),
                            "NAME_EN": dg.get("DATAGROUP_TYPE_ENG"),
                            "CATEGORY_TR": c.get("TOPIC_TITLE_TR"),
                            "FREQUENCY_STR": dg.get("FREQUENCY_STR"),
                        })
        if scope in {"all", "series"}:
            # Only fully scan the series tree when explicitly requested or when
            # category/datagroup scans yielded no candidates.
            for c in cats:
                for dg in c.get("DATAGROUPS", []) or []:
                    dg_code = dg.get("DATAGROUP_CODE")
                    if not dg_code:
                        continue
                    series_list = self._provider.get_series_list(dg_code)
                    for s in series_list:
                        tr = (s.get("SERIE_NAME") or "").lower()
                        en = (s.get("SERIE_NAME_ENG") or "").lower()
                        sc = (s.get("SERIE_CODE") or "").lower()
                        hit = (
                            (lang == "tr" and (needle in tr or needle in en or needle in sc))
                            or (lang == "en" and (needle in en or needle in sc))
                        )
                        if hit:
                            results.append({
                                "hit_type": "series",
                                "CODE": denormalize_code(s.get("SERIE_CODE", "")),
                                "NAME_TR": s.get("SERIE_NAME"),
                                "NAME_EN": s.get("SERIE_NAME_ENG"),
                                "DATAGROUP_CODE": dg_code,
                                "DATAGROUP_TR": dg.get("DATAGROUP_TYPE"),
                                "FREQUENCY_STR": s.get("FREQUENCY_STR"),
                            })
        return pd.DataFrame(results)

    # ----- Series & dashboards ------------------------------------------------

    def series(self, code: str) -> EVDSSeries:
        """Construct an :class:`EVDSSeries` for the given code."""
        return EVDSSeries(code)

    def dashboard(self, slug: str = "baslica-gostergeler") -> dict:
        """Return raw dashboard payload (chart settings + metadata)."""
        return self._provider.get_dashboard(slug)

    def announcements(self) -> list[dict]:
        """List EVDS announcements (TCMB releases, methodology updates etc.)."""
        return self._provider.get_announcements()

    def home_page_dashboards(self) -> pd.DataFrame:
        """List the 10 TCMB-curated home-page dashboards.

        TCMB hand-picks 10 dashboards that appear on the EVDS home page
        (Reserves, Current Account, M-Aggregates, CPI, Card Spending,
        FX Deposits, TL Deposit Rates, External Debt etc.). Each row gives
        you the ``encoded_id`` you can pass to :meth:`dashboard_by_id` for
        full chart data.
        """
        items = self._provider.get_home_page_dashboards()
        rows = [
            {
                "name": d.get("dashboardName"),
                "name_en": d.get("dashboardNameEn"),
                "encoded_id": d.get("encodedId"),
                "chart_count": len(d.get("chartsList") or []),
                "screen_order": d.get("ekranSiraNo"),
            }
            for d in items
        ]
        return pd.DataFrame(rows).sort_values("screen_order").reset_index(drop=True)

    def dashboard_by_id(self, encoded_id: str) -> dict:
        """Fetch a dashboard's full payload by encoded id.

        Use ``encoded_id`` from :meth:`home_page_dashboards` to drill into
        any of the 10 hand-picked dashboards.
        """
        return self._provider.get_dashboard_by_encoded_id(encoded_id)

    def search_server(self, term: str) -> dict:
        """Server-side full-text search via TCMB's official ``/searchResults``.

        Faster and broader than :meth:`search` (which walks the cached
        catalogue client-side) — the server indexes datagroup names, series
        names, **tags**, and report pages.

        Returns:
            Dict with three keys:

            - ``"datagroups"``: matching data-group records
            - ``"series"``: matching series records (with tags)
            - ``"reports"``: matching report-page records

            Each list is capped at 100 records by the backend.
        """
        raw = self._provider.search_server(term)
        # Surface English keys so the API stays consistent with the rest
        # of borsapy (Turkish keys preserved on the inner dicts).
        return {
            "datagroups": raw.get("veriGruplari") or [],
            "series": raw.get("seriler") or [],
            "reports": raw.get("raporlar") or [],
        }

    def datagroup_data(
        self,
        datagroup_code: str,
        period: str | None = None,
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
        frequency: str | int | None = None,
        decimals: int = 2,
    ) -> pd.DataFrame:
        """Fetch every series in a datagroup with one HTTP call (key required).

        Mirror of TCMB's ``/datagroup=...`` REST endpoint — returns a wide
        DataFrame with one column per series in the group. Far more efficient
        than building a long ``series=A-B-C-...`` list manually.

        Args:
            datagroup_code: e.g. ``"bie_dkdovizgn"``. Use :meth:`datagroups`
                to discover.
            period: yfinance-style window (``"1y"``, ``"3mo"`` ...) — ignored
                if start/end are given.
            start, end: Manual date range.
            frequency: Optional snake_case key (``"daily"``, ``"monthly"``)
                or integer. ``None`` uses the datagroup's native frequency.
            decimals: Decimal places for numeric formatting.

        Example:
            >>> bp.set_evds_key("...")
            >>> df = bp.EVDS().datagroup_data("bie_dkdovizgn", period="1mo")
            >>> df.columns  # 137 daily-FX series in one DataFrame
        """
        start_str, end_str = _resolve_window(period, start, end)
        payload = self._provider.get_datagroup_data(
            datagroup_code,
            start=start_str,
            end=end_str,
            frequency=frequency,
            decimals=decimals,
        )
        # Discover series codes from the payload so _frame_from_payload knows
        # which columns to numericify.
        rows = []
        if isinstance(payload, dict):
            for key in ("items", "data", "observations", "result"):
                if isinstance(payload.get(key), list):
                    rows = payload[key]
                    break
        elif isinstance(payload, list):
            rows = payload
        # All non-Tarih/UNIXTIME columns are series.
        series_cols: list[str] = []
        if rows:
            sample_keys = list(rows[0].keys())
            series_cols = [
                k for k in sample_keys
                if k.upper() not in {"TARIH", "DATE", "UNIXTIME", "DATESTRING"}
            ]
        return _frame_from_payload(payload, series_cols)

    def __repr__(self) -> str:  # pragma: no cover
        return "EVDS()"


# ----- Module-level shortcuts -------------------------------------------------

def evds_categories() -> pd.DataFrame:
    """Shortcut: ``EVDS().categories``."""
    return EVDS().categories


def evds_search(term: str, lang: str = "tr", scope: str = "all") -> pd.DataFrame:
    """Shortcut: ``EVDS().search(term, lang, scope)``."""
    return EVDS().search(term, lang=lang, scope=scope)


def evds_series(
    code: str,
    period: str = "1y",
    start: str | date | datetime | None = None,
    end: str | date | datetime | None = None,
    frequency: str | int | None = None,
    aggregation: str = "avg",
    formula: str = "level",
    decimals: int = 2,
    decimal_separator: str = ".",
) -> pd.DataFrame:
    """Fetch a single series's history.

    Equivalent to::

        EVDSSeries(code).history(period=..., start=..., end=..., ...)
    """
    return EVDSSeries(code).history(
        period=period,
        start=start,
        end=end,
        frequency=frequency,
        aggregation=aggregation,
        formula=formula,
        decimals=decimals,
        decimal_separator=decimal_separator,
    )


def evds_download(
    codes: list[str] | str,
    period: str = "1y",
    start: str | date | datetime | None = None,
    end: str | date | datetime | None = None,
    frequency: str | int = "monthly",
    aggregation: str | list[str] = "avg",
    formula: str | list[str] = "level",
    decimals: int = 2,
    decimal_separator: str = ".",
) -> pd.DataFrame:
    """Fetch multiple series in a single POST, returning a wide DataFrame.

    Mirrors :func:`borsapy.download` for stocks.

    Args:
        codes: List or single string of dot-separated series codes
            (e.g. ``["TP.DK.USD.A", "TP.DK.EUR.A"]``).
        period / start / end: yfinance-style window selection.
        frequency: snake_case key (``"daily"``, ``"monthly"`` ...) or 1..8.
        aggregation: scalar (broadcast) or per-series list.
        formula: scalar or per-series list.

    Returns:
        Wide DataFrame indexed by Date, one column per series (user-facing
        dot-separated codes).
    """
    if isinstance(codes, str):
        codes = [codes]
    if not codes:
        raise ValueError("at least one series code is required")
    start_str, end_str = _resolve_window(period, start, end)
    provider = get_evds_provider()
    payload = provider.get_series_data(
        codes,
        start=start_str,
        end=end_str,
        frequency=frequency,
        aggregation=aggregation,
        formula=formula,
        decimals=decimals,
        decimal_separator=decimal_separator,
    )
    df = _frame_from_payload(payload, codes)
    # If only a single series, normalize to user-facing column.
    if len(codes) == 1 and "Value" in df.columns:
        df = df.rename(columns={"Value": codes[0]})
    return df


__all__ = [
    "EVDS",
    "EVDSSeries",
    "evds_categories",
    "evds_search",
    "evds_series",
    "evds_download",
    "set_evds_key",
    "clear_evds_key",
    "get_evds_key",
    "AGGREGATION",
    "FORMULA",
    "FREQUENCY",
    # Re-export upstream errors for convenience.
    "APIError",
    "DataNotAvailableError",
]
