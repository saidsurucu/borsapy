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
        - GetSermayeArttirimlari: Dividends and capital increases
    """

    BASE_URL = "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/Common"
    STOCK_INFO_URL = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/StockInfo/CompanyInfoAjax.aspx"

    # Financial statement groups
    FINANCIAL_GROUP_INDUSTRIAL = "XI_29"  # Sanayi şirketleri
    FINANCIAL_GROUP_BANK = "UFRS"  # Bankalar

    # Known market indices
    INDICES = {
        "XU100": "BIST 100",
        "XU050": "BIST 50",
        "XU030": "BIST 30",
        "XBANK": "BIST Banka",
        "XUSIN": "BIST Sınai",
        "XHOLD": "BIST Holding ve Yatırım",
        "XUTEK": "BIST Teknoloji",
        "XGIDA": "BIST Gıda",
        "XTRZM": "BIST Turizm",
        "XULAS": "BIST Ulaştırma",
        "XSGRT": "BIST Sigorta",
        "XMANA": "BIST Metal Ana",
        "XKMYA": "BIST Kimya",
        "XMADN": "BIST Maden",
        "XELKT": "BIST Elektrik",
        "XTEKS": "BIST Tekstil",
        "XILTM": "BIST İletişim",
        "XUMAL": "BIST Mali",
        "XUTUM": "BIST Tüm",
    }

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

        url = f"{self.BASE_URL}/Data.aspx/OneEndeks"
        params = {"endeks": symbol}
        
        headers = {
            "Referer": "https://www.isyatirim.com.tr/tr-tr/analiz/Sayfalar/default.aspx"
        }

        try:
            response = self._get(url, params=params, headers=headers)
            data = response.json()
        except Exception as e:
            raise APIError(f"Failed to fetch quote for {symbol}: {e}") from e

        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        if not data or "symbol" not in data:
            raise TickerNotFoundError(symbol)

        result = self._parse_quote(data)
        self._cache_set(cache_key, result, TTL.REALTIME_PRICE)

        return result

    def get_index_history(
        self,
        index_code: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Get historical data for an index.

        Args:
            index_code: Index code (e.g., "XU100", "XU030", "XBANK").
            start: Start date.
            end: End date.

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume.
        """
        index_code = index_code.upper()

        # Default date range
        if end is None:
            end = datetime.now()
        if start is None:
            from datetime import timedelta

            start = end - timedelta(days=365)

        start_str = start.strftime("%Y%m%d%H%M%S")
        end_str = end.strftime("%Y%m%d%H%M%S")

        cache_key = f"isyatirim:index_history:{index_code}:{start_str}:{end_str}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}/ChartData.aspx/IndexHistoricalAll"
        
        params = {
            "endeks": index_code,
            "period": "1440",
            "from": start_str,
            "to": end_str,
        }
        
        headers = {
            "Referer": "https://www.isyatirim.com.tr/tr-tr/analiz/Sayfalar/default.aspx"
        }

        try:
            response = self._get(url, params=params, headers=headers)
            data = response.json()
        except Exception as e:
            raise APIError(f"Failed to fetch index history for {index_code}: {e}") from e

        if not data:
            raise DataNotAvailableError(f"No data for index: {index_code}")

        df = self._parse_index_history(data)
        self._cache_set(cache_key, df, TTL.OHLCV_HISTORY)

        return df

    def _parse_index_history(self, data: dict[str, Any] | list) -> pd.DataFrame:
        """Parse index history response into DataFrame."""
        records = []
        
        history_data = data
        if isinstance(data, dict):
             history_data = data.get("data", [])
             
        if not history_data or not isinstance(history_data, list):
             return pd.DataFrame()

        for item in history_data:
            try:
                if isinstance(item, list) and len(item) >= 2:
                    timestamp = float(item[0])
                    value = float(item[1])
                    
                    if not timestamp:
                        continue
                        
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    
                    records.append({
                        "Date": dt,
                        "Open": value,
                        "High": value,
                        "Low": value,
                        "Close": value,
                        "Volume": 0
                    })
                    continue

                date_str = item.get("date", "")
                if date_str:
                    dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
                else:
                    continue

                records.append(
                    {
                        "Date": dt,
                        "Open": float(item.get("open", 0)),
                        "High": float(item.get("high", 0)),
                        "Low": float(item.get("low", 0)),
                        "Close": float(item.get("close", 0)),
                        "Volume": int(item.get("volume", 0)),
                    }
                )
            except (ValueError, TypeError):
                continue

        df = pd.DataFrame(records)
        if not df.empty:
            df.set_index("Date", inplace=True)
            df.sort_index(inplace=True)

        return df

    def get_index_info(self, index_code: str) -> dict[str, Any]:
        """
        Get current information for an index.

        Args:
            index_code: Index code (e.g., "XU100").

        Returns:
            Dictionary with index information.
        """
        index_code = index_code.upper()

        if index_code not in self.INDICES:
            raise TickerNotFoundError(f"Unknown index: {index_code}")

        # Use the same quote endpoint for indices
        quote = self.get_realtime_quote(index_code)
        quote["name"] = self.INDICES.get(index_code, index_code)
        quote["type"] = "index"

        return quote

    def _get_session_for_stock(self, symbol: str) -> None:
        """Initialize session by visiting stock page to get cookies."""
        stock_page_url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={symbol}"
        try:
            # Just make a GET request to establish session cookies
            self._client.get(stock_page_url, timeout=10)
        except Exception:
            pass  # Ignore errors, we'll try the API anyway

    def _fetch_sermaye_data(self, symbol: str) -> dict:
        """
        Fetch dividend and capital increase data from İş Yatırım API.

        Returns combined data with both temettuList and sermayeList.
        """
        import json

        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        # First establish session to get ASP.NET_SessionId cookie
        self._get_session_for_stock(symbol)

        url = f"{self.STOCK_INFO_URL}/GetSermayeArttirimlari"

        # ASP.NET WebMethod expects specific format
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={symbol}",
            "Origin": "https://www.isyatirim.com.tr",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        }

        # Correct payload format with hisseKodu
        payload = json.dumps({
            "hisseKodu": symbol,
            "hisseTanimKodu": "",
            "yil": 0,
            "zaman": "HEPSI",
            "endeksKodu": "09",
            "sektorKodu": "",
        })

        try:
            response = self._client.post(url, content=payload, headers=headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise APIError(f"Failed to fetch sermaye data for {symbol}: {e}") from e

    def get_dividends(self, symbol: str) -> pd.DataFrame:
        """
        Get dividend history for a stock.

        Args:
            symbol: Stock symbol (e.g., "THYAO").

        Returns:
            DataFrame with columns: Date, Amount, GrossRate, TotalDividend.
        """
        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        cache_key = f"isyatirim:dividends:{symbol}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            data = self._fetch_sermaye_data(symbol)
        except APIError:
            # Return empty DataFrame if API fails
            return pd.DataFrame(columns=["Amount", "GrossRate", "NetRate", "TotalDividend"])

        # Parse dividends from response
        df = self._parse_dividends(data)
        self._cache_set(cache_key, df, TTL.FINANCIAL_STATEMENTS)

        return df

    def _parse_sermaye_response(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse GetSermayeArttirimlari response into list of records."""
        import json

        # Response structure: {"d": "[{...}, {...}]"} - JSON string inside JSON
        d_value = data.get("d", "[]")

        if isinstance(d_value, str):
            try:
                return json.loads(d_value)
            except json.JSONDecodeError:
                return []
        elif isinstance(d_value, list):
            return d_value
        return []

    def _parse_dividends(self, data: dict[str, Any]) -> pd.DataFrame:
        """Parse dividend data from GetSermayeArttirimlari response."""
        records = []
        items = self._parse_sermaye_response(data)

        for item in items:
            try:
                # Filter for cash dividend type only: 04 (Nakit Temettü)
                tip = item.get("SHT_KODU", "")
                if tip != "04":
                    continue

                # Parse date from timestamp (milliseconds) - strip time
                timestamp = item.get("SHHE_TARIH", 0)
                if timestamp:
                    dt = datetime.fromtimestamp(timestamp / 1000).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                else:
                    continue

                # Cash dividend rate and amount
                gross_rate = float(item.get("SHHE_NAKIT_TM_ORAN", 0) or 0)
                net_rate = float(item.get("SHHE_NAKIT_TM_ORAN_NET", 0) or 0)
                total_dividend = float(item.get("SHHE_NAKIT_TM_TUTAR", 0) or 0)

                # Calculate per-share amount (rate / 100 since it's percentage of nominal)
                amount = gross_rate / 100 if gross_rate else 0

                records.append(
                    {
                        "Date": dt,
                        "Amount": round(amount, 4),
                        "GrossRate": round(gross_rate, 2),
                        "NetRate": round(net_rate, 2),
                        "TotalDividend": total_dividend,
                    }
                )
            except (ValueError, TypeError):
                continue

        df = pd.DataFrame(records)
        if not df.empty:
            df.set_index("Date", inplace=True)
            df.sort_index(ascending=False, inplace=True)

        return df

    def get_capital_increases(self, symbol: str) -> pd.DataFrame:
        """
        Get capital increase (split) history for a stock.

        Args:
            symbol: Stock symbol (e.g., "THYAO").

        Returns:
            DataFrame with columns: Date, Capital, RightsIssue, BonusFromCapital, BonusFromDividend.
        """
        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        cache_key = f"isyatirim:splits:{symbol}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            data = self._fetch_sermaye_data(symbol)
        except APIError:
            # Return empty DataFrame if API fails
            return pd.DataFrame(columns=["Capital", "RightsIssue", "BonusFromCapital", "BonusFromDividend"])

        # Parse capital increases from response
        df = self._parse_capital_increases(data)
        self._cache_set(cache_key, df, TTL.FINANCIAL_STATEMENTS)

        return df

    def _parse_capital_increases(self, data: dict[str, Any]) -> pd.DataFrame:
        """Parse capital increase data from GetSermayeArttirimlari response."""
        records = []
        items = self._parse_sermaye_response(data)

        for item in items:
            try:
                # Filter for valid capital increase types:
                # - Type 01: Bedelli Sermaye Artırımı (rights issue only)
                # - Type 02: Bedelsiz Sermaye Artırımı (bonus issue from capital reserves)
                # - Type 03: Bedelli ve Bedelsiz Sermaye Artırımı (rights + bonus issue)
                # - Type 09: Bedelsiz Temettü (stock dividend / bonus from dividend)
                # Exclude: 04, 07, 79, 90, 99 (administrative/technical records)
                tip = item.get("SHT_KODU", "")
                if tip not in ("01", "02", "03", "09"):
                    continue

                # Parse date from timestamp (milliseconds) - strip time
                timestamp = item.get("SHHE_TARIH", 0)
                if timestamp:
                    dt = datetime.fromtimestamp(timestamp / 1000).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                else:
                    continue

                # Get capital after increase
                capital = float(item.get("HSP_BOLUNME_SONRASI_SERMAYE", 0) or 0)

                # Rights issue rate (Bedelli)
                rights_issue = float(item.get("SHHE_BDLI_ORAN", 0) or 0)

                # Bonus from capital reserves (Bedelsiz İç Kaynak)
                bonus_capital = float(item.get("SHHE_BDSZ_IK_ORAN", 0) or 0)

                # Bonus from dividend (Bedelsiz Temettüden)
                bonus_dividend = float(item.get("SHHE_BDSZ_TM_ORAN", 0) or 0)

                records.append(
                    {
                        "Date": dt,
                        "Capital": capital,
                        "RightsIssue": round(rights_issue, 2),
                        "BonusFromCapital": round(bonus_capital, 2),
                        "BonusFromDividend": round(bonus_dividend, 2),
                    }
                )
            except (ValueError, TypeError):
                continue

        df = pd.DataFrame(records)
        if not df.empty:
            df.set_index("Date", inplace=True)
            df.sort_index(ascending=False, inplace=True)

        return df

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
        """Generate period tuples (year, period) for financial queries.

        For quarterly data, starts from the last completed quarter.
        For annual data, starts from the previous year (current year data
        typically not available until Q1 of next year).
        """
        periods = []
        if quarterly:
            # Determine last AVAILABLE quarter based on current month
            # Financial data has ~45-60 day publication delay after quarter end
            current_month = datetime.now().month
            #
            # Publication timeline (approximate):
            #   Q1 (Jan-Mar) data → published May/June
            #   Q2 (Apr-Jun) data → published Aug/Sep
            #   Q3 (Jul-Sep) data → published Nov/Dec
            #   Q4 (Oct-Dec) data → published Feb/Mar of next year
            #
            # So available data by month:
            #   Jan-Feb: Q3 of previous year is latest
            #   Mar-May: Q4 of previous year is latest
            #   Jun-Aug: Q1 of current year is latest
            #   Sep-Nov: Q2 of current year is latest
            #   Dec: Q3 of current year is latest
            #
            if current_month <= 2:
                # Jan-Feb: Q3 of previous year is latest available
                start_year = current_year - 1
                start_period = 9
            elif current_month <= 5:
                # Mar-May: Q4 of previous year is latest
                start_year = current_year - 1
                start_period = 12
            elif current_month <= 8:
                # Jun-Aug: Q1 of current year is latest
                start_year = current_year
                start_period = 3
            elif current_month <= 11:
                # Sep-Nov: Q2 of current year is latest
                start_year = current_year
                start_period = 6
            else:
                # Dec: Q3 of current year is latest
                start_year = current_year
                start_period = 9

            # Generate quarters going backward from start
            year = start_year
            period = start_period
            for _ in range(count * 4):
                periods.append((year, period))
                # Move to previous quarter
                period -= 3
                if period <= 0:
                    period = 12
                    year -= 1
        else:
            # Annual: start from previous year (current year data not ready)
            for i in range(count):
                periods.append((current_year - 1 - i, 12))
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

        # Detect quarterly vs annual: annual has all periods = 12
        is_quarterly = len({p[1] for p in periods}) > 1

        records = []
        for item in items:
            row_name = item.get("itemDescTr", item.get("itemDescEng", "Unknown"))
            row_data = {"Item": row_name}

            for i, (year, period) in enumerate(periods[:5], 1):
                if is_quarterly:
                    col_name = f"{year}Q{period // 3}"
                else:
                    col_name = str(year)
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

    def get_major_holders(self, symbol: str) -> pd.DataFrame:
        """
        Get major shareholders (ortaklık yapısı) for a stock.

        Args:
            symbol: Stock symbol (e.g., "THYAO").

        Returns:
            DataFrame with columns: Holder, Percentage.
        """
        import json
        import re

        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        cache_key = f"isyatirim:major_holders:{symbol}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # Fetch the stock page HTML
        stock_page_url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={symbol}"

        try:
            response = self._client.get(stock_page_url, timeout=15)
            response.raise_for_status()
            html = response.text
        except Exception as e:
            raise APIError(f"Failed to fetch major holders for {symbol}: {e}") from e

        # Parse JavaScript variable: var OrtaklikYapisidata = [{name: 'xxx', y: 50.88}, ...]
        pattern = r"var OrtaklikYapisidata = \[(.*?)\];"
        match = re.search(pattern, html, re.DOTALL)

        if not match:
            return pd.DataFrame(columns=["Holder", "Percentage"])

        js_array = match.group(1).strip()
        if not js_array:
            return pd.DataFrame(columns=["Holder", "Percentage"])

        # Convert JS object to valid JSON: {name: 'x'} -> {"name": "x"}
        json_str = re.sub(r"([{,])(\w+):", r'\1"\2":', js_array)
        json_str = json_str.replace("'", '"')

        try:
            data = json.loads(f"[{json_str}]")
        except json.JSONDecodeError:
            return pd.DataFrame(columns=["Holder", "Percentage"])

        records = []
        for item in data:
            holder = item.get("name", "Unknown")
            percentage = float(item.get("y", 0))
            records.append({"Holder": holder, "Percentage": round(percentage, 2)})

        df = pd.DataFrame(records)
        if not df.empty:
            df.set_index("Holder", inplace=True)

        self._cache_set(cache_key, df, TTL.FINANCIAL_STATEMENTS)
        return df

    def get_recommendations(self, symbol: str) -> dict[str, Any]:
        """
        Get analyst recommendations and target price for a stock.

        Args:
            symbol: Stock symbol (e.g., "THYAO").

        Returns:
            Dictionary with:
            - recommendation: Buy/Hold/Sell (AL/TUT/SAT)
            - target_price: Analyst target price
            - upside_potential: Expected upside (%)
        """
        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        cache_key = f"isyatirim:recommendations:{symbol}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            data = self._fetch_sermaye_data(symbol)
        except APIError:
            return {
                "recommendation": None,
                "target_price": None,
                "upside_potential": None,
            }

        # Parse recommendations from sermaye response
        items = self._parse_sermaye_response(data)

        result = {
            "recommendation": None,
            "target_price": None,
            "upside_potential": None,
        }

        # Get the most recent entry with recommendation data
        for item in items:
            oneri = item.get("ONERI")
            hedef_fiyat = item.get("HEDEF_FIYAT")
            getiri_pot = item.get("GETIRI_POT")

            if oneri:
                result["recommendation"] = oneri
            if hedef_fiyat:
                result["target_price"] = round(float(hedef_fiyat), 2)
            if getiri_pot:
                result["upside_potential"] = round(float(getiri_pot) * 100, 2)

            # Break on first item with data
            if oneri or hedef_fiyat:
                break

        self._cache_set(cache_key, result, TTL.REALTIME_PRICE)
        return result

    def get_company_metrics(self, symbol: str) -> dict[str, Any]:
        """
        Get company metrics from şirket kartı page (Cari Değerler).

        Args:
            symbol: Stock symbol (e.g., "THYAO").

        Returns:
            Dictionary with:
            - market_cap: Market capitalization (TL)
            - pe_ratio: Price/Earnings ratio (F/K)
            - pb_ratio: Price/Book ratio (PD/DD)
            - ev_ebitda: Enterprise Value/EBITDA (FD/FAVÖK)
            - free_float: Free float percentage
            - foreign_ratio: Foreign ownership percentage
            - net_debt: Net debt (TL)
        """
        import re

        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        cache_key = f"isyatirim:metrics:{symbol}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        stock_page_url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={symbol}"

        # Retry logic for unstable İş Yatırım connection
        import time
        max_retries = 3
        last_error = None
        html = None

        for attempt in range(max_retries):
            try:
                response = self._client.get(stock_page_url, timeout=15)
                response.raise_for_status()
                html = response.text
                break
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))  # 1s, 2s backoff
                continue

        if html is None:
            raise APIError(f"Failed to fetch company metrics for {symbol}: {last_error}") from last_error

        result: dict[str, Any] = {
            "market_cap": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "ev_ebitda": None,
            "free_float": None,
            "foreign_ratio": None,
            "net_debt": None,
        }

        # Find Cari Değerler section
        idx = html.find("Cari Değerler")
        if idx > 0:
            snippet = html[idx : idx + 3000]

            # Parse th/td pairs
            pattern = r"<th[^>]*>([^<]+)</th>\s*<td[^>]*>([^<]+)</td>"
            matches = re.findall(pattern, snippet)

            for label, value in matches:
                label = label.strip()
                value = value.strip().replace(".", "").replace(",", ".")

                try:
                    if "F/K" in label and "FD" not in label:
                        result["pe_ratio"] = float(value)
                    elif "PD/DD" in label:
                        result["pb_ratio"] = float(value)
                    elif "FD/FAVÖK" in label:
                        result["ev_ebitda"] = float(value)
                    elif "Piyasa Değeri" in label:
                        # Value is in mnTL, convert to TL
                        num = float(re.sub(r"[^\d.]", "", value))
                        result["market_cap"] = int(num * 1_000_000)
                    elif "Net Borç" in label:
                        num = float(re.sub(r"[^\d.]", "", value))
                        result["net_debt"] = int(num * 1_000_000)
                    elif "Halka Açıklık" in label:
                        result["free_float"] = float(re.sub(r"[^\d.]", "", value))
                    elif "Yabancı Oranı" in label:
                        result["foreign_ratio"] = float(re.sub(r"[^\d.]", "", value))
                except (ValueError, TypeError):
                    continue

        self._cache_set(cache_key, result, TTL.REALTIME_PRICE)
        return result

    def get_business_summary(self, symbol: str) -> str | None:
        """
        Get business summary (Faal Alanı) for a stock.

        Args:
            symbol: Stock symbol (e.g., "THYAO").

        Returns:
            Business summary text or None if not available.
        """
        import re

        symbol = symbol.upper().replace(".IS", "").replace(".E", "")

        cache_key = f"isyatirim:business_summary:{symbol}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        stock_page_url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={symbol}"

        try:
            response = self._client.get(stock_page_url, timeout=15)
            response.raise_for_status()
            html = response.text
        except Exception:
            return None

        # Find "Faal Alanı" table row
        pattern = r'<th[^>]*>Faal Alanı</th>\s*<td[^>]*>([^<]+)</td>'
        match = re.search(pattern, html)

        if not match:
            return None

        summary = match.group(1).strip()
        if not summary:
            return None

        self._cache_set(cache_key, summary, TTL.FINANCIAL_STATEMENTS)
        return summary


# Singleton instance
_provider: IsYatirimProvider | None = None


def get_isyatirim_provider() -> IsYatirimProvider:
    """Get the singleton İş Yatırım provider instance."""
    global _provider
    if _provider is None:
        _provider = IsYatirimProvider()
    return _provider
