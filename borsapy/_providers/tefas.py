"""TEFAS provider for mutual fund data."""

from datetime import datetime, timedelta
from typing import Any

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

# Standardized asset names (for GetAllFundAnalyzeData API which returns full Turkish names)
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

    BASE_URL = "https://www.tefas.gov.tr/api/DB"

    def __init__(self):
        super().__init__()
        # Disable SSL verification for TEFAS
        self._client.verify = False

    def get_fund_detail(self, fund_code: str) -> dict[str, Any]:
        """
        Get detailed information about a fund.

        Args:
            fund_code: TEFAS fund code (e.g., "AAK", "TTE")

        Returns:
            Dictionary with fund details.
        """
        fund_code = fund_code.upper()

        cache_key = f"tefas:detail:{fund_code}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            url = f"{self.BASE_URL}/GetAllFundAnalyzeData"
            data = {"dil": "TR", "fonkod": fund_code}

            headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
                "Accept": "application/json, text/plain, */*",
            }

            response = self._client.post(url, data=data, headers=headers)
            response.raise_for_status()
            result = response.json()

            if not result or not result.get("fundInfo"):
                raise DataNotAvailableError(f"No data for fund: {fund_code}")

            fund_info = result["fundInfo"][0]
            fund_return = result.get("fundReturn", [{}])[0] if result.get("fundReturn") else {}
            fund_profile = result.get("fundProfile", [{}])[0] if result.get("fundProfile") else {}
            fund_allocation = result.get("fundAllocation", [])

            # Parse allocation data
            allocation = None
            if fund_allocation:
                allocation = []
                for item in fund_allocation:
                    weight = float(item.get("PORTFOYORANI", 0) or 0)
                    if weight > 0:
                        asset_type_tr = item.get("KIYMETTIP", "")
                        allocation.append({
                            "asset_type": asset_type_tr,
                            "asset_name": ASSET_NAME_STANDARDIZATION.get(asset_type_tr, asset_type_tr),
                            "weight": weight,
                        })
                # Sort by weight descending
                allocation.sort(key=lambda x: x["weight"], reverse=True)

            detail = {
                "fund_code": fund_code,
                "name": fund_info.get("FONUNVAN", ""),
                "date": fund_info.get("TARIH", ""),
                "price": float(fund_info.get("SONFIYAT", 0) or 0),
                "fund_size": float(fund_info.get("PORTBUYUKLUK", 0) or 0),
                "investor_count": int(fund_info.get("YATIRIMCISAYI", 0) or 0),
                "founder": fund_info.get("KURUCU", ""),
                "manager": fund_info.get("YONETICI", ""),
                "fund_type": fund_info.get("FONTUR", ""),
                "category": fund_info.get("FONKATEGORI", ""),
                "risk_value": int(fund_info.get("RISKDEGERI", 0) or 0),
                # Performance metrics
                "return_1m": fund_return.get("GETIRI1A"),
                "return_3m": fund_return.get("GETIRI3A"),
                "return_6m": fund_return.get("GETIRI6A"),
                "return_ytd": fund_return.get("GETIRIYB"),
                "return_1y": fund_return.get("GETIRI1Y"),
                "return_3y": fund_return.get("GETIRI3Y"),
                "return_5y": fund_return.get("GETIRI5Y"),
                # Daily/weekly change
                "daily_return": fund_info.get("GUNLUKGETIRI"),
                "weekly_return": fund_info.get("HAFTALIKGETIRI"),
                # Category ranking
                "category_rank": fund_info.get("KATEGORIDERECE"),
                "category_fund_count": fund_info.get("KATEGORIFONSAY"),
                "market_share": fund_info.get("PAZARPAYI"),
                # Fund profile (from fundProfile)
                "isin": fund_profile.get("ISINKOD"),
                "last_trading_time": fund_profile.get("SONISSAAT"),
                "min_purchase": fund_profile.get("MINALIS"),
                "min_redemption": fund_profile.get("MINSATIS"),
                "entry_fee": fund_profile.get("GIRISKOMISYONU"),
                "exit_fee": fund_profile.get("CIKISKOMISYONU"),
                "kap_link": fund_profile.get("KAPLINK"),
                # Portfolio allocation (from fundAllocation)
                "allocation": allocation,
            }

            self._cache_set(cache_key, detail, TTL.FX_RATES)
            return detail

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
    ) -> pd.DataFrame:
        """
        Get historical price data for a fund.

        Args:
            fund_code: TEFAS fund code
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 3y, 5y, max)
            start: Start date
            end: End date

        Returns:
            DataFrame with price history.

        Note:
            For periods longer than 90 days, data is fetched in chunks
            to avoid TEFAS WAF blocking.
        """
        fund_code = fund_code.upper()

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

        cache_key = f"tefas:history:{fund_code}:{start_dt.date()}:{end_dt.date()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # Check if we need chunked requests
        total_days = (end_dt - start_dt).days
        if total_days > self.MAX_CHUNK_DAYS:
            df = self._get_history_chunked(fund_code, start_dt, end_dt)
        else:
            df = self._fetch_history_chunk(fund_code, start_dt, end_dt)

        self._cache_set(cache_key, df, TTL.OHLCV_HISTORY)
        return df

    def _get_history_chunked(
        self,
        fund_code: str,
        start_dt: datetime,
        end_dt: datetime,
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

                chunk_df = self._fetch_history_chunk(fund_code, chunk_start, chunk_end)
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
    ) -> pd.DataFrame:
        """Fetch a single chunk of history data (max ~90 days)."""
        try:
            url = f"{self.BASE_URL}/BindHistoryInfo"

            data = {
                "fontip": "YAT",
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

            response = self._client.post(url, data=data, headers=headers)
            response.raise_for_status()

            # Check if response is JSON (not HTML error page)
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type:
                raise APIError("TEFAS WAF blocked the request")

            result = response.json()

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

        except Exception as e:
            if "WAF" in str(e):
                raise
            raise APIError(f"Failed to fetch history for {fund_code}: {e}") from e

    def get_allocation(
        self,
        fund_code: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Get portfolio allocation (asset breakdown) for a fund.

        Args:
            fund_code: TEFAS fund code
            start: Start date (default: 7 days ago)
            end: End date (default: today)

        Returns:
            DataFrame with columns: Date, asset_type, asset_name, weight
        """
        fund_code = fund_code.upper()

        # Default date range (1 week)
        end_dt = end or datetime.now()
        start_dt = start or (end_dt - timedelta(days=7))

        cache_key = f"tefas:allocation:{fund_code}:{start_dt.date()}:{end_dt.date()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            url = f"{self.BASE_URL}/BindHistoryAllocation"

            data = {
                "fontip": "YAT",
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

            response = self._client.post(url, data=data, headers=headers)
            response.raise_for_status()
            result = response.json()

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
            url = f"{self.BASE_URL}/BindComparisonFundReturns"

            # Use calismatipi=2 for period-based returns (1A, 3A, 6A, YB, 1Y, 3Y, 5Y)
            data = {
                "calismatipi": "2",  # Period-based returns
                "fontip": fund_type,
                "sfontur": "Tümü",
                "kurucukod": founder or "",
                "fongrup": "",
                "bastarih": "Başlangıç",  # Start (placeholder for period-based)
                "bittarih": "Bitiş",  # End (placeholder for period-based)
                "fonturkod": "",
                "fonunvantip": "",
                "strperiod": "1,1,1,1,1,1,1",  # All periods: 1A, 3A, 6A, YB, 1Y, 3Y, 5Y
                "islemdurum": "1",  # Active funds only
            }

            headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "https://www.tefas.gov.tr",
                "Referer": "https://www.tefas.gov.tr/FonKarsilastirma.aspx",
                "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
                "X-Requested-With": "XMLHttpRequest",
            }

            response = self._client.post(url, data=data, headers=headers)
            response.raise_for_status()
            result = response.json()

            all_funds = result.get("data", []) if isinstance(result, dict) else result

            # Apply return-based filters
            filtered = []
            for fund in all_funds:
                # Extract return values
                r1m = fund.get("GETIRI1A")
                r3m = fund.get("GETIRI3A")
                r6m = fund.get("GETIRI6A")
                rytd = fund.get("GETIRIYB")
                r1y = fund.get("GETIRI1Y")
                r3y = fund.get("GETIRI3Y")
                r5y = fund.get("GETIRI5Y")

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
                    "fund_code": fund.get("FONKODU", ""),
                    "name": fund.get("FONUNVAN", ""),
                    "fund_type": fund.get("FONTURACIKLAMA", ""),
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
            url = f"{self.BASE_URL}/BindComparisonFundReturns"

            data = {
                "calismatipi": "2",
                "fontip": "YAT",
                "sfontur": "Tümü",
                "kurucukod": "",
                "fongrup": "",
                "bastarih": "Başlangıç",
                "bittarih": "Bitiş",
                "fonturkod": "",
                "fonunvantip": "",
                "strperiod": "1,1,1,1,1,1,1",
                "islemdurum": "1",
            }

            headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "https://www.tefas.gov.tr",
                "Referer": "https://www.tefas.gov.tr/FonKarsilastirma.aspx",
                "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
                "X-Requested-With": "XMLHttpRequest",
            }

            response = self._client.post(url, data=data, headers=headers)
            response.raise_for_status()
            result = response.json()

            all_funds = result.get("data", []) if isinstance(result, dict) else result

            # Normalize query for matching
            query_lower = query.lower()

            matching = []
            for fund in all_funds:
                code = fund.get("FONKODU", "").lower()
                name = fund.get("FONUNVAN", "").lower()

                if query_lower in code or query_lower in name:
                    matching.append(
                        {
                            "fund_code": fund.get("FONKODU", ""),
                            "name": fund.get("FONUNVAN", ""),
                            "fund_type": fund.get("FONTURACIKLAMA", ""),
                            "return_1y": fund.get("GETIRI1Y"),
                        }
                    )

                if len(matching) >= limit:
                    break

            return matching

        except Exception as e:
            raise APIError(f"Failed to search funds: {e}") from e


# Singleton
_provider: TEFASProvider | None = None


def get_tefas_provider() -> TEFASProvider:
    """Get singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = TEFASProvider()
    return _provider
