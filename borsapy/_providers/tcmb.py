"""TCMB provider for inflation data."""

import re
from datetime import datetime
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL
from borsapy.exceptions import APIError, DataNotAvailableError


class TCMBProvider(BaseProvider):
    """
    Provider for inflation data from TCMB (Turkish Central Bank).

    Provides:
    - TÜFE (CPI) inflation data
    - ÜFE (PPI) inflation data
    - Inflation calculation between dates
    """

    BASE_URL = "https://www.tcmb.gov.tr"
    CALC_API_URL = "https://appg.tcmb.gov.tr/KIMENFH/enflasyon/hesapla"

    INFLATION_PATHS = {
        "tufe": "/wps/wcm/connect/tr/tcmb+tr/main+menu/istatistikler/enflasyon+verileri",
        "ufe": "/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Istatistikler/Enflasyon+Verileri/Uretici+Fiyatlari",
    }

    def calculate_inflation(
        self,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        basket_value: float = 100.0,
    ) -> dict[str, Any]:
        """
        Calculate inflation between two dates using TCMB API.

        Args:
            start_year: Starting year (e.g., 2020)
            start_month: Starting month (1-12)
            end_year: Ending year (e.g., 2024)
            end_month: Ending month (1-12)
            basket_value: Initial value in TRY (default: 100.0)

        Returns:
            Dictionary with:
            - start_date: Start date string
            - end_date: End date string
            - initial_value: Initial basket value
            - final_value: Final value after inflation
            - total_years: Total years elapsed
            - total_months: Total months elapsed
            - total_change: Total percentage change
            - avg_yearly_inflation: Average yearly inflation
            - start_cpi: CPI at start date
            - end_cpi: CPI at end date
        """
        # Validate inputs
        now = datetime.now()
        if not (1982 <= start_year <= now.year):
            raise ValueError(f"Start year must be between 1982 and {now.year}")
        if not (1982 <= end_year <= now.year):
            raise ValueError(f"End year must be between 1982 and {now.year}")
        if not (1 <= start_month <= 12) or not (1 <= end_month <= 12):
            raise ValueError("Month must be between 1 and 12")
        if basket_value <= 0:
            raise ValueError("Basket value must be positive")

        start_date = datetime(start_year, start_month, 1)
        end_date = datetime(end_year, end_month, 1)
        if start_date >= end_date:
            raise ValueError("Start date must be before end date")

        try:
            headers = {
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": "https://herkesicin.tcmb.gov.tr",
                "Referer": "https://herkesicin.tcmb.gov.tr/",
                "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
            }

            payload = {
                "baslangicYil": str(start_year),
                "baslangicAy": str(start_month),
                "bitisYil": str(end_year),
                "bitisAy": str(end_month),
                "malSepeti": str(basket_value),
            }

            response = self._client.post(
                self.CALC_API_URL, headers=headers, json=payload, timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            return {
                "start_date": f"{start_year}-{start_month:02d}",
                "end_date": f"{end_year}-{end_month:02d}",
                "initial_value": basket_value,
                "final_value": self._parse_float(data.get("yeniSepetDeger", "")),
                "total_years": int(data.get("toplamYil", 0)),
                "total_months": int(data.get("toplamAy", 0)),
                "total_change": self._parse_float(data.get("toplamDegisim", "")),
                "avg_yearly_inflation": self._parse_float(data.get("ortalamaYillikEnflasyon", "")),
                "start_cpi": self._parse_float(data.get("ilkYilTufe", "")),
                "end_cpi": self._parse_float(data.get("sonYilTufe", "")),
            }

        except Exception as e:
            raise APIError(f"Failed to calculate inflation: {e}") from e

    def get_data(
        self,
        inflation_type: str = "tufe",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Get inflation data from TCMB website.

        Args:
            inflation_type: 'tufe' (CPI) or 'ufe' (PPI)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            limit: Maximum number of records

        Returns:
            DataFrame with columns: Date, YearMonth, YearlyInflation, MonthlyInflation
        """
        if inflation_type not in self.INFLATION_PATHS:
            raise ValueError(f"Invalid type: {inflation_type}. Use 'tufe' or 'ufe'")

        cache_key = f"tcmb:data:{inflation_type}"
        cached = self._cache_get(cache_key)

        if cached is None:
            try:
                url = self.BASE_URL + self.INFLATION_PATHS[inflation_type]
                headers = {
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "tr-TR,tr;q=0.9",
                    "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
                }

                response = self._client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()

                cached = self._parse_inflation_table(response.text)
                self._cache_set(cache_key, cached, TTL.FX_RATES)

            except Exception as e:
                raise APIError(f"Failed to fetch inflation data: {e}") from e

        df = pd.DataFrame(cached)
        if df.empty:
            raise DataNotAvailableError(f"No data available for {inflation_type}")

        # Apply filters
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            df = df[df["Date"] >= start_dt]

        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            df = df[df["Date"] <= end_dt]

        if limit and limit > 0:
            df = df.head(limit)

        df.set_index("Date", inplace=True)
        return df

    def get_latest(self, inflation_type: str = "tufe") -> dict[str, Any]:
        """
        Get the latest inflation data point.

        Args:
            inflation_type: 'tufe' (CPI) or 'ufe' (PPI)

        Returns:
            Dictionary with latest inflation data.
        """
        df = self.get_data(inflation_type, limit=1)
        if df.empty:
            raise DataNotAvailableError(f"No data available for {inflation_type}")

        row = df.iloc[0]
        return {
            "date": df.index[0].strftime("%Y-%m-%d"),
            "year_month": row["YearMonth"],
            "yearly_inflation": row["YearlyInflation"],
            "monthly_inflation": row["MonthlyInflation"],
            "type": inflation_type.upper(),
        }

    def _parse_inflation_table(self, html_content: str) -> list[dict[str, Any]]:
        """Parse HTML table and extract inflation data."""
        soup = BeautifulSoup(html_content, "html.parser")
        tables = soup.find_all("table")

        inflation_data = []

        for table in tables:
            headers_row = table.find("tr")
            if not headers_row:
                continue

            headers = [th.get_text(strip=True) for th in headers_row.find_all(["th", "td"])]
            header_text = " ".join(headers).lower()

            if not any(kw in header_text for kw in ["tüfe", "üfe", "enflasyon", "yıllık", "%"]):
                continue

            rows = table.find_all("tr")[1:]

            for row in rows:
                cells = row.find_all(["td", "th"])
                cell_texts = [cell.get_text(strip=True) for cell in cells]

                if not cell_texts or not cell_texts[0] or "ÜFE" in cell_texts[0]:
                    continue

                try:
                    if len(cell_texts) >= 5:  # ÜFE format
                        date_str = cell_texts[0]
                        yearly_str = cell_texts[2]
                        monthly_str = cell_texts[4] if len(cell_texts) > 4 else ""
                    elif len(cell_texts) >= 3:  # TÜFE format
                        date_str = cell_texts[0]
                        yearly_str = cell_texts[1]
                        monthly_str = cell_texts[2]
                    else:
                        continue

                    date_obj = self._parse_date(date_str)
                    yearly_pct = self._parse_percentage(yearly_str)
                    monthly_pct = self._parse_percentage(monthly_str)

                    if date_obj and yearly_pct is not None:
                        inflation_data.append(
                            {
                                "Date": date_obj,
                                "YearMonth": date_str,
                                "YearlyInflation": yearly_pct,
                                "MonthlyInflation": monthly_pct,
                            }
                        )

                except Exception:
                    continue

            break

        # Sort by date (newest first)
        inflation_data.sort(key=lambda x: x["Date"], reverse=True)
        return inflation_data

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse date string from TCMB format (MM-YYYY)."""
        if not date_str:
            return None

        date_str = date_str.strip().replace(".", "").replace(",", "")
        match = re.search(r"(\d{1,2})-(\d{4})", date_str)

        if match:
            month, year = match.groups()
            try:
                return datetime(int(year), int(month), 1)
            except ValueError:
                pass

        return None

    def _parse_percentage(self, pct_str: str) -> float | None:
        """Parse percentage string to float."""
        if not pct_str:
            return None

        pct_str = pct_str.strip().replace("%", "").replace(",", ".")
        pct_str = re.sub(r"[^\d\-\.]", "", pct_str)

        try:
            return float(pct_str)
        except ValueError:
            return None

    def _parse_float(self, value: str) -> float | None:
        """Parse float from string, handling TCMB API number format."""
        if not value:
            return None
        try:
            # TCMB API format: 444,399.15 (comma=thousands, dot=decimal)
            value = str(value).replace(",", "")
            return float(value)
        except (ValueError, TypeError):
            return None


# Singleton
_provider: TCMBProvider | None = None


def get_tcmb_provider() -> TCMBProvider:
    """Get singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = TCMBProvider()
    return _provider
