"""TradingView Scanner provider for technical analysis signals."""

from typing import Any

from borsapy._providers.base import BaseProvider
from borsapy.exceptions import APIError

# Oscillator columns requested from TradingView Scanner
OSCILLATOR_COLUMNS = [
    "RSI",
    "RSI[1]",  # Previous RSI for comparison
    "Stoch.K",
    "Stoch.D",
    "Stoch.K[1]",
    "Stoch.D[1]",
    "CCI20",
    "CCI20[1]",
    "ADX",
    "ADX+DI",
    "ADX-DI",
    "ADX+DI[1]",
    "ADX-DI[1]",
    "AO",
    "AO[1]",
    "AO[2]",  # For saucer pattern
    "Mom",
    "Mom[1]",
    "MACD.macd",
    "MACD.signal",
    "Rec.Stoch.RSI",
    "Stoch.RSI.K",
    "Rec.WR",
    "W.R",
    "Rec.BBPower",
    "BBPower",
    "Rec.UO",
    "UO",
]

# Moving average columns
MOVING_AVERAGE_COLUMNS = [
    "EMA5",
    "SMA5",
    "EMA10",
    "SMA10",
    "EMA20",
    "SMA20",
    "EMA30",
    "SMA30",
    "EMA50",
    "SMA50",
    "EMA100",
    "SMA100",
    "EMA200",
    "SMA200",
    "Rec.Ichimoku",
    "Ichimoku.BLine",
    "Rec.VWMA",
    "VWMA",
    "Rec.HullMA9",
    "HullMA9",
    "close",  # For comparison
]

# Interval to TradingView suffix mapping
# Empty string means daily (default)
INTERVAL_MAP = {
    "1m": "|1",
    "5m": "|5",
    "15m": "|15",
    "30m": "|30",
    "1h": "|60",
    "2h": "|120",
    "4h": "|240",
    "1d": "",  # Daily is default
    "1W": "|1W",
    "1M": "|1M",
}


class TradingViewScannerProvider(BaseProvider):
    """
    TradingView Scanner API provider for technical analysis signals.

    The Scanner API is public and doesn't require authentication.
    It returns technical analysis recommendations (BUY/SELL/NEUTRAL)
    along with indicator values.

    Based on: https://github.com/brian-the-dev/python-tradingview-ta
    """

    SCANNER_URL = "https://scanner.tradingview.com/{screener}/scan"

    # Screener mapping
    SCREENERS = {
        "turkey": "turkey",
        "forex": "forex",
        "crypto": "crypto",
        "america": "america",
        "europe": "europe",
        "global": "global",
    }

    def __init__(self):
        super().__init__()
        # Cache for TA signals (1 minute TTL)
        self._cache_ttl = 60

    def _get_columns_with_interval(
        self, columns: list[str], interval: str
    ) -> list[str]:
        """Add interval suffix to column names."""
        suffix = INTERVAL_MAP.get(interval, "")
        return [f"{col}{suffix}" for col in columns]

    def get_ta_signals(
        self,
        symbol: str,
        screener: str = "turkey",
        interval: str = "1d",
    ) -> dict[str, Any]:
        """
        Get technical analysis signals from TradingView Scanner.

        Args:
            symbol: Full TradingView symbol (e.g., "BIST:THYAO", "FX:USDTRY")
            screener: Market screener (turkey, forex, crypto, america, europe)
            interval: Timeframe (1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1W, 1M)

        Returns:
            Dict with structure:
            {
                "symbol": str,
                "exchange": str,
                "interval": str,
                "summary": {
                    "recommendation": str,  # STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
                    "buy": int,
                    "sell": int,
                    "neutral": int
                },
                "oscillators": {
                    "recommendation": str,
                    "buy": int,
                    "sell": int,
                    "neutral": int,
                    "compute": {indicator: signal},  # e.g., {"RSI": "NEUTRAL"}
                    "values": {indicator: value}  # e.g., {"RSI": 48.95}
                },
                "moving_averages": {
                    "recommendation": str,
                    "buy": int,
                    "sell": int,
                    "neutral": int,
                    "compute": {indicator: signal},
                    "values": {indicator: value}
                }
            }

        Raises:
            APIError: If the API request fails or symbol is not found
        """
        # Check cache
        cache_key = f"ta_signals:{symbol}:{screener}:{interval}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # Validate screener
        if screener not in self.SCREENERS:
            raise ValueError(f"Invalid screener: {screener}. Valid: {list(self.SCREENERS.keys())}")

        # Validate interval
        if interval not in INTERVAL_MAP:
            raise ValueError(f"Invalid interval: {interval}. Valid: {list(INTERVAL_MAP.keys())}")

        # Get columns with interval suffix
        osc_columns = self._get_columns_with_interval(OSCILLATOR_COLUMNS, interval)
        ma_columns = self._get_columns_with_interval(MOVING_AVERAGE_COLUMNS, interval)
        all_columns = osc_columns + ma_columns

        # Build request payload
        payload = {
            "symbols": {"tickers": [symbol], "query": {"types": []}},
            "columns": all_columns,
        }

        # Make request
        url = self.SCANNER_URL.format(screener=screener)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        try:
            response = self._post(url, json=payload, headers=headers)
        except Exception as e:
            raise APIError(f"TradingView Scanner API error: {e}") from e

        data = response.json()

        # Check for data
        if not data.get("data") or len(data["data"]) == 0:
            raise APIError(f"No data found for symbol: {symbol}")

        # Parse response
        row = data["data"][0]
        symbol_name = row.get("s", symbol)
        values = row.get("d", [])

        # Build column-value mapping
        suffix = INTERVAL_MAP.get(interval, "")
        raw_values = dict(zip(all_columns, values))

        # Extract exchange and symbol from full symbol
        if ":" in symbol_name:
            exchange, sym = symbol_name.split(":", 1)
        else:
            exchange = screener.upper()
            sym = symbol_name

        # Calculate signals
        result = self._calculate_signals(raw_values, suffix, interval)
        result["symbol"] = sym
        result["exchange"] = exchange
        result["interval"] = interval

        # Cache result
        self._cache_set(cache_key, result, self._cache_ttl)

        return result

    def _calculate_signals(
        self,
        raw_values: dict[str, Any],
        suffix: str,
        interval: str,
    ) -> dict[str, Any]:
        """Calculate buy/sell/neutral signals from raw values."""
        # Oscillator computations
        osc_compute = {}
        osc_values = {}

        # RSI (14)
        rsi = raw_values.get(f"RSI{suffix}")
        rsi_prev = raw_values.get(f"RSI[1]{suffix}")
        if rsi is not None:
            osc_values["RSI"] = round(rsi, 2) if rsi else None
            if rsi is not None:
                if rsi < 30:
                    osc_compute["RSI"] = "BUY"
                elif rsi > 70:
                    osc_compute["RSI"] = "SELL"
                else:
                    osc_compute["RSI"] = "NEUTRAL"

        # Stochastic %K
        stoch_k = raw_values.get(f"Stoch.K{suffix}")
        stoch_d = raw_values.get(f"Stoch.D{suffix}")
        stoch_k_prev = raw_values.get(f"Stoch.K[1]{suffix}")
        stoch_d_prev = raw_values.get(f"Stoch.D[1]{suffix}")
        if stoch_k is not None:
            osc_values["Stoch.K"] = round(stoch_k, 2) if stoch_k else None
            osc_values["Stoch.D"] = round(stoch_d, 2) if stoch_d else None
            if stoch_k is not None and stoch_d is not None:
                if stoch_k < 20 and stoch_k > stoch_d:
                    osc_compute["Stoch.K"] = "BUY"
                elif stoch_k > 80 and stoch_k < stoch_d:
                    osc_compute["Stoch.K"] = "SELL"
                else:
                    osc_compute["Stoch.K"] = "NEUTRAL"

        # CCI (20)
        cci = raw_values.get(f"CCI20{suffix}")
        cci_prev = raw_values.get(f"CCI20[1]{suffix}")
        if cci is not None:
            osc_values["CCI20"] = round(cci, 2) if cci else None
            if cci is not None:
                if cci < -100:
                    osc_compute["CCI20"] = "BUY"
                elif cci > 100:
                    osc_compute["CCI20"] = "SELL"
                else:
                    osc_compute["CCI20"] = "NEUTRAL"

        # ADX
        adx = raw_values.get(f"ADX{suffix}")
        adx_plus = raw_values.get(f"ADX+DI{suffix}")
        adx_minus = raw_values.get(f"ADX-DI{suffix}")
        adx_plus_prev = raw_values.get(f"ADX+DI[1]{suffix}")
        adx_minus_prev = raw_values.get(f"ADX-DI[1]{suffix}")
        if adx is not None:
            osc_values["ADX"] = round(adx, 2) if adx else None
            osc_values["ADX+DI"] = round(adx_plus, 2) if adx_plus else None
            osc_values["ADX-DI"] = round(adx_minus, 2) if adx_minus else None
            if adx is not None and adx_plus is not None and adx_minus is not None and adx > 20:
                if adx_plus > adx_minus:
                    osc_compute["ADX"] = "BUY"
                elif adx_minus > adx_plus:
                    osc_compute["ADX"] = "SELL"
                else:
                    osc_compute["ADX"] = "NEUTRAL"
            else:
                osc_compute["ADX"] = "NEUTRAL"

        # Awesome Oscillator
        ao = raw_values.get(f"AO{suffix}")
        ao_prev = raw_values.get(f"AO[1]{suffix}")
        ao_prev2 = raw_values.get(f"AO[2]{suffix}")
        if ao is not None:
            osc_values["AO"] = round(ao, 4) if ao else None
            if ao is not None and ao_prev is not None:
                if ao > 0 and ao > ao_prev:
                    osc_compute["AO"] = "BUY"
                elif ao < 0 and ao < ao_prev:
                    osc_compute["AO"] = "SELL"
                else:
                    osc_compute["AO"] = "NEUTRAL"

        # Momentum
        mom = raw_values.get(f"Mom{suffix}")
        mom_prev = raw_values.get(f"Mom[1]{suffix}")
        if mom is not None:
            osc_values["Mom"] = round(mom, 4) if mom else None
            if mom is not None and mom_prev is not None:
                if mom > mom_prev:
                    osc_compute["Mom"] = "BUY"
                elif mom < mom_prev:
                    osc_compute["Mom"] = "SELL"
                else:
                    osc_compute["Mom"] = "NEUTRAL"

        # MACD
        macd = raw_values.get(f"MACD.macd{suffix}")
        macd_signal = raw_values.get(f"MACD.signal{suffix}")
        if macd is not None:
            osc_values["MACD.macd"] = round(macd, 4) if macd else None
            osc_values["MACD.signal"] = round(macd_signal, 4) if macd_signal else None
            if macd is not None and macd_signal is not None:
                if macd > macd_signal:
                    osc_compute["MACD"] = "BUY"
                elif macd < macd_signal:
                    osc_compute["MACD"] = "SELL"
                else:
                    osc_compute["MACD"] = "NEUTRAL"

        # Pre-computed oscillator recommendations from TradingView
        rec_stoch_rsi = raw_values.get(f"Rec.Stoch.RSI{suffix}")
        if rec_stoch_rsi is not None:
            osc_values["Stoch.RSI.K"] = raw_values.get(f"Stoch.RSI.K{suffix}")
            osc_compute["Stoch.RSI"] = self._recommendation_to_signal(rec_stoch_rsi)

        rec_wr = raw_values.get(f"Rec.WR{suffix}")
        if rec_wr is not None:
            osc_values["W.R"] = raw_values.get(f"W.R{suffix}")
            osc_compute["W.R"] = self._recommendation_to_signal(rec_wr)

        rec_bbpower = raw_values.get(f"Rec.BBPower{suffix}")
        if rec_bbpower is not None:
            osc_values["BBPower"] = raw_values.get(f"BBPower{suffix}")
            osc_compute["BBPower"] = self._recommendation_to_signal(rec_bbpower)

        rec_uo = raw_values.get(f"Rec.UO{suffix}")
        if rec_uo is not None:
            osc_values["UO"] = raw_values.get(f"UO{suffix}")
            osc_compute["UO"] = self._recommendation_to_signal(rec_uo)

        # Moving averages computations
        ma_compute = {}
        ma_values = {}

        close = raw_values.get(f"close{suffix}")
        if close is not None:
            ma_values["close"] = round(close, 4)

        # Check each EMA and SMA against close price
        for period in [5, 10, 20, 30, 50, 100, 200]:
            ema_key = f"EMA{period}{suffix}"
            sma_key = f"SMA{period}{suffix}"

            ema_val = raw_values.get(ema_key)
            sma_val = raw_values.get(sma_key)

            if ema_val is not None:
                ma_values[f"EMA{period}"] = round(ema_val, 4)
                if close is not None:
                    if close > ema_val:
                        ma_compute[f"EMA{period}"] = "BUY"
                    elif close < ema_val:
                        ma_compute[f"EMA{period}"] = "SELL"
                    else:
                        ma_compute[f"EMA{period}"] = "NEUTRAL"

            if sma_val is not None:
                ma_values[f"SMA{period}"] = round(sma_val, 4)
                if close is not None:
                    if close > sma_val:
                        ma_compute[f"SMA{period}"] = "BUY"
                    elif close < sma_val:
                        ma_compute[f"SMA{period}"] = "SELL"
                    else:
                        ma_compute[f"SMA{period}"] = "NEUTRAL"

        # Pre-computed MA recommendations
        rec_ichimoku = raw_values.get(f"Rec.Ichimoku{suffix}")
        if rec_ichimoku is not None:
            ma_values["Ichimoku.BLine"] = raw_values.get(f"Ichimoku.BLine{suffix}")
            ma_compute["Ichimoku"] = self._recommendation_to_signal(rec_ichimoku)

        rec_vwma = raw_values.get(f"Rec.VWMA{suffix}")
        if rec_vwma is not None:
            ma_values["VWMA"] = raw_values.get(f"VWMA{suffix}")
            ma_compute["VWMA"] = self._recommendation_to_signal(rec_vwma)

        rec_hull = raw_values.get(f"Rec.HullMA9{suffix}")
        if rec_hull is not None:
            ma_values["HullMA9"] = raw_values.get(f"HullMA9{suffix}")
            ma_compute["HullMA9"] = self._recommendation_to_signal(rec_hull)

        # Calculate counts
        osc_buy = sum(1 for v in osc_compute.values() if v == "BUY")
        osc_sell = sum(1 for v in osc_compute.values() if v == "SELL")
        osc_neutral = sum(1 for v in osc_compute.values() if v == "NEUTRAL")

        ma_buy = sum(1 for v in ma_compute.values() if v == "BUY")
        ma_sell = sum(1 for v in ma_compute.values() if v == "SELL")
        ma_neutral = sum(1 for v in ma_compute.values() if v == "NEUTRAL")

        total_buy = osc_buy + ma_buy
        total_sell = osc_sell + ma_sell
        total_neutral = osc_neutral + ma_neutral

        return {
            "summary": {
                "recommendation": self._get_recommendation(total_buy, total_sell, total_neutral),
                "buy": total_buy,
                "sell": total_sell,
                "neutral": total_neutral,
            },
            "oscillators": {
                "recommendation": self._get_recommendation(osc_buy, osc_sell, osc_neutral),
                "buy": osc_buy,
                "sell": osc_sell,
                "neutral": osc_neutral,
                "compute": osc_compute,
                "values": osc_values,
            },
            "moving_averages": {
                "recommendation": self._get_recommendation(ma_buy, ma_sell, ma_neutral),
                "buy": ma_buy,
                "sell": ma_sell,
                "neutral": ma_neutral,
                "compute": ma_compute,
                "values": ma_values,
            },
        }

    def _recommendation_to_signal(self, rec_value: float | None) -> str:
        """Convert TradingView recommendation value to signal string."""
        if rec_value is None:
            return "NEUTRAL"
        if rec_value >= 0.5:
            return "BUY"
        elif rec_value <= -0.5:
            return "SELL"
        else:
            return "NEUTRAL"

    def _get_recommendation(self, buy: int, sell: int, neutral: int) -> str:
        """Calculate overall recommendation from counts."""
        total = buy + sell + neutral
        if total == 0:
            return "NEUTRAL"

        score = (buy - sell) / total

        if score >= 0.5:
            return "STRONG_BUY"
        elif score >= 0.1:
            return "BUY"
        elif score <= -0.5:
            return "STRONG_SELL"
        elif score <= -0.1:
            return "SELL"
        else:
            return "NEUTRAL"


# Singleton instance
_provider: TradingViewScannerProvider | None = None


def get_scanner_provider() -> TradingViewScannerProvider:
    """Get singleton TradingView Scanner provider instance."""
    global _provider
    if _provider is None:
        _provider = TradingViewScannerProvider()
    return _provider
