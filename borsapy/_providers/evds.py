"""EVDS (TCMB Elektronik Veri Dağıtım Sistemi) v3 backend provider.

Wraps the EVDS3 REST API at https://evds3.tcmb.gov.tr (deployed late 2025).

The legacy ``evds2.tcmb.gov.tr/service/evds/...`` URLs were retired during
the migration — every request now 302 redirects to the v3 SPA HTML, breaking
the entire historical PyPI ecosystem (``evds``, ``evdsAPI`` and friends).

This provider exposes two surfaces:

1. **Official REST API** (key-based, GET only) — the production data
   surface. Requires a free API key from https://evds3.tcmb.gov.tr
   → BENİM SAYFAM → register → copy key. Set with :func:`set_evds_key`
   (or via ``EVDS_API_KEY`` env var).

2. **Anonymous SPA-internal endpoints** (path-style query strings such as
   ``categories/withDatagroups/type=json``) — used by the React app for
   catalogue navigation. Work without a key but cover only metadata.

Endpoint map (verified by reverse engineering the SPA bundle's ``Le`` axios
instance and the ``fatihmete/evds`` v0.4.0 reference client):

============================================================  =======  ==============================
Endpoint                                                      Method   Auth
============================================================  =======  ==============================
``/?series={A-B-C}&startDate=&endDate=&type=json&...``        GET      key (REST, primary data)
``/categories/withDatagroups/type=json``                      GET      anonymous (SPA)
``/serieList/fe/type=json&code={DATAGROUP}``                  GET      anonymous (SPA)
``/dashboards/{slug}``                                        GET      anonymous (SPA)
``/genel-ayarlar?key={KEY}``                                  GET      anonymous (SPA)
``/announcements``                                            GET      anonymous (SPA)
``/serieList/baslangicBitis``                                 POST     session cookie (SPA)
============================================================  =======  ==============================

System-imposed limits (live from ``/genel-ayarlar``): ``MAX_SERIE_COUNT=400``,
``MAX_GRID_COUNT=900`` rows.

The original SPA-internal ``POST /fe`` (and ``POST /fe/excel-indir``) paths
were dropped: the gateway returns HTTP 500 for every external client (curl,
httpx, real Chrome, Scrapling stealth) — even the SPA's own dashboard
chart-refresh requests fail with 500. ``get_series_data`` uses the REST
endpoint exclusively and raises a clear error when no key is configured.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL
from borsapy.exceptions import APIError

# ----- API key management -----------------------------------------------------

_api_key: str | None = None


def set_evds_key(key: str) -> None:
    """Configure the EVDS API key used by the official REST endpoints.

    Args:
        key: The API key copied from https://evds3.tcmb.gov.tr → BENİM SAYFAM.

    Once set, :class:`EVDSProvider` routes :meth:`get_series_data` (and the
    other time-series fetches) through the official REST API, which is far
    more reliable than the SPA-internal ``POST /fe`` path.

    The key may also be provided via the ``EVDS_API_KEY`` environment
    variable.
    """
    global _api_key
    if not key or not isinstance(key, str):
        raise ValueError("EVDS API key must be a non-empty string")
    _api_key = key.strip()
    # Reset the singleton so the next call rebuilds the session with the new
    # auth headers.
    global _provider
    _provider = None


def clear_evds_key() -> None:
    """Forget the configured EVDS API key (revert to anonymous mode)."""
    global _api_key, _provider
    _api_key = None
    _provider = None


def get_evds_key() -> str | None:
    """Return the configured EVDS API key, or ``None`` if not set.

    Falls back to ``EVDS_API_KEY`` environment variable when no key has been
    set programmatically.
    """
    if _api_key:
        return _api_key
    env = os.environ.get("EVDS_API_KEY", "").strip()
    return env or None

# ----- Constants --------------------------------------------------------------

BASE_URL = "https://evds3.tcmb.gov.tr"
API_PREFIX = "/igmevdsms-dis"

# User-friendly snake_case → backend INTEGER (sent as STRING in POST /fe).
# Mapping verified against the SPA bundle (`new Map([[1,"Date"],[2,"WORKDAY"],
# [3,"YEARWEEK"],[4,"TWO_WEEK"],[5,"MONTH"],[6,"QUARTER"],[7,"SEMIYEAR"],
# [8,"YEAR"]])`).
FREQUENCY: dict[str, int] = {
    "daily": 1,        # GÜNLÜK
    "workday": 2,      # İŞ GÜNÜ
    "weekly": 3,       # HAFTALIK
    "biweekly": 4,     # İKİ HAFTALIK
    "monthly": 5,      # AYLIK
    "quarterly": 6,    # ÜÇ AYLIK
    "semiannual": 7,   # ALTI AYLIK
    "annual": 8,       # YILLIK
}

# Numeric FREQUENCY found in /categories metadata (sometimes 9/13/16/18 — the
# old v2 enum) → integer used by the new POST /fe body.
NUMERIC_FREQ_NORMALIZE: dict[int, int] = {
    1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
    9: 5, 13: 6, 16: 7, 18: 8,
}

AGGREGATION: tuple[str, ...] = ("avg", "min", "max", "first", "last", "sum")

# Formula ID (string) → human label. POST /fe wants `formulas="0"` etc.
FORMULA: dict[str, tuple[str, str]] = {
    # key: (string_id, turkish_label)
    "level":            ("0", "Düzey"),
    "pct_change":       ("1", "Önceki Döneme Göre Yüzde Değişim"),
    "diff":             ("2", "Önceki Döneme Göre Fark"),
    "yoy_pct":          ("3", "Yıllık Yüzde Değişim"),
    "yoy_diff":         ("4", "Yıllık Fark"),
    "moving_avg":       ("5", "Hareketli Ortalama"),
    "moving_sum":       ("6", "Hareketli Toplam"),
    "yoy_moving_pct":   ("7", "Yıllık Hareketli Yüzde Değişim"),
    "yoy_moving_diff":  ("8", "Yıllık Hareketli Fark"),
}

# Browser-like headers used for both REST GETs and the working POST endpoints
# (e.g. ``/serieList/baslangicBitis``). The gateway is picky about Origin/
# Referer when serving cookie-sticky POSTs.
BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/tumSeriler",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


# ----- Helpers ----------------------------------------------------------------

def normalize_code(code: str) -> str:
    """Turn user-facing series codes (``TP.DK.USD.A``) into the backend's
    underscore form (``TP_DK_USD_A``)."""
    return code.replace(".", "_")


def denormalize_code(code: str) -> str:
    """Inverse of :func:`normalize_code` — used when surfacing series back to
    callers."""
    return code.replace("_", ".")


def _format_date(value: str | date | datetime) -> str:
    """Coerce a date input into the EVDS DD-MM-YYYY representation."""
    if isinstance(value, str):
        # Allow common formats (YYYY-MM-DD, DD-MM-YYYY) and pass-through.
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt).strftime("%d-%m-%Y")
            except ValueError:
                continue
        raise ValueError(
            f"Could not parse date '{value}'. Use YYYY-MM-DD or DD-MM-YYYY."
        )
    if isinstance(value, datetime):
        return value.strftime("%d-%m-%Y")
    if isinstance(value, date):
        return value.strftime("%d-%m-%Y")
    raise TypeError(f"Unsupported date value: {value!r}")


# Approximate observations per day for each backend frequency code.
# Used to estimate when a query will exceed the 1000-observation cap.
_OBS_PER_DAY: dict[int, float] = {
    1: 1.0,           # daily
    2: 5.0 / 7.0,     # workday (~5 of 7)
    3: 1.0 / 7.0,     # weekly
    4: 1.0 / 14.0,    # biweekly
    5: 1.0 / 30.0,    # monthly
    6: 1.0 / 91.0,    # quarterly
    7: 1.0 / 182.0,   # semiannual
    8: 1.0 / 365.0,   # annual
}


def _estimate_observations(start_str: str, end_str: str, freq_int: int) -> int:
    """Approximate the number of observations in a date range at a given freq.

    Used purely for chunking decisions; off-by-a-few errors are harmless
    because the chunker uses the same estimate to size each window.
    """
    start_dt = datetime.strptime(start_str, "%d-%m-%Y")
    end_dt = datetime.strptime(end_str, "%d-%m-%Y")
    days = max(0, (end_dt - start_dt).days) + 1
    rate = _OBS_PER_DAY.get(freq_int, 1.0)
    return int(days * rate) + 1


def _split_window(
    start_str: str, end_str: str, freq_int: int, max_obs: int
) -> list[tuple[str, str]]:
    """Split [start, end] into consecutive sub-ranges each ≤ max_obs."""
    start_dt = datetime.strptime(start_str, "%d-%m-%Y")
    end_dt = datetime.strptime(end_str, "%d-%m-%Y")
    rate = _OBS_PER_DAY.get(freq_int, 1.0)
    # Days per chunk = max_obs / rate, leave a small safety margin.
    safety = max(0.9, 1.0 - 50 / max_obs)
    days_per_chunk = max(1, int((max_obs * safety) / rate))
    windows: list[tuple[str, str]] = []
    cursor = start_dt
    while cursor <= end_dt:
        chunk_end = min(end_dt, cursor + timedelta(days=days_per_chunk - 1))
        windows.append((cursor.strftime("%d-%m-%Y"), chunk_end.strftime("%d-%m-%Y")))
        cursor = chunk_end + timedelta(days=1)
    return windows


def _merge_chunks(chunks: list[dict]) -> dict:
    """Concatenate ``items`` lists from sequential chunked responses.

    Deduplicates by ``Tarih`` key so overlapping windows stay clean.
    """
    if not chunks:
        return {"totalCount": 0, "items": []}
    merged_items: list[dict] = []
    seen_dates: set[str] = set()
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        items = chunk.get("items") or chunk.get("data") or []
        for item in items:
            tarih = item.get("Tarih") or item.get("TARIH") or ""
            if tarih and tarih in seen_dates:
                continue
            if tarih:
                seen_dates.add(tarih)
            merged_items.append(item)
    return {"totalCount": len(merged_items), "items": merged_items}


def period_to_dates(period: str) -> tuple[str, str]:
    """Translate yfinance-style period (``"1y"``, ``"3mo"``, ``"max"``) into
    (start, end) DD-MM-YYYY tuple. ``end`` is always today."""
    period = (period or "").lower().strip()
    end = datetime.now().date()
    deltas = {
        "1d": timedelta(days=1),
        "5d": timedelta(days=5),
        "1w": timedelta(days=7),
        "1mo": timedelta(days=31),
        "3mo": timedelta(days=92),
        "6mo": timedelta(days=183),
        "1y": timedelta(days=366),
        "2y": timedelta(days=731),
        "3y": timedelta(days=1096),
        "5y": timedelta(days=1826),
        "10y": timedelta(days=3653),
        "max": timedelta(days=365 * 80),  # EVDS has data back to ~1950.
    }
    if period == "ytd":
        start = end.replace(month=1, day=1)
    elif period in deltas:
        start = end - deltas[period]
    else:
        raise ValueError(
            f"Invalid period '{period}'. Valid: {list(deltas) + ['ytd']}"
        )
    return _format_date(start), _format_date(end)


# ----- Provider ---------------------------------------------------------------

class EVDSProvider(BaseProvider):
    """HTTP client for the EVDS v3 backend.

    Maintains a sticky :class:`httpx.Client` cookie jar so the POST endpoints
    can reuse whatever session the SPA gateway issues on the first visit.
    """

    BASE_URL = BASE_URL
    API_PREFIX = API_PREFIX
    MAX_SERIES_PER_CALL = 400
    # Per the official TCMB Web Service guide: requests are silently truncated
    # to the most-recent 1000 observations. We chunk longer ranges client-side.
    MAX_OBSERVATIONS_PER_CALL = 1000

    def __init__(self) -> None:
        super().__init__(timeout=60.0)
        # Override the BaseProvider headers with the browser-like set the
        # gateway expects (see module docstring).
        self._client.headers.update(BROWSER_HEADERS)
        # If the user configured an EVDS API key (programmatically or via the
        # EVDS_API_KEY env var), forward it with every request so the REST
        # endpoints stay accessible.
        key = get_evds_key()
        if key:
            self._client.headers["key"] = key
        self._session_warmed = False

    @property
    def has_api_key(self) -> bool:
        """Whether the provider was constructed with a usable EVDS API key."""
        return bool(self._client.headers.get("key"))

    # ----- Session management -------------------------------------------------

    def _warm_session(self) -> None:
        """Touch the SPA root + categories endpoint to populate the cookie jar
        before the first POST. The backend gateway issues a sticky session
        cookie on these requests."""
        if self._session_warmed:
            return
        try:
            self._client.get(f"{self.BASE_URL}/tumSeriler")
            self._client.get(f"{self.BASE_URL}{self.API_PREFIX}/genel-ayarlar/multiple"
                             "?keys=MAX_SERIE_COUNT,MAX_GRID_COUNT")
        except httpx.HTTPError:
            # Warm-up failures are not fatal; the actual call will surface
            # the relevant error.
            pass
        self._session_warmed = True

    def _api(self, path: str) -> str:
        """Compose a fully-qualified API URL."""
        return f"{self.BASE_URL}{self.API_PREFIX}{path}"

    # ----- Official REST catalogue endpoints (key required, fallback) ---------

    def get_categories_rest(self) -> list[dict]:
        """Fetch categories via the official REST endpoint (key required).

        Backup for :meth:`get_categories` if the SPA-internal anonymous
        endpoint ever changes. Returns the same shape (CATEGORY_ID +
        TOPIC_TITLE_TR/ENG) but **without** the embedded ``DATAGROUPS``.
        """
        if not self.has_api_key:
            raise APIError("get_categories_rest requires an API key")
        cache_key = "evds:rest:categories"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        url = self._api("/categories/type=json")
        try:
            response = self._client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise APIError(f"EVDS REST /categories failed: {e}") from e
        out = data if isinstance(data, list) else []
        self._cache_set(cache_key, out, TTL.EVDS_CATALOG)
        return out

    def get_datagroups_rest(
        self, datagroup_code: str | None = None
    ) -> list[dict]:
        """Fetch datagroups via the official REST endpoint (key required).

        - ``datagroup_code=None`` → ``mode=0`` (all datagroups)
        - ``datagroup_code="bie_yssk"`` → ``mode=1&code=bie_yssk`` (single)
        """
        if not self.has_api_key:
            raise APIError("get_datagroups_rest requires an API key")
        cache_key = f"evds:rest:datagroups:{datagroup_code or 'all'}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        if datagroup_code:
            url = self._api(f"/datagroups/mode=1&code={datagroup_code}&type=json")
        else:
            url = self._api("/datagroups/mode=0&type=json")
        try:
            response = self._client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise APIError(f"EVDS REST /datagroups failed: {e}") from e
        out = data if isinstance(data, list) else []
        self._cache_set(cache_key, out, TTL.EVDS_CATALOG)
        return out

    def get_series_list_rest(self, code: str) -> list[dict]:
        """Fetch series list via the official REST endpoint (key required).

        ``code`` may be a datagroup code (``bie_yssk``) or a series code
        (``TP.DK.USD.A``); both work per the TCMB Web Service guide.
        """
        if not self.has_api_key:
            raise APIError("get_series_list_rest requires an API key")
        cache_key = f"evds:rest:serieList:{code}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        url = self._api(f"/serieList/type=json&code={code}")
        try:
            response = self._client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise APIError(f"EVDS REST /serieList failed: {e}") from e
        out = data if isinstance(data, list) else []
        self._cache_set(cache_key, out, TTL.EVDS_CATALOG)
        return out

    # ----- Catalogue: categories + datagroups (anonymous GET) -----------------

    def get_categories(self) -> list[dict]:
        """Fetch the full category tree, with datagroups embedded.

        Returns:
            List of category dicts. Each one contains ``CATEGORY_ID``,
            ``TOPIC_TITLE_TR``, ``TOPIC_TITLE_ENG``, ``SEVIYE``,
            ``UST_CATEGORY_ID`` and a ``DATAGROUPS`` array.
        """
        cache_key = "evds:categories:withDatagroups"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            response = self._client.get(
                self._api("/categories/withDatagroups/type=json")
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise APIError(f"Failed to fetch EVDS categories: {e}") from e
        if not isinstance(data, list):
            raise APIError(f"Unexpected EVDS categories response: {type(data)}")
        self._cache_set(cache_key, data, TTL.EVDS_CATALOG)
        return data

    def get_series_list(self, datagroup_code: str) -> list[dict]:
        """Fetch the series in a given datagroup.

        Args:
            datagroup_code: e.g. ``"bie_dkdovizgn"`` (daily exchange rates).
                Take it from the ``DATAGROUP_CODE`` field of a catalogue entry.

        Returns:
            List of series dicts with ``SERIE_CODE``, ``SERIE_NAME``,
            ``SERIE_NAME_ENG``, ``FREQUENCY_STR``, ``DEFAULT_AGG_METHOD``,
            ``*ABLE`` aggregation flags and ``SCREEN_ORDER``.
        """
        if not datagroup_code:
            raise ValueError("datagroup_code is required")
        cache_key = f"evds:serielist:{datagroup_code}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        url = self._api(f"/serieList/fe/type=json&code={datagroup_code}")
        try:
            response = self._client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise APIError(
                f"Failed to fetch series list for '{datagroup_code}': {e}"
            ) from e
        if not isinstance(data, list):
            raise APIError(f"Unexpected serieList response: {type(data)}")
        self._cache_set(cache_key, data, TTL.EVDS_CATALOG)
        return data

    def get_settings(self, *keys: str) -> dict[str, str]:
        """Fetch one or more EVDS system settings (e.g. ``MAX_SERIE_COUNT``).

        Returns:
            Mapping of key → string value (backend stores everything as
            strings).
        """
        if not keys:
            raise ValueError("at least one settings key is required")
        cache_key = f"evds:settings:{','.join(sorted(keys))}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        if len(keys) == 1:
            url = self._api(f"/genel-ayarlar?key={keys[0]}")
        else:
            url = self._api(f"/genel-ayarlar/multiple?keys={','.join(keys)}")
        try:
            response = self._client.get(url)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as e:
            raise APIError(f"Failed to fetch EVDS settings: {e}") from e

        # Single-key endpoint returns a dict, multiple returns a list of dicts.
        out: dict[str, str] = {}
        if isinstance(payload, dict) and "key" in payload:
            out[payload["key"]] = payload.get("value", "")
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and "key" in item:
                    out[item["key"]] = item.get("value", "")
        self._cache_set(cache_key, out, TTL.EVDS_CATALOG)
        return out

    def get_dashboard(self, slug: str) -> dict:
        """Fetch a predefined dashboard (e.g. ``"baslica-gostergeler"`` =
        TCMB's "major indicators")."""
        if not slug:
            raise ValueError("dashboard slug is required")
        cache_key = f"evds:dashboard:{slug}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            response = self._client.get(self._api(f"/dashboards/{slug}"))
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise APIError(f"Failed to fetch dashboard '{slug}': {e}") from e
        self._cache_set(cache_key, data, TTL.EVDS_DASHBOARD)
        return data

    def get_home_page_dashboards(self) -> list[dict]:
        """Fetch the 10 TCMB-curated home-page dashboards.

        Each entry has the dashboard's metadata plus an embedded
        ``chartsList`` (typically a single chart per home-page dashboard).
        Use ``encodedId`` with :meth:`get_dashboard_by_encoded_id` for
        details, or browse via :class:`EVDS.dashboards` DataFrame.
        """
        cache_key = "evds:dashboards:home-page"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            response = self._client.get(self._api("/dashboards/home-page-dashboards"))
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise APIError(f"Failed to fetch home-page dashboards: {e}") from e
        out = data if isinstance(data, list) else []
        self._cache_set(cache_key, out, TTL.EVDS_DASHBOARD)
        return out

    def get_dashboard_by_encoded_id(self, encoded_id: str) -> dict:
        """Fetch a dashboard by its public encoded id.

        Use this when iterating :meth:`get_home_page_dashboards` results
        (each entry has an ``encodedId`` field).
        """
        if not encoded_id:
            raise ValueError("encoded_id is required")
        cache_key = f"evds:dashboard:encoded:{encoded_id}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            response = self._client.get(
                self._api(f"/public/dashboards/portlet/{encoded_id}")
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise APIError(f"Failed to fetch dashboard {encoded_id}: {e}") from e
        self._cache_set(cache_key, data, TTL.EVDS_DASHBOARD)
        return data

    def search_server(self, term: str) -> dict:
        """Server-side full-text search across the EVDS catalogue.

        URL: ``GET /igmevdsms-dis/searchResults?searchVal=<term>``

        The backend indexes data groups, series (with their tags), and
        report pages — broader than the client-side :meth:`EVDS.search`
        which walks the cached catalogue tree. Results are capped at 100
        records per category, per the TCMB UI guide.

        Returns:
            Dict with ``veriGruplari``, ``seriler``, ``raporlar`` lists
            (Turkish keys preserved from the backend).
        """
        if not term or not isinstance(term, str):
            raise ValueError("search term is required")
        cache_key = f"evds:searchresults:{term.strip().lower()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            response = self._client.get(
                self._api(f"/searchResults?searchVal={term.strip()}")
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise APIError(f"EVDS server-side search failed: {e}") from e
        self._cache_set(cache_key, data, TTL.EVDS_DASHBOARD)
        return data

    def get_announcements(self) -> list[dict]:
        """Fetch the EVDS announcements list."""
        cache_key = "evds:announcements"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            response = self._client.get(self._api("/announcements"))
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise APIError(f"Failed to fetch announcements: {e}") from e
        out = data if isinstance(data, list) else data.get("data", [])
        self._cache_set(cache_key, out, TTL.EVDS_DASHBOARD)
        return out

    # ----- Catalogue lookups (derived from get_categories) --------------------

    def find_datagroup(self, datagroup_code: str) -> dict | None:
        """Find a datagroup in the cached category tree."""
        for category in self.get_categories():
            for dg in category.get("DATAGROUPS", []):
                if dg.get("DATAGROUP_CODE") == datagroup_code:
                    return {**dg, "_category": category}
        return None

    def find_series(self, series_code: str) -> dict | None:
        """Locate a series across all datagroups (slow first call, cached after).

        Walks the catalogue tree, then drills into each datagroup's serieList.
        Caches the result so a second lookup is essentially free.

        Catalog responses use **dot-form** codes (``TP.DK.USD.A``) but POST /fe
        wants **underscore-form**; the comparison here normalizes both sides
        to dot-form so users can pass either.
        """
        target_dot = denormalize_code(series_code).upper()
        cache_key = f"evds:series_lookup:{target_dot}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # The EVDS bundle exposes /seri-konum?dataGroupCode=X for the inverse
        # mapping; we use the cached catalogue tree instead so the lookup
        # remains entirely client-side once categories are warm.
        for category in self.get_categories():
            for dg in category.get("DATAGROUPS", []):
                dg_code = dg.get("DATAGROUP_CODE")
                if not dg_code:
                    continue
                series_list = self.get_series_list(dg_code)
                for serie in series_list:
                    raw = serie.get("SERIE_CODE", "")
                    if denormalize_code(raw).upper() == target_dot:
                        out = {
                            **serie,
                            "_datagroup": dg,
                            "_category": category,
                        }
                        self._cache_set(cache_key, out, TTL.EVDS_CATALOG)
                        return out
        return None

    # ----- Time-series data (POST endpoints, session cookie sticky) -----------

    def _post_json(
        self,
        path: str,
        body: dict | list,
        headers_extra: dict[str, str] | None = None,
    ) -> Any:
        """Issue a POST against the EVDS gateway.

        Used by the working POST endpoints (e.g. ``/serieList/baslangicBitis``).
        Performs a one-time session warm-up so the gateway's sticky cookies
        are available for subsequent calls.
        """
        self._warm_session()
        url = self._api(path)
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            **(headers_extra or {}),
        }

        last_error: Exception | None = None
        for _attempt in range(2):  # one retry for transient gateway hiccups
            try:
                response = self._client.post(
                    url,
                    content=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                    headers=headers,
                )
            except httpx.HTTPError as e:
                last_error = e
                continue
            ct = response.headers.get("content-type", "")
            if response.status_code < 400 and "json" in ct.lower():
                return response.json()
            if response.status_code < 400:
                return response.content
            last_error = APIError(
                f"EVDS POST {path} returned HTTP {response.status_code}: "
                f"{response.text[:200]}",
                status_code=response.status_code,
            )
            # Re-warm cookies on a fresh attempt.
            self._session_warmed = False

        if last_error:
            raise last_error
        raise APIError(f"EVDS POST {path} failed without a response")

    def get_series_range(
        self,
        series_codes: list[str],
        datagroup_codes: list[str] | None = None,
        frequency: str | int = "monthly",
    ) -> dict[str, dict]:
        """Fetch min/max available observation dates for one or more series.

        Body shape (from bundle's ``sn`` thunk for ``getBaslangicBitis``)::

            {
              "frequency": <int>,
              "series": ["TP_FG_J0", ...],
              "datagroups": ["bie_tukfiy4", ...]
            }

        Args:
            series_codes: User-facing codes (dot-separated).
            datagroup_codes: Optional list of datagroup codes (one per series).
                If omitted, looked up from the catalogue.
            frequency: Same encoding as :meth:`get_series_data`.

        Returns:
            Mapping of normalized series code → ``{"start": <date>, "end": <date>}``.
        """
        if not series_codes:
            raise ValueError("at least one series code is required")
        normalized = [normalize_code(c) for c in series_codes]

        # Resolve datagroups if not supplied.
        if not datagroup_codes:
            datagroup_codes = []
            for code in series_codes:
                located = self.find_series(code)
                if located and located.get("_datagroup"):
                    datagroup_codes.append(
                        located["_datagroup"].get("DATAGROUP_CODE", "")
                    )
                else:
                    datagroup_codes.append("")

        freq_int = self._resolve_frequency(frequency)

        cache_key = (
            "evds:range:"
            + ",".join(sorted(normalized))
            + f":{freq_int}"
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        body = {
            "frequency": freq_int,
            "series": normalized,
            "datagroups": datagroup_codes,
        }
        try:
            data = self._post_json("/serieList/baslangicBitis", body)
        except APIError:
            return {}

        # Possible shapes: list of {SERIE_CODE, START_DATE, END_DATE}, or
        # {startDate: "01-01-1950", endDate: "12-12-2025"} top-level.
        out: dict[str, dict] = {}
        if isinstance(data, list):
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                code = entry.get("SERIE_CODE") or entry.get("serieCode")
                if not code:
                    continue
                out[code.upper()] = {
                    "start": entry.get("START_DATE")
                    or entry.get("startDate")
                    or entry.get("BASLANGIC_TARIHI"),
                    "end": entry.get("END_DATE")
                    or entry.get("endDate")
                    or entry.get("BITIS_TARIHI"),
                }
        elif isinstance(data, dict):
            # Top-level start/end (single-series shorthand seen in some deployments)
            top_start = data.get("startDate") or data.get("START_DATE")
            top_end = data.get("endDate") or data.get("END_DATE")
            if top_start and top_end and len(normalized) == 1:
                out[normalized[0].upper()] = {
                    "start": top_start,
                    "end": top_end,
                }
            for entry in data.get("data", data.get("items", [])):
                if not isinstance(entry, dict):
                    continue
                code = entry.get("SERIE_CODE") or entry.get("serieCode")
                if not code:
                    continue
                out[code.upper()] = {
                    "start": entry.get("START_DATE")
                    or entry.get("startDate")
                    or entry.get("BASLANGIC_TARIHI"),
                    "end": entry.get("END_DATE")
                    or entry.get("endDate")
                    or entry.get("BITIS_TARIHI"),
                }
        self._cache_set(cache_key, out, 3600)
        return out

    def _resolve_frequency(self, frequency: int | str) -> int:
        """Coerce frequency input into the backend's integer encoding."""
        if isinstance(frequency, int):
            return NUMERIC_FREQ_NORMALIZE.get(frequency, frequency)
        s = frequency.strip().lower()
        if s in FREQUENCY:
            return FREQUENCY[s]
        # Allow numeric strings.
        try:
            n = int(s)
            return NUMERIC_FREQ_NORMALIZE.get(n, n)
        except ValueError:
            pass
        raise ValueError(
            f"Invalid frequency '{frequency}'. Use one of {list(FREQUENCY)} "
            f"or an integer 1..8."
        )

    def _resolve_formula(self, formula: str | int) -> tuple[str, str]:
        """Coerce formula input into ``(string_id, turkish_label)``."""
        if isinstance(formula, str) and formula in FORMULA:
            return FORMULA[formula]
        f_str = str(formula)
        for fid, label in FORMULA.values():
            if fid == f_str:
                return fid, label
        raise ValueError(
            f"Invalid formula '{formula}'. Use one of {list(FORMULA)} "
            "or a string ID 0..8."
        )

    def get_series_data(
        self,
        series_codes: list[str] | str,
        start: str | date | datetime,
        end: str | date | datetime,
        frequency: str | int = "monthly",
        aggregation: str | list[str] = "avg",
        formula: str | list[str] = "level",
        decimals: int = 2,
        date_format: int = 0,
        output_format: str = "json",
        decimal_separator: str = ".",
    ) -> Any:
        """Fetch observation data for one or more series via the official
        REST endpoint.

        Requires an EVDS API key — get one (free) from
        https://evds3.tcmb.gov.tr → BENİM SAYFAM → Kayıt Ol, then configure
        with :func:`set_evds_key` or the ``EVDS_API_KEY`` env var.

        Args:
            series_codes: Single code (``"TP.DK.USD.A"``) or list. Internally
                normalized to underscore form. Up to
                :attr:`MAX_SERIES_PER_CALL` series per call.
            start: Start date (str ``YYYY-MM-DD`` / ``DD-MM-YYYY``, ``date`` or
                ``datetime``).
            end: End date.
            frequency: User-friendly key (``"daily"``, ``"monthly"`` ...) or
                integer (1..8). See :data:`FREQUENCY`.
            aggregation: Single string (applied to all series) or per-series
                list. Each value is one of :data:`AGGREGATION`.
            formula: Single string/int or per-series list. Each value is a
                key from :data:`FORMULA` (``"level"``, ``"yoy_pct"`` ...) or
                the raw string ID (``"0"``, ``"3"`` ...).
            decimals: Decimal places for numeric formatting.
            date_format: 0 (default) for the EVDS internal day stamp.

        Returns:
            Raw JSON dict from the backend (totalCount + items array etc.).
        """
        if not self.has_api_key:
            raise APIError(
                "EVDS time-series fetch requires an API key. Get a free key "
                "at https://evds3.tcmb.gov.tr (BENİM SAYFAM → Kayıt Ol) and "
                "configure with bp.set_evds_key(<key>) or set the "
                "EVDS_API_KEY environment variable."
            )

        if isinstance(series_codes, str):
            series_codes = [series_codes]
        if not series_codes:
            raise ValueError("at least one series code is required")
        if len(series_codes) > self.MAX_SERIES_PER_CALL:
            raise ValueError(
                f"max {self.MAX_SERIES_PER_CALL} series per call "
                f"(got {len(series_codes)})"
            )

        # The REST endpoint wants DOT-form codes (verified against the
        # official TCMB Web Service guide: ``series=TP.DK.USD.A-TP.DK.EUR.A``).
        normalized = [denormalize_code(c) for c in series_codes]
        codes_str = "-".join(normalized)

        n = len(normalized)
        # Aggregation may be a list per-series or a scalar broadcast across all.
        if isinstance(aggregation, str):
            aggs = [aggregation.lower()] * n
        else:
            aggs = [a.lower() for a in aggregation]
            if len(aggs) != n:
                raise ValueError(
                    f"aggregation list length ({len(aggs)}) must match "
                    f"series count ({n})"
                )
        for agg in aggs:
            if agg not in AGGREGATION:
                raise ValueError(
                    f"Invalid aggregation '{agg}'. Use one of {AGGREGATION}"
                )
        agg_str = "-".join(aggs)

        # Formula: same broadcasting logic.
        if isinstance(formula, list):
            formula_inputs = formula
            if len(formula_inputs) != n:
                raise ValueError(
                    f"formula list length ({len(formula_inputs)}) must match "
                    f"series count ({n})"
                )
        else:
            formula_inputs = [formula] * n
        formula_ids = [self._resolve_formula(f)[0] for f in formula_inputs]
        formulas_str = "-".join(formula_ids)

        freq_int = self._resolve_frequency(frequency)
        start_str = _format_date(start)
        end_str = _format_date(end)

        cache_key = (
            f"evds:data:{codes_str}:{start_str}:{end_str}:"
            f"{freq_int}:{agg_str}:{formulas_str}:{decimals}:"
            f"{output_format}:{decimal_separator}"
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # CSV/XML are returned as raw text; chunking would require parsing
        # to merge so we skip the chunker and let TCMB return up to 1000 obs.
        if output_format != "json":
            data = self._get_series_data_rest(
                codes_str=codes_str,
                start_str=start_str,
                end_str=end_str,
                freq_int=freq_int,
                agg_str=agg_str,
                formulas_str=formulas_str,
                decimals=decimals,
                date_format=date_format,
                output_format=output_format,
                decimal_separator=decimal_separator,
            )
            self._cache_set(cache_key, data, TTL.EVDS_DATA)
            return data

        # Estimate observation count; if it exceeds the gateway's 1000-row
        # silent-truncation limit, chunk the request client-side and stitch
        # the responses back together.
        try:
            obs_estimate = _estimate_observations(start_str, end_str, freq_int)
        except Exception:
            obs_estimate = 0
        chunk_threshold = self.MAX_OBSERVATIONS_PER_CALL

        if obs_estimate > chunk_threshold:
            # Walk the range in 1000-observation windows.
            windows = _split_window(start_str, end_str, freq_int, chunk_threshold)
            chunks: list[dict] = []
            for w_start, w_end in windows:
                part = self._get_series_data_rest(
                    codes_str=codes_str,
                    start_str=w_start,
                    end_str=w_end,
                    freq_int=freq_int,
                    agg_str=agg_str,
                    formulas_str=formulas_str,
                    decimals=decimals,
                    date_format=date_format,
                    decimal_separator=decimal_separator,
                )
                chunks.append(part)
            data = _merge_chunks(chunks)
        else:
            data = self._get_series_data_rest(
                codes_str=codes_str,
                start_str=start_str,
                end_str=end_str,
                freq_int=freq_int,
                agg_str=agg_str,
                formulas_str=formulas_str,
                decimals=decimals,
                date_format=date_format,
                decimal_separator=decimal_separator,
            )

        self._cache_set(cache_key, data, TTL.EVDS_DATA)
        return data

    def _rest_data_get(
        self,
        ordered_params: list[tuple[str, str]],
        output_format: str = "json",
    ) -> Any:
        """Generic helper for the EVDS REST data endpoints.

        URL is path-style (``/k1=v1&k2=v2`` literal — no ``?``), per the
        official TCMB Web Service guide. Both ``series=`` and ``datagroup=``
        endpoints follow this contract.

        Args:
            ordered_params: ``[(key, value), ...]`` — order matters because the
                gateway expects ``series=`` / ``datagroup=`` to come first.
            output_format: ``"json"`` (default, returns parsed dict),
                ``"csv"`` or ``"xml"`` (returns raw text body).

        Returns:
            Parsed JSON dict for ``json``, raw ``str`` body for ``csv``/``xml``.
        """
        # Build the path-style query string by hand; httpx would otherwise
        # turn `/key=foo` into `/?key=foo`, which the gateway 404s.
        path = "/" + "&".join(f"{k}={v}" for k, v in ordered_params if v != "")
        url = self._api(path)
        try:
            response = self._client.get(url)
            response.raise_for_status()
            if output_format == "json":
                return response.json()
            return response.text
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            preview = e.response.text[:200]
            if status in (401, 403):
                raise APIError(
                    f"EVDS REST: HTTP {status} (key invalid or missing). "
                    f"Re-check the key at https://evds3.tcmb.gov.tr — {preview}",
                    status_code=status,
                ) from e
            raise APIError(
                f"EVDS REST returned HTTP {status}: {preview}",
                status_code=status,
            ) from e
        except httpx.HTTPError as e:
            raise APIError(f"EVDS REST request failed: {e}") from e

    def _get_series_data_rest(
        self,
        codes_str: str,
        start_str: str,
        end_str: str,
        freq_int: int,
        agg_str: str,
        formulas_str: str,
        decimals: int,
        date_format: int,
        output_format: str = "json",
        decimal_separator: str = ".",
    ) -> Any:
        """Fetch via the official REST series endpoint (key required).

        URL pattern (TCMB Web Service guide)::

            GET /igmevdsms-dis/series=A-B-C&startDate=...&endDate=...&type=json
                &frequency=N&aggregationTypes=avg-...&formulas=...
        """
        parts: list[tuple[str, str]] = [
            ("series", codes_str),
            ("startDate", start_str),
            ("endDate", end_str),
            ("type", output_format),
        ]
        if freq_int:
            parts.append(("frequency", str(freq_int)))
        if agg_str:
            parts.append(("aggregationTypes", agg_str))
        if formulas_str:
            parts.append(("formulas", formulas_str))
        parts.append(("decimalSeperator", decimal_separator))
        parts.append(("decimal", str(decimals)))
        parts.append(("dateFormat", str(date_format)))
        return self._rest_data_get(parts, output_format=output_format)

    def get_datagroup_data(
        self,
        datagroup_code: str,
        start: str | date | datetime,
        end: str | date | datetime,
        frequency: str | int | None = None,
        decimals: int = 2,
    ) -> Any:
        """Fetch every series in a datagroup with one HTTP call.

        URL pattern (TCMB Web Service guide § IV)::

            GET /igmevdsms-dis/datagroup=bie_yssk&startDate=...&endDate=...
                &type=json[&frequency=N]

        This is far more efficient than building a long ``series=A-B-C-...``
        list when you want every series in a group (e.g. all 137 daily FX
        series in ``bie_dkdovizgn``).

        Requires an EVDS API key.

        Args:
            datagroup_code: e.g. ``"bie_dkdovizgn"`` (from
                :meth:`get_categories` / :meth:`find_datagroup`).
            start, end: Date inputs (str / date / datetime).
            frequency: Optional snake_case key or 1..8. Backend uses the
                datagroup's native frequency by default.
            decimals: Decimal places for numeric formatting.

        Returns:
            Raw JSON dict (``totalCount`` + ``items`` array etc.).
        """
        if not self.has_api_key:
            raise APIError(
                "EVDS datagroup data fetch requires an API key. "
                "Configure with bp.set_evds_key(<key>) or set EVDS_API_KEY."
            )
        if not datagroup_code:
            raise ValueError("datagroup_code is required")

        start_str = _format_date(start)
        end_str = _format_date(end)
        freq_int = self._resolve_frequency(frequency) if frequency is not None else None

        cache_key = (
            f"evds:datagroup:{datagroup_code}:{start_str}:{end_str}:"
            f"{freq_int or 'native'}:{decimals}"
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        parts: list[tuple[str, str]] = [
            ("datagroup", datagroup_code),
            ("startDate", start_str),
            ("endDate", end_str),
            ("type", "json"),
        ]
        if freq_int:
            parts.append(("frequency", str(freq_int)))
        parts.append(("decimalSeperator", "."))
        parts.append(("decimal", str(decimals)))
        data = self._rest_data_get(parts)
        self._cache_set(cache_key, data, TTL.EVDS_DATA)
        return data

# ----- Singleton --------------------------------------------------------------

_provider: EVDSProvider | None = None


def get_evds_provider() -> EVDSProvider:
    """Return the singleton :class:`EVDSProvider` instance."""
    global _provider
    if _provider is None:
        _provider = EVDSProvider()
    return _provider
