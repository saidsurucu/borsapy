"""TEFAS provider for mutual fund data."""

import json
import re
import time
from datetime import datetime
from typing import Any

import httpx
import pandas as pd
import urllib3

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL
from borsapy.exceptions import APIError, DataNotAvailableError

# Disable SSL warnings for TEFAS
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Asset type code mapping (Turkish abbreviations to full names)
# Used by BindHistoryAllocation API (returns abbreviations like "HS", "TR")
ASSET_TYPE_MAPPING = {
    "BB": "Banka Bonosu",
    "BYF": "Borsa Yatırım Fonu",
    "D": "Döviz",
    "DB": "Devlet Bonusu",
    "DT": "Devlet Tahvili",
    "DÖT": "Döviz Ödenekli Tahvil",
    "EUT": "Eurobond Tahvil",
    "FB": "Finansman Bonosu",
    "FKB": "Fon Katılma Belgesi",
    "GAS": "Gümüş",
    "GSYKB": "Girişim Sermayesi Yatırım Katılma Belgesi",
    "GSYY": "Girişim Sermayesi Yatırım",
    "GYKB": "Gayrimenkul Yatırım Katılma Belgesi",
    "GYY": "Gayrimenkul Yatırım",
    "HB": "Hazine Bonosu",
    "HS": "Hisse Senedi",
    "KBA": "Kira Sertifikası Alım",
    "KH": "Katılım Hesabı",
    "KHAU": "Katılım Hesabı ABD Doları",
    "KHD": "Katılım Hesabı Döviz",
    "KHTL": "Katılım Hesabı Türk Lirası",
    "KKS": "Kira Sertifikası",
    "KKSD": "Kira Sertifikası Döviz",
    "KKSTL": "Kira Sertifikası Türk Lirası",
    "KKSYD": "Kira Sertifikası Yabancı Döviz",
    "KM": "Kıymetli Maden",
    "KMBYF": "Kıymetli Maden Borsa Yatırım Fonu",
    "KMKBA": "Kıymetli Maden Katılma Belgesi Alım",
    "KMKKS": "Kıymetli Maden Kira Sertifikası",
    "KİBD": "Kira Sertifikası İpotekli Borçlanma",
    "OSKS": "Özel Sektör Kira Sertifikası",
    "OST": "Özel Sektör Tahvili",
    "R": "Repo",
    "T": "Tahvil",
    "TPP": "Ters Repo Para Piyasası",
    "TR": "Ters Repo",
    "VDM": "Vadeli Mevduat",
    "VM": "Vadesiz Mevduat",
    "VMAU": "Vadesiz Mevduat ABD Doları",
    "VMD": "Vadesiz Mevduat Döviz",
    "VMTL": "Vadesiz Mevduat Türk Lirası",
    "VİNT": "Varlık İpotek Tahvil",
    "YBA": "Yabancı Borçlanma Araçları",
    "YBKB": "Yabancı Borsa Katılma Belgesi",
    "YBOSB": "Yabancı Borsa Özel Sektör Bonusu",
    "YBYF": "Yabancı Borsa Yatırım Fonu",
    "YHS": "Yabancı Hisse Senedi",
    "YMK": "Yabancı Menkul Kıymet",
    "YYF": "Yabancı Yatırım Fonu",
    "ÖKSYD": "Özel Sektör Kira Sertifikası Yabancı Döviz",
    "ÖSDB": "Özel Sektör Devlet Bonusu",
}

# Standardized asset names (maps various API response names to standardized English names)
# Maps various API response names to standardized English names
ASSET_NAME_STANDARDIZATION = {
    # Direct mappings (API returns these exact names)
    "Hisse Senedi": "Stocks",
    "Ters-Repo": "Reverse Repo",
    "Finansman Bonosu": "Commercial Paper",
    "Özel Sektör Tahvili": "Corporate Bonds",
    "Mevduat (TL)": "TL Deposits",
    "Yatırım Fonları Katılma Payları": "Fund Shares",
    "Girişim Sermayesi Yatırım Fonları Katılma Payları": "VC Fund Shares",
    "Vadeli İşlemler Nakit Teminatları": "Futures Margin",
    "Diğer": "Other",
    # Additional common names
    "Devlet Tahvili": "Government Bonds",
    "Hazine Bonosu": "Treasury Bills",
    "Kıymetli Maden": "Precious Metals",
    "Döviz": "Foreign Currency",
    "Repo": "Repo",
}


class TEFASProvider(BaseProvider):
    """
    Provider for mutual fund data from TEFAS.

    Provides:
    - Fund details and current prices
    - Historical performance data
    - Fund search
    """

    BASE_URL = "https://www.tefas.gov.tr/api/funds"

    # Map borsapy period strings to the new fonFiyatBilgiGetir "periyod" enum.
    # The new API only accepts these fixed codes — arbitrary day counts and
    # date ranges return "Sistem Hatası!!". periyod=60 (5y) is the maximum.
    _PERIOD_TO_PERIYOD: dict[str, int] = {
        "1d": 13,    # weekly bucket — minimum granularity (~5 rows)
        "5d": 13,
        "1w": 13,
        "1wk": 13,
        "1mo": 1,
        "3mo": 3,
        "6mo": 6,
        "ytd": 0,
        "1y": 12,
        "2y": 36,    # no native 2y bucket — round up to 3y
        "3y": 36,
        "5y": 60,
        "max": 60,   # 5 years is the API's hard cap
    }

    # Maximum periyod code (5 years) — used as fallback for arbitrary date
    # ranges, then filtered client-side.
    _PERIYOD_MAX = 60

    def __init__(self):
        super().__init__(verify=False)

    @staticmethod
    def _parse_turkish_decimal(value: str | None) -> float | None:
        """Parse Turkish decimal string (comma as decimal separator) to float.

        Args:
            value: Turkish decimal string (e.g., "2,2" for 2.2), None, or "0".

        Returns:
            Float value or None if input is None/empty/invalid.
        """
        if value is None:
            return None
        value = str(value).strip()
        if not value:
            return None
        try:
            return float(value.replace(",", "."))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_json(response: httpx.Response, endpoint: str) -> Any:
        """Parse TEFAS JSON response with descriptive errors for non-JSON bodies.

        TEFAS occasionally returns an empty body or an HTML maintenance/WAF page
        with HTTP 200 instead of JSON. The stock ``response.json()`` masks this
        as a bare ``JSONDecodeError`` — this wrapper surfaces the HTTP status,
        content type, and a body preview so callers can diagnose the upstream
        failure.
        """
        status = response.status_code
        content_type = response.headers.get("content-type", "")
        body = response.content or b""

        if not body.strip():
            raise APIError(
                f"TEFAS {endpoint} returned an empty response "
                f"(HTTP {status}, content-type={content_type!r}). "
                "Upstream API may be down or rate-limited."
            )

        if "json" not in content_type.lower():
            preview = body[:200].decode("utf-8", errors="replace")
            raise APIError(
                f"TEFAS {endpoint} returned non-JSON response "
                f"(HTTP {status}, content-type={content_type!r}). "
                f"Body preview: {preview!r}"
            )

        try:
            return response.json()
        except json.JSONDecodeError as e:
            preview = body[:200].decode("utf-8", errors="replace")
            raise APIError(
                f"TEFAS {endpoint} returned malformed JSON "
                f"(HTTP {status}, content-type={content_type!r}): {e.msg}. "
                f"Body preview: {preview!r}"
            ) from e

    def _post_json(
        self,
        url: str,
        data: dict[str, Any],
        endpoint: str,
        headers: dict[str, str] | None = None,
        max_retries: int = 3,
    ) -> Any:
        """POST to TEFAS (form-urlencoded) and parse JSON, retrying transient WAF blocks.

        Used for legacy ``/api/DB`` endpoints which expect
        ``application/x-www-form-urlencoded`` payloads.

        TEFAS WAF intermittently returns empty bodies or HTML maintenance
        pages with HTTP 200. Retries with exponential backoff (0.5s, 1s, 2s)
        when :meth:`_safe_json` detects such non-JSON responses.
        """
        last_error: APIError | None = None
        for attempt in range(max_retries):
            if attempt > 0:
                time.sleep(0.5 * (2 ** (attempt - 1)))

            response = self._client.post(url, data=data, headers=headers)
            response.raise_for_status()
            try:
                return self._safe_json(response, endpoint)
            except APIError as e:
                last_error = e

        assert last_error is not None  # loop always runs at least once
        raise last_error

    def _post_json_v2(
        self,
        endpoint_path: str,
        payload: dict[str, Any],
        endpoint_label: str,
        max_retries: int = 3,
    ) -> list[dict[str, Any]]:
        """POST to the new TEFAS ``/api/funds/*`` endpoints with a JSON body.

        The redesigned (2025+) TEFAS API uses ``Content-Type: application/json``
        and returns a standard envelope::

            {"errorCode": ..., "errorMessage": ..., "resultList": [...]}

        This method handles that envelope, retries transient failures, and
        returns the ``resultList`` directly.

        Raises:
            APIError: On non-retryable upstream errors or after exhausting
                retries.
        """
        url = f"{self.BASE_URL}/{endpoint_path}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
        }

        last_error: APIError | None = None
        for attempt in range(max_retries):
            if attempt > 0:
                time.sleep(0.5 * (2 ** (attempt - 1)))

            response = self._client.post(
                url, json=payload, headers=headers,
            )
            response.raise_for_status()

            try:
                data = self._safe_json(response, endpoint_label)
            except APIError as e:
                last_error = e
                continue

            # Unwrap the v2 envelope
            if isinstance(data, dict):
                err_msg = data.get("errorMessage")
                if err_msg:
                    raise APIError(
                        f"TEFAS {endpoint_label} returned error: {err_msg}"
                    )
                result_list = data.get("resultList")
                if result_list is None:
                    return []
                return result_list

            # Unexpected shape — return as-is wrapped in a list
            return [data] if data else []

        assert last_error is not None
        raise last_error

    def get_fund_detail(self, fund_code: str, fund_type: str = "YAT") -> dict[str, Any]:
        """
        Get detailed information about a fund.

        Args:
            fund_code: TEFAS fund code (e.g., "AAK", "TTE")
            fund_type: Fund type - "YAT" for investment funds, "EMK" for pension funds.

        Returns:
            Dictionary with fund details.
        """
        fund_code = fund_code.upper()
        fund_type = fund_type.upper()

        cache_key = f"tefas:detail:{fund_code}:{fund_type}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            # --- 1. Core fund info from fonBilgiGetir ---
            info_list = self._post_json_v2(
                "fonBilgiGetir",
                {"fonKodu": fund_code},
                "fonBilgiGetir",
            )

            if not info_list:
                raise DataNotAvailableError(f"No data for fund: {fund_code}")

            fund_info = info_list[0]

            # --- 2. Return data from fonGetiriBazliBilgiGetir ---
            # This endpoint returns ALL funds; we filter client-side.
            # Also used to detect fund_class ("YAT" vs "EMK") — if the requested
            # fund_type list doesn't contain the code, fall back to the other.
            fund_return: dict[str, Any] = {}
            detected_class: str | None = None
            try:
                fund_return, detected_class = self._lookup_fund_returns(
                    fund_code, fund_type
                )
            except APIError:
                pass  # Returns data is supplementary; don't fail the whole call

            # --- 3. Profile data from fonProfilBilgiGetir ---
            # ISIN, KAP link, fees, valor — restored in v0.8.8 after we
            # discovered the correct endpoint name (PR #16 used the empty
            # fonProfilDtyGetir variant by mistake).
            fund_profile: dict[str, Any] = {}
            try:
                profile_list = self._post_json_v2(
                    "fonProfilBilgiGetir",
                    {"fonKodu": fund_code, "dil": "TR"},
                    "fonProfilBilgiGetir",
                )
                if profile_list:
                    fund_profile = profile_list[0]
            except APIError:
                pass  # Profile data is supplementary

            detail = {
                "fund_code": fund_code,
                "name": fund_info.get("fonUnvan", "") or fund_profile.get("fonUnvan", ""),
                "date": "",  # Not available in fonBilgiGetir
                "price": float(fund_info.get("sonFiyat", 0) or 0),
                "fund_size": float(fund_info.get("portBuyukluk", 0) or 0),
                "investor_count": int(fund_info.get("yatirimciSayi", 0) or 0),
                "founder": "",  # Not available in fonBilgiGetir
                "manager": "",  # Not available in fonBilgiGetir
                "fund_type": fund_return.get("fonTurAciklama", ""),
                # fund_class is "YAT" or "EMK" — used by Fund.fund_type for
                # downstream API calls that need this distinction.
                "fund_class": detected_class or fund_type,
                "category": fund_info.get("fonKategori", ""),
                "risk_value": int(
                    fund_profile.get("riskDegeri")
                    or fund_return.get("riskDegeri")
                    or 0
                ),
                # Performance metrics (from fonGetiriBazliBilgiGetir)
                "return_1m": fund_return.get("getiri1a"),
                "return_3m": fund_return.get("getiri3a"),
                "return_6m": fund_return.get("getiri6a"),
                "return_ytd": fund_return.get("getiriyb"),
                "return_1y": fund_return.get("getiri1y"),
                "return_3y": fund_return.get("getiri3y"),
                "return_5y": fund_return.get("getiri5y"),
                # Daily/weekly change
                "daily_return": fund_info.get("gunlukGetiri"),
                "weekly_return": None,  # Still not available in new API
                # Category ranking
                "category_rank": fund_info.get("kategoriDerece"),
                "category_fund_count": fund_info.get("kategoriFonSay"),
                "market_share": fund_info.get("pazarPayi"),
                # Fund profile (restored from fonProfilBilgiGetir)
                "isin": fund_profile.get("isinKodu"),
                "last_trading_time": fund_profile.get("sonIsSaat"),
                "first_trading_time": fund_profile.get("basIsSaat"),
                "min_purchase": fund_profile.get("minAlis"),
                "min_redemption": fund_profile.get("minSatis"),
                "max_purchase": fund_profile.get("maxAlis"),
                "max_redemption": fund_profile.get("maxSatis"),
                "buy_valor": fund_profile.get("fonGeriAlisValor"),
                "sell_valor": fund_profile.get("fonSatisValor"),
                "entry_fee": fund_profile.get("girisKomisyonu"),
                "exit_fee": fund_profile.get("cikisKomisyonu"),
                "kap_link": fund_profile.get("kapLink"),
                "tefas_status": fund_profile.get("tefasDurum"),
                # Portfolio allocation — only available via Fund.allocation
                # (Playwright-based SSR scrape since 2026-04 TEFAS migration).
                "allocation": None,
            }

            self._cache_set(cache_key, detail, TTL.FX_RATES)
            return detail

        except DataNotAvailableError:
            raise
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Failed to fetch fund detail for {fund_code}: {e}") from e

    def _lookup_fund_returns(
        self, fund_code: str, fund_type: str
    ) -> tuple[dict[str, Any], str | None]:
        """Find a fund in the cached returns list, falling back to the other
        fund_class if not present.

        Returns ``(return_row, detected_class)`` where ``detected_class`` is
        "YAT", "EMK", or None when no match is found.
        """
        for ftype in (fund_type, "EMK" if fund_type == "YAT" else "YAT"):
            cache_key = f"tefas:all_returns:{ftype}"
            all_returns = self._cache_get(cache_key)
            if all_returns is None:
                all_returns = self._post_json_v2(
                    "fonGetiriBazliBilgiGetir",
                    {
                        "fonTipi": ftype,
                        "dil": "TR",
                        "calismaTipi": 2,
                        "donemGetiri1a": "1",
                        "donemGetiri3a": "1",
                        "donemGetiri6a": "1",
                        "donemGetiriyb": "1",
                        "donemGetiri1y": "1",
                        "donemGetiri3y": "1",
                        "donemGetiri5y": "1",
                    },
                    "fonGetiriBazliBilgiGetir",
                )
                self._cache_set(cache_key, all_returns, TTL.FX_RATES)

            for entry in all_returns:
                if entry.get("fonKodu") == fund_code:
                    return entry, ftype

        return {}, None

    def _resolve_periyod(
        self,
        period: str,
        start: datetime | None,
        end: datetime | None,
    ) -> int:
        """Pick the smallest periyod code that covers the requested window.

        When ``start`` is given we fetch the maximum 5y window and let the
        caller filter client-side. Without explicit dates we map ``period``
        through :data:`_PERIOD_TO_PERIYOD`, defaulting to ``1`` (1 month) for
        unrecognized values to match the legacy behavior.
        """
        if start is not None:
            now = datetime.now()
            span_days = (now - start).days
            # Pick the smallest enum bucket large enough to cover the span.
            for code, days in (
                (13, 7),
                (1, 31),
                (3, 95),
                (6, 190),
                (12, 380),
                (36, 365 * 3 + 5),
                (60, 365 * 5 + 5),
            ):
                if span_days <= days:
                    return code
            return self._PERIYOD_MAX
        if end is not None and start is None:
            # Only end given — fetch max and let caller filter
            return self._PERIYOD_MAX
        return self._PERIOD_TO_PERIYOD.get(period, 1)

    def get_history(
        self,
        fund_code: str,
        period: str = "1mo",
        start: datetime | None = None,
        end: datetime | None = None,
        fund_type: str = "YAT",
    ) -> pd.DataFrame:
        """Get historical NAV (unit price) for a fund.

        Uses ``fonFiyatBilgiGetir`` from the redesigned 2026-04 TEFAS API,
        which only accepts a fixed set of period codes (see
        :data:`_PERIOD_TO_PERIYOD`). Maximum window is **5 years**.

        Args:
            fund_code: TEFAS fund code.
            period: Convenience period — ``1d``/``5d``/``1mo``/``3mo``/``6mo``/
                ``ytd``/``1y``/``3y``/``5y``/``max``. Ignored if ``start`` is
                set.
            start: Start datetime; the smallest period bucket covering
                ``start..now`` is fetched, then results are filtered.
            end: End datetime for client-side filtering.
            fund_type: Accepted for backward compatibility; the new endpoint
                doesn't take ``fonTipi`` and works for both YAT and EMK funds.

        Returns:
            DataFrame indexed by Date with a ``Price`` column. The legacy
            ``FundSize`` and ``Investors`` columns are no longer provided by
            the new API and are populated as NaN/0 for backward compatibility.
        """
        fund_code = fund_code.upper()

        periyod = self._resolve_periyod(period, start, end)

        # Cache by periyod (not start/end) so multiple windows reuse the same
        # upstream fetch.
        cache_key = f"tefas:history:{fund_code}:periyod={periyod}"
        cached = self._cache_get(cache_key)

        if cached is None:
            try:
                rows = self._post_json_v2(
                    "fonFiyatBilgiGetir",
                    {"fonKodu": fund_code, "dil": "TR", "periyod": periyod},
                    "fonFiyatBilgiGetir",
                )
            except APIError as e:
                raise APIError(
                    f"Failed to fetch history for {fund_code}: {e}"
                ) from e

            if not rows:
                raise DataNotAvailableError(f"No history for fund: {fund_code}")

            records = []
            for row in rows:
                tarih = row.get("tarih")
                fiyat = row.get("fiyat")
                if not tarih or fiyat is None:
                    continue
                try:
                    dt = datetime.fromisoformat(str(tarih)[:10])
                except ValueError:
                    continue
                records.append(
                    {
                        "Date": dt,
                        "Price": float(fiyat),
                        # Lost in the v2 API — kept for backward compat.
                        "FundSize": float("nan"),
                        "Investors": 0,
                    }
                )

            df = pd.DataFrame(records)
            if not df.empty:
                df.set_index("Date", inplace=True)
                df.sort_index(inplace=True)

            self._cache_set(cache_key, df, TTL.OHLCV_HISTORY)
            cached = df

        df = cached.copy()

        # Client-side date filtering for explicit ranges.
        if start is not None and not df.empty:
            df = df[df.index >= pd.Timestamp(start)]
        if end is not None and not df.empty:
            df = df[df.index <= pd.Timestamp(end)]

        if df.empty:
            raise DataNotAvailableError(
                f"No history for fund {fund_code} in requested range"
            )

        return df

    # Regex used to pull allocation rows out of the SSR HTML payload.
    # Next.js renders escaped JSON inside a <script> tag, e.g.
    #   \"fonKodu\":\"AAK\",...\"kiymetTip\":\"Hisse Senedi\",\"portfoyOrani\":29.75
    @staticmethod
    def _build_allocation_pattern(fund_code: str) -> re.Pattern[str]:
        # Built dynamically rather than via str.format because the regex
        # contains literal ``{`` / ``}`` characters that would confuse
        # ``str.format``.
        code = re.escape(fund_code)
        pattern = (
            r'\\"fonKodu\\"\s*:\s*\\"' + code + r'\\"'
            r'[^}]*?\\"kiymetTip\\"\s*:\s*\\"([^\\"]+)\\"'
            r'[^}]*?\\"portfoyOrani\\"\s*:\s*([\d.]+)'
        )
        return re.compile(pattern, re.IGNORECASE)

    def get_allocation(
        self,
        fund_code: str,
        start: datetime | None = None,
        end: datetime | None = None,
        fund_type: str = "YAT",
    ) -> pd.DataFrame:
        """Get the current portfolio allocation (asset breakdown) for a fund.

        After the 2026-04 TEFAS migration, allocation data is no longer
        exposed through any JSON endpoint — it is rendered server-side into
        the ``/tr/fon-detayli-analiz/<code>`` HTML page, which is protected
        by an Akamai TSPD JS challenge that pure-HTTP clients cannot solve.

        This method uses Scrapling's :class:`StealthyFetcher`, which is
        built on patchright (a stealth Playwright/Chromium fork) that
        bypasses Akamai's bot detection, then extracts the inline
        ``varlikData`` JSON. Install with::

            pip install borsapy[allocation]
            playwright install chromium  # one-time browser binary download

        Only a snapshot for the current day is returned. The legacy date-range
        parameters (``start``, ``end``) are accepted for backward compatibility
        but ignored — historical allocation is no longer available.

        Args:
            fund_code: TEFAS fund code.
            start: Ignored (kept for backward compatibility).
            end: Ignored (kept for backward compatibility).
            fund_type: Ignored (kept for backward compatibility).

        Returns:
            DataFrame with columns ``Date``, ``asset_type``, ``asset_name``,
            ``weight`` (percent). One row per asset class.

        Raises:
            ImportError: If Playwright is not installed.
            DataNotAvailableError: If the page renders but contains no
                allocation rows for this fund.
            APIError: On network or rendering failures.
        """
        fund_code = fund_code.upper()
        # start/end/fund_type are intentionally ignored — see docstring.
        del start, end, fund_type

        cache_key = f"tefas:allocation:{fund_code}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        html = self._fetch_fund_page_html(fund_code)

        pattern = self._build_allocation_pattern(fund_code)
        matches = pattern.findall(html)

        if not matches:
            raise DataNotAvailableError(
                f"No allocation data found in TEFAS HTML for fund: {fund_code}"
            )

        today = datetime.now()
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for asset_type_tr, weight_str in matches:
            if asset_type_tr in seen:
                continue
            seen.add(asset_type_tr)
            try:
                weight = float(weight_str)
            except ValueError:
                continue
            if weight <= 0:
                continue
            records.append(
                {
                    "Date": today,
                    "asset_type": asset_type_tr,
                    "asset_name": ASSET_NAME_STANDARDIZATION.get(
                        asset_type_tr, asset_type_tr
                    ),
                    "weight": weight,
                }
            )

        if not records:
            raise DataNotAvailableError(
                f"No allocation data found in TEFAS HTML for fund: {fund_code}"
            )

        df = pd.DataFrame(records)
        df.sort_values("weight", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)

        self._cache_set(cache_key, df, TTL.FX_RATES)
        return df

    def _fetch_fund_page_html(self, fund_code: str) -> str:
        """Render the WAF-protected TEFAS fund page via Scrapling.

        Plain headless Chromium gets blocked by Akamai's bot detection
        (TSPD JS challenge), so we use Scrapling's :class:`StealthyFetcher`
        which is built on patchright (a stealth Playwright/Chromium fork)
        and routinely bypasses these protections.

        Separated from :meth:`get_allocation` so tests can stub it.
        """
        try:
            from scrapling.fetchers import StealthyFetcher
        except ImportError as e:
            raise ImportError(
                "Fund.allocation requires Scrapling since TEFAS migrated "
                "(2026-04) to an Akamai-protected SSR site. Install with: "
                "    pip install borsapy[allocation] && "
                "playwright install chromium"
            ) from e

        url = f"https://www.tefas.gov.tr/tr/fon-detayli-analiz/{fund_code}"

        try:
            page = StealthyFetcher.fetch(
                url,
                headless=True,
                network_idle=True,
                # Akamai TSPD challenges complete within ~5 s on a warm cache.
                timeout=45_000,
            )
        except Exception as e:
            raise APIError(
                f"Failed to render TEFAS allocation page for {fund_code}: {e}"
            ) from e

        if getattr(page, "status", 200) >= 400:
            raise APIError(
                f"TEFAS allocation page returned HTTP {page.status} "
                f"for {fund_code}"
            )

        # Scrapling's response object has .body (bytes) and .html_content (str)
        html = getattr(page, "html_content", None) or str(page)
        return html

    def screen_funds(
        self,
        fund_type: str = "YAT",
        founder: str | None = None,
        min_return_1m: float | None = None,
        min_return_3m: float | None = None,
        min_return_6m: float | None = None,
        min_return_ytd: float | None = None,
        min_return_1y: float | None = None,
        min_return_3y: float | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Screen funds based on fund type and return criteria.

        Args:
            fund_type: Fund type filter:
                - "YAT": Investment Funds (Yatırım Fonları) - default
                - "EMK": Pension Funds (Emeklilik Fonları)
            founder: Filter by fund management company code (e.g., "AKP", "GPY", "ISP")
            min_return_1m: Minimum 1-month return (%)
            min_return_3m: Minimum 3-month return (%)
            min_return_6m: Minimum 6-month return (%)
            min_return_ytd: Minimum year-to-date return (%)
            min_return_1y: Minimum 1-year return (%)
            min_return_3y: Minimum 3-year return (%)
            limit: Maximum number of results (default: 50)

        Returns:
            List of funds matching the criteria, sorted by 1-year return.

        Examples:
            >>> provider.screen_funds(fund_type="EMK")  # All pension funds
            >>> provider.screen_funds(min_return_1y=50)  # Funds with >50% 1Y return
            >>> provider.screen_funds(fund_type="EMK", min_return_ytd=20)
        """
        try:
            all_funds = self._post_json_v2(
                "fonGetiriBazliBilgiGetir",
                {
                    "fonTipi": fund_type,
                    "dil": "TR",
                    "calismaTipi": 2,
                    "donemGetiri1a": "1",
                    "donemGetiri3a": "1",
                    "donemGetiri6a": "1",
                    "donemGetiriyb": "1",
                    "donemGetiri1y": "1",
                    "donemGetiri3y": "1",
                    "donemGetiri5y": "1",
                },
                "fonGetiriBazliBilgiGetir",
            )

            # Apply return-based filters
            filtered = []
            for fund in all_funds:
                # Optionally filter by founder (client-side)
                if founder and fund.get("kurucuKod", "") != founder:
                    continue

                # Extract return values
                r1m = fund.get("getiri1a")
                r3m = fund.get("getiri3a")
                r6m = fund.get("getiri6a")
                rytd = fund.get("getiriyb")
                r1y = fund.get("getiri1y")
                r3y = fund.get("getiri3y")
                r5y = fund.get("getiri5y")

                # Apply filters
                if min_return_1m is not None and (r1m is None or r1m < min_return_1m):
                    continue
                if min_return_3m is not None and (r3m is None or r3m < min_return_3m):
                    continue
                if min_return_6m is not None and (r6m is None or r6m < min_return_6m):
                    continue
                if min_return_ytd is not None and (rytd is None or rytd < min_return_ytd):
                    continue
                if min_return_1y is not None and (r1y is None or r1y < min_return_1y):
                    continue
                if min_return_3y is not None and (r3y is None or r3y < min_return_3y):
                    continue

                filtered.append({
                    "fund_code": fund.get("fonKodu", ""),
                    "name": fund.get("fonUnvan", ""),
                    "fund_type": fund.get("fonTurAciklama", ""),
                    "return_1m": r1m,
                    "return_3m": r3m,
                    "return_6m": r6m,
                    "return_ytd": rytd,
                    "return_1y": r1y,
                    "return_3y": r3y,
                    "return_5y": r5y,
                })

            # Sort by 1-year return (descending), then YTD if 1Y not available
            def sort_key(x):
                r1y = x.get("return_1y")
                rytd = x.get("return_ytd")
                if r1y is not None:
                    return (1, r1y)
                if rytd is not None:
                    return (0, rytd)
                return (-1, 0)

            filtered.sort(key=sort_key, reverse=True)

            return filtered[:limit]

        except Exception as e:
            raise APIError(f"Failed to screen funds: {e}") from e

    def compare_funds(self, fund_codes: list[str]) -> dict[str, Any]:
        """
        Compare multiple funds side by side.

        Args:
            fund_codes: List of TEFAS fund codes to compare (max 10)

        Returns:
            Dictionary with:
            - funds: List of fund details with performance metrics
            - rankings: Ranking by different criteria
            - summary: Aggregate statistics

        Examples:
            >>> provider.compare_funds(["AAK", "TTE", "YAF"])
        """
        if not fund_codes:
            return {"funds": [], "rankings": {}, "summary": {}}

        # Limit to 10 funds
        fund_codes = [code.upper() for code in fund_codes[:10]]

        funds_data = []
        errors = []

        for code in fund_codes:
            try:
                detail = self.get_fund_detail(code)
                funds_data.append({
                    "fund_code": detail.get("fund_code"),
                    "name": detail.get("name"),
                    "fund_type": detail.get("fund_type"),
                    "category": detail.get("category"),
                    "founder": detail.get("founder"),
                    "price": detail.get("price"),
                    "fund_size": detail.get("fund_size"),
                    "investor_count": detail.get("investor_count"),
                    "risk_value": detail.get("risk_value"),
                    # Returns
                    "daily_return": detail.get("daily_return"),
                    "weekly_return": detail.get("weekly_return"),
                    "return_1m": detail.get("return_1m"),
                    "return_3m": detail.get("return_3m"),
                    "return_6m": detail.get("return_6m"),
                    "return_ytd": detail.get("return_ytd"),
                    "return_1y": detail.get("return_1y"),
                    "return_3y": detail.get("return_3y"),
                    "return_5y": detail.get("return_5y"),
                    # Allocation summary
                    "allocation": detail.get("allocation"),
                })
            except Exception as e:
                errors.append({"fund_code": code, "error": str(e)})

        if not funds_data:
            return {"funds": [], "rankings": {}, "summary": {}, "errors": errors}

        # Calculate rankings
        rankings = {}

        # Rank by 1-year return
        sorted_1y = sorted(
            [f for f in funds_data if f.get("return_1y") is not None],
            key=lambda x: x["return_1y"],
            reverse=True,
        )
        rankings["by_return_1y"] = [f["fund_code"] for f in sorted_1y]

        # Rank by YTD return
        sorted_ytd = sorted(
            [f for f in funds_data if f.get("return_ytd") is not None],
            key=lambda x: x["return_ytd"],
            reverse=True,
        )
        rankings["by_return_ytd"] = [f["fund_code"] for f in sorted_ytd]

        # Rank by fund size
        sorted_size = sorted(
            [f for f in funds_data if f.get("fund_size") is not None],
            key=lambda x: x["fund_size"],
            reverse=True,
        )
        rankings["by_size"] = [f["fund_code"] for f in sorted_size]

        # Rank by risk (ascending - lower is better)
        sorted_risk = sorted(
            [f for f in funds_data if f.get("risk_value") is not None],
            key=lambda x: x["risk_value"],
        )
        rankings["by_risk_asc"] = [f["fund_code"] for f in sorted_risk]

        # Summary statistics
        returns_1y = [f["return_1y"] for f in funds_data if f.get("return_1y") is not None]
        returns_ytd = [f["return_ytd"] for f in funds_data if f.get("return_ytd") is not None]
        sizes = [f["fund_size"] for f in funds_data if f.get("fund_size") is not None]

        summary = {
            "fund_count": len(funds_data),
            "total_size": sum(sizes) if sizes else 0,
            "avg_return_1y": sum(returns_1y) / len(returns_1y) if returns_1y else None,
            "avg_return_ytd": sum(returns_ytd) / len(returns_ytd) if returns_ytd else None,
            "best_return_1y": max(returns_1y) if returns_1y else None,
            "worst_return_1y": min(returns_1y) if returns_1y else None,
        }

        result = {
            "funds": funds_data,
            "rankings": rankings,
            "summary": summary,
        }

        if errors:
            result["errors"] = errors

        return result

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Search for funds by name or code.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching funds.
        """
        try:
            results = self._post_json_v2(
                "fonUnvanAra",
                {"aranan": query},
                "fonUnvanAra",
            )

            matching = []
            for fund in results:
                matching.append(
                    {
                        "fund_code": fund.get("fonKodu", ""),
                        "name": fund.get("fonUnvan", ""),
                        "fund_type": "",  # Not available from fonUnvanAra
                        "return_1y": None,  # Not available from fonUnvanAra
                    }
                )

                if len(matching) >= limit:
                    break

            return matching

        except Exception as e:
            raise APIError(f"Failed to search funds: {e}") from e

    def get_management_fees(
        self,
        fund_type: str = "YAT",
        founder: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get management fee data for funds.

        Args:
            fund_type: Fund type - "YAT" for investment funds, "EMK" for pension funds.
            founder: Filter by founder company code (e.g., "AKP", "GPY").

        Returns:
            List of dicts with keys: fund_code, name, fund_category, founder_code,
            applied_fee, prospectus_fee, max_expense_ratio, annual_return.
        """
        try:
            all_funds = self._post_json_v2(
                "fonYonetimBazliBilgiGetir",
                {"fonTipi": fund_type, "dil": "TR"},
                "fonYonetimBazliBilgiGetir",
            )

            funds = []
            for fund in all_funds:
                # Filter by founder if specified
                if founder and fund.get("kurucuKod", "") != founder:
                    continue

                funds.append({
                    "fund_code": fund.get("fonKodu", ""),
                    "name": fund.get("fonUnvan", ""),
                    "fund_category": fund.get("fonTurAciklama", ""),
                    "founder_code": fund.get("kurucuKod", ""),
                    "applied_fee": self._parse_turkish_decimal(fund.get("uygulananYu1Y")),
                    "prospectus_fee": self._parse_turkish_decimal(fund.get("fonIcTuzukYu1G")),
                    "max_expense_ratio": self._parse_turkish_decimal(fund.get("fonTopGiderKesoran")),
                    "annual_return": fund.get("yillikGetiri"),
                })

            return funds

        except Exception as e:
            raise APIError(f"Failed to fetch management fees: {e}") from e


# Singleton
_provider: TEFASProvider | None = None


def get_tefas_provider() -> TEFASProvider:
    """Get singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = TEFASProvider()
    return _provider
