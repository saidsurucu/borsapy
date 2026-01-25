"""TradingView-native screening provider using tradingview-screener package.

This module provides a wrapper around the tradingview-screener package for
batch screening of BIST stocks using TradingView's Scanner API.

Examples:
    >>> from borsapy._providers.tradingview_screener_native import TVScreenerProvider
    >>> provider = TVScreenerProvider()
    >>> df = provider.scan(["THYAO", "GARAN"], ["rsi < 30"])
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

try:
    from tradingview_screener import Query, col
except ImportError:
    raise ImportError(
        "tradingview-screener package is required. Install with: pip install tradingview-screener"
    ) from None

__all__ = ["TVScreenerProvider", "get_tv_screener_provider"]


# Singleton instance
_provider: TVScreenerProvider | None = None


def get_tv_screener_provider() -> TVScreenerProvider:
    """Get singleton TVScreenerProvider instance."""
    global _provider
    if _provider is None:
        _provider = TVScreenerProvider()
    return _provider


class TVScreenerProvider:
    """TradingView Scanner API wrapper for batch screening.

    Uses tradingview-screener package for direct API access without
    local indicator calculations.

    Supports both public (delayed) and authenticated (real-time) data.
    Use `borsapy.set_tradingview_auth()` for real-time data access.

    Some indicators (Supertrend, Tilson T3) are not available in TradingView
    Scanner API and are calculated locally from historical data.

    Examples:
        >>> provider = TVScreenerProvider()
        >>> df = provider.scan(
        ...     symbols=["THYAO", "GARAN", "ASELS"],
        ...     conditions=["rsi < 30", "close > sma_50"],
        ...     interval="1d",
        ... )
        >>> # Local calculation indicators
        >>> df = provider.scan(
        ...     symbols=["THYAO", "GARAN"],
        ...     conditions=["supertrend_direction == 1"],  # Bullish trend
        ... )
    """

    # Fields that require local calculation (not available in TradingView Scanner API)
    LOCAL_CALC_FIELDS: set[str] = {
        "supertrend",
        "supertrend_direction",
        "supertrend_upper",
        "supertrend_lower",
        "t3",
        "tilson_t3",
    }

    # borsapy field name -> TradingView column name
    FIELD_MAP: dict[str, str] = {
        # Price fields
        "price": "close",
        "close": "close",
        "open": "open",
        "high": "high",
        "low": "low",
        "volume": "volume",
        "change": "change",
        "change_percent": "change",
        "market_cap": "market_cap_basic",
        # RSI
        "rsi": "RSI",
        "rsi_7": "RSI7",
        "rsi_14": "RSI",
        # Moving Averages - SMA
        "sma_5": "SMA5",
        "sma_10": "SMA10",
        "sma_20": "SMA20",
        "sma_30": "SMA30",
        "sma_50": "SMA50",
        "sma_100": "SMA100",
        "sma_200": "SMA200",
        # Moving Averages - EMA
        "ema_5": "EMA5",
        "ema_10": "EMA10",
        "ema_12": "EMA12",
        "ema_20": "EMA20",
        "ema_26": "EMA26",
        "ema_50": "EMA50",
        "ema_100": "EMA100",
        "ema_200": "EMA200",
        # MACD
        "macd": "MACD.macd",
        "signal": "MACD.signal",
        "macd_signal": "MACD.signal",
        "histogram": "MACD.hist",
        "macd_histogram": "MACD.hist",
        # Stochastic
        "stoch_k": "Stoch.K",
        "stoch_d": "Stoch.D",
        # ADX
        "adx": "ADX",
        "adx_14": "ADX",
        # CCI
        "cci": "CCI20",
        "cci_20": "CCI20",
        # Awesome Oscillator
        "ao": "AO",
        # Momentum
        "mom": "Mom",
        "momentum": "Mom",
        # Bollinger Bands
        "bb_upper": "BB.upper",
        "bb_lower": "BB.lower",
        "bb_middle": "BB.basis",
        "bb_basis": "BB.basis",
        # ATR
        "atr": "ATR",
        "atr_14": "ATR",
        # Williams %R
        "williams_r": "W.R",
        "wr": "W.R",
        # VWMA
        "vwma": "VWMA",
        # Parabolic SAR
        "psar": "P.SAR",
        "parabolic_sar": "P.SAR",
        # Aroon
        "aroon_up": "Aroon.Up",
        "aroon_down": "Aroon.Down",
        # Ichimoku
        "ichimoku_base": "Ichimoku.BLine",
        "ichimoku_conversion": "Ichimoku.CLine",
        # Ratings
        "rating": "Recommend.All",
        "rating_ma": "Recommend.MA",
        "rating_oscillators": "Recommend.Other",
    }

    # Timeframe mapping: borsapy interval -> TradingView suffix
    INTERVAL_MAP: dict[str, str] = {
        "1m": "|1",
        "5m": "|5",
        "15m": "|15",
        "30m": "|30",
        "1h": "|60",
        "2h": "|120",
        "4h": "|240",
        "1d": "",  # Default, no suffix
        "1W": "|1W",
        "1wk": "|1W",
        "1M": "|1M",
        "1mo": "|1M",
    }

    # Comparison operators
    OPERATORS: dict[str, str] = {
        ">": "greater",
        "<": "less",
        ">=": "egreater",
        "<=": "eless",
        "==": "equal",
        "!=": "nequal",
    }

    # Default columns to always retrieve
    DEFAULT_COLUMNS: list[str] = [
        "name",
        "close",
        "change",
        "volume",
        "market_cap_basic",
    ]

    def __init__(self) -> None:
        """Initialize the provider."""
        pass

    def _get_auth_cookies(self) -> dict[str, str] | None:
        """Get TradingView auth cookies if available.

        Returns:
            Dictionary of cookies or None if not authenticated.
        """
        from borsapy._providers.tradingview import get_tradingview_auth

        creds = get_tradingview_auth()
        if creds and creds.get("session"):
            cookies = {"sessionid": creds["session"]}
            if creds.get("session_sign"):
                cookies["sessionid_sign"] = creds["session_sign"]
            return cookies
        return None

    def scan(
        self,
        symbols: list[str],
        conditions: list[str],
        columns: list[str] | None = None,
        interval: str = "1d",
        limit: int = 100,
    ) -> pd.DataFrame:
        """Execute scan using TradingView Scanner API.

        Some indicators (Supertrend, Tilson T3) are calculated locally since
        they're not available in TradingView Scanner API.

        Args:
            symbols: List of BIST symbols to scan (e.g., ["THYAO", "GARAN"])
            conditions: List of conditions (e.g., ["rsi < 30", "close > sma_50"])
                Local calculation fields: supertrend, supertrend_direction,
                supertrend_upper, supertrend_lower, t3, tilson_t3
            columns: Additional columns to retrieve
            interval: Timeframe for indicators ("1m", "5m", "15m", "30m", "1h", "4h", "1d", "1W", "1M")
            limit: Maximum number of results

        Returns:
            DataFrame with matching symbols and their data

        Examples:
            >>> provider = TVScreenerProvider()
            >>> df = provider.scan(["THYAO", "GARAN"], ["rsi < 30"])
            >>> # Local calculation example
            >>> df = provider.scan(["THYAO", "GARAN"], ["supertrend_direction == 1"])
        """
        if not symbols:
            return pd.DataFrame()

        if not conditions:
            return pd.DataFrame()

        symbols_upper = [s.upper() for s in symbols]

        # Separate conditions into API and local calculation
        api_conditions, local_conditions = self._separate_conditions(conditions)

        # Case 1: Only local conditions - process all symbols locally
        if not api_conditions and local_conditions:
            df = self._apply_local_conditions(symbols_upper, local_conditions, interval)
            return df.head(limit) if not df.empty else df

        # Case 2: Only API conditions - use TradingView API
        if api_conditions and not local_conditions:
            return self._scan_api(symbols_upper, api_conditions, columns, interval, limit)

        # Case 3: Both API and local conditions
        # First filter with API, then apply local conditions
        api_df = self._scan_api(symbols_upper, api_conditions, columns, interval, limit * 5)

        if api_df.empty:
            return api_df

        # Get symbols that passed API filter
        api_symbols = api_df["symbol"].tolist() if "symbol" in api_df.columns else []

        if not api_symbols:
            return pd.DataFrame()

        # Apply local conditions to API-filtered symbols
        local_df = self._apply_local_conditions(api_symbols, local_conditions, interval)

        if local_df.empty:
            return local_df

        # Merge API data with local calculations
        if "symbol" in api_df.columns and "symbol" in local_df.columns:
            # Keep local_df columns and add any missing from api_df
            merged = local_df.merge(
                api_df.drop(columns=["close", "price"], errors="ignore"),
                on="symbol",
                how="inner",
                suffixes=("", "_api"),
            )
            # Remove duplicate columns
            merged = merged.loc[:, ~merged.columns.str.endswith("_api")]
            return merged.head(limit)

        return local_df.head(limit)

    def _scan_api(
        self,
        symbols: list[str],
        conditions: list[str],
        columns: list[str] | None,
        interval: str,
        limit: int,
    ) -> pd.DataFrame:
        """Execute scan using TradingView Scanner API only.

        Args:
            symbols: List of BIST symbols
            conditions: API-compatible conditions
            columns: Additional columns
            interval: Timeframe
            limit: Maximum results

        Returns:
            DataFrame with matching symbols
        """
        # Build query - always use turkey endpoint
        query = Query().set_markets("turkey")

        # Parse all conditions first
        filters: list[Any] = []
        for cond in conditions:
            try:
                filter_expr = self._parse_condition(cond, interval)
                if filter_expr is not None:
                    filters.append(filter_expr)
            except Exception as e:
                import warnings

                warnings.warn(f"Failed to parse condition '{cond}': {e}", stacklevel=2)
                continue

        # If no valid filters were parsed, return empty DataFrame
        if not filters:
            import warnings

            warnings.warn("No valid conditions were parsed. Returning empty DataFrame.", stacklevel=2)
            return pd.DataFrame()

        # Apply all filters in single where() call
        query = query.where(*filters)

        # Determine columns to select
        select_cols = self._get_select_columns(conditions, columns, interval)
        query = query.select(*select_cols)

        # Set limit - get more results since we filter client-side
        query_limit = limit * 10
        query = query.limit(query_limit)

        try:
            # Execute query with auth cookies for real-time data (if available)
            cookies = self._get_auth_cookies()
            if cookies:
                count, df = query.get_scanner_data(cookies=cookies)
            else:
                count, df = query.get_scanner_data()
        except Exception as e:
            import warnings

            warnings.warn(f"TradingView Scanner API error: {e}", stacklevel=2)
            return pd.DataFrame()

        if df.empty:
            return df

        # Normalize column names and extract symbol
        df = self._normalize_columns(df, interval)

        # Filter to requested symbols (client-side)
        if "symbol" in df.columns:
            df = df[df["symbol"].isin(symbols)]
            df = df.head(limit)

        return df

    def _parse_condition(self, condition: str, interval: str) -> Any:
        """Parse condition string into tradingview-screener filter expression.

        Args:
            condition: Condition like "rsi < 30" or "close > sma_50"
            interval: Timeframe for applying suffix

        Returns:
            tradingview-screener filter expression or None
        """
        condition = condition.strip().lower()

        # Check for crossover conditions (crosses, crosses_above, crosses_below)
        if "crosses" in condition:
            return self._parse_crossover(condition, interval)

        # Check for percentage conditions (above_pct, below_pct)
        if "above_pct" in condition or "below_pct" in condition:
            return self._parse_pct_condition(condition, interval)

        # Standard comparison: field op value/field
        # Pattern: field operator value
        pattern = r"^(\w+)\s*(>=|<=|>|<|==|!=)\s*(.+)$"
        match = re.match(pattern, condition)

        if not match:
            return None

        left_field = match.group(1).strip()
        operator = match.group(2).strip()
        right_value = match.group(3).strip()

        # Get TradingView column name for left field
        tv_left = self._get_tv_column(left_field, interval)

        # Try to parse right side as number or field
        try:
            # Try as number (handle K, M, B suffixes)
            right_num = self._parse_number(right_value)
            # Simple comparison with numeric value
            left_col = col(tv_left)

            if operator == ">":
                return left_col > right_num
            elif operator == "<":
                return left_col < right_num
            elif operator == ">=":
                return left_col >= right_num
            elif operator == "<=":
                return left_col <= right_num
            elif operator == "==":
                return left_col == right_num
            elif operator == "!=":
                return left_col != right_num
        except ValueError:
            # Right side is a field name
            tv_right = self._get_tv_column(right_value, interval)
            left_col = col(tv_left)
            right_col = col(tv_right)

            if operator == ">":
                return left_col > right_col
            elif operator == "<":
                return left_col < right_col
            elif operator == ">=":
                return left_col >= right_col
            elif operator == "<=":
                return left_col <= right_col
            elif operator == "==":
                return left_col == right_col
            elif operator == "!=":
                return left_col != right_col

        return None

    def _parse_crossover(self, condition: str, interval: str) -> Any:
        """Parse crossover condition.

        Uses tradingview-screener's Column.crosses(), crosses_above(), and crosses_below() methods.

        Args:
            condition: Condition like "sma_20 crosses sma_50" or "sma_20 crosses_above sma_50"
            interval: Timeframe

        Returns:
            tradingview-screener filter expression for crossover
        """
        condition = condition.strip().lower()

        # Pattern: field1 crosses_above field2
        crosses_above_match = re.match(r"^(\w+)\s+crosses_above\s+(\w+)$", condition)
        if crosses_above_match:
            left_field = crosses_above_match.group(1)
            right_field = crosses_above_match.group(2)
            tv_left = self._get_tv_column(left_field, interval)
            tv_right = self._get_tv_column(right_field, interval)
            return col(tv_left).crosses_above(col(tv_right))

        # Pattern: field1 crosses_below field2
        crosses_below_match = re.match(r"^(\w+)\s+crosses_below\s+(\w+)$", condition)
        if crosses_below_match:
            left_field = crosses_below_match.group(1)
            right_field = crosses_below_match.group(2)
            tv_left = self._get_tv_column(left_field, interval)
            tv_right = self._get_tv_column(right_field, interval)
            return col(tv_left).crosses_below(col(tv_right))

        # Pattern: field1 crosses field2 (any direction)
        crosses_match = re.match(r"^(\w+)\s+crosses\s+(\w+)$", condition)
        if crosses_match:
            left_field = crosses_match.group(1)
            right_field = crosses_match.group(2)
            tv_left = self._get_tv_column(left_field, interval)
            tv_right = self._get_tv_column(right_field, interval)
            return col(tv_left).crosses(col(tv_right))

        return None

    def _parse_pct_condition(self, condition: str, interval: str) -> Any:
        """Parse percentage condition.

        Uses tradingview-screener's Column.above_pct() and below_pct() methods.

        Args:
            condition: Condition like "close above_pct bb_lower 1.02" or "price below_pct sma_50 0.95"
            interval: Timeframe

        Returns:
            tradingview-screener filter expression for percentage comparison
        """
        condition = condition.strip().lower()

        # Pattern: field1 above_pct field2 value
        above_pct_match = re.match(r"^(\w+)\s+above_pct\s+(\w+)\s+([\d.]+)$", condition)
        if above_pct_match:
            left_field = above_pct_match.group(1)
            right_field = above_pct_match.group(2)
            pct_value = float(above_pct_match.group(3))
            tv_left = self._get_tv_column(left_field, interval)
            tv_right = self._get_tv_column(right_field, interval)
            return col(tv_left).above_pct(tv_right, pct_value)

        # Pattern: field1 below_pct field2 value
        below_pct_match = re.match(r"^(\w+)\s+below_pct\s+(\w+)\s+([\d.]+)$", condition)
        if below_pct_match:
            left_field = below_pct_match.group(1)
            right_field = below_pct_match.group(2)
            pct_value = float(below_pct_match.group(3))
            tv_left = self._get_tv_column(left_field, interval)
            tv_right = self._get_tv_column(right_field, interval)
            return col(tv_left).below_pct(tv_right, pct_value)

        return None

    def _get_tv_column(self, field: str, interval: str = "1d") -> str:
        """Get TradingView column name for a borsapy field.

        Args:
            field: Field name (e.g., "rsi", "sma_50", "close")
            interval: Timeframe to apply

        Returns:
            TradingView column name with interval suffix if needed
        """
        field = field.lower().strip()

        # Check direct mapping
        if field in self.FIELD_MAP:
            tv_col = self.FIELD_MAP[field]
        else:
            # Try pattern matching for dynamic indicators
            # sma_N, ema_N, rsi_N patterns
            sma_match = re.match(r"^sma_(\d+)$", field)
            if sma_match:
                period = sma_match.group(1)
                tv_col = f"SMA{period}"
            else:
                ema_match = re.match(r"^ema_(\d+)$", field)
                if ema_match:
                    period = ema_match.group(1)
                    tv_col = f"EMA{period}"
                else:
                    rsi_match = re.match(r"^rsi_(\d+)$", field)
                    if rsi_match:
                        period = rsi_match.group(1)
                        tv_col = f"RSI{period}" if period != "14" else "RSI"
                    else:
                        # Use as-is (TradingView may accept it)
                        tv_col = field

        # Apply interval suffix for non-daily timeframes
        suffix = self.INTERVAL_MAP.get(interval, "")
        if suffix and not tv_col.endswith("]"):
            tv_col = f"{tv_col}{suffix}"

        return tv_col

    def _parse_number(self, value: str) -> float:
        """Parse number string, handling K/M/B suffixes.

        Args:
            value: Number string like "1000000", "1M", "1.5K"

        Returns:
            Float value

        Raises:
            ValueError: If not a valid number
        """
        value = value.strip().upper()

        multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}

        for suffix, mult in multipliers.items():
            if value.endswith(suffix):
                return float(value[:-1]) * mult

        return float(value)

    def _get_select_columns(
        self,
        conditions: list[str],
        extra_columns: list[str] | None,
        interval: str,
    ) -> list[str]:
        """Determine columns to retrieve from TradingView.

        Args:
            conditions: List of condition strings
            extra_columns: User-requested additional columns
            interval: Timeframe

        Returns:
            List of TradingView column names
        """
        columns = set(self.DEFAULT_COLUMNS)

        # Extract fields from conditions
        for cond in conditions:
            fields = self._extract_fields_from_condition(cond)
            for field in fields:
                tv_col = self._get_tv_column(field, interval)
                # Remove interval suffix for selection (select base columns)
                base_col = tv_col.split("|")[0].rstrip("[1]")
                columns.add(base_col)

        # Add extra columns
        if extra_columns:
            for col_name in extra_columns:
                tv_col = self._get_tv_column(col_name, interval)
                base_col = tv_col.split("|")[0]
                columns.add(base_col)

        return list(columns)

    def _extract_fields_from_condition(self, condition: str) -> list[str]:
        """Extract field names from a condition string.

        Args:
            condition: Condition like "rsi < 30 and close > sma_50"

        Returns:
            List of field names
        """
        fields = []

        # Remove operators and keywords from condition
        condition = condition.lower()
        condition = re.sub(r"(>=|<=|>|<|==|!=)", " ", condition)
        # Remove logical operators and special operation keywords
        condition = re.sub(
            r"\b(and|or|crosses_above|crosses_below|crosses|above_pct|below_pct)\b",
            " ",
            condition,
        )

        tokens = condition.split()

        for token in tokens:
            token = token.strip()
            if not token:
                continue

            # Skip if it's a pure number
            try:
                self._parse_number(token)
                continue
            except ValueError:
                pass

            # It's a field name
            fields.append(token)

        return fields

    def _normalize_columns(self, df: pd.DataFrame, interval: str) -> pd.DataFrame:
        """Normalize TradingView column names to borsapy format.

        Args:
            df: DataFrame from TradingView
            interval: Timeframe used

        Returns:
            DataFrame with normalized column names
        """
        result = df.copy()

        # Extract symbol from ticker column
        if "ticker" in result.columns:
            result["symbol"] = result["ticker"].str.replace("BIST:", "", regex=False)
            result = result.drop(columns=["ticker"])

        # Rename columns to lowercase
        rename_map = {}
        for col_name in result.columns:
            new_name = col_name.lower()
            # Simplify common names
            new_name = new_name.replace("market_cap_basic", "market_cap")
            new_name = new_name.replace(".macd", "")
            new_name = new_name.replace(".signal", "_signal")
            new_name = new_name.replace(".hist", "_histogram")
            new_name = new_name.replace(".upper", "_upper")
            new_name = new_name.replace(".lower", "_lower")
            new_name = new_name.replace(".basis", "_middle")
            new_name = new_name.replace(".k", "_k")
            new_name = new_name.replace(".d", "_d")
            rename_map[col_name] = new_name

        result = result.rename(columns=rename_map)

        return result

    def _requires_local_calc(self, field: str) -> bool:
        """Check if a field requires local calculation.

        Args:
            field: Field name

        Returns:
            True if field needs local calculation
        """
        field = field.lower().strip()

        # Check direct match
        if field in self.LOCAL_CALC_FIELDS:
            return True

        # Check patterns: supertrend_*, t3_*, tilson_t3_*
        if field.startswith(("supertrend", "t3_", "tilson_t3")):
            return True

        return False

    def _separate_conditions(
        self, conditions: list[str]
    ) -> tuple[list[str], list[str]]:
        """Separate conditions into API and local calculation conditions.

        Args:
            conditions: List of condition strings

        Returns:
            Tuple of (api_conditions, local_conditions)
        """
        api_conditions = []
        local_conditions = []

        for cond in conditions:
            fields = self._extract_fields_from_condition(cond)
            needs_local = any(self._requires_local_calc(f) for f in fields)

            if needs_local:
                local_conditions.append(cond)
            else:
                api_conditions.append(cond)

        return api_conditions, local_conditions

    def _apply_local_conditions(
        self,
        symbols: list[str],
        conditions: list[str],
        interval: str,
    ) -> pd.DataFrame:
        """Apply local calculation conditions to symbols.

        Fetches historical data, calculates indicators, and filters.

        Args:
            symbols: List of symbols to process
            conditions: Local calculation conditions
            interval: Timeframe

        Returns:
            DataFrame with symbols matching all conditions
        """
        from borsapy.technical import calculate_supertrend, calculate_tilson_t3

        if not symbols or not conditions:
            return pd.DataFrame()

        results = []

        # Process each symbol
        for symbol in symbols:
            try:
                # Fetch historical data
                from borsapy.ticker import Ticker

                ticker = Ticker(symbol)
                df = ticker.history(period="3mo", interval=interval)

                if df.empty or len(df) < 20:
                    continue

                # Calculate local indicators
                indicators: dict[str, Any] = {}

                # Supertrend
                st_df = calculate_supertrend(df)
                if not st_df.empty:
                    indicators["supertrend"] = st_df["Supertrend"].iloc[-1]
                    indicators["supertrend_direction"] = st_df[
                        "Supertrend_Direction"
                    ].iloc[-1]
                    indicators["supertrend_upper"] = st_df["Supertrend_Upper"].iloc[-1]
                    indicators["supertrend_lower"] = st_df["Supertrend_Lower"].iloc[-1]

                # Tilson T3
                t3_series = calculate_tilson_t3(df)
                if not t3_series.empty:
                    indicators["t3"] = t3_series.iloc[-1]
                    indicators["tilson_t3"] = t3_series.iloc[-1]
                    indicators["t3_5"] = t3_series.iloc[-1]

                # Add price data
                indicators["close"] = df["Close"].iloc[-1]
                indicators["price"] = df["Close"].iloc[-1]

                # Check all conditions
                matches = True
                for cond in conditions:
                    if not self._evaluate_local_condition(cond, indicators):
                        matches = False
                        break

                if matches:
                    result_row = {"symbol": symbol}
                    result_row.update(indicators)
                    results.append(result_row)

            except Exception:
                # Skip symbols that fail
                continue

        if not results:
            return pd.DataFrame()

        return pd.DataFrame(results)

    def _evaluate_local_condition(
        self, condition: str, indicators: dict[str, Any]
    ) -> bool:
        """Evaluate a condition against calculated indicators.

        Args:
            condition: Condition string like "supertrend_direction == 1"
            indicators: Dictionary of indicator values

        Returns:
            True if condition is satisfied
        """
        import operator

        condition = condition.strip().lower()

        # Parse condition: field op value
        pattern = r"^(\w+)\s*(>=|<=|>|<|==|!=)\s*(.+)$"
        match = re.match(pattern, condition)

        if not match:
            return True  # Skip unparseable conditions

        field = match.group(1).strip()
        op_str = match.group(2).strip()
        right_str = match.group(3).strip()

        # Get left value
        left_val = indicators.get(field)
        if left_val is None:
            return False

        # Get right value (number or another field)
        try:
            right_val = self._parse_number(right_str)
        except ValueError:
            right_val = indicators.get(right_str)
            if right_val is None:
                return False

        # Apply operator
        ops = {
            ">": operator.gt,
            "<": operator.lt,
            ">=": operator.ge,
            "<=": operator.le,
            "==": operator.eq,
            "!=": operator.ne,
        }

        op_func = ops.get(op_str)
        if op_func is None:
            return True

        try:
            return op_func(float(left_val), float(right_val))
        except (ValueError, TypeError):
            return False
