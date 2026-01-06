"""İş Yatırım Stock Screener provider for borsapy."""

import json
from typing import Any

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL
from borsapy.exceptions import APIError


class IsyatirimScreenerProvider(BaseProvider):
    """
    Provider for BIST stock screener from İş Yatırım.

    API: https://www.isyatirim.com.tr
    Note: This API requires session cookies obtained from the main page.
    """

    BASE_URL = "https://www.isyatirim.com.tr"
    PAGE_URL = f"{BASE_URL}/tr-tr/analiz/hisse/Sayfalar/gelismis-hisse-arama.aspx"
    SCREENER_URL = f"{BASE_URL}/tr-tr/analiz/_Layouts/15/IsYatirim.Website/StockInfo/CompanyInfoAjax.aspx/getScreenerDataNEW"
    CRITERIA_URL = f"{BASE_URL}/_layouts/15/IsYatirim.Website/Common/Data.aspx/StockScreenerGenelKriterler"
    HIERARCHY_URL = f"{BASE_URL}/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseHiyerasi"

    # Criteria ID mapping (discovered from browser DevTools - data-tanimid attributes)
    # These IDs are used in the getScreenerDataNEW API requests
    CRITERIA_MAP = {
        # Price & Market Cap
        "price": "7",  # Kapanış (TL)
        "market_cap": "8",  # Piyasa Değeri (mn TL)
        "market_cap_usd": "9",  # Piyasa Değeri (mn $)
        "market_cap_1y_avg": "10",  # Piyasa Değeri 1Y Ort. (mn $)
        "float_ratio": "11",  # Halka Açıklık Oranı (%)
        "float_market_cap": "12",  # Halka Açık Piy.Değ.(mn $)
        # Performance - Relative Returns
        "return_1d": "21",  # 1 Gün Rel. (%)
        "return_1w": "22",  # 1 Hafta Rel. (%)
        "return_1m": "23",  # 1 Ay Rel. (%)
        "return_1y": "24",  # 1 Yıl Rel. (%)
        "return_ytd": "25",  # Yıliçi Rel. (%)
        # Performance - TL Returns
        "return_1d_tl": "16",  # 1 Gün TL (%)
        "return_1w_tl": "17",  # 1 Hafta TL (%)
        "return_1m_tl": "18",  # 1 Ay TL (%)
        "return_1y_tl": "19",  # 1 Yıl TL (%)
        "return_ytd_tl": "20",  # Yıliçi TL (%)
        # Volume
        "volume_3m": "26",  # 3 Ay (mn $)
        "volume_12m": "27",  # 12 Ay (mn $)
        # Valuation - Current
        "pe": "28",  # Cari F/K
        "ev_ebitda": "29",  # Cari FD/FAVÖK
        "pb": "30",  # Cari PD/DD
        "ev_sales": "31",  # Cari FD/Satışlar
        # Valuation - Forward (2025)
        "pe_2025": "135",  # 2025 F/K
        "pb_2025": "138",  # 2025 PD/DD
        "ev_ebitda_2025": "141",  # 2025 FD/FAVÖK
        # Dividends
        "dividend_yield": "33",  # 2024 Temettü Verimi (%)
        "dividend_yield_2025": "36",  # 2025 Temettü Verimi (%)
        "dividend_yield_5y_avg": "38",  # Temettü Verimi 5Y Ort%
        # Foreign Ownership
        "foreign_ratio": "40",  # Cari Yabancı Oranı (%)
        "foreign_ratio_1w_change": "44",  # Yabancı Oranı Son 1 Haftalık Değişimi (Baz)
        "foreign_ratio_1m_change": "45",  # Yabancı Oranı Son 1 Aylık Değişimi (Baz)
        # Target Price
        "target_price": "51",  # Hedef Fiyat (TL)
        "upside_potential": "61",  # Getiri Potansiyeli (%)
        # Profitability - Current
        "roe": "422",  # Cari ROE
        "roa": "423",  # Cari ROA
        # Profitability - Forward (2025)
        "net_margin": "119",  # 2025 Net Kar Marjı (%)
        "ebitda_margin": "120",  # 2025 FAVÖK Marjı (%)
        "roe_2025": "225",  # 2025 ROE
        "roa_2025": "247",  # 2025 ROA
        # Historical Averages
        "pe_hist_avg": "126",  # Tarihsel Ort. F/K
        "pb_hist_avg": "127",  # Tarihsel Ort. PD/DD
        "ev_ebitda_hist_avg": "128",  # Tarihsel Ort. FD/FAVÖK
        # Index Weights
        "bist100_weight": "375",  # BIST 100 Endeks Ağırlığı
        "bist50_weight": "376",  # BIST50 Endeks Ağırlığı
        "bist30_weight": "377",  # BIST30 Endeks Ağırlığı
    }

    # Default price criteria - API requires at least one criteria with min/max
    DEFAULT_CRITERIA = [("7", "1", "50000", "False")]  # Price 1-50000 TL

    # Pre-defined templates with actual working criteria
    # Note: API requires criteria with both min AND max values to work
    # Market cap in TL (ID 8): roughly $1B = 43B TL, $5B = 215B TL (at ~43 TL/USD)
    TEMPLATES = {
        "small_cap": {
            "criteria": [("8", "0", "43000", "False")],  # Market cap < ~$1B (43B TL)
        },
        "mid_cap": {
            "criteria": [("8", "43000", "215000", "False")],  # Market cap $1B-$5B
        },
        "large_cap": {
            "criteria": [("8", "215000", "5000000", "False")],  # Market cap > $5B
        },
        "high_dividend": {
            "criteria": [("33", "2", "100", "False")],  # Dividend yield > 2%
        },
        "high_upside": {
            "criteria": [("61", "0", "200", "False")],  # Positive upside potential
        },
        "low_upside": {
            "criteria": [("61", "-100", "0", "False")],  # Negative upside
        },
        "high_volume": {
            "criteria": [("26", "1", "1000", "False")],  # 3M avg volume > $1M
        },
        "low_volume": {
            "criteria": [("26", "0", "0.5", "False")],  # 3M avg volume < $0.5M
        },
        "buy_recommendation": {
            "criteria": [("7", "1", "50000", "False")],
            "oneri": "AL",
        },
        "sell_recommendation": {
            "criteria": [("7", "1", "50000", "False")],
            "oneri": "SAT",
        },
        "high_net_margin": {
            "criteria": [("119", "10", "200", "False")],  # Net margin > 10%
        },
        "high_return": {
            "criteria": [("22", "0", "100", "False")],  # Positive 1-week relative return
        },
        "low_pe": {
            "criteria": [("28", "0", "10", "False")],  # P/E < 10
        },
        "high_roe": {
            "criteria": [("422", "15", "200", "False")],  # ROE > 15%
        },
        "high_foreign_ownership": {
            "criteria": [("40", "30", "100", "False")],  # Foreign ownership > 30%
        },
    }

    def __init__(self, timeout: float = 30.0, cache=None):
        """Initialize the provider."""
        super().__init__(timeout=timeout, cache=cache)
        self._criteria_cache: list[dict[str, Any]] | None = None
        self._sectors_cache: list[dict[str, Any]] | None = None
        self._indices_cache: list[dict[str, Any]] | None = None
        self._session_initialized = False
        self._request_digest: str | None = None

    def _init_session(self) -> None:
        """Initialize session by fetching the main page to get cookies."""
        if self._session_initialized:
            return

        try:
            # Fetch the main page to establish session cookies
            response = self._get(
                self.PAGE_URL,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )

            # Extract request digest from page if present
            import re

            digest_match = re.search(r'id="__REQUESTDIGEST"[^>]*value="([^"]+)"', response.text)
            if digest_match:
                self._request_digest = digest_match.group(1)

            self._session_initialized = True
        except Exception:
            # Session initialization failed, but we can still try without it
            self._session_initialized = True

    def _get_headers(self) -> dict[str, str]:
        """Get headers for İş Yatırım API."""
        headers = {
            **self.DEFAULT_HEADERS,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": self.BASE_URL,
            "Referer": self.PAGE_URL,
        }
        if self._request_digest:
            headers["X-RequestDigest"] = self._request_digest
        return headers

    def get_criteria(self) -> list[dict[str, Any]]:
        """
        Get all available screening criteria.

        Returns:
            List of criteria with id, name, min, max values.
        """
        if self._criteria_cache is not None:
            return self._criteria_cache

        cache_key = "isyatirim:screener:criteria"
        cached = self._cache_get(cache_key)
        if cached is not None:
            self._criteria_cache = cached
            return cached

        try:
            response = self._get(
                self.CRITERIA_URL,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            data = response.json()

            criteria = []
            for item in data.get("value", []):
                # Parse the complex format
                kriter_tanim = item.get("KriterTanim", "")
                if ";#" in kriter_tanim:
                    parts = kriter_tanim.split(";#")
                    kriter_id = parts[0] if len(parts) > 0 else None
                else:
                    kriter_id = None

                # Get name from another field
                name_field = item.get("KriterTanim_x003a_Ba_x015f_l_x01", "")
                if ";#" in name_field:
                    name = name_field.split(";#")[1] if len(name_field.split(";#")) > 1 else ""
                else:
                    name = name_field

                # Get min/max
                min_field = item.get("KriterTanim_x003a_MIN_DEGER", "")
                max_field = item.get("KriterTanim_x003a_MAX_DEGER", "")

                min_val = min_field.split(";#")[1] if ";#" in min_field else min_field
                max_val = max_field.split(";#")[1] if ";#" in max_field else max_field

                if kriter_id and name:
                    criteria.append({
                        "id": kriter_id,
                        "name": name,
                        "min": min_val,
                        "max": max_val,
                    })

            # Deduplicate by id
            seen = set()
            unique_criteria = []
            for c in criteria:
                if c["id"] not in seen:
                    seen.add(c["id"])
                    unique_criteria.append(c)

            self._criteria_cache = unique_criteria
            self._cache_set(cache_key, unique_criteria, TTL.COMPANY_LIST)
            return unique_criteria

        except Exception as e:
            raise APIError(f"Failed to fetch screening criteria: {e}") from e

    def get_sectors(self) -> list[dict[str, Any]]:
        """
        Get list of sectors for filtering.

        Returns:
            List of sectors with id and name.
        """
        if self._sectors_cache is not None:
            return self._sectors_cache

        cache_key = "isyatirim:screener:sectors"
        cached = self._cache_get(cache_key)
        if cached is not None:
            self._sectors_cache = cached
            return cached

        # Extract from page HTML
        sectors = self._extract_sectors_from_page()
        if sectors:
            self._sectors_cache = sectors
            self._cache_set(cache_key, sectors, TTL.COMPANY_LIST)
            return sectors

        return []

    def get_indices(self) -> list[dict[str, Any]]:
        """
        Get list of indices for filtering.

        Returns:
            List of indices with id and name.
        """
        if self._indices_cache is not None:
            return self._indices_cache

        cache_key = "isyatirim:screener:indices"
        cached = self._cache_get(cache_key)
        if cached is not None:
            self._indices_cache = cached
            return cached

        # Extract from page HTML
        indices = self._extract_indices_from_page()
        if indices:
            self._indices_cache = indices
            self._cache_set(cache_key, indices, TTL.COMPANY_LIST)
            return indices

        return []

    def _extract_sectors_from_page(self) -> list[dict[str, Any]]:
        """Extract sectors from the screener page HTML."""
        from bs4 import BeautifulSoup

        try:
            self._init_session()
            response = self._get(self.PAGE_URL)
            soup = BeautifulSoup(response.content, "html.parser")

            # Find sector dropdown
            sector_select = soup.find("select", id="ctl00_ctl58_g_877a6dc3_ec50_46c8_9ce3_f240bf1fe822_ctl00_ddlStockSector")
            if not sector_select:
                return []

            sectors = []
            for opt in sector_select.find_all("option"):
                value = opt.get("value", "")
                name = opt.text.strip()
                if value and name and name != "Sektör Seçiniz":
                    sectors.append({"id": value, "name": name})

            return sectors

        except Exception:
            return []

    def _extract_indices_from_page(self) -> list[dict[str, Any]]:
        """Extract indices from the screener page HTML."""
        # Note: The İş Yatırım screener API does not reliably support
        # index filtering. Return a static list of common indices.
        return [
            {"id": "BIST 30", "name": "BIST 30"},
            {"id": "BIST 50", "name": "BIST 50"},
            {"id": "BIST 100", "name": "BIST 100"},
            {"id": "BIST BANKA", "name": "BIST BANKA"},
            {"id": "BIST SINAİ", "name": "BIST SINAİ"},
            {"id": "BIST HİZMETLER", "name": "BIST HİZMETLER"},
            {"id": "BIST TEKNOLOJİ", "name": "BIST TEKNOLOJİ"},
        ]

    def screen(
        self,
        criterias: list[tuple[str, str, str, str]] | None = None,
        sector: str | None = None,
        index: str | None = None,
        recommendation: str | None = None,
        template: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Screen stocks based on criteria.

        Args:
            criterias: List of (criteria_id, min, max, required) tuples.
            sector: Sector filter (e.g., "Bankacılık").
            index: Index filter (e.g., "BIST30").
            recommendation: Recommendation filter ("AL", "SAT", "TUT").
            template: Pre-defined template name (see TEMPLATES).

        Returns:
            List of matching stocks with requested criteria values.
        """
        # Build request payload
        payload = {
            "sektor": sector or "",
            "endeks": index or "",
            "takip": "",
            "oneri": recommendation or "",
            "criterias": [],
            "lang": "1055",  # Turkish
        }

        # Apply template if specified
        if template and template in self.TEMPLATES:
            tmpl = self.TEMPLATES[template]
            if "criteria" in tmpl:
                payload["criterias"] = [list(c) for c in tmpl["criteria"]]
            if "oneri" in tmpl:
                payload["oneri"] = tmpl["oneri"]

        # Add custom criterias
        if criterias:
            for c in criterias:
                payload["criterias"].append(list(c))

        # If no criterias specified, add default price criteria
        if not payload["criterias"]:
            payload["criterias"] = [["7", "1", "50000", "False"]]  # Price > 1 TL

        # Initialize session to get cookies
        self._init_session()

        # Build cache key
        cache_key = f"isyatirim:screener:{json.dumps(payload, sort_keys=True)}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            response = self._post(
                self.SCREENER_URL,
                json=payload,
                headers=self._get_headers(),
            )

            data = response.json()

            # Parse response - it's a JSON string inside "d" field
            result_str = data.get("d", "[]")
            results = json.loads(result_str)

            # Parse results
            stocks = []
            for item in results:
                # Parse "Hisse" field: "THYAO - Türk Hava Yolları"
                hisse = item.get("Hisse", "")
                if " - " in hisse:
                    parts = hisse.split(" - ", 1)
                    symbol = parts[0].strip()
                    name = parts[1].strip()
                else:
                    symbol = hisse
                    name = ""

                stock = {
                    "symbol": symbol,
                    "name": name,
                }

                # Add criteria values
                for key, value in item.items():
                    if key != "Hisse":
                        try:
                            stock[f"criteria_{key}"] = float(value)
                        except (ValueError, TypeError):
                            stock[f"criteria_{key}"] = value

                stocks.append(stock)

            self._cache_set(cache_key, stocks, TTL.REALTIME_PRICE * 15)  # 15 minutes
            return stocks

        except Exception as e:
            raise APIError(f"Failed to screen stocks: {e}") from e


# Singleton instance
_provider: IsyatirimScreenerProvider | None = None


def get_screener_provider() -> IsyatirimScreenerProvider:
    """Get the singleton screener provider instance."""
    global _provider
    if _provider is None:
        _provider = IsyatirimScreenerProvider()
    return _provider
