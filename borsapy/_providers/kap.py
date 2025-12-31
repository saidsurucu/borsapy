"""KAP provider for company list data."""

import io
import re
import time

import pandas as pd

from borsapy._providers.base import BaseProvider
from borsapy.exceptions import APIError


class KAPProvider(BaseProvider):
    """
    Provider for company data from KAP (Public Disclosure Platform).

    Provides:
    - List of all BIST companies with ticker codes
    - Company search functionality
    """

    EXCEL_URL = "https://www.kap.org.tr/tr/api/company/generic/excel/IGS/A"
    CACHE_DURATION = 86400  # 24 hours

    def __init__(self):
        super().__init__()
        self._company_cache: pd.DataFrame | None = None
        self._cache_time: float = 0

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


# Singleton
_provider: KAPProvider | None = None


def get_kap_provider() -> KAPProvider:
    """Get singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = KAPProvider()
    return _provider
