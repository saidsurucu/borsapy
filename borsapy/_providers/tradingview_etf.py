"""TradingView ETF holders provider."""

import json
import re
from typing import Any

import pandas as pd

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL


class TradingViewETFProvider(BaseProvider):
    """
    Provider for ETF holder data from TradingView.

    Extracts ETF holder information from TradingView's ETF pages by parsing
    the embedded JavaScript data (window.initData.XXXXX).
    """

    BASE_URL = "https://tr.tradingview.com/symbols/BIST-{symbol}/etfs/"

    # Cache TTL for ETF holders (1 hour - positions don't change frequently)
    CACHE_TTL = TTL.OHLCV_HISTORY  # 3600 seconds

    # Management style translation (Turkish -> English)
    MANAGEMENT_MAP = {
        "Pasif": "Passive",
        "Aktif": "Active",
    }

    # Focus translation (Turkish -> English)
    FOCUS_MAP = {
        "Toplam piyasa": "Total Market",
        "Büyük ölçekli": "Large Cap",
        "Orta ölçekli": "Mid Cap",
        "Küçük ölçekli": "Small Cap",
        "Gelişen pazarlar": "Emerging Markets",
        "Gelişmiş pazarlar": "Developed Markets",
        "Sektörel": "Sector",
        "Temettü": "Dividend",
        "Büyüme": "Growth",
        "Değer": "Value",
    }

    def get_etf_holders(self, symbol: str) -> pd.DataFrame:
        """
        Get international ETFs that hold a specific BIST stock.

        Args:
            symbol: BIST stock symbol (e.g., "ASELS", "THYAO")

        Returns:
            DataFrame with ETF holder information including:
            - symbol: ETF ticker symbol
            - exchange: Exchange (AMEX, NASDAQ, etc.)
            - name: ETF full name
            - market_cap_usd: Position value in USD
            - holding_weight_pct: Weight percentage
            - issuer: ETF issuer (BlackRock, Vanguard, etc.)
            - management: Management style (Passive/Active)
            - focus: Investment focus
            - expense_ratio: Expense ratio
            - aum_usd: Total assets under management (USD)
            - price: Current price
            - change_pct: Change percentage

        Example:
            >>> provider = TradingViewETFProvider()
            >>> holders = provider.get_etf_holders("ASELS")
            >>> holders[['symbol', 'name', 'holding_weight_pct']].head()
        """
        symbol = symbol.upper()
        cache_key = f"etf_holders:{symbol}"

        # Check cache first
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # Fetch and parse data
        try:
            url = self.BASE_URL.format(symbol=symbol)
            response = self._client.get(url)
            response.raise_for_status()

            data = self._extract_etf_data(response.text)
            if not data:
                df = pd.DataFrame()
                self._cache_set(cache_key, df, self.CACHE_TTL)
                return df

            df = self._parse_etf_data(data)
            self._cache_set(cache_key, df, self.CACHE_TTL)
            return df

        except Exception:
            # Return empty DataFrame on any error
            return pd.DataFrame()

    def _extract_etf_data(self, html: str) -> dict | None:
        """
        Extract ETF data from embedded JavaScript in the HTML page.

        The data is stored within a script block as a JSON object starting
        with {"context"...} and containing "screener" data.

        Args:
            html: HTML content of the ETF page

        Returns:
            Parsed JSON data or None if not found
        """
        # Find all script blocks
        script_pattern = r'<script[^>]*>(.*?)</script>'
        scripts = re.findall(script_pattern, html, re.DOTALL)

        for script in scripts:
            # Look for script containing screener data
            if '"screener":' not in script or '"totalCount":' not in script:
                continue

            # Find JSON object starting with {"context"
            start = script.find('{"context"')
            if start < 0:
                continue

            # Extract JSON with brace matching
            json_str = self._extract_balanced_json(script, start)
            if not json_str:
                continue

            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Try to fix and parse again
                try:
                    fixed = self._fix_json_string(json_str)
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    continue

        return None

    def _extract_balanced_json(self, text: str, start: int) -> str | None:
        """Extract a JSON object by balancing braces."""
        brace_count = 0
        in_string = False
        escape_next = False
        end = start

        for i, c in enumerate(text[start:start + 500000]):  # Limit to 500KB
            if escape_next:
                escape_next = False
                continue
            if c == '\\':
                escape_next = True
                continue
            if c == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = start + i + 1
                    return text[start:end]

        return None

    def _fix_json_string(self, json_str: str) -> str:
        """Attempt to fix common JSON parsing issues."""
        # Remove any trailing semicolons or whitespace
        json_str = json_str.rstrip().rstrip(";")

        # Balance braces if needed
        open_braces = json_str.count("{")
        close_braces = json_str.count("}")
        if open_braces > close_braces:
            json_str += "}" * (open_braces - close_braces)

        return json_str

    def _parse_etf_data(self, data: dict) -> pd.DataFrame:
        """
        Parse extracted TradingView data into a DataFrame.

        The data structure is:
        {
            "data": {
                "screener": {
                    "data": {
                        "symbols": ["AMEX:IEMG", "AMEX:VWO", ...],
                        "data": [
                            {"id": "TickerUniversal", "rawValues": [...]},
                            {"id": "MarketValue", "rawValues": [...]},
                            ...
                        ]
                    }
                }
            }
        }

        Args:
            data: Parsed JSON data from TradingView

        Returns:
            DataFrame with ETF holder information
        """
        try:
            screener_data = data.get("data", {}).get("screener", {}).get("data", {})
            symbols = screener_data.get("symbols", [])
            data_arrays = screener_data.get("data", [])

            if not symbols or not data_arrays:
                return pd.DataFrame()

            # Build field map from data arrays
            field_map: dict[str, list] = {}
            for item in data_arrays:
                field_id = item.get("id", "")
                raw_values = item.get("rawValues", [])
                field_map[field_id] = raw_values

            # Parse each ETF
            rows = []
            for i, full_symbol in enumerate(symbols):
                try:
                    # Parse exchange:symbol format
                    parts = full_symbol.split(":")
                    if len(parts) == 2:
                        exchange, etf_symbol = parts
                    else:
                        exchange = ""
                        etf_symbol = full_symbol

                    # Get ticker info for name/description
                    ticker_info = self._safe_get(field_map, "TickerUniversal", i, {})
                    if isinstance(ticker_info, dict):
                        name = ticker_info.get("description", "")
                    else:
                        name = str(ticker_info) if ticker_info else ""

                    # Get management and translate
                    management_raw = self._safe_get(field_map, "Management", i)
                    management = self.MANAGEMENT_MAP.get(management_raw, management_raw) if management_raw else None

                    # Get focus and translate
                    focus_raw = self._safe_get(field_map, "Focus", i)
                    focus = self.FOCUS_MAP.get(focus_raw, focus_raw) if focus_raw else None

                    row = {
                        "symbol": etf_symbol,
                        "exchange": exchange,
                        "name": name,
                        "market_cap_usd": self._safe_get(field_map, "MarketValue", i),
                        "holding_weight_pct": self._safe_get(field_map, "HoldingWeight", i),
                        "issuer": self._safe_get(field_map, "Issuer", i),
                        "management": management,
                        "focus": focus,
                        "expense_ratio": self._safe_get(field_map, "ExpenseRatio", i),
                        "aum_usd": self._safe_get(field_map, "AssetsUnderManagement", i),
                        "price": self._safe_get(field_map, "Price", i),
                        "change_pct": self._safe_get(field_map, "Change", i),
                    }
                    rows.append(row)

                except Exception:
                    # Skip malformed entries
                    continue

            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame(rows)

            # Sort by market value (position size) descending
            if "market_cap_usd" in df.columns and not df["market_cap_usd"].isna().all():
                df = df.sort_values("market_cap_usd", ascending=False, na_position="last")
                df = df.reset_index(drop=True)

            return df

        except Exception:
            return pd.DataFrame()

    def _safe_get(self, field_map: dict, field_id: str, index: int, default: Any = None) -> Any:
        """Safely get a value from field_map by field ID and index."""
        values = field_map.get(field_id, [])
        if index < len(values):
            value = values[index]
            # Handle None-like values
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return default
            return value
        return default


# Singleton instance
_provider: TradingViewETFProvider | None = None


def get_tradingview_etf_provider() -> TradingViewETFProvider:
    """Get the singleton TradingView ETF provider instance."""
    global _provider
    if _provider is None:
        _provider = TradingViewETFProvider()
    return _provider
