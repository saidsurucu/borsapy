"""TEFAS provider for mutual fund data."""

import json
import time
from datetime import datetime, timedelta
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
    BASE_URL_LEGACY = "https://www.tefas.gov.tr/api/DB"

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
            fund_return: dict[str, Any] = {}
            try:
                returns_cache_key = f"tefas:all_returns:{fund_type}"
                all_returns = self._cache_get(returns_cache_key)
                if all_returns is None:
                    all_returns = self._post_json_v2(
                        "fonGetiriBazliBilgiGetir",
                        {
                            "fonKodu": fund_code,
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
                    self._cache_set(returns_cache_key, all_returns, TTL.FX_RATES)

                for entry in all_returns:
                    if entry.get("fonKodu") == fund_code:
                        fund_return = entry
                        break
            except APIError:
                pass  # Returns data is supplementary; don't fail the whole call

            detail = {
                "fund_code": fund_code,
                "name": fund_info.get("fonUnvan", ""),
                "date": "",  # Not available in fonBilgiGetir
                "price": float(fund_info.get("sonFiyat", 0) or 0),
                "fund_size": float(fund_info.get("portBuyukluk", 0) or 0),
                "investor_count": int(fund_info.get("yatirimciSayi", 0) or 0),
                "founder": "",  # Not available in fonBilgiGetir
                "manager": "",  # Not available in fonBilgiGetir
                "fund_type": fund_return.get("fonTurAciklama", ""),
                "category": fund_info.get("fonKategori", ""),
                "risk_value": int(fund_return.get("riskDegeri", 0) or 0),
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
                "weekly_return": None,  # Not available in new API
                # Category ranking
                "category_rank": fund_info.get("kategoriDerece"),
                "category_fund_count": fund_info.get("kategoriFonSay"),
                "market_share": fund_info.get("pazarPayi"),
                # Fund profile — fonProfilDtyGetir currently returns empty
                "isin": None,
                "last_trading_time": None,
                "min_purchase": None,
                "min_redemption": None,
                "entry_fee": None,
                "exit_fee": None,
                "kap_link": None,
                # Portfolio allocation — not available from fonBilgiGetir
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

    # WAF limit for TEFAS API - requests longer than ~90 days get blocked
    MAX_CHUNK_DAYS = 90

    def get_history(
        self,
        fund_code: str,
        period: str = "1mo",
        start: datetime | None = None,
        end: datetime | None = None,
        fund_type: str = "YAT",
    ) -> pd.DataFrame:
        """
        Get historical price data for a fund.

        Args:
            fund_code: TEFAS fund code
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 3y, 5y, max)
            start: Start date
            end: End date
            fund_type: Fund type - "YAT" for investment funds, "EMK" for pension funds.

        Returns:
            DataFrame with price history.

        Note:
            For periods longer than 90 days, data is fetched in chunks
            to avoid TEFAS WAF blocking.
        """
        fund_code = fund_code.upper()
        fund_type = fund_type.upper()

        # Calculate date range
        end_dt = end or datetime.now()
        if start:
            start_dt = start
        else:
            days = {
                "1d": 1,
                "5d": 5,
                "1mo": 30,
                "3mo": 90,
                "6mo": 180,
                "1y": 365,
                "3y": 365 * 3,
                "5y": 365 * 5,
                "max": 365 * 5,  # Limited to 5y due to WAF constraints
            }.get(period, 30)
            start_dt = end_dt - timedelta(days=days)

        cache_key = f"tefas:history:{fund_code}:{fund_type}:{start_dt.date()}:{end_dt.date()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # Check if we need chunked requests
        total_days = (end_dt - start_dt).days
        if total_days > self.MAX_CHUNK_DAYS:
            df = self._get_history_chunked(fund_code, start_dt, end_dt, fund_type)
        else:
            df = self._fetch_history_chunk(fund_code, start_dt, end_dt, fund_type)

        self._cache_set(cache_key, df, TTL.OHLCV_HISTORY)
        return df

    def _get_history_chunked(
        self,
        fund_code: str,
        start_dt: datetime,
        end_dt: datetime,
        fund_type: str = "YAT",
    ) -> pd.DataFrame:
        """
        Fetch history in chunks to avoid WAF blocking.

        TEFAS WAF blocks requests longer than ~90-100 days.
        This method fetches data in chunks and combines them.
        """
        import time

        all_records = []
        chunk_start = start_dt
        chunk_count = 0

        while chunk_start < end_dt:
            chunk_end = min(chunk_start + timedelta(days=self.MAX_CHUNK_DAYS), end_dt)

            try:
                # Add delay between requests to avoid rate limiting
                if chunk_count > 0:
                    time.sleep(0.3)

                chunk_df = self._fetch_history_chunk(fund_code, chunk_start, chunk_end, fund_type)
                if not chunk_df.empty:
                    all_records.append(chunk_df)
                chunk_count += 1
            except DataNotAvailableError:
                # No data for this chunk, continue to next
                pass
            except APIError:
                # WAF blocked - stop fetching older data
                # Return what we have so far
                break

            # Move to next chunk
            chunk_start = chunk_end + timedelta(days=1)

        if not all_records:
            raise DataNotAvailableError(f"No history for fund: {fund_code}")

        # Combine all chunks
        df = pd.concat(all_records)
        df = df[~df.index.duplicated(keep="last")]  # Remove duplicate dates
        df.sort_index(inplace=True)
        return df

    def _fetch_history_chunk(
        self,
        fund_code: str,
        start_dt: datetime,
        end_dt: datetime,
        fund_type: str = "YAT",
    ) -> pd.DataFrame:
        """Fetch a single chunk of history data (max ~90 days)."""
        try:
            url = f"{self.BASE_URL_LEGACY}/BindHistoryInfo"

            data = {
                "fontip": fund_type,
                "sfontur": "",
                "fonkod": fund_code,
                "fongrup": "",
                "bastarih": start_dt.strftime("%d.%m.%Y"),
                "bittarih": end_dt.strftime("%d.%m.%Y"),
                "fonturkod": "",
                "fonunvantip": "",
                "kurucukod": "",
            }

            headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "https://www.tefas.gov.tr",
                "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx",
                "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
                "X-Requested-With": "XMLHttpRequest",
            }

            result = self._post_json(url, data, "BindHistoryInfo", headers=headers)

            if not result.get("data"):
                raise DataNotAvailableError(f"No history for fund: {fund_code}")

            records = []
            for item in result["data"]:
                timestamp = int(item.get("TARIH", 0))
                if timestamp > 0:
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    records.append(
                        {
                            "Date": dt,
                            "Price": float(item.get("FIYAT", 0)),
                            "FundSize": float(item.get("PORTFOYBUYUKLUK", 0)),
                            "Investors": int(item.get("KISISAYISI", 0)),
                        }
                    )

            df = pd.DataFrame(records)
            if not df.empty:
                df.set_index("Date", inplace=True)
                df.sort_index(inplace=True)

            return df

        except DataNotAvailableError:
            # Re-raise DataNotAvailableError so chunked fetch can handle it
            raise
        except APIError:
            # Re-raise APIError (including WAF errors)
            raise
        except Exception as e:
            raise APIError(f"Failed to fetch history for {fund_code}: {e}") from e

    def get_allocation(
        self,
        fund_code: str,
        start: datetime | None = None,
        end: datetime | None = None,
        fund_type: str = "YAT",
    ) -> pd.DataFrame:
        """
        Get portfolio allocation (asset breakdown) for a fund.

        Args:
            fund_code: TEFAS fund code
            start: Start date (default: 7 days ago)
            end: End date (default: today)
            fund_type: Fund type - "YAT" for investment funds, "EMK" for pension funds.

        Returns:
            DataFrame with columns: Date, asset_type, asset_name, weight
        """
        fund_code = fund_code.upper()
        fund_type = fund_type.upper()

        # Default date range (1 week)
        end_dt = end or datetime.now()
        start_dt = start or (end_dt - timedelta(days=7))

        cache_key = f"tefas:allocation:{fund_code}:{fund_type}:{start_dt.date()}:{end_dt.date()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            url = f"{self.BASE_URL_LEGACY}/BindHistoryAllocation"

            data = {
                "fontip": fund_type,
                "sfontur": "",
                "fonkod": fund_code,
                "fongrup": "",
                "bastarih": start_dt.strftime("%d.%m.%Y"),
                "bittarih": end_dt.strftime("%d.%m.%Y"),
                "fonturkod": "",
                "fonunvantip": "",
                "kurucukod": "",
            }

            headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "https://www.tefas.gov.tr",
                "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx",
                "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
                "X-Requested-With": "XMLHttpRequest",
            }

            result = self._post_json(url, data, "BindHistoryAllocation", headers=headers)

            if not result.get("data"):
                raise DataNotAvailableError(f"No allocation data for fund: {fund_code}")

            records = []
            for item in result["data"]:
                timestamp = int(item.get("TARIH", 0))
                if timestamp > 0:
                    dt = datetime.fromtimestamp(timestamp / 1000)

                    # Extract allocation percentages for each asset type
                    for key, value in item.items():
                        if key not in ["TARIH", "FONKODU", "FONUNVAN", "BilFiyat"] and value is not None:
                            asset_name = ASSET_TYPE_MAPPING.get(key, key)
                            weight = float(value)
                            if weight > 0:  # Only include non-zero allocations
                                records.append({
                                    "Date": dt,
                                    "asset_type": key,
                                    "asset_name": asset_name,
                                    "weight": weight,
                                })

            if not records:
                raise DataNotAvailableError(f"No allocation data for fund: {fund_code}")

            df = pd.DataFrame(records)
            df.sort_values(["Date", "weight"], ascending=[False, False], inplace=True)

            self._cache_set(cache_key, df, TTL.FX_RATES)
            return df

        except Exception as e:
            raise APIError(f"Failed to fetch allocation for {fund_code}: {e}") from e

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
