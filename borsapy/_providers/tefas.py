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
                # Daily change
                "daily_return": fund_info.get("GUNLUKGETIRI"),
            }

            self._cache_set(cache_key, detail, TTL.FX_RATES)
            return detail

        except Exception as e:
            raise APIError(f"Failed to fetch fund detail for {fund_code}: {e}") from e

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
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y)
            start: Start date
            end: End date

        Returns:
            DataFrame with price history.
        """
        fund_code = fund_code.upper()

        # Calculate date range
        end_dt = end or datetime.now()
        if start:
            start_dt = start
        else:
            days = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}.get(period, 30)
            start_dt = end_dt - timedelta(days=days)

        cache_key = f"tefas:history:{fund_code}:{start_dt.date()}:{end_dt.date()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

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

            self._cache_set(cache_key, df, TTL.OHLCV_HISTORY)
            return df

        except Exception as e:
            raise APIError(f"Failed to fetch history for {fund_code}: {e}") from e

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
