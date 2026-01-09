"""Doviz.com provider for forex and commodity data."""

import re
import time
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL
from borsapy.exceptions import APIError, DataNotAvailableError


class DovizcomProvider(BaseProvider):
    """
    Provider for forex and commodity data from doviz.com.

    Supported assets:
    - Currencies: USD, EUR, GBP, JPY, CHF, CAD, AUD
    - Precious Metals: gram-altin, gumus, ons, XAG-USD, XPT-USD, XPD-USD
    - Energy: BRENT, WTI
    - Fuel: diesel, gasoline, lpg
    """

    BASE_URL = "https://api.doviz.com/api/v12"
    KUR_BASE_URL = "https://kur.doviz.com"
    TOKEN_EXPIRY = 3600  # 1 hour

    FALLBACK_TOKEN = "3e75d7fabf1c50c8b962626dd0e5ea22d8000815e1b0920d0a26afd77fcd6609"

    # Bank slug mapping for kur.doviz.com
    BANK_SLUGS = {
        "kapalicarsi": "kapalicarsi",
        "altinkaynak": "altinkaynak",
        "harem": "harem",
        "odaci": "odaci",
        "venus": "venus",
        "getirfinans": "getirfinans",
        "akbank": "akbank",
        "albaraka": "albaraka-turk",
        "alternatifbank": "alternatif-bank",
        "anadolubank": "anadolubank",
        "cepteteb": "cepteteb",
        "denizbank": "denizbank",
        "destekbank": "destekbank",
        "dunyakatilim": "dunya-katilim",
        "emlakkatilim": "emlak-katilim",
        "enpara": "enpara",
        "fibabanka": "fibabanka",
        "garanti": "garanti-bbva",
        "hadi": "hadi",
        "halkbank": "halkbank",
        "hayatfinans": "hayat-finans",
        "hsbc": "hsbc",
        "ing": "ing-bank",
        "isbank": "isbankasi",
        "kuveytturk": "kuveyt-turk",
        "tcmb": "merkez-bankasi",
        "misyonbank": "misyon-bank",
        "odeabank": "odeabank",
        "qnb": "qnb-finansbank",
        "sekerbank": "sekerbank",
        "turkiyefinans": "turkiye-finans",
        "vakifbank": "vakifbank",
        "vakifkatilim": "vakif-katilim",
        "yapikredi": "yapikredi",
        "ziraat": "ziraat-bankasi",
        "ziraatkatilim": "ziraat-katilim",
    }

    # Currency slug mapping for kur.doviz.com
    CURRENCY_SLUGS = {
        "USD": "amerikan-dolari",
        "EUR": "euro",
        "GBP": "sterlin",
        "CHF": "isvicre-frangi",
        "CAD": "kanada-dolari",
        "AUD": "avustralya-dolari",
        "JPY": "japon-yeni",
        "RUB": "rus-rublesi",
        "AED": "birlesik-arap-emirlikleri-dirhemi",
        "DKK": "danimarka-kronu",
        "SEK": "isvec-kronu",
        "NOK": "norvec-kronu",
        "KWD": "kuveyt-dinari",
        "ZAR": "guney-afrika-randi",
        "SAR": "suudi-arabistan-riyali",
        "PLN": "polonya-zlotisi",
        "RON": "romen-leyi",
        "CNY": "cin-yuani",
        "HKD": "hong-kong-dolari",
        "KRW": "guney-kore-wonu",
        "QAR": "katar-riyali",
    }

    # Precious metal slug mapping for altin.doviz.com institution rates
    METAL_SLUGS = {
        "gram-altin": "gram-altin",
        "gram-gumus": "gumus",
        "ons-altin": "ons",
        "gram-platin": "gram-platin",
        "gram-paladyum": "gram-paladyum",
    }

    # Asset to API slug mapping (for history/current endpoints)
    # Some assets use different slugs in API vs user-facing names
    HISTORY_API_SLUGS = {
        "gram-gumus": "gumus",
        "ons-altin": "ons",
    }

    # Institution ID mapping for history API
    # Pattern: {institution_id}-{metal_slug} → e.g., "1-gram-altin" for Akbank gram gold
    # IDs discovered from altin.doviz.com/{institution}/{metal} pages
    INSTITUTION_IDS = {
        "akbank": 1,
        "qnb-finansbank": 2,
        "halkbank": 3,
        "isbankasi": 4,
        "vakifbank": 5,
        "yapikredi": 6,
        "ziraat-bankasi": 7,
        "garanti-bbva": 8,
        "sekerbank": 9,
        "denizbank": 10,
        "hsbc": 12,
        "turkiye-finans": 13,
        "ziraat-katilim": 14,
        "vakif-katilim": 15,
        "ing-bank": 16,
        "kuveyt-turk": 17,
        "albaraka-turk": 18,
        "enpara": 19,
        "kapalicarsi": 20,
        "odaci": 22,
        "harem": 23,
        "altinkaynak": 24,
        "hayat-finans": 29,
        "emlak-katilim": 30,
        "fibabanka": 31,
        "odeabank": 36,
        "getirfinans": 37,
    }

    SUPPORTED_ASSETS = {
        # Currencies
        "USD",
        "EUR",
        "GBP",
        "JPY",
        "CHF",
        "CAD",
        "AUD",
        # Precious Metals (TRY)
        "gram-altin",
        "gumus",
        "gram-gumus",
        "gram-platin",
        "gram-paladyum",
        # Precious Metals (USD)
        "ons",
        "ons-altin",
        "XAG-USD",
        "XPT-USD",
        "XPD-USD",
        # Energy
        "BRENT",
        "WTI",
        # Fuel
        "diesel",
        "gasoline",
        "lpg",
    }

    FUEL_ASSETS = {"gasoline", "diesel", "lpg"}

    def __init__(self):
        super().__init__()
        self._token: str | None = None
        self._token_expiry: float = 0

    def _get_token(self) -> str:
        """Get valid Bearer token."""
        if self._token and time.time() < self._token_expiry:
            return self._token

        # Try to extract token from website
        try:
            token = self._extract_token()
            if token:
                self._token = token
                self._token_expiry = time.time() + self.TOKEN_EXPIRY
                return token
        except Exception:
            pass

        # Use fallback
        return self.FALLBACK_TOKEN

    def _extract_token(self) -> str | None:
        """Extract token from doviz.com website."""
        try:
            response = self._client.get("https://www.doviz.com/")
            html = response.text

            # Look for 64-char hex token
            patterns = [
                r'token["\']?\s*:\s*["\']([a-f0-9]{64})["\']',
                r"Bearer\s+([a-f0-9]{64})",
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    return match.group(1)

            return None
        except Exception:
            return None

    def _get_headers(self, asset: str) -> dict[str, str]:
        """Get request headers with token."""
        if asset in ["gram-altin", "gumus", "ons"]:
            origin = "https://altin.doviz.com"
        else:
            origin = "https://www.doviz.com"

        token = self._get_token()

        return {
            "Accept": "*/*",
            "Authorization": f"Bearer {token}",
            "Origin": origin,
            "Referer": f"{origin}/",
            "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
        }

    def get_current(self, asset: str) -> dict[str, Any]:
        """
        Get current price for an asset.

        Args:
            asset: Asset code (USD, EUR, gram-altin, BRENT, etc.)

        Returns:
            Dictionary with current price data.
        """
        asset = asset.upper() if asset.upper() in self.SUPPORTED_ASSETS else asset

        if asset not in self.SUPPORTED_ASSETS:
            raise DataNotAvailableError(
                f"Unsupported asset: {asset}. Supported: {sorted(self.SUPPORTED_ASSETS)}"
            )

        cache_key = f"dovizcom:current:{asset}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        try:
            if asset in self.FUEL_ASSETS:
                data = self._get_from_archive(asset, days=7)
            else:
                data = self._get_from_daily(asset)

            if not data:
                raise DataNotAvailableError(f"No data for {asset}")

            result = {
                "symbol": asset,
                "last": float(data.get("close", 0)),
                "open": float(data.get("open", 0)),
                "high": float(data.get("highest", 0)),
                "low": float(data.get("lowest", 0)),
                "update_time": self._parse_timestamp(data.get("update_date")),
            }

            self._cache_set(cache_key, result, TTL.FX_RATES)
            return result

        except Exception as e:
            raise APIError(f"Failed to fetch {asset}: {e}") from e

    def get_history(
        self,
        asset: str,
        period: str = "1mo",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Get historical data for an asset.

        Args:
            asset: Asset code.
            period: Period (1d, 5d, 1mo, 3mo, 6mo, 1y).
            start: Start date.
            end: End date.

        Returns:
            DataFrame with OHLC data.
        """
        asset = asset.upper() if asset.upper() in self.SUPPORTED_ASSETS else asset

        if asset not in self.SUPPORTED_ASSETS:
            raise DataNotAvailableError(f"Unsupported asset: {asset}")

        # Calculate date range
        end_dt = end or datetime.now()
        if start:
            start_dt = start
        else:
            days = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}.get(period, 30)
            start_dt = end_dt - timedelta(days=days)

        cache_key = f"dovizcom:history:{asset}:{start_dt.date()}:{end_dt.date()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            api_slug = self.HISTORY_API_SLUGS.get(asset, asset)
            url = f"{self.BASE_URL}/assets/{api_slug}/archive"
            params = {
                "start": int(start_dt.timestamp()),
                "end": int(end_dt.timestamp()),
            }

            response = self._client.get(url, headers=self._get_headers(asset), params=params)
            response.raise_for_status()
            data = response.json()

            archive = data.get("data", {}).get("archive", [])

            records = []
            for item in archive:
                records.append(
                    {
                        "Date": self._parse_timestamp(item.get("update_date")),
                        "Open": float(item.get("open", 0)),
                        "High": float(item.get("highest", 0)),
                        "Low": float(item.get("lowest", 0)),
                        "Close": float(item.get("close", 0)),
                    }
                )

            df = pd.DataFrame(records)
            if not df.empty:
                df.set_index("Date", inplace=True)
                df.sort_index(inplace=True)

            self._cache_set(cache_key, df, TTL.OHLCV_HISTORY)
            return df

        except Exception as e:
            raise APIError(f"Failed to fetch history for {asset}: {e}") from e

    def _get_from_daily(self, asset: str) -> dict | None:
        """Get latest data from daily endpoint."""
        api_slug = self.HISTORY_API_SLUGS.get(asset, asset)
        url = f"{self.BASE_URL}/assets/{api_slug}/daily"
        response = self._client.get(url, headers=self._get_headers(asset), params={"limit": 1})
        response.raise_for_status()
        data = response.json()

        archive = data.get("data", {}).get("archive", [])
        return archive[0] if archive else None

    def _get_from_archive(self, asset: str, days: int = 7) -> dict | None:
        """Get latest data from archive endpoint."""
        end_time = int(time.time())
        start_time = end_time - (days * 86400)

        api_slug = self.HISTORY_API_SLUGS.get(asset, asset)
        url = f"{self.BASE_URL}/assets/{api_slug}/archive"
        params = {"start": start_time, "end": end_time}

        response = self._client.get(url, headers=self._get_headers(asset), params=params)
        response.raise_for_status()
        data = response.json()

        archive = data.get("data", {}).get("archive", [])
        return archive[-1] if archive else None

    def _parse_timestamp(self, ts: Any) -> datetime:
        """Parse timestamp to datetime."""
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts)
        if isinstance(ts, datetime):
            return ts
        return datetime.now()

    def get_banks(self) -> list[str]:
        """
        Get list of supported banks.

        Returns:
            List of bank codes.
        """
        return sorted(self.BANK_SLUGS.keys())

    def get_bank_rates(
        self, asset: str, bank: str | None = None
    ) -> pd.DataFrame | dict[str, Any]:
        """
        Get bank exchange rates for a currency.

        Args:
            asset: Currency code (USD, EUR, GBP, etc.)
            bank: Bank code (akbank, garanti, etc.) or None for all banks.

        Returns:
            If bank is None: DataFrame with all bank rates.
            If bank is specified: Dictionary with single bank rate.
        """
        asset = asset.upper()
        currency_slug = self.CURRENCY_SLUGS.get(asset)
        if not currency_slug:
            raise DataNotAvailableError(
                f"Unsupported currency for bank rates: {asset}. "
                f"Supported: {sorted(self.CURRENCY_SLUGS.keys())}"
            )

        if bank:
            # Single bank
            bank = bank.lower()
            bank_slug = self.BANK_SLUGS.get(bank)
            if not bank_slug:
                raise DataNotAvailableError(
                    f"Unknown bank: {bank}. Supported: {sorted(self.BANK_SLUGS.keys())}"
                )

            cache_key = f"dovizcom:bank_rate:{asset}:{bank}"
            cached = self._cache_get(cache_key)
            if cached:
                return cached

            result = self._fetch_single_bank_rate(bank, bank_slug, currency_slug, asset)
            self._cache_set(cache_key, result, TTL.FX_RATES)
            return result
        else:
            # All banks
            cache_key = f"dovizcom:bank_rates:{asset}"
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

            result = self._fetch_all_bank_rates(currency_slug, asset)
            self._cache_set(cache_key, result, TTL.FX_RATES)
            return result

    def _fetch_single_bank_rate(
        self, bank: str, bank_slug: str, currency_slug: str, asset: str
    ) -> dict[str, Any]:
        """Fetch exchange rate for a single bank."""
        url = f"{self.KUR_BASE_URL}/{bank_slug}/{currency_slug}"

        try:
            response = self._client.get(url)
            response.raise_for_status()
            html = response.text

            # Parse buy/sell rates from HTML
            buy, sell = self._parse_bank_rate_html(html)

            if buy is None or sell is None:
                raise DataNotAvailableError(f"Could not parse rates for {bank}")

            spread = ((sell - buy) / buy * 100) if buy > 0 else 0

            return {
                "bank": bank,
                "currency": asset,
                "buy": buy,
                "sell": sell,
                "spread": round(spread, 2),
            }

        except Exception as e:
            raise APIError(f"Failed to fetch bank rate for {bank}: {e}") from e

    def _fetch_all_bank_rates(self, currency_slug: str, asset: str) -> pd.DataFrame:
        """Fetch exchange rates for all banks."""
        url = f"{self.KUR_BASE_URL}/serbest-piyasa/{currency_slug}"

        try:
            response = self._client.get(url)
            response.raise_for_status()
            html = response.text

            # Parse all bank rates from the table
            records = self._parse_all_bank_rates_html(html, asset)

            if not records:
                raise DataNotAvailableError(f"Could not parse bank rates for {asset}")

            df = pd.DataFrame(records)
            df = df.sort_values("bank").reset_index(drop=True)
            return df

        except Exception as e:
            raise APIError(f"Failed to fetch bank rates for {asset}: {e}") from e

    def _parse_bank_rate_html(self, html: str) -> tuple[float | None, float | None]:
        """Parse buy/sell rates from single bank page HTML using BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")
        buy = None
        sell = None

        # Method 1: data-socket-attr="bid" and "ask"
        bid_elem = soup.find(attrs={"data-socket-attr": "bid"})
        ask_elem = soup.find(attrs={"data-socket-attr": "ask"})

        if bid_elem and ask_elem:
            buy = self._parse_turkish_number(bid_elem.get_text(strip=True))
            sell = self._parse_turkish_number(ask_elem.get_text(strip=True))
            return buy, sell

        # Method 2: Regex fallback for "Alış X / Satış Y" pattern
        pattern = r"Al[ıi][şs]\s*([\d.,]+)\s*/\s*Sat[ıi][şs]\s*([\d.,]+)"
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            buy = self._parse_turkish_number(match.group(1))
            sell = self._parse_turkish_number(match.group(2))

        return buy, sell

    def _parse_all_bank_rates_html(self, html: str, asset: str) -> list[dict[str, Any]]:
        """Parse all bank rates from the main currency page HTML using BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")
        records = []

        # Find the bank rates table
        tables = soup.find_all("table", {"data-sortable": True})
        if not tables:
            return records

        for table in tables:
            tbody = table.find("tbody")
            if not tbody:
                continue

            for row in tbody.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue

                # First cell contains the bank link and name
                link = cells[0].find("a")
                if not link or "href" not in link.attrs:
                    continue

                href = link["href"]
                # Extract bank slug from URL: https://kur.doviz.com/bank-slug/currency
                slug_match = re.search(r"kur\.doviz\.com/([^/]+)/", href)
                if not slug_match:
                    continue

                bank_slug = slug_match.group(1)
                bank_name = link.get_text(strip=True)

                # Parse numeric values from cells
                buy = self._parse_turkish_number(cells[1].get_text(strip=True))
                sell = self._parse_turkish_number(cells[2].get_text(strip=True))
                spread_text = cells[4].get_text(strip=True).replace("%", "")
                spread = self._parse_turkish_number(spread_text)

                if buy and sell:
                    # Find bank code from slug
                    bank_code = None
                    for code, slug in self.BANK_SLUGS.items():
                        if slug == bank_slug:
                            bank_code = code
                            break

                    records.append(
                        {
                            "bank": bank_code or bank_slug,
                            "bank_name": bank_name,
                            "currency": asset,
                            "buy": buy,
                            "sell": sell,
                            "spread": spread if spread else round((sell - buy) / buy * 100, 2),
                        }
                    )

        return records

    def _parse_turkish_number(self, value: str) -> float | None:
        """Parse Turkish formatted number (comma as decimal separator)."""
        if not value:
            return None
        try:
            # Remove spaces and handle Turkish format
            value = value.strip().replace(" ", "")
            # If both . and , exist, assume . is thousands separator
            if "." in value and "," in value:
                value = value.replace(".", "").replace(",", ".")
            elif "," in value:
                value = value.replace(",", ".")
            return float(value)
        except (ValueError, TypeError):
            return None

    # ========== Metal Institution Rates ==========

    def get_metal_institutions(self) -> list[str]:
        """Get list of supported precious metal assets for institution rates."""
        return sorted(self.METAL_SLUGS.keys())

    def get_metal_institution_rates(
        self, asset: str, institution: str | None = None
    ) -> pd.DataFrame | dict[str, Any]:
        """
        Get precious metal rates from institutions (kuyumcular, bankalar).

        Args:
            asset: Asset code (gram-altin, gram-gumus, ons-altin, gram-platin, gram-paladyum)
            institution: Optional institution slug. If None, returns all institutions.

        Returns:
            DataFrame with all institutions or dict for single institution.
        """
        if asset not in self.METAL_SLUGS:
            raise DataNotAvailableError(
                f"Asset '{asset}' not supported for institution rates. "
                f"Supported: {', '.join(sorted(self.METAL_SLUGS.keys()))}"
            )

        if institution:
            # Single institution - filter from all rates
            cache_key = f"dovizcom:metal_institution_rate:{asset}:{institution}"
            cached = self._cache.get(cache_key)
            if cached:
                return cached

            all_rates = self._fetch_all_metal_institution_rates(asset)
            for rate in all_rates:
                if rate["institution"] == institution:
                    self._cache.set(cache_key, rate, TTL.FX_RATES)
                    return rate

            raise DataNotAvailableError(
                f"Institution '{institution}' not found for asset '{asset}'"
            )

        # All institutions
        cache_key = f"dovizcom:metal_institution_rates:{asset}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        rates = self._fetch_all_metal_institution_rates(asset)
        df = pd.DataFrame(rates)
        if not df.empty:
            df = df.sort_values("institution").reset_index(drop=True)

        self._cache.set(cache_key, df, TTL.FX_RATES)
        return df

    def _fetch_all_metal_institution_rates(self, asset: str) -> list[dict[str, Any]]:
        """Fetch institution rates from altin.doviz.com."""
        slug = self.METAL_SLUGS.get(asset, asset)
        url = f"https://altin.doviz.com/{slug}"

        try:
            response = self._client.get(
                url,
                headers={
                    "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            response.raise_for_status()
            return self._parse_metal_institution_rates_html(response.text, asset)
        except Exception as e:
            raise APIError(f"Failed to fetch metal institution rates: {e}") from e

    def _parse_metal_institution_rates_html(
        self, html: str, asset: str
    ) -> list[dict[str, Any]]:
        """Parse institution rates table from altin.doviz.com HTML."""
        soup = BeautifulSoup(html, "html.parser")
        records = []

        # Find the bank rates table (data-sortable attribute)
        tables = soup.find_all("table", {"data-sortable": True})
        if not tables:
            # Try alternative: look for table with specific class patterns
            tables = soup.find_all("table", class_=re.compile(r"table|kurlar", re.I))

        for table in tables:
            tbody = table.find("tbody")
            if not tbody:
                continue

            for row in tbody.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue

                # First cell contains the institution link and name
                link = cells[0].find("a")
                if not link:
                    continue

                href = link.get("href", "")
                institution_name = link.get_text(strip=True)

                # Extract institution slug from URL
                # URL pattern: https://altin.doviz.com/institution-slug/asset-slug
                # or: https://altin.doviz.com/institution-slug
                slug_match = re.search(r"altin\.doviz\.com/([^/]+)", href)
                if not slug_match:
                    continue

                institution_slug = slug_match.group(1)

                # Skip if it's an asset page, not an institution
                if institution_slug in self.METAL_SLUGS.values():
                    continue

                # Parse numeric values
                buy = self._parse_turkish_number(cells[1].get_text(strip=True))
                sell = self._parse_turkish_number(cells[2].get_text(strip=True))

                # Spread is in cell 4 (index 4), remove % sign
                spread_text = cells[4].get_text(strip=True).replace("%", "").strip()
                spread = self._parse_turkish_number(spread_text)

                if buy and sell:
                    records.append(
                        {
                            "institution": institution_slug,
                            "institution_name": institution_name,
                            "asset": asset,
                            "buy": buy,
                            "sell": sell,
                            "spread": spread if spread else round((sell - buy) / buy * 100, 2),
                        }
                    )

        return records

    def get_institution_history(
        self,
        asset: str,
        institution: str,
        period: str = "1mo",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Get historical data for a specific institution's rates.

        Supports both precious metals and currencies.

        Args:
            asset: Asset code. Supported:
                   - Metals: gram-altin, gram-gumus, ons-altin, gram-platin, gram-paladyum
                   - Currencies: USD, EUR, GBP, CHF, CAD, AUD, JPY, etc.
            institution: Institution slug (akbank, kapalicarsi, harem, etc.).
            period: Period (1d, 5d, 1mo, 3mo, 6mo, 1y). Ignored if start is provided.
            start: Start date.
            end: End date.

        Returns:
            DataFrame with OHLC data (Open, High, Low, Close) indexed by Date.
            Note: Banks typically return only Close values (Open/High/Low = 0).

        Raises:
            DataNotAvailableError: If asset or institution is not supported.
            APIError: If API request fails.

        Examples:
            >>> provider = get_dovizcom_provider()
            >>> # Metal history
            >>> provider.get_institution_history("gram-altin", "akbank", period="1mo")
            >>> # Currency history
            >>> provider.get_institution_history("USD", "akbank", period="1mo")
        """
        # Validate institution
        if institution not in self.INSTITUTION_IDS:
            supported = ", ".join(self.INSTITUTION_IDS.keys())
            raise DataNotAvailableError(
                f"Unsupported institution: {institution}. Supported: {supported}"
            )

        # Determine asset type and build API slug
        asset_upper = asset.upper()
        if asset in self.METAL_SLUGS:
            # Metal asset
            api_asset_slug = self.METAL_SLUGS[asset]
        elif asset_upper in self.CURRENCY_SLUGS:
            # Currency asset
            api_asset_slug = asset_upper
        else:
            metal_supported = ", ".join(self.METAL_SLUGS.keys())
            currency_supported = ", ".join(self.CURRENCY_SLUGS.keys())
            raise DataNotAvailableError(
                f"Unsupported asset: {asset}. "
                f"Supported metals: {metal_supported}. "
                f"Supported currencies: {currency_supported}"
            )

        # Calculate date range
        end_dt = end or datetime.now()
        if start:
            start_dt = start
        else:
            days = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}.get(period, 30)
            start_dt = end_dt - timedelta(days=days)

        cache_key = f"dovizcom:institution_history:{asset}:{institution}:{start_dt.date()}:{end_dt.date()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            # Build API slug: {institution_id}-{asset_slug}
            institution_id = self.INSTITUTION_IDS[institution]
            api_slug = f"{institution_id}-{api_asset_slug}"

            url = f"{self.BASE_URL}/assets/{api_slug}/archive"
            params = {
                "start": int(start_dt.timestamp()),
                "end": int(end_dt.timestamp()),
            }

            response = self._client.get(url, headers=self._get_headers(asset), params=params)
            response.raise_for_status()
            data = response.json()

            archive = data.get("data", {}).get("archive", [])

            records = []
            for item in archive:
                records.append(
                    {
                        "Date": self._parse_timestamp(item.get("update_date")),
                        "Open": float(item.get("open", 0)),
                        "High": float(item.get("highest", 0)),
                        "Low": float(item.get("lowest", 0)),
                        "Close": float(item.get("close", 0)),
                    }
                )

            df = pd.DataFrame(records)
            if not df.empty:
                df.set_index("Date", inplace=True)
                df.sort_index(inplace=True)

            self._cache_set(cache_key, df, TTL.OHLCV_HISTORY)
            return df

        except Exception as e:
            raise APIError(f"Failed to fetch institution history for {asset} from {institution}: {e}") from e

    def get_metal_institutions(self) -> list[str]:
        """
        Get list of institutions that support metal history data.

        Returns:
            List of institution slugs.
        """
        return list(self.INSTITUTION_IDS.keys())


# Singleton
_provider: DovizcomProvider | None = None


def get_dovizcom_provider() -> DovizcomProvider:
    """Get singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = DovizcomProvider()
    return _provider
