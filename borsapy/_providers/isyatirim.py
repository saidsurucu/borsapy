"""İş Yatırım provider for real-time prices and financial statements."""

from datetime import datetime
from typing import Any

import pandas as pd

from borsapy._providers.base import BaseProvider
from borsapy.cache import TTL
from borsapy.exceptions import APIError, DataNotAvailableError, TickerNotFoundError


class IsYatirimProvider(BaseProvider):
    """
    Provider for real-time stock data and financial statements from İş Yatırım.

    APIs:
        - OneEndeks: Real-time OHLCV data
        - MaliTablo: Financial statements (balance sheet, income, cash flow)
    """

    BASE_URL = "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/Common"

    # Financial statement groups
    FINANCIAL_GROUP_INDUSTRIAL = "XI_29"  # Sanayi şirketleri
    FINANCIAL_GROUP_BANK = "UFRS"  # Bankalar

    def get_realtime_quote(self, symbol: str) -> dict[str, Any]:
        """
        Get real-time quote for a symbol using OneEndeks API.

        Args:
            symbol: Stock symbol (e.g., "THYAO", "GARAN").

        Returns:
            Dictionary with quote data:
            - symbol: Stock symbol
            - last: Last price
            - open: Opening price
            - high: High price
            - low: Low price
            - close: Previous day close
            - volume: Trading volume
            - bid: Bid price
            - ask: Ask price
            - change: Price change
            - change_percent: Price change percentage
            - update_time: Last update time
        """
        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        cache_key = f"isyatirim:quote:{symbol}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}/ChartData.aspx/OneEndeks"
        params = {"endeks": symbol}

        try:
            response = self._get(url, params=params)
            data = response.json()
        except Exception as e:
            raise APIError(f"Failed to fetch quote for {symbol}: {e}") from e

        if not data or "symbol" not in data:
            raise TickerNotFoundError(symbol)

        result = self._parse_quote(data)
        self._cache_set(cache_key, result, TTL.REALTIME_PRICE)

        return result

    def _parse_quote(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse OneEndeks response into standardized format."""
        last = float(data.get("last", 0))
        prev_close = float(data.get("dayClose", 0))
        change = last - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        update_str = data.get("updateDate", "")
        try:
            update_time = datetime.fromisoformat(update_str.replace("+03", "+03:00"))
        except (ValueError, AttributeError):
            update_time = datetime.now()

        return {
            "symbol": data.get("symbol", ""),
            "last": last,
            "open": float(data.get("open", 0)),
            "high": float(data.get("high", 0)),
            "low": float(data.get("low", 0)),
            "close": prev_close,
            "volume": int(data.get("volume", 0)),
            "quantity": int(data.get("quantity", 0)),
            "bid": float(data.get("bid", 0)),
            "ask": float(data.get("ask", 0)),
            "change": round(change, 2),
            "change_percent": round(change_pct, 2),
            "week_close": float(data.get("weekClose", 0)),
            "month_close": float(data.get("monthClose", 0)),
            "year_close": float(data.get("yearClose", 0)),
            "update_time": update_time,
        }

    def get_financial_statements(
        self,
        symbol: str,
        statement_type: str = "balance_sheet",
        quarterly: bool = False,
        financial_group: str | None = None,
    ) -> pd.DataFrame:
        """
        Get financial statements for a company.

        Args:
            symbol: Stock symbol.
            statement_type: Type of statement ("balance_sheet", "income_stmt", "cashflow").
            quarterly: If True, return quarterly data. If False, return annual data.
            financial_group: Financial group code (XI_29 for industrial, UFRS for banks).

        Returns:
            DataFrame with financial data.
        """
        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        cache_key = f"isyatirim:financial:{symbol}:{statement_type}:{quarterly}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # Determine financial group
        if financial_group is None:
            financial_group = self.FINANCIAL_GROUP_INDUSTRIAL

        # Map statement type to table names
        table_map = {
            "balance_sheet": ["BILANCO_AKTIF", "BILANCO_PASIF"],
            "income_stmt": ["GELIR_TABLOSU"],
            "cashflow": ["NAKIT_AKIM_TABLOSU"],
        }

        tables = table_map.get(statement_type, ["BILANCO_AKTIF", "BILANCO_PASIF"])

        # Get last 5 years/quarters
        current_year = datetime.now().year
        periods = self._get_periods(current_year, quarterly, count=5)

        all_data = []
        for table_name in tables:
            try:
                df = self._fetch_financial_table(
                    symbol=symbol,
                    table_name=table_name,
                    financial_group=financial_group,
                    periods=periods,
                )
                if not df.empty:
                    all_data.append(df)
            except Exception:
                continue

        if not all_data:
            raise DataNotAvailableError(f"No financial data available for {symbol}")

        result = pd.concat(all_data, axis=0) if len(all_data) > 1 else all_data[0]
        result = result.drop_duplicates()

        self._cache_set(cache_key, result, TTL.FINANCIAL_STATEMENTS)

        return result

    def _get_periods(
        self,
        current_year: int,
        quarterly: bool,
        count: int = 5,
    ) -> list[tuple[int, int]]:
        """Generate period tuples (year, period) for financial queries."""
        periods = []
        if quarterly:
            # Quarters: 3, 6, 9, 12
            for i in range(count * 4):
                year = current_year - (i // 4)
                quarter = 12 - (i % 4) * 3
                if quarter <= 0:
                    quarter = 12
                    year -= 1
                periods.append((year, quarter))
        else:
            # Annual: period 12
            for i in range(count):
                periods.append((current_year - i, 12))
        return periods

    def _fetch_financial_table(
        self,
        symbol: str,
        table_name: str,
        financial_group: str,
        periods: list[tuple[int, int]],
    ) -> pd.DataFrame:
        """Fetch a specific financial table."""
        url = f"{self.BASE_URL}/Data.aspx/MaliTablo"

        # Build params with multiple year/period pairs
        params: dict[str, Any] = {
            "companyCode": symbol,
            "exchange": "TRY",
            "financialGroup": financial_group,
        }

        for i, (year, period) in enumerate(periods[:5], 1):
            params[f"year{i}"] = year
            params[f"period{i}"] = period

        try:
            response = self._get(url, params=params)
            data = response.json()
        except Exception as e:
            raise APIError(f"Failed to fetch financial data for {symbol}: {e}") from e

        return self._parse_financial_response(data, periods)

    def _parse_financial_response(
        self,
        data: Any,
        periods: list[tuple[int, int]],
    ) -> pd.DataFrame:
        """Parse MaliTablo API response into DataFrame."""
        if not data or not isinstance(data, dict):
            return pd.DataFrame()

        # API returns: {"value": [{"itemDescTr": "...", "value1": ..., "value2": ...}, ...]}
        items = data.get("value", [])
        if not items:
            return pd.DataFrame()

        records = []
        for item in items:
            row_name = item.get("itemDescTr", item.get("itemDescEng", "Unknown"))
            row_data = {"Item": row_name}

            for i, (year, period) in enumerate(periods[:5], 1):
                col_name = f"{year}Q{period // 3}" if period < 12 else str(year)
                value = item.get(f"value{i}")
                if value is not None:
                    try:
                        row_data[col_name] = float(value)
                    except (ValueError, TypeError):
                        row_data[col_name] = value

            records.append(row_data)

        df = pd.DataFrame(records)
        if not df.empty and "Item" in df.columns:
            df.set_index("Item", inplace=True)

        return df


# Singleton instance
_provider: IsYatirimProvider | None = None


def get_isyatirim_provider() -> IsYatirimProvider:
    """Get the singleton İş Yatırım provider instance."""
    global _provider
    if _provider is None:
        _provider = IsYatirimProvider()
    return _provider
