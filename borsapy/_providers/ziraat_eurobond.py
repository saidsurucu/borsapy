"""Ziraat Bank Eurobond API provider.

Fetches Turkish sovereign Eurobond data from Ziraat Bank's API.
Includes USD and EUR denominated bonds with bid/ask prices and yields.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as date_type
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL

# Ziraat Bank Eurobond API endpoint
ZIRAAT_URL = "https://www.ziraatbank.com.tr/tr/_layouts/15/Ziraat/FaizOranlari/Ajax.aspx/GetZBBonoTahvilOran"


class ZiraatEurobondProvider(BaseProvider):
    """Provider for Eurobond data from Ziraat Bank."""

    def _parse_turkish_number(self, text: str) -> float | None:
        """Parse Turkish number format (comma as decimal separator).

        Examples:
            "101,613667" -> 101.613667
            "22,48" -> 22.48
            "0,00" -> 0.0
        """
        text = text.strip()
        if not text or text == "-":
            return None
        try:
            return float(text.replace(",", "."))
        except ValueError:
            return None

    def _parse_date(self, text: str) -> datetime | None:
        """Parse Ziraat date format.

        Examples:
            "26.01.2026 " -> datetime(2026, 1, 26)
            "14.04.2026 " -> datetime(2026, 4, 14)
        """
        text = text.strip()
        if not text:
            return None

        try:
            return datetime.strptime(text, "%d.%m.%Y")
        except ValueError:
            return None

    def _fetch_bonds_for_date(self, date_str: str) -> list[dict]:
        """Fetch bonds for a specific date.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            List of bond dicts
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://www.ziraatbank.com.tr",
            "Referer": "https://www.ziraatbank.com.tr/tr/bireysel/yatirim/eurobond",
        }

        payload = {
            "kiymetTipi": "EURO",
            "date": date_str,
            "hideIfStartWith": "",
        }

        response = self._post(ZIRAAT_URL, json=payload, headers=headers)
        data = response.json()

        # Extract HTML from response
        html = data.get("d", {}).get("Data", "")
        if not html:
            return []

        # Parse HTML table
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            return []

        bonds = []
        rows = table.find_all("tr")

        for row in rows[1:]:  # Skip header row
            cols = row.find_all("td")
            if len(cols) < 8:
                continue

            bond = {
                "isin": cols[0].text.strip(),
                "maturity": self._parse_date(cols[1].text),
                "days_to_maturity": int(cols[2].text.strip()) if cols[2].text.strip().isdigit() else 0,
                "currency": cols[3].text.strip(),
                "bid_price": self._parse_turkish_number(cols[4].text),
                "bid_yield": self._parse_turkish_number(cols[5].text),
                "ask_price": self._parse_turkish_number(cols[6].text),
                "ask_yield": self._parse_turkish_number(cols[7].text),
            }
            bonds.append(bond)

        return bonds

    def _has_valid_yields(self, bonds: list[dict]) -> bool:
        """Check if bonds have valid (non-zero) yield data.

        Args:
            bonds: List of bond dicts

        Returns:
            True if at least one bond has non-zero yield
        """
        for bond in bonds:
            if bond.get("bid_yield") and bond["bid_yield"] > 0:
                return True
            if bond.get("ask_yield") and bond["ask_yield"] > 0:
                return True
        return False

    def get_eurobonds(self, currency: str | None = None) -> list[dict]:
        """Get all Turkish Eurobonds.

        Args:
            currency: Optional filter by currency ("USD" or "EUR").

        Returns:
            List of Eurobond dicts with isin, maturity, days_to_maturity,
            currency, bid_price, bid_yield, ask_price, ask_yield.

        Example:
            [
                {
                    "isin": "US900123DG28",
                    "maturity": datetime(2033, 1, 19),
                    "days_to_maturity": 2562,
                    "currency": "USD",
                    "bid_price": 120.26,
                    "bid_yield": 6.55,
                    "ask_price": 122.19,
                    "ask_yield": 6.24,
                },
                ...
            ]
        """
        cache_key = "ziraat_eurobonds"
        cached = self._cache_get(cache_key)

        if cached is None:
            # Try today first, then go back up to 7 days to find valid data
            # This handles cases where the system date is ahead of API data
            bonds = []
            for days_back in range(8):
                try_date = datetime.now() - timedelta(days=days_back)
                date_str = try_date.strftime("%Y-%m-%d")
                bonds = self._fetch_bonds_for_date(date_str)

                if bonds and self._has_valid_yields(bonds):
                    break

            # Cache for 5 minutes
            self._cache_set(cache_key, bonds, TTL.FX_RATES)
            cached = bonds

        # Apply currency filter if specified
        if currency:
            currency = currency.upper()
            return [b for b in cached if b["currency"] == currency]

        return cached

    def get_eurobond(self, isin: str) -> dict | None:
        """Get single Eurobond by ISIN.

        Args:
            isin: ISIN code (e.g., "US900123DG28")

        Returns:
            Eurobond dict or None if not found.
        """
        isin = isin.upper()
        bonds = self.get_eurobonds()

        for bond in bonds:
            if bond["isin"] == isin:
                return bond

        return None

    def _fetch_bonds_for_date_cached(self, date_str: str) -> list[dict]:
        """Cached wrapper around :meth:`_fetch_bonds_for_date`.

        Historical daily data doesn't change, so it's safe to cache aggressively.
        """
        cache_key = f"ziraat_eurobonds:{date_str}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        bonds = self._fetch_bonds_for_date(date_str)
        self._cache_set(cache_key, bonds, TTL.OHLCV_HISTORY)
        return bonds

    @staticmethod
    def _iter_business_dates(
        start: date_type, end: date_type, skip_weekends: bool = True
    ) -> list[date_type]:
        """Enumerate dates between ``start`` and ``end`` inclusive.

        Weekdays only if ``skip_weekends`` is True. Turkish public holidays
        still appear (we'd need a holiday calendar to drop them); zero-price
        rows from the API are filtered downstream.
        """
        if end < start:
            return []
        dates: list[date_type] = []
        current = start
        while current <= end:
            if not skip_weekends or current.weekday() < 5:
                dates.append(current)
            current += timedelta(days=1)
        return dates

    def get_history(
        self,
        isin: str,
        start: datetime | date_type,
        end: datetime | date_type,
        skip_weekends: bool = True,
        max_workers: int = 5,
    ) -> list[dict]:
        """Fetch daily bond data for a single ISIN across a date range.

        Args:
            isin: ISIN code (e.g., "US900123DG28").
            start: Start date (inclusive).
            end: End date (inclusive).
            skip_weekends: Skip Saturdays/Sundays (API returns zeros).
            max_workers: Concurrent request workers.

        Returns:
            List of dicts sorted by date ascending. Each dict includes the
            date plus bid/ask price/yield and days_to_maturity. Rows where
            bid_price is 0 or None (holidays, suspensions) are dropped.
        """
        isin = isin.upper()
        start_d = start.date() if isinstance(start, datetime) else start
        end_d = end.date() if isinstance(end, datetime) else end
        dates = self._iter_business_dates(start_d, end_d, skip_weekends)
        if not dates:
            return []

        def _fetch_one(d: date_type) -> dict | None:
            date_str = d.strftime("%Y-%m-%d")
            bonds = self._fetch_bonds_for_date_cached(date_str)
            for b in bonds:
                if b.get("isin") == isin:
                    price = b.get("bid_price")
                    if price is None or price == 0:
                        return None
                    return {
                        "date": d,
                        "bid_price": b.get("bid_price"),
                        "bid_yield": b.get("bid_yield"),
                        "ask_price": b.get("ask_price"),
                        "ask_yield": b.get("ask_yield"),
                        "days_to_maturity": b.get("days_to_maturity", 0),
                    }
            return None

        # Concurrent fetch with bounded worker count
        workers = max(1, min(max_workers, len(dates)))
        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_fetch_one, d): d for d in dates}
            for fut in as_completed(futures):
                row = fut.result()
                if row is not None:
                    results.append(row)

        results.sort(key=lambda r: r["date"])
        return results


# Singleton instance
_provider: ZiraatEurobondProvider | None = None


def get_eurobond_provider() -> ZiraatEurobondProvider:
    """Get the singleton Eurobond provider instance."""
    global _provider
    if _provider is None:
        _provider = ZiraatEurobondProvider()
    return _provider
