"""KAP (Kamuyu Aydınlatma Platformu) provider for disclosures and calendar."""

import io
import re
import time
from datetime import datetime, timedelta

import pandas as pd

from borsapy._providers.base import BaseProvider
from borsapy.exceptions import APIError


class KAPProvider(BaseProvider):
    """
    Provider for KAP (Kamuyu Aydınlatma Platformu) data.

    KAP is the official disclosure platform for publicly traded
    companies in Turkey, similar to SEC EDGAR in the US.

    Provides:
    - List of all BIST companies with ticker codes
    - Company search functionality
    - Company disclosures (bildirimler)
    - Expected disclosure calendar (beklenen bildirimler)
    """

    EXCEL_URL = "https://www.kap.org.tr/tr/api/company/generic/excel/IGS/A"
    BIST_COMPANIES_URL = "https://www.kap.org.tr/tr/bist-sirketler"
    DISCLOSURE_URL = "https://www.kap.org.tr/tr/bildirim-sorgu-sonuc"
    CALENDAR_API_URL = "https://kap.org.tr/tr/api/expected-disclosure-inquiry/company"
    CACHE_DURATION = 86400  # 24 hours

    def __init__(self):
        super().__init__()
        self._company_cache: pd.DataFrame | None = None
        self._cache_time: float = 0
        self._oid_map: dict[str, str] | None = None
        self._oid_cache_time: float = 0

    def get_companies(self) -> pd.DataFrame:
        """
        Get list of all BIST companies.

        Returns:
            DataFrame with columns: ticker, name, city
        """
        current_time = time.time()

        # Check cache
        if (
            self._company_cache is not None
            and (current_time - self._cache_time) < self.CACHE_DURATION
        ):
            return self._company_cache

        try:
            headers = {
                "Accept": "*/*",
                "Accept-Language": "tr",
                "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
                "Referer": "https://www.kap.org.tr/tr/bist-sirketler",
            }

            response = self._client.get(self.EXCEL_URL, headers=headers)
            response.raise_for_status()

            # Read Excel data
            df = pd.read_excel(io.BytesIO(response.content))

            companies = []
            for _, row in df.iterrows():
                if len(row) >= 3:
                    ticker_field = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                    name = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                    city = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""

                    # Skip header or empty rows
                    if ticker_field and name and ticker_field not in ("BIST KODU", "Kod"):
                        # Handle multiple tickers (e.g., "GARAN, TGB")
                        if "," in ticker_field:
                            tickers = [t.strip() for t in ticker_field.split(",")]
                            for ticker in tickers:
                                if ticker:
                                    companies.append(
                                        {
                                            "ticker": ticker,
                                            "name": name,
                                            "city": city,
                                        }
                                    )
                        else:
                            companies.append(
                                {
                                    "ticker": ticker_field,
                                    "name": name,
                                    "city": city,
                                }
                            )

            result = pd.DataFrame(companies)
            self._company_cache = result
            self._cache_time = current_time
            return result

        except Exception as e:
            raise APIError(f"Failed to fetch company list: {e}") from e

    def search(self, query: str) -> pd.DataFrame:
        """
        Search companies by name or ticker.

        Args:
            query: Search query (ticker code or company name)

        Returns:
            DataFrame with matching companies
        """
        if not query:
            return pd.DataFrame(columns=["ticker", "name", "city"])

        companies = self.get_companies()
        if companies.empty:
            return companies

        query_normalized = self._normalize_text(query)
        query_upper = query.upper()

        # Score and filter results
        results = []
        for _, row in companies.iterrows():
            score = 0
            ticker = row["ticker"]
            name = row["name"]

            # Exact ticker match
            if ticker.upper() == query_upper:
                score = 1000
            # Ticker starts with query
            elif ticker.upper().startswith(query_upper):
                score = 500
            # Name contains query
            elif query_normalized in self._normalize_text(name):
                score = 100

            if score > 0:
                results.append((score, row))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)

        if not results:
            return pd.DataFrame(columns=["ticker", "name", "city"])

        return pd.DataFrame([r[1] for r in results])

    def _normalize_text(self, text: str) -> str:
        """Normalize Turkish text for comparison."""
        tr_map = str.maketrans("İıÖöÜüŞşÇçĞğ", "iioouussccgg")
        normalized = text.translate(tr_map).lower()
        # Remove common suffixes
        normalized = re.sub(r"[\.,']|\s+a\.s\.?|\s+anonim sirketi", "", normalized)
        return normalized.strip()

    def get_member_oid(self, symbol: str) -> str | None:
        """
        Get KAP member OID (mkkMemberOid) for a stock symbol.

        The member OID is required to query disclosures from KAP.

        Args:
            symbol: Stock symbol (e.g., "THYAO").

        Returns:
            Member OID string or None if not found.
        """
        symbol = symbol.upper().replace(".IS", "").replace(".E", "")
        current_time = time.time()

        # Check cache
        if (
            self._oid_map is not None
            and (current_time - self._oid_cache_time) < self.CACHE_DURATION
        ):
            return self._oid_map.get(symbol)

        # Fetch BIST companies list from KAP
        try:
            response = self._client.get(self.BIST_COMPANIES_URL, timeout=20)
            response.raise_for_status()

            # Parse mkkMemberOid and stockCode pairs from Next.js data
            # Format: \"mkkMemberOid\":\"xxx\",\"kapMemberTitle\":\"...\",
            #         \"relatedMemberTitle\":\"...\",\"stockCode\":\"THYAO\",...
            # Note: stockCode may contain multiple codes like "GARAN, TGB"
            pattern = (
                r'\\"mkkMemberOid\\":\\"([^\\"]+)\\",'
                r'\\"kapMemberTitle\\":\\"[^\\"]+\\",'
                r'\\"relatedMemberTitle\\":\\"[^\\"]*\\",'
                r'\\"stockCode\\":\\"([^\\"]+)\\"'
            )
            matches = re.findall(pattern, response.text)

            # Build mapping: stockCode -> mkkMemberOid
            # Handle multiple codes per company (e.g., "GARAN, TGB")
            self._oid_map = {}
            for oid, codes_str in matches:
                for code in codes_str.split(","):
                    code = code.strip()
                    if code:
                        self._oid_map[code] = oid

            self._oid_cache_time = current_time
            return self._oid_map.get(symbol)

        except Exception:
            return None

    def get_disclosures(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        """
        Get KAP disclosures (bildirimler) for a stock.

        Args:
            symbol: Stock symbol (e.g., "THYAO").
            limit: Maximum number of disclosures to return (default: 20).

        Returns:
            DataFrame with columns: Date, Title, URL.
        """
        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        # Get KAP member OID for the symbol
        member_oid = self.get_member_oid(symbol)
        if not member_oid:
            return pd.DataFrame(columns=["Date", "Title", "URL"])

        # Fetch disclosures from KAP
        disc_url = f"{self.DISCLOSURE_URL}?member={member_oid}"

        try:
            response = self._client.get(disc_url, timeout=15)
            response.raise_for_status()

            # Parse disclosures from Next.js embedded data
            # Format: publishDate\\":\\"29.12.2025 19:21:18\\",\\"disclosureIndex\\":1530826...
            pattern = (
                r'publishDate\\":\\"([^\\"]+)\\".*?'
                r'disclosureIndex\\":(\d+).*?'
                r'title\\":\\"([^\\"]+)\\"'
            )
            matches = re.findall(pattern, response.text, re.DOTALL)

            records = []
            for date, idx, title in matches[:limit]:
                url = f"https://www.kap.org.tr/tr/Bildirim/{idx}"
                records.append({
                    "Date": date,
                    "Title": title,
                    "URL": url,
                })

            return pd.DataFrame(records)

        except Exception as e:
            raise APIError(f"Failed to fetch disclosures for {symbol}: {e}") from e

    def get_calendar(self, symbol: str) -> pd.DataFrame:
        """
        Get expected disclosure calendar for a stock from KAP.

        Returns upcoming expected disclosures like financial reports,
        annual reports, sustainability reports, and corporate governance reports.

        Args:
            symbol: Stock symbol (e.g., "THYAO").

        Returns:
            DataFrame with columns:
            - StartDate: Expected disclosure window start
            - EndDate: Expected disclosure window end
            - Subject: Type of disclosure (e.g., "Finansal Rapor")
            - Period: Report period (e.g., "Yıllık", "3 Aylık")
            - Year: Fiscal year
        """
        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        # Get KAP member OID for the symbol
        member_oid = self.get_member_oid(symbol)
        if not member_oid:
            return pd.DataFrame(columns=["StartDate", "EndDate", "Subject", "Period", "Year"])

        # Calculate date range: today to 6 months from now
        now = datetime.now()
        start_date = now.strftime("%Y-%m-%d")
        end_date = (now + timedelta(days=180)).strftime("%Y-%m-%d")

        # Fetch expected disclosures from KAP API
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://kap.org.tr",
            "Referer": "https://kap.org.tr/tr/beklenen-bildirim-sorgu",
        }
        payload = {
            "startDate": start_date,
            "endDate": end_date,
            "memberTypes": ["IGS"],
            "mkkMemberOidList": [member_oid],
            "disclosureClass": "",
            "subjects": [],
            "mainSector": "",
            "sector": "",
            "subSector": "",
            "market": "",
            "index": "",
            "year": "",
            "term": "",
            "ruleType": "",
        }

        try:
            response = self._client.post(
                self.CALENDAR_API_URL,
                json=payload,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            records = []
            for item in data:
                records.append({
                    "StartDate": item.get("startDate", ""),
                    "EndDate": item.get("endDate", ""),
                    "Subject": item.get("subject", ""),
                    "Period": item.get("ruleTypeTerm", ""),
                    "Year": item.get("year", ""),
                })

            return pd.DataFrame(records)

        except Exception as e:
            raise APIError(f"Failed to fetch calendar for {symbol}: {e}") from e


# Singleton
_provider: KAPProvider | None = None


def get_kap_provider() -> KAPProvider:
    """Get singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = KAPProvider()
    return _provider
